#!/usr/bin/env python3
"""
server.py — Wine label scanner + dashboard server for 86 Wine Cellar.

Serves the dashboard and provides a phone-friendly label scanning UI.
Photo → Gemini Vision → enriched wine entry → wines.json → regenerated dashboard.

Usage:
    GEMINI_API_KEY=xxx python3 server.py

Env vars:
    GEMINI_API_KEY  — required, Gemini API key
    PORT            — optional, default 8086
    SCAN_SECRET     — optional, shared secret to gate scan access
"""

import json
import os
import base64
import subprocess
import sys
from datetime import date
from pathlib import Path

from flask import Flask, request, jsonify, send_file, redirect

from google import genai

# ── config ───────────────────────────────────────────────────────────────────

DIR = Path(__file__).parent.resolve()
JSON_PATH = DIR / "wines.json"
PORT = int(os.environ.get("PORT", 8086))
SCAN_SECRET = os.environ.get("SCAN_SECRET", "")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY env var is required")
    sys.exit(1)

gemini_client = genai.Client(api_key=api_key)

app = Flask(__name__)

# ── helpers ──────────────────────────────────────────────────────────────────

def load_wines():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_wines(wines):
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(wines, f, ensure_ascii=False, indent=2)
        f.write("\n")


def recompute_fields(wines):
    """Recompute qprRaw, qprIndex, drinkStatus for all wines."""
    cy = date.today().year

    for w in wines:
        eff = w.get("purchasePriceEff") or w.get("purchasePrice") or w.get("marketPrice") or 1
        w["purchasePriceEff"] = eff
        w["qprRaw"] = w["score"] / eff if eff else 1.0

        df = w.get("drinkFrom", cy)
        dt = w.get("drinkTo", cy + 10)
        if dt < cy:
            w["drinkStatus"] = "past"
        elif df <= cy:
            w["drinkStatus"] = "urgent" if (dt - cy <= 2) else "now"
        elif df <= cy + 2:
            w["drinkStatus"] = "soon"
        else:
            w["drinkStatus"] = "wait"

    raws = [w["qprRaw"] for w in wines]
    mn, mx = min(raws), max(raws)
    for w in wines:
        if mn == mx:
            w["qprIndex"] = 5.0
        else:
            w["qprIndex"] = round(((w["qprRaw"] - mn) / (mx - mn)) * 9 + 1, 1)


def next_id(wines):
    return max((w["id"] for w in wines), default=0) + 1


def regenerate_dashboard():
    """Run generate_dashboard.py to rebuild the HTML."""
    subprocess.run(
        [sys.executable, str(DIR / "generate_dashboard.py")],
        cwd=str(DIR),
        check=True,
    )


def find_dashboard_html():
    """Find the most recent dashboard HTML file."""
    candidates = sorted(DIR.glob("*_Wine Cellar Dashboard.html"), reverse=True)
    return candidates[0] if candidates else None


def extract_wine_from_label(image_bytes, mime_type="image/jpeg"):
    """Send label image to Gemini Vision, get structured wine data back."""

    extract_prompt = """\
You are a wine expert examining a wine bottle label photo.

Extract every detail you can identify from the label. Then, using your wine knowledge,
fill in the remaining fields needed for a wine cellar database.

Return ONLY a JSON object with these fields (no markdown, no explanation):
{
  "producer": "...",
  "wine": "...",
  "appellation": "...",
  "country": "...",
  "region": "...",
  "vintage": 2023,
  "varietal": "...",
  "style": "red|white|sparkling|rosé|dessert|orange",
  "purchasePrice": null,
  "marketPrice": 25,
  "score": 88,
  "drinkFrom": 2024,
  "drinkTo": 2030,
  "pairings": ["food1", "food2", "food3"],
  "summary": "2-3 sentence tasting note and context."
}

Rules:
- "vintage" should be an integer year, or "NV" for non-vintage
- "style" must be one of: red, white, sparkling, rosé, dessert, orange
- "marketPrice" is your best estimate of current US retail price
- "score" is your best estimate of critic consensus (Wine Advocate, Wine Spectator, etc.)
- "drinkFrom"/"drinkTo" are drinking window years — use your knowledge of the vintage and region
- "pairings" should be 3 specific food pairings
- "summary" should mention the producer's reputation, vintage character, and what to expect
- "purchasePrice" should be null (the user will fill this in)
- If you can't read something from the label, use your wine knowledge to fill it in
- If you truly cannot identify the wine at all, set "producer" to null
"""

    b64_data = base64.standard_b64encode(image_bytes).decode("utf-8")

    response = gemini_client.models.generate_content(
        model="gemma-4-31b-it",
        contents=[
            genai.types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            extract_prompt,
        ],
    )

    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

    return json.loads(text)


