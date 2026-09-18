# Session Handoff — June 28, 2026

## Personalized scoring system (brainstorm, not built)

GA is skeptical of critic scores and wants a scoring system tuned to his own taste. The concept: use consumed wines with honest personal ratings (`myRating`, WSET SAT scale) as ground truth, then look for patterns — which varietals, regions, price points, or producers correlate with ratings he finds outstanding vs. merely acceptable.

Constraints we identified:
- Only wines that pass through the collection and get consumed accumulate ratings. Ad-hoc tastings (new `adhoc: true` flag) expand the data set.
- Current data is thin: ~11 consumed, 7 rated. Useful signal probably requires 30–50 honest ratings before patterns emerge.
- No action was taken on this — it's a future feature once enough data accumulates.

## What was actually built this session

### 1. Ad-hoc tasting log (Log Tasting button)
Added a "Log Tasting" button next to "Add to Collection" in the Add Wine drawer tab. Clicking it takes the same form fields and writes an entry directly to `CONSUMED` with `adhoc: true` — the wine is never added to `WINES`. This lets GA log glasses/tastings of wines he doesn't own without polluting the active collection.

Files changed: `dashboard.js` (new `logTasting()` function), `template.html.j2` (button), `dashboard.css`.

### 2. Log tasting from inventory (tasting button per row)
Added a small "tasting" button on each row in the Inventory tab. Clicking it opens the same rating modal, copies the wine's data to a new `CONSUMED` entry with `adhoc: true` and today's date, but does **not** decrement qty or touch `WINES`. Use case: GA opens a bottle from the collection, has a glass, wants to note it — without marking it consumed.

Files changed: `dashboard.js` (new `logTastingFromWine(id)` function, updated `renderInvList()`), `dashboard.css` (`.tasting-link` style).

### 3. generate_dashboard.py diff output
Updated `--sync` diff printing to separately report "New tastings (ad-hoc)" vs "New consumed" entries, since they have different implications for data quality review.

### 4. wine-dashboard-sync skill update
The installed skill was asking for retroactive tasting notes after consumed moves — unaware of the built-in rating modal. Updated skill with explicit directives:
- Don't prompt for retroactive notes on consumed moves or tasting logs — the modal already captures them.
- Ad-hoc tastings are not data quality issues; missing price/QPR fields are expected.
- Steps 4 and 5 (data quality + enrichment) only apply to "New wines" diff entries.

The updated skill is at `wine-dashboard-sync/SKILL.md` in this folder. A packaged `wine-dashboard-sync.skill` file was also produced for reinstallation via Cowork Settings → Capabilities.

### 5. CLAUDE.md + README.md
Both updated to document the ad-hoc tasting flow, the inventory tasting button, and to clarify the `adhoc: true` schema field.
