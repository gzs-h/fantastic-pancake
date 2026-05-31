# Mobile Tasting Form Plan

## What we're building and why

The Netlify dashboard at https://ga-wine-cellar.netlify.app is read-only — edits made there
don't persist anywhere. When a tasting happens away from a desktop, there's no way to capture
notes without a full export-and-sync cycle later.

This plan adds a lightweight mobile-first "Log Tasting" page (`log.html`) hosted on the same
Netlify site. It includes the existing Gemini label-scanning logic (client-side, no server
needed), submits entries to Netlify Forms, and extends `generate_dashboard.py` to pull those
submissions into `wines.json` during the normal sync flow.

---

## Architecture overview

```
Phone browser → log.html (Netlify) → Netlify Forms (stores submission)
                                              ↓
                              generate_dashboard.py --pull-forms
                                              ↓
                                        wines.json (consumed array)
                                              ↓
                              generate_dashboard.py (regenerate + deploy)
```

The form page is a static HTML file that lives alongside the dashboard. The Netlify deploy
process (in `generate_dashboard.py`) needs to be updated to include it in the zip. Everything
else is additive — no changes to `template.html.j2`, `dashboard.css`, or `dashboard.js`.

---

## Files to create / modify

| File | Action |
|------|--------|
| `log.html` | **Create** — the mobile tasting form |
| `generate_dashboard.py` | **Modify** in two places: (1) include `log.html` in the Netlify zip deploy; (2) add `--pull-forms` flag |
| `netlify_forms_state.json` | **Auto-created** by `--pull-forms` on first run — tracks processed submission IDs |

**Do not edit** `dashboard.css`, `dashboard.js`, `template.html.j2`, `wines.json`, or any
generated HTML file directly.

---

## Part 1 — Create `log.html`

`log.html` is a self-contained single-file HTML page. It should be saved directly in the
`86 Wine` folder (alongside `generate_dashboard.py`).

### Visual design

Match the existing dashboard aesthetic exactly:
- Same CSS variables (dark background `#0f0a0e`, gold `#c9a84c`, cream `#e8ddd0`, etc.)
- Same Georgia serif font
- Same border/surface colours
- No tabs, no nav bar — it's a single focused form

The page should feel like the "Add Wine" tab of the existing edit drawer, but full-screen
and mobile-optimised.

### Page structure

```
┌─────────────────────────────────┐
│  🍷  Log a Tasting              │  ← simple header, no nav
├─────────────────────────────────┤
│  [📷 Scan Label]                │  ← triggers camera, fills fields
│  Scan status line               │
│  ─────────────────              │
│  API key: ✓ set  [change]       │  ← same key management as dashboard
├─────────────────────────────────┤
│  Producer          (text)       │
│  Wine name         (text)       │
│  Vintage           (number)     │
│  Country           (select)     │
│  Style             (select)     │
│  ─────────────────              │
│  Date              (date, today)│
│  My Rating         (select)     │  ← WSET scale
│  Tasting note      (textarea)   │
│  ─────────────────              │
│  (hidden: varietal, appellation,│  ← populated by scan, not
│   region, score, marketPrice,   │     user-visible but submitted
│   drinkFrom, drinkTo, pairings, │     with the form
│   summary)                      │
├─────────────────────────────────┤
│  [    Submit Tasting    ]       │
│  status message                 │
└─────────────────────────────────┘
```

### Form fields

| Field | Type | Notes |
|-------|------|-------|
| producer | text | Required. Pre-filled by scan. |
| wine | text | Required. Pre-filled by scan. |
| vintage | number | Optional. Pre-filled by scan. |
| country | select | Same country list as dashboard. Pre-filled by scan. |
| style | select | red/white/sparkling/rosé/dessert/orange. Pre-filled by scan. |
| date | date | Default: today. |
| myRating | select | faulty/poor/acceptable/good/very good/outstanding (WSET SAT). |
| myNote | textarea | Free-text tasting note. |

Hidden fields populated by scan (not user-visible):

