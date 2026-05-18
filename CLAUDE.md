# 86 Wine Cellar Dashboard — Project Context

This file is the operating brief for any Claude session working on this project. Read it before doing anything else.

---

## What this project is

A self-contained, single-file HTML wine cellar dashboard with a built-in edit UI. There is no backend, no server, no database. Everything lives in three files in this folder:

- `wines.json` — canonical data source (two-array format: `wines` + `consumed`)
- `generate_dashboard.py` — Python script that reads wines.json and writes the dated HTML
- `YYYYMMDD_Wine Cellar Dashboard.html` — generated dashboard (read-only artifact; regenerated from wines.json)

Excel has been retired. The dashboard is the only interface for managing the collection.

**Workflow note:** The user primarily works by making edits in the browser UI, exporting the HTML, and handing that HTML to Claude. Claude reads both `WINES` and `CONSUMED` out of the embedded JS, writes them back to `wines.json`, and regenerates. The user does not manually export JSON.

---

## File naming convention

Every time the HTML dashboard is updated, name it:

```
YYYYMMDD_Wine Cellar Dashboard.html
```

**Versioning logic (apply every time `generate_dashboard.py` is run):**
1. Check whether a dated dashboard file already exists in this folder.
2. If the existing file has **today's date** — overwrite it. No archive needed.
3. If the existing file has an **earlier date** — move it to `Archive/` first, then write the new file with today's date.

This keeps exactly one active dashboard in the folder at all times, with prior versions preserved in `Archive/`.

---

## Source of truth

**`wines.json` is always the source of truth for data.** The HTML dashboard is generated from it via `generate_dashboard.py`, which lives permanently in this folder alongside `wines.json`.

If the HTML and JSON are out of sync, regenerate the HTML from the JSON. Never edit the HTML directly to fix data.

---

## wines.json structure

`wines.json` is a two-key object — **not** a flat array:

```json
{
  "wines": [ ...active collection... ],
  "consumed": [ ...drinking history... ]
}
```

`generate_dashboard.py` handles a legacy flat array gracefully (treats it as `wines`, `consumed = []`), but always writes the two-key format.

---

## Wine schema (wines.json)

Each wine object in `wines` has these fields:

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

Each object in `consumed` has all the same fields as a wine (with `qty` always set to `1`, since each entry represents a single bottle consumed), plus these additional fields:

```json
"removedDate": "2026-05-11",   // ISO date string — when the bottle was logged as consumed
"myRating": "good",            // optional — WSET SAT quality level: faulty | poor | acceptable | good | very good | outstanding
"myNote": "Bright acidity..."  // optional — free-text tasting note
```

`myRating` and `myNote` are captured via a rating modal at consumption time. Older consumed entries may lack these fields — the dashboard renders "—" when absent.

**QPR formula:**
- `qprRaw = score / purchasePriceEff`
- `qprIndex = ((qprRaw - min) / (max - min)) * 9 + 1`, rounded to 1 decimal
- min/max are across the entire collection

**drinkStatus logic (CY = current year):**

`drinkStatus` is a **fully derived field** — always computed from `drinkFrom`, `drinkTo`, and CY. The five valid values (matching dashboard CSS classes and labels) are:

- `past`: CY > drinkTo
- `urgent`: drinkFrom <= CY <= drinkTo AND drinkTo == CY
- `now`: drinkFrom <= CY <= drinkTo AND (drinkTo − CY) > 2
- `soon`: CY < drinkFrom AND drinkFrom <= CY + 2
- `wait`: CY < drinkFrom AND drinkFrom > CY + 2

**Do not use** `early`, `late`, or `peak` — these are not recognised by the dashboard and will render as "undefined". `generate_dashboard.py` now recomputes `drinkStatus` for every wine on each run and writes the corrected values back to `wines.json`, so stale or invalid statuses are automatically fixed at generation time.

---

## Dashboard sections

The HTML has five tabs:

1. **Overview** — stat cards (total bottles, SKUs, countries, market value, vintage span) + Chart.js charts (style breakdown, country breakdown, score distribution, QPR scatter)
2. **Drinking Windows** — sortable Gantt-style table of all active wines
3. **Wine Profiles** — card view with tasting notes, pairings, drinking window
4. **QPR Analysis** — ranked list by qprIndex with score/price/QPR display
5. **Drinking History** — read-only table of consumed wines, sorted by date consumed (most recent first), showing: date consumed, wine, vintage, style, score, my rating (WSET SAT level + optional tasting note)

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
- `const WINES = [...];` and `const CONSUMED = [...];` — both arrays are embedded in the HTML and are the live in-browser state
- Charts: named instances in `let _charts = {}`, destroyed and recreated on tab switch via `buildCharts()`
- `exportHTML()` uses `document.documentElement.outerHTML` (not fetch) — works in all browsers including Arc/Firefox/Safari for `file://` URLs
- Before writing the export blob, strip open drawer classes AND update both constants:
  ```js
  src = src.replace(/class="drawer-overlay open"/g, 'class="drawer-overlay"');
  src = src.replace(/class="drawer open"/g, 'class="drawer"');
  // replace both WINES and CONSUMED constants in the exported HTML
  ```
