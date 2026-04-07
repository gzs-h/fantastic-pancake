# 86 Wine Cellar

A self-contained wine cellar dashboard — no backend, no database, no dependencies beyond a browser.

## What's here

| File | Purpose |
|---|---|
| `wines.json` | Canonical data source. Every bottle lives here. |
| `generate_dashboard.py` | Reads `wines.json`, writes the dated HTML dashboard. |
| `CLAUDE.md` | Operating brief for Claude sessions working on this project. |

## Generating the dashboard

```bash
python3 generate_dashboard.py
```

Outputs `YYYYMMDD_Wine Cellar Dashboard.html` in this folder. Open it in any browser — no server needed. If a dashboard from a prior date already exists, it's automatically moved to `Archive/`.

## Dashboard features

- **Overview** — stat cards, charts (style, country, varietal breakdown)
- **Drinking Windows** — Gantt-style view, sortable by urgency / vintage / country / style
- **Wine Profiles** — card view with tasting notes, pairings, drinking window; filterable
- **QPR Analysis** — collection ranked by value score (critic score ÷ price paid, normalized 1–10)
- **Edit drawer** — add/remove wines, adjust quantities, export updated HTML or JSON — all in-browser

## Data model

Each wine in `wines.json` has the following fields:

```json
{
  "id": 1,
  "producer": "Domaine Leflaive",
  "wine": "Puligny-Montrachet",
  "appellation": "Puligny-Montrachet",
  "country": "France",
  "region": "Burgundy",
  "vintage": 2021,
  "qty": 1,
  "varietal": "Chardonnay",
  "style": "white",
  "purchasePrice": 95,
  "marketPrice": 120,
  "score": 93,
  "drinkFrom": 2024,
  "drinkTo": 2033,
  "pairings": ["Roast chicken", "Grilled lobster"],
  "summary": "2-3 sentence tasting and context note.",
  "purchasePriceEff": 95,
  "qprRaw": 0.979,
  "qprIndex": 6.2,
  "drinkStatus": "now"
}
```

`qprRaw`, `qprIndex`, and `drinkStatus` are computed — recalculate across the full collection whenever wines are added, edited, or removed.

## Setup

### Static dashboard (no server needed)

No installation required. Just run the generator and open the HTML in a browser:

```bash
python3 generate_dashboard.py
open "YYYYMMDD_Wine Cellar Dashboard.html"
```

### Label scanner (optional)

The label scanner (`server.py`) lets you photograph a bottle and add it to the collection automatically. It requires a Gemini API key and two Python packages.

**1. Install dependencies**

```bash
pip3 install flask google-genai
```

**2. Get a Gemini API key**

Create one at [aistudio.google.com](https://aistudio.google.com). Free tier is sufficient.

**3. Run the server**

```bash
GEMINI_API_KEY=your_key_here python3 server.py
```

The dashboard is served at `http://localhost:8086` and the scan UI at `http://localhost:8086/scan`. Open the scan URL on your phone (must be on the same network) to photograph labels.

**Optional env vars:**

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | required | Gemini API key |
| `PORT` | `8086` | Server port |
| `SCAN_SECRET` | _(none)_ | Shared secret to restrict scan access |

---

## Workflow

**Adding a wine:** edit `wines.json`, recompute QPR fields and `drinkStatus`, run the generator.

**Enriching a wine added via the browser UI:** export the dashboard HTML, bring it to a Claude session — it will pull the new entry, research the missing fields, and regenerate.

**Quick in-session edits** (qty adjustments, removals): use the Edit drawer in the dashboard, then export the updated JSON to sync back to `wines.json`.