| Field | Type | Notes |
|-------|------|-------|
| varietal | hidden | Pre-filled by scan. Empty if no scan. |
| appellation | hidden | Pre-filled by scan. |
| region | hidden | Pre-filled by scan. |
| score | hidden | Pre-filled by scan. |
| marketPrice | hidden | Pre-filled by scan. |
| drinkFrom | hidden | Pre-filled by scan. |
| drinkTo | hidden | Pre-filled by scan. |
| pairings | hidden | JSON-stringified array. Pre-filled by scan. |
| summary | hidden | Pre-filled by scan. |

These fields capture everything Gemini returns from a label scan. Without a scan they
submit as empty strings, and `--pull-forms` treats empties as `None`/`""` (same as any
manual ad-hoc entry). This way scan data isn't lost just because the form has no visible
field for it.

Hidden fields required by Netlify Forms:
- `form-name` (value: `"tasting-log"`) — Netlify uses this to identify the form

### Netlify Forms integration

Add these attributes to the `<form>` tag:
```html
<form name="tasting-log" method="POST" data-netlify="true">
  <input type="hidden" name="form-name" value="tasting-log" />
  ...
</form>
```

Netlify detects the `data-netlify="true"` attribute at deploy time and automatically handles
form submissions. No additional backend setup required.

On submit, intercept the default POST with JavaScript, send it manually (so we can show a
success/error message rather than redirecting away), and clear the form:

```js
form.addEventListener('submit', function(e) {
  e.preventDefault();
  var data = new FormData(form);
  fetch('/', { method: 'POST', body: data })
    .then(function() { showSuccess(); form.reset(); clearDraft(); })
    .catch(function(err) { saveDraft(); showError(err); });
});
```

### Offline resilience (draft persistence)

The form should survive a failed submission without data loss. On submit failure:

1. **`saveDraft()`** — serialise all form field values to `localStorage` under key
   `tasting_draft`. This includes both visible and hidden fields.
2. **`showError()`** — display a clear message: "Submission failed — your entry has been
   saved. Tap Submit again when you have signal." The form stays filled.
3. **On page load** — check for `tasting_draft` in `localStorage`. If present, restore all
   field values and show a banner: "You have an unsaved tasting. Review and submit."
4. **`clearDraft()`** — called on successful submit. Removes `tasting_draft` from
   `localStorage`.

This is deliberately simple: no background retry queue, no service worker. The user taps
Submit manually once they have connectivity. The guarantee is just that navigating away or
closing the browser won't lose their data.

### Scanning logic

Copy the following functions verbatim from `dashboard.js`:

- `_scanKey()`
- `_updateKeyStatus()`
- `toggleKeyArea()`
- `saveKey()`
- `clearKey()`
- `scanLabel()`
- `handleScanFile()`
- `_callGeminiVision()`

These functions reference specific DOM element IDs internally. For them to work without
modification, `log.html` **must** use these exact IDs:

| Element | Required ID | Used by |
|---------|-------------|---------|
| API key status text | `keyStatusLine` | `_updateKeyStatus()` |
| Scan button | `scanBtn` | `_updateKeyStatus()` |
| Key input area wrapper | `keyArea` | `toggleKeyArea()` |
| Key text input | `keyInput` | `saveKey()`, `clearKey()` |
| File input (hidden) | `scanInput` | `scanLabel()` |
| Scan status line | `scanStatus` | `scanLabel()`, `_callGeminiVision()` |

`_fillFormFromScan()` needs a **new version** for `log.html`. The dashboard version
targets `f-producer`, `f-wine`, etc. — the tasting form uses different IDs. The new version
should also populate the hidden fields (varietal, appellation, region, score, marketPrice,
drinkFrom, drinkTo) and JSON-stringify `pairings` and `summary` into their respective
hidden inputs. `_scanPending` is not needed and should be omitted.

The scan input element needs `accept="image/*" capture="environment"` to trigger the rear
camera on mobile:
```html
<input type="file" id="scanInput" accept="image/*" capture="environment"
       style="display:none" onchange="handleScanFile(this)">
```

### Tap target sizing

