---
name: wine-dashboard-sync
description: >
  Sync the wine cellar dashboard from an exported HTML file. Use this skill whenever the user
  uploads or references an HTML file in the 86 Wine project — this is the standard update workflow.
  Triggers include: uploading a Wine Cellar Dashboard HTML, mentioning an exported HTML,
  asking to "update the dashboard", "sync the collection", or handing over a file that looks like
  a dashboard export (dated HTML with wine data). Even if the user just drops an HTML file without
  explanation, this skill almost certainly applies.
---

# Wine Dashboard Sync

This skill handles the most common operation in the wine cellar project: the user has made edits
in the browser-based dashboard UI, exported the HTML, and now wants `wines.json` and the
generated dashboard updated to reflect those changes.

## Why this exists

Without this skill, every sync session starts with Claude reconstructing the extraction logic
from scratch — reading CLAUDE.md, figuring out the regex, writing a one-off diff script. The
`--sync` flag on `generate_dashboard.py` now handles all of that deterministically. This skill
just tells Claude to use it.

## Steps

### 1. Identify the uploaded HTML file

The user will either attach it directly or reference a path. The file is typically named
`YYYYMMDD_Wine Cellar Dashboard.html`. If there's ambiguity about which file, ask — but
usually there's only one.

### 2. Run the sync

```bash
python3 generate_dashboard.py --sync <path-to-uploaded-html> --pull-forms
```

Run this from the `86 Wine` project folder. Always include `--pull-forms` alongside `--sync`
to pick up any pending mobile tasting submissions from Netlify Forms in the same pass.

The `--sync` flag:
- Extracts `WINES` and `CONSUMED` arrays from the HTML
- Diffs them against `wines.json` (reports new wines, consumed moves, qty changes)
- Checks for ID collisions between the two arrays (reassigns if found)
- Preserves `myRating`/`myNote` on existing consumed entries
- Writes the updated `wines.json`

The `--pull-forms` flag (runs after `--sync`):
- Fetches pending submissions from the Netlify Forms API (`tasting-log` form)
- Converts them to ad-hoc consumed entries and appends to `wines.json`
- Deduplicates by Netlify submission ID (tracked in `netlify_forms_state.json`)
- Reports how many submissions were pulled (0 is normal if no mobile tastings were logged)

Both mutations complete before the script regenerates and deploys.

### 3. Review the output

The script prints a diff summary. Relay it to the user concisely — they care about what
changed, not the mechanics.

**Zero-change case:** If the diff reports no changes at all, something is likely off — the
user probably uploaded the wrong file or an older export. Flag this clearly:
"These are already in sync — is this the right dashboard export?" Don't proceed to
regeneration until the user confirms.

**Consumed moves and tasting logs:** When wines appear in the diff as moved to consumed or
as new consumed entries, do not ask the user to add ratings or notes. The dashboard has a
built-in rating modal that captures `myRating` and `myNote` at the moment of consumption or
tasting — if those fields are present they are already recorded, and if they are absent the
user chose to skip them. Either way, prompting for retroactive notes is redundant. Just
report what moved and continue.

**Ad-hoc tastings** appear in the diff output as "New tastings (ad-hoc, no data quality check
needed)". These are entries logged via the dashboard's "Log Tasting" flow or via the mobile
tasting form (`log.html` → Netlify Forms → `--pull-forms`) directly to consumed without
ever being in the active collection. Acknowledge them briefly in the summary but do not treat
them as data quality issues or offer to enrich them — missing price, drink window, and QPR
fields are expected and correct for these entries. Mobile-submitted entries may have scan-
populated fields (varietal, score, appellation, etc.) if the user scanned a label.

### 4. Flag data quality issues on new wines

After the sync, check any **newly added wines** (IDs that appeared in the diff under "New wines")
for incomplete data:
- `marketPrice` of 0 or missing
- `purchasePrice` missing
- `score` of 0 or missing
- Any field that's clearly a placeholder (empty string, "TBD", etc.)

Skip this check for consumed moves, tasting logs, and ad-hoc entries — it only applies to
wines newly added to the active collection.

Mention data quality issues to the user but don't block the update.

### 5. Enrich new wines

This step applies only when the diff showed new wine IDs under "New wines" — skip it entirely
for syncs that only involved consumed moves, tasting logs, or qty changes.

For each new wine with incomplete data, offer to enrich it by researching the
producer + wine name + vintage online. The goal is to fill in:
- `appellation`, `region`, `varietal` (if missing or generic)
- `score` (critic score — prefer Wine Spectator, Wine Advocate, Vinous, JancisRobinson.com)
- `marketPrice` (current retail — prefer Wine-Searcher average)
- `drinkFrom` / `drinkTo` (drinking window from a credible source)
- `pairings` (2–4 food pairings appropriate to the wine's style and weight)
- `summary` (2–3 sentence tasting/context note — not a copy-paste from a review, but an
  original synthesis of what makes this wine notable, its vintage context, and where it
  sits in the collection)

Present the enrichment data to the user for approval before writing it to `wines.json`.
If a field can't be reliably sourced, say so rather than guessing — the user can fill it
in later.

After enrichment is approved and written to `wines.json`, regenerate the dashboard. Derived fields (`qprRaw`, `qprIndex`, `drinkStatus`, `purchasePriceEff`) are computed in `dashboard.js` at page load — no manual recompute needed. The corrected values flow back to `wines.json` on the user's next `--sync`.
