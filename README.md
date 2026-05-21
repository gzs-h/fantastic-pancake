# 86 Wine Cellar

A self-contained wine cellar dashboard. The generated HTML runs in any browser — no backend or database. The build step requires Python + Jinja2.

## What's here

| File | Purpose |
|---|---|
| `wines.json` | Canonical data source. Every bottle lives here. |
| `generate_dashboard.py` | Build script. Reads `wines.json`, renders the template, writes the dated HTML dashboard. |
| `template.html.j2` | Jinja2 template defining the dashboard's HTML structure. |
| `dashboard.css` | Dashboard styles. Inlined into the output HTML at build time. |
| `dashboard.js` | Dashboard logic — filtering, charts, edit drawer, rating modal. Inlined into the output. |
| `requirements.txt` | Python dependencies (`jinja2` for the build; `flask` + `google-genai` for the optional label scanner). |
| `server.py` | Optional Flask-based label scanner server (see "Label scanner" below). |
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
- **Drinking History** — consumed bottles and ad-hoc tastings, sorted by date, with WSET SAT ratings and tasting notes
- **Edit drawer** — add/remove wines, adjust quantities, log ad-hoc tastings, scan labels, export updated HTML or JSON — all in-browser

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

`qprRaw`, `qprIndex`, `purchasePriceEff`, and `drinkStatus` are derived fields. They're computed by `dashboard.js` every time the dashboard is opened in a browser, so you don't need to maintain them by hand. Stale values in `wines.json` self-correct on the next browser-load-export-sync cycle.

## Setup

### Static dashboard (no server needed)

No installation required. Just run the generator and open the HTML in a browser:

```bash
python3 generate_dashboard.py
open "YYYYMMDD_Wine Cellar Dashboard.html"
```

### Label scanner (built-in)

The label scanner is built directly into the dashboard. Open the Edit drawer → Add Wine tab → click "Scan Label". On first use it will prompt for a Gemini API key, which is stored in your browser's localStorage (not written into the HTML file).

Get a key at [aistudio.google.com](https://aistudio.google.com). Free tier is sufficient.

The scan fills in producer, wine, vintage, varietal, region, score, market price, drinking window, pairings, and a tasting note. You review the fields, then click "Add to Collection" to cellar it or "Log Tasting" to record it as a one-off tasting without adding to inventory.

`server.py` is an older, standalone label scanner that runs as a local Flask server. It is not required and not integrated into the current workflow — the browser-based scanner above supersedes it.

---

## Workflow

**Adding a wine:** edit `wines.json` with the input fields (producer, wine, country, style, vintage, qty, prices, score, drinking window), then run the generator. Derived fields populate automatically when the dashboard is opened in a browser.

**Enriching a wine added via the browser UI:** export the dashboard HTML, bring it to a Claude session — it will run `python3 generate_dashboard.py --sync <html-file>` to pull the new entry into `wines.json`, then research the missing fields and regenerate.

**Quick in-session edits** (qty adjustments, removals): use the Edit drawer in the dashboard, click Download Updated Dashboard, then run `python3 generate_dashboard.py --sync <html-file>` to write the changes back to `wines.json`. The JSON export button is available as a backup but isn't the standard path.

**Logging an ad-hoc tasting** (wine not in your collection): Edit drawer → Add Wine tab → fill in the fields (or scan the label) → click "Log Tasting". A rating modal fires immediately. The entry lands in `consumed` with `adhoc: true` and never touches your active collection.