# ── scan page HTML ───────────────────────────────────────────────────────────

SCAN_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Scan Wine Label</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: Georgia, serif;
    background: #0f0a0e; color: #e8ddd0;
    min-height: 100dvh; display: flex; flex-direction: column;
    align-items: center; padding: 20px;
  }
  h1 {
    font-size: 18px; letter-spacing: 2px; font-variant: small-caps;
    color: #c9a84c; margin: 20px 0 8px;
  }
  .subtitle { font-size: 13px; color: #9b8a7a; margin-bottom: 30px; }
  .scan-area {
    width: 100%; max-width: 400px; display: flex; flex-direction: column;
    align-items: center; gap: 20px;
  }
  .preview {
    width: 100%; max-width: 350px; aspect-ratio: 3/4;
    border: 2px dashed #3a2535; border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden; position: relative; background: #1a1118;
  }
  .preview img {
    width: 100%; height: 100%; object-fit: cover; border-radius: 10px;
  }
  .preview .placeholder {
    color: #9b8a7a; font-size: 14px; text-align: center; padding: 20px;
  }
  .btn {
    display: inline-flex; align-items: center; justify-content: center;
    gap: 8px; padding: 14px 28px; border-radius: 8px; border: none;
    font-family: Georgia, serif; font-size: 15px; cursor: pointer;
    transition: all 0.2s; letter-spacing: 0.5px; width: 100%; max-width: 350px;
  }
  .btn-primary {
    background: #7c2d3f; color: #e8ddd0;
  }
  .btn-primary:hover { background: #963850; }
  .btn-primary:disabled { background: #3a2535; color: #9b8a7a; cursor: not-allowed; }
  .btn-secondary {
    background: #1a1118; color: #c9a84c; border: 1px solid #3a2535;
  }
  .btn-secondary:hover { border-color: #c9a84c; }
  input[type="file"] { display: none; }
  .status {
    font-size: 13px; color: #9b8a7a; min-height: 20px; text-align: center;
  }
  .status.error { color: #e07830; }
  .status.success { color: #4caf7a; }
  .result-card {
    width: 100%; max-width: 400px; background: #1a1118;
    border: 1px solid #3a2535; border-radius: 10px;
    padding: 20px; margin-top: 10px; display: none;
  }
  .result-card h2 {
    font-size: 16px; color: #c9a84c; margin-bottom: 4px;
  }
  .result-card .producer { font-size: 13px; color: #9b8a7a; margin-bottom: 12px; }
  .result-card .detail { font-size: 13px; color: #e8ddd0; margin: 6px 0; }
  .result-card .detail span { color: #9b8a7a; }
  .result-card .summary {
    font-size: 13px; color: #9b8a7a; font-style: italic;
    margin-top: 12px; line-height: 1.5;
  }
  .price-input-row {
    display: flex; align-items: center; gap: 10px; margin: 12px 0;
  }
  .price-input-row label { font-size: 13px; color: #9b8a7a; white-space: nowrap; }
  .price-input-row input {
    width: 80px; padding: 6px 10px; border-radius: 6px;
    border: 1px solid #3a2535; background: #231820; color: #e8ddd0;
    font-family: Georgia, serif; font-size: 14px;
  }
  .spinner {
    display: inline-block; width: 18px; height: 18px;
    border: 2px solid #3a2535; border-top-color: #c9a84c;
    border-radius: 50%; animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .back-link {
    margin-top: 30px; font-size: 13px; color: #9b8a7a;
    text-decoration: none; letter-spacing: 0.5px;
  }
  .back-link:hover { color: #c9a84c; }
  .qty-input-row {
    display: flex; align-items: center; gap: 10px; margin: 6px 0;
  }
  .qty-input-row label { font-size: 13px; color: #9b8a7a; white-space: nowrap; }
  .qty-input-row input {
    width: 60px; padding: 6px 10px; border-radius: 6px;
    border: 1px solid #3a2535; background: #231820; color: #e8ddd0;
    font-family: Georgia, serif; font-size: 14px; text-align: center;
  }
</style>
</head>
<body>

<h1>\\U0001F377 Scan Label</h1>
<p class="subtitle">Take a photo of a wine label to add it to the cellar</p>

<div class="scan-area">
  <div class="preview" id="preview">
    <div class="placeholder" id="placeholder">Tap below to take a photo<br>or choose from gallery</div>
  </div>

  <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()">
    \\U0001F4F7 Take Photo
  </button>
  <input type="file" id="fileInput" accept="image/*" capture="environment" onchange="handleFile(this)">

  <button class="btn btn-secondary" id="chooseBtn" onclick="chooseFromGallery()">
    Choose from gallery
  </button>
  <input type="file" id="galleryInput" accept="image/*" onchange="handleFile(this)">

  <p class="status" id="status"></p>
</div>

<div class="result-card" id="resultCard">
  <h2 id="rWine"></h2>
  <div class="producer" id="rProducer"></div>
  <div class="detail"><span>Region:</span> <span id="rRegion"></span></div>
  <div class="detail"><span>Vintage:</span> <span id="rVintage"></span></div>
  <div class="detail"><span>Varietal:</span> <span id="rVarietal"></span></div>
  <div class="detail"><span>Style:</span> <span id="rStyle"></span></div>
  <div class="detail"><span>Est. Market Price:</span> $<span id="rMarket"></span></div>
  <div class="detail"><span>Score:</span> <span id="rScore"></span></div>
  <div class="detail"><span>Drink:</span> <span id="rWindow"></span></div>
  <div class="detail"><span>Pairings:</span> <span id="rPairings"></span></div>
  <div class="summary" id="rSummary"></div>

  <div class="price-input-row">
    <label>Purchase price: $</label>
    <input type="number" id="purchasePrice" placeholder="0" min="0" step="1">
  </div>
  <div class="qty-input-row">
    <label>Quantity:</label>
    <input type="number" id="qty" value="1" min="1" step="1">
  </div>

  <button class="btn btn-primary" id="addBtn" onclick="addToCollection()" style="margin-top:16px">
    Add to Collection
  </button>
  <p class="status" id="addStatus" style="margin-top:8px"></p>
</div>

<a class="back-link" href="/">&larr; Back to Dashboard</a>

<script>
let pendingWine = null;

function chooseFromGallery() {
  document.getElementById('galleryInput').click();
}

function handleFile(input) {
  const file = input.files[0];
  if (!file) return;

  // Show preview
  const reader = new FileReader();
  reader.onload = function(e) {
    document.getElementById('placeholder').style.display = 'none';
    const img = document.createElement('img');
    img.src = e.target.result;
    const preview = document.getElementById('preview');
    const existing = preview.querySelector('img');
    if (existing) existing.remove();
    preview.appendChild(img);
  };
  reader.readAsDataURL(file);

  // Upload
  const status = document.getElementById('status');
  status.className = 'status';
  status.innerHTML = '<span class="spinner"></span> Identifying wine...';
  document.getElementById('resultCard').style.display = 'none';

  const formData = new FormData();
  formData.append('image', file);

  fetch('/api/scan', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        status.className = 'status error';
        status.textContent = data.error;
        return;
      }
      status.className = 'status success';
      status.textContent = 'Wine identified!';
      pendingWine = data;
      showResult(data);
    })
    .catch(err => {
      status.className = 'status error';
      status.textContent = 'Failed to scan: ' + err.message;
    });
}

function showResult(w) {
  document.getElementById('rWine').textContent = w.wine || 'Unknown';
  document.getElementById('rProducer').textContent = w.producer || 'Unknown Producer';
  document.getElementById('rRegion').textContent = (w.appellation || '') + (w.region ? ', ' + w.region : '') + (w.country ? ' \\u2014 ' + w.country : '');
  document.getElementById('rVintage').textContent = w.vintage || 'NV';
  document.getElementById('rVarietal').textContent = w.varietal || '\\u2014';
  document.getElementById('rStyle').textContent = w.style || '\\u2014';
  document.getElementById('rMarket').textContent = w.marketPrice || '\\u2014';
  document.getElementById('rScore').textContent = w.score || '\\u2014';
  document.getElementById('rWindow').textContent = (w.drinkFrom || '?') + '\\u2013' + (w.drinkTo || '?');
  document.getElementById('rPairings').textContent = (w.pairings || []).join(', ');
  document.getElementById('rSummary').textContent = w.summary || '';
  document.getElementById('purchasePrice').value = '';
  document.getElementById('qty').value = '1';
  document.getElementById('addStatus').textContent = '';
  document.getElementById('resultCard').style.display = 'block';
}

function addToCollection() {
  if (!pendingWine) return;
  const btn = document.getElementById('addBtn');
  const status = document.getElementById('addStatus');
  btn.disabled = true;
  status.className = 'status';
  status.innerHTML = '<span class="spinner"></span> Adding to collection...';

  const pp = document.getElementById('purchasePrice').value;
  const qty = document.getElementById('qty').value;
  pendingWine.purchasePrice = pp ? parseFloat(pp) : null;
  pendingWine.qty = qty ? parseInt(qty) : 1;

  fetch('/api/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(pendingWine),
  })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        status.className = 'status error';
        status.textContent = data.error;
        btn.disabled = false;
        return;
      }
      status.className = 'status success';
      status.textContent = '\\u2713 Added! ' + data.producer + ' ' + data.wine + ' (' + data.vintage + ')';
      pendingWine = null;
      btn.disabled = true;
    })
    .catch(err => {
      status.className = 'status error';
      status.textContent = 'Failed: ' + err.message;
      btn.disabled = false;
    });
}
</script>
</body>
</html>
"""

# ── routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    html = find_dashboard_html()
    if html:
        return send_file(str(html))
    return "No dashboard found. Run generate_dashboard.py first.", 404


@app.route("/scan")
def scan_page():
    return SCAN_PAGE


@app.route("/api/scan", methods=["POST"])
def api_scan():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file = request.files["image"]
    image_bytes = file.read()
    mime_type = file.content_type or "image/jpeg"

    try:
        wine_data = extract_wine_from_label(image_bytes, mime_type)
    except json.JSONDecodeError as e:
        return jsonify({"error": "Could not parse Gemini response: " + str(e)}), 500
    except Exception as e:
        return jsonify({"error": "Scan failed: " + str(e)}), 500

    if not wine_data.get("producer"):
        return jsonify({"error": "Could not identify the wine from this image. Try a clearer photo of the label."}), 422

    return jsonify(wine_data)


@app.route("/api/add", methods=["POST"])
def api_add():
    wine_data = request.get_json()
    if not wine_data or not wine_data.get("producer"):
        return jsonify({"error": "Invalid wine data"}), 400

    wines = load_wines()

    new_wine = {
        "id": next_id(wines),
        "producer": wine_data.get("producer", ""),
        "wine": wine_data.get("wine", ""),
        "appellation": wine_data.get("appellation", ""),
        "country": wine_data.get("country", ""),
        "region": wine_data.get("region", ""),
        "vintage": wine_data.get("vintage", "NV"),
        "qty": wine_data.get("qty", 1),
        "varietal": wine_data.get("varietal", ""),
        "style": wine_data.get("style", "red"),
        "purchasePrice": wine_data.get("purchasePrice"),
        "marketPrice": wine_data.get("marketPrice"),
        "score": wine_data.get("score", 85),
        "drinkFrom": wine_data.get("drinkFrom", date.today().year),
        "drinkTo": wine_data.get("drinkTo", date.today().year + 5),
        "pairings": wine_data.get("pairings", []),
        "summary": wine_data.get("summary", ""),
        "purchasePriceEff": wine_data.get("purchasePrice") or wine_data.get("marketPrice") or 1,
        "qprRaw": 1.0,
        "qprIndex": 5.0,
        "drinkStatus": "now",
    }

    wines.append(new_wine)
    recompute_fields(wines)
    save_wines(wines)

    try:
        regenerate_dashboard()
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Wine added but dashboard regeneration failed: " + str(e)}), 500

    return jsonify({
        "ok": True,
        "id": new_wine["id"],
        "producer": new_wine["producer"],
        "wine": new_wine["wine"],
        "vintage": new_wine["vintage"],
    })


if __name__ == "__main__":
    # Ensure a dashboard exists
    if not find_dashboard_html():
        print("No dashboard found, generating...")
        regenerate_dashboard()

    print("86 Wine Cellar — http://0.0.0.0:" + str(PORT))
    print("Scan page  — http://0.0.0.0:" + str(PORT) + "/scan")
    app.run(host="0.0.0.0", port=PORT, debug=False)