- `exportJSON()` exports `{"wines": WINES, "consumed": CONSUMED}` — not a flat array
- `removeWine()` opens a rating modal (WSET SAT levels + optional tasting note), then on confirm: stamps `removedDate`, optionally `myRating` and `myNote`, pushes to `CONSUMED`, splices from `WINES`, recomputes QPR, and re-renders.
- `adjustQty()` with a minus delta also opens the same rating modal. If qty > 1, the wine stays in `WINES` with decremented qty and a consumed copy (qty=1) is pushed to `CONSUMED`. If qty = 1, the wine is removed from `WINES` entirely (same as the ✕ button). Plus deltas increment immediately with no modal.

---

## Collection stats (as of 2026-05-09)

- 56 SKUs, 60 bottles (active)
- 9 bottles consumed (tracked in `consumed` array)
- 7 countries: Argentina, Australia, Chile, France, Germany, Italy, USA
- Vintage span: 1988–2025
- Market value: ~$5.3k
- Next available ID: 66

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

**Remove a wine (mark as consumed):**
- In the dashboard UI: click ✕ on a wine or use the minus button in the Edit drawer → a rating modal appears (WSET SAT level + optional tasting note) → on confirm, the wine moves to `CONSUMED` with today's date and any rating/note. If qty was > 1 and minus was used, only the qty decrements (wine stays in `WINES`); otherwise the wine is removed from `WINES` entirely.
- Via JSON: move the wine object from `wines` to `consumed`, add `"removedDate": "YYYY-MM-DD"` and optionally `"myRating"` and `"myNote"`, set `qty` to 1, recompute QPR across remaining `wines`, regenerate HTML

**Regenerate the dashboard** (the most common operation):
```bash
python3 generate_dashboard.py
```
The script reads `wines.json` from this folder and writes the dated HTML back to this folder. After running, apply the versioning logic above (archive old file if it's from a prior date).

---

## What NOT to do

- Do not edit the HTML file directly to change data — always go through wines.json
- Do not use f-strings in the Python generator
- Do not use `\uD83C\uDF77`-style surrogate pairs for emoji in Python — use `\U0001F377`
- Do not use `fetch(location.href)` for HTML export — it's blocked for file:// URLs
- Do not leave the edit drawer open state in exported HTML

---

## generate_dashboard.py

The script lives permanently in this folder and is tracked in git. It should not need to be reconstructed. If it is somehow missing, it can be rebuilt — it is ~600 lines of Python that:
1. Reads `wines.json` (two-array format: `{"wines": [...], "consumed": [...]}`)
2. Computes stats (bottles, value, style/country counts) — stats operate on `wines` only, not `consumed`
3. Assembles HTML via string list (`p = []`)
4. Embeds both `const WINES = [...]` and `const CONSUMED = [...]` in the output
5. Outputs `YYYYMMDD_Wine Cellar Dashboard.html`

The script also supports `--sync <html_file>`, which extracts both arrays from an exported dashboard HTML, diffs against `wines.json`, checks for ID collisions, preserves `myRating`/`myNote` on consumed entries, and writes the updated JSON — then proceeds to regenerate as normal. This is the standard path for syncing user edits back from the browser.

The curated collection narrative lives in `OVERVIEW_PARAS` and `GAP_ITEMS` near the top of the script — update those when the collection changes significantly without needing to touch the rest of the script.

**When Claude receives an HTML file from the user:**

Run `python3 generate_dashboard.py --sync <path-to-html>` from this folder. The `--sync` flag handles extraction, diffing, ID collision checks, and JSON write in one step. Review the printed diff summary and relay it to the user. If the diff shows zero changes, flag it — the user may have uploaded the wrong file.

**ID assignment note:** `generate_dashboard.py` now derives new wine IDs from `Math.max` across both `WINES` and `CONSUMED` (patched 2026-05-11). Before this fix, new wines were assigned IDs based on `WINES` only, which could collide with IDs already used by consumed wines.
