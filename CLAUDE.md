# 86 Wine Cellar Dashboard — Project Context

This file is the operating brief for any Claude session working on this project. Read it before doing anything else.

---

## What this project is

A self-contained, single-file HTML wine cellar dashboard with a built-in edit UI. There is no backend, no server, no database. Everything lives in two files in this folder:

- `wines.json` — canonical data source (56 SKUs, 60 bottles as of April 2026)
- `YYYYMMDD_Wine Cellar Dashboard.html` — generated dashboard (read-only artifact; regenerated from wines.json)

Excel has been retired. The dashboard is the only interface for managing the collection.

---

## File naming convention

Every time the HTML dashboard is updated, name it:

```
YYYYMMDD_Wine Cellar Dashboard.html
```

Use the actual current date (e.g. `20260402_Wine Cellar Dashboard.html`). Overwrite the existing file with the same date; do not accumulate old versions.

---

## Source of truth

**`wines.json` is always the source of truth for data.** The HTML dashboard is generated from it via `generate_dashboard.py` (located at `/sessions/<session>/generate_dashboard.py` — will need to be reconstructed each session from this brief if not present).

If the HTML and JSON are out of sync, regenerate the HTML from the JSON. Never edit the HTML directly to fix data.

---

## Wine schema (wines.json)

Each wine object has these fields:

```json
{
  "id": 1,                          // integer, unique, never reuse
  "producer": "Rutherford Ranch",
  "wine": "Cabernet Sauvignon Reserve",
  "appellation": "Napa Valley",
  "country": "USA",
  "region": "Napa Valley",
  "vintage": 2018,                  // integer year, or "NV" string
  "qty": 1,                         // bottle count
  "varietal": "Cabernet Sauvignon",
  "style": "red",                   // red | white | sparkling | rosé | dessert | orange
  "purchasePrice": 18,              // per bottle, USD
  "marketPrice": 28,                // per bottle, current market USD
  "score": 87,                      // critic score (85–100 typical)
  "drinkFrom": 2020,                // drinking window start year
  "drinkTo": 2028,                  // drinking window end year
  "pairings": ["Grilled ribeye"],   // array of food pairing strings
  "summary": "...",                 // 2–3 sentence tasting/context note
  "purchasePriceEff": 18,           // effective purchase price (accounts for discounts)
  "qprRaw": 4.83,                   // score / purchasePriceEff (computed)
  "qprIndex": 8.8,                  // normalized 1–10 (computed)
  "drinkStatus": "now"              // "early" | "now" | "peak" | "late" (computed vs CY)
}
```

Fields marked (computed) are derived — recalculate whenever wines are added/edited.

**QPR formula:**
- `qprRaw = score / purchasePriceEff`
- `qprIndex = ((qprRaw - min) / (max - min)) * 9 + 1`, rounded to 1 decimal
- min/max are across the entire collection

**drinkStatus logic (CY = current year):**
- `early`: CY < drinkFrom
- `now`: drinkFrom <= CY <= drinkTo
- `peak`: (subjective; mid-window, not used in current logic)
- `late`: CY > drinkTo

---

## Dashboard sections

The HTML has four tabs:

1. **Overview** — stat cards (total bottles, SKUs, countries, market value, vintage span) + Chart.js charts (style breakdown, country breakdown, score distribution, QPR scatter)
2. **Inventory** — sortable table of all wines
3. **Profiles** — card view with tasting notes, pairings, drinking window
4. **QPR Index** — ranked list by qprIndex with score/price/QPR display

Plus an **Edit Collection drawer** (slide-in panel) for add/edit/remove wine operations and HTML/JSON export.

---

## Key technical constraints

**Python generation script:**
- Use `p = []` list + `''.join(p)` pattern — never f-strings (they collide with JS `${}` template literals)
- Emoji in Python string literals: use `\U0001F377` (8-digit) not `\uD83C\uDF77` (surrogate pairs) — surrogates cause UnicodeEncodeError on file write
- Write output with `open(path, 'w', encoding='utf-8')`
- **Inline style attributes in string-concatenated JS:** always close the attribute quote before `>`. Pattern must be `'">'` not `'>'`. Example — the QPR table discount cell:
  ```python
  # CORRECT
  p.append("+ '<td style=\"color:'+(disc>0?'#4caf7a':'var(--muted)')+'\">'\n")
  # WRONG — missing closing quote, browser eats cell content as attribute value
  p.append("+ '<td style=\"color:'+(disc>0?'#4caf7a':'var(--muted)')+'>')\n")
  ```

**JavaScript in the dashboard:**
- `const WINES = [...];` array embedded in the HTML — this is what gets edited in-browser and exported
- Charts: named instances in `let _charts = {}`, destroyed and recreated on tab switch via `buildCharts()`
- `exportHTML()` uses `document.documentElement.outerHTML` (not fetch) — works in all browsers including Arc/Firefox/Safari for `file://` URLs
- Before writing the export blob, strip open drawer classes:
  ```js
  src = src.replace(/class="drawer-overlay open"/g, 'class="drawer-overlay"');
  src = src.replace(/class="drawer open"/g, 'class="drawer"');
  ```
- `removeWine()` must call both `renderInvList()` and `refreshStats()` after splice

---

## Collection stats (as of 2026-04-02)

- 56 SKUs, 60 bottles
- 7 countries: Argentina, Australia, Chile, France, Germany, Italy, USA
- Styles: red (33), white (10), sparkling (9), rosé (2), dessert (1), orange (1)
- Vintage span: 1988–2025
- Market value: ~$4,655

---

## Common tasks

**Add a wine:**
1. Edit `wines.json` — assign the next available `id`, fill all fields
2. Recompute `qprRaw`, `qprIndex` (requires recalculating min/max across full collection), `drinkStatus`
3. Run `generate_dashboard.py` to rebuild the HTML

**Enrich a pending wine** (one added manually with placeholder data):
- Search for the producer + wine + vintage online
- Fill: `appellation`, `region`, `varietal`, `score`, `marketPrice`, `drinkFrom`, `drinkTo`, `pairings`, `summary`
- Remove `"pending": true` flag if present
- Recompute QPR fields and regenerate

**Remove a wine:**
1. Delete from `wines.json`
2. Recompute QPR normalization across remaining wines
3. Regenerate HTML

**Regenerate the dashboard** (the most common operation):
```bash
python3 generate_dashboard.py
```
The script reads `wines.json` from this folder and writes the dated HTML back to this folder.

---

## What NOT to do

- Do not edit the HTML file directly to change data — always go through wines.json
- Do not use f-strings in the Python generator
- Do not use `\uD83C\uDF77`-style surrogate pairs for emoji in Python — use `\U0001F377`
- Do not use `fetch(location.href)` for HTML export — it's blocked for file:// URLs
- Do not leave the edit drawer open state in exported HTML

---

## Regenerating generate_dashboard.py

If the session is fresh and the script is missing, it must be reconstructed. The script is ~840 lines of Python that:
1. Reads `wines.json`
2. Computes stats (bottles, value, style/country counts)
3. Assembles HTML via string list (`p = []`)
4. Outputs `YYYYMMDD_Wine Cellar Dashboard.html`

Refer to the session transcript or prior CLAUDE.md history to recover it, or rebuild from this brief + the wines.json schema above.