All buttons and select elements must be at least 44px tall. Use `padding: 12px` on inputs
and `font-size: 16px` (prevents iOS auto-zoom on focus).

---

## Part 2 — Update `generate_dashboard.py`

### 2a. Include `log.html` in the Netlify zip deploy

In `_deploy_to_netlify()`, update the `_headers` content and add `log.html` to the zip:

```python
# Update _headers to cover both pages
_headers_content = (
    '/index.html\n  Content-Type: text/html; charset=utf-8\n'
    '/log.html\n  Content-Type: text/html; charset=utf-8\n'
)

with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(html_path, 'index.html')
    zf.writestr('_headers', _headers_content)
    # Add tasting form if it exists
    log_path = os.path.join(DIR, 'log.html')
    if os.path.exists(log_path):
        zf.write(log_path, 'log.html')
```

This makes `log.html` available at `https://ga-wine-cellar.netlify.app/log.html`.

**Important:** Netlify Forms only activates for a form if it detects `data-netlify="true"` in
a deployed HTML file. The form will not capture submissions until after the first deploy that
includes `log.html`.

### 2b. Add `--pull-forms` flag

Add a new argparse argument alongside `--sync`:
```python
_parser.add_argument('--pull-forms', action='store_true',
                     help='Pull pending Netlify Forms tasting submissions into wines.json.')
```

Implement a `_pull_netlify_forms()` function with this logic:

**Step 1 — Load state**
Read `netlify_forms_state.json` from the project folder. This file stores a list of
already-processed Netlify submission IDs:
```json
{"processed_ids": ["abc123", "def456", ...]}
```
On first run the file won't exist; treat `processed_ids` as an empty set.

**Step 2 — Discover the form ID**
Call `GET https://api.netlify.com/api/v1/sites/{SITE_ID}/forms` with Bearer token.
Find the form where `name == "tasting-log"`. Extract its `id`. If the form doesn't exist yet
(not yet deployed or no submissions ever received), print a message and exit gracefully.

**Step 3 — Fetch submissions**
Call `GET https://api.netlify.com/api/v1/forms/{FORM_ID}/submissions` with Bearer token.
Paginate if necessary (Netlify returns max 100 per page — pass `?page=N` until the response
is empty). Filter out any submission whose `id` is already in `processed_ids`. Each
submission's `data` field is a dict of form field values.

**Step 4 — Convert to consumed entries**
For each new submission, build a consumed entry. Scan-populated hidden fields are included
when present:

```python
def _parse_int_or_none(val):
    try: return int(val)
    except (TypeError, ValueError): return None

def _parse_float_or_none(val):
    try: return float(val)
    except (TypeError, ValueError): return None

def _parse_json_or_none(val):
    if not val: return None
    try: return json.loads(val)
    except (TypeError, json.JSONDecodeError): return None

{
  "id": <next_available_id>,        # max across wines + consumed + 1
  "producer": data.get("producer", ""),
  "wine": data.get("wine", ""),
  "vintage": _parse_int_or_none(data.get("vintage")) or "NV",
  "country": data.get("country", ""),
  "style": data.get("style", "red"),
  "qty": 1,
  "removedDate": data.get("date") or submission["created_at"][:10],
  "myRating": data.get("myRating") or None,
  "myNote": data.get("myNote") or None,
  "adhoc": True,
  "purchasePrice": None,
  "purchasePriceEff": None,
  "qprRaw": None,
  "qprIndex": None,
  # Scan-populated fields (present if scanned, empty/null otherwise):
  "varietal": data.get("varietal", ""),
  "appellation": data.get("appellation", ""),
  "region": data.get("region", ""),
  "score": _parse_int_or_none(data.get("score")),
  "marketPrice": _parse_float_or_none(data.get("marketPrice")),
  "drinkFrom": _parse_int_or_none(data.get("drinkFrom")),
  "drinkTo": _parse_int_or_none(data.get("drinkTo")),
  "pairings": _parse_json_or_none(data.get("pairings")),
  "summary": data.get("summary", ""),
}
```

**Step 5 — Merge and write**
Load `wines.json`, append the new consumed entries, write back. Print a summary:
```
Pulled 3 tasting submission(s) from Netlify Forms.
  → Calstar Cellars Sangiacomo Pinot Noir (2026-05-21)
  → ...
```

**Step 6 — Update state**
Append the `id` of each processed submission to `processed_ids` and write
`netlify_forms_state.json`. This is the primary deduplication mechanism — if the state file
is deleted, re-running `--pull-forms` will re-process everything. As a secondary guard,
before appending each entry, check whether a consumed entry with the same `producer +
wine + vintage + removedDate` combination already exists in `wines.json` and skip if so.

**Step 7 — Regenerate**
After pulling, proceed to regenerate the dashboard as normal (the script already does this
after `--sync`; same pattern applies here).

### Execution order

Currently `_deploy_to_netlify(out_path)` runs at module level (line 467) after the
dashboard HTML is written. The `--pull-forms` logic must execute **before** the regenerate
step so that pulled entries appear in the newly generated HTML and the subsequent deploy.

When both flags are present, the order is:
1. `--sync` (extract data from exported HTML → update `wines.json`)
2. `--pull-forms` (fetch Netlify Forms submissions → append to `wines.json`)
3. Regenerate dashboard HTML from the now-updated `wines.json`
4. Deploy to Netlify (the generated HTML now includes the pulled entries)

This means the deploy call should move inside a function that runs after all data mutations
are complete, rather than at the bare module level.

### Invocation

```bash
# Pull pending tasting form submissions and regenerate:
python3 generate_dashboard.py --pull-forms

# Pull AND sync an exported HTML in one step:
python3 generate_dashboard.py --sync exported.html --pull-forms
```

---

## Part 3 — Verification

### Form verification (on phone)
1. Deploy (run `python3 generate_dashboard.py` after `log.html` exists)
2. Open `https://ga-wine-cellar.netlify.app/log.html` on a phone
3. Enter Gemini API key → confirm "✓ API key set" appears
4. Tap "Scan Label", photograph a wine bottle → confirm fields pre-fill
5. Fill rating + note, tap Submit → confirm success message
6. Check Netlify dashboard (app.netlify.com → site → Forms → tasting-log) for the submission

### Pull verification (desktop)
1. Run `python3 generate_dashboard.py --pull-forms`
2. Confirm the submission appears in `wines.json` under `consumed` with `adhoc: true`
3. Confirm `netlify_forms_state.json` was written with a timestamp
4. Run again immediately → confirm "0 new submissions" (no duplicates)

### Checklist
- [ ] `log.html` loads at `/log.html` on Netlify
- [ ] Scan fills producer, wine, vintage, country, style + hidden fields
- [ ] API key persists across page reloads (localStorage)
- [ ] Submit works without page redirect
- [ ] Success message shown after submit
- [ ] Submit failure saves draft to localStorage; page reload restores it
- [ ] Submission visible in Netlify Forms dashboard
- [ ] Submission includes hidden scan fields when scanned
- [ ] `--pull-forms` converts submission to ad-hoc consumed entry in wines.json
- [ ] Scan-populated fields (varietal, score, etc.) appear in the consumed entry
- [ ] Re-running `--pull-forms` does not duplicate entries (submission ID check)
- [ ] Deleting state file + re-running doesn't duplicate (secondary field-match check)
- [ ] `--sync` and `--pull-forms` can be combined in one command
- [ ] Deploy includes pulled entries (execution order is correct)

---

## Implementation notes

- The Netlify API token and site ID are already in `netlify.env` — reuse `_load_netlify_env()`
- Free tier Netlify Forms limit: 100 submissions/month. This is fine for tasting logs.
- The form page should link back to the main dashboard: a small "← View collection" link
  in the header pointing to `/`.
- The main dashboard's nav or overview could eventually link to `/log.html` as a
  "Log a Tasting" shortcut — but that's a future enhancement, not part of this plan.
- `netlify_forms_state.json` should be added to `.gitignore` — it's local sync state,
  not project source.
