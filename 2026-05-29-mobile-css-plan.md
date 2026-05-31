# Mobile CSS Plan — Wine Cellar Dashboard

## Context

The dashboard is a single-file HTML app built from source files in this folder and deployed
to https://ga-wine-cellar.netlify.app via `generate_dashboard.py`. All styles live in
`dashboard.css`, which is inlined into the output HTML at build time. The Jinja2 template is
`template.html.j2`. The viewport meta tag (`width=device-width, initial-scale=1.0`) is
already present in the template — no changes needed there.

**Do not edit the generated HTML directly.** Edit `dashboard.css` (and `template.html.j2` if
structural changes are needed), then run:

```bash
cd "/path/to/86 Wine"
python3 generate_dashboard.py
```

The script archives any prior-day dashboard to `Archive/`, writes a new dated HTML, and
deploys to Netlify automatically (credentials are in `netlify.env`).

---

## Problems to fix

All issues were identified by auditing `dashboard.css`. There are no existing `@media` queries
in the file — everything below is additive. Target breakpoint: **600px** (covers phones in
portrait; tablets in landscape are already fine at desktop layout).

### 1. Nav bar overflow (highest priority — most visible breakage)

**Current:** `.nav-tabs` is a flex row of five tabs inside a fixed 56px nav bar. On a ~375px
phone the tabs overflow and clip.

**Fix options (pick one — preference is A):**

**A. Scrollable tab row** — simplest, preserves the existing layout:
```css
@media (max-width: 600px) {
  .nav-tabs {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .nav-tabs::-webkit-scrollbar { display: none; }
  .nav-tab {
    white-space: nowrap;
    padding: 0 14px;
    font-size: 11px;
  }
}
```

**B. Two-row nav** — logo row + full-width scrollable tab row below:
Requires a small template change to wrap tabs in their own `<div class="nav-tab-row">`,
then set `nav` to `flex-direction: column; height: auto` and give the tab row
`overflow-x: auto`. More work but cleaner on very small screens.

### 2. Stat grid (5 columns → 2-across)

**Current:** `.stat-grid { grid-template-columns: repeat(5, 1fr) }` — five cards in a row.
On mobile each card is ~60px wide, illegibly narrow.

**Fix:**
```css
@media (max-width: 600px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
```
Five cards in a 2-column grid gives 2 / 2 / 1 layout — the last card spanning alone is
acceptable. If it looks odd, a 3-column grid (giving 3 / 2) is an alternative.

### 3. Charts grid (side-by-side → stacked)

**Current:** `.charts-grid { grid-template-columns: 1fr 1fr }` — two charts side by side.

**Fix:**
```css
@media (max-width: 600px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }
}
```
`.chart-card.full` (the QPR scatter that already spans both columns) needs no change.

### 4. Edit drawer width

**Current:** `.drawer { width: 480px }` — wider than a 375px viewport, slides in off-screen.

**Fix:**
```css
@media (max-width: 600px) {
  .drawer {
    width: 100%;
  }
}
```

### 5. Drawer form grid (2-column → single column)

**Current:** `.form-grid { grid-template-columns: 1fr 1fr }` — two-column form layout inside
the drawer. Already cramped at 480px desktop width; unusable inside a full-width mobile drawer.

**Fix:**
```css
@media (max-width: 600px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
```

### 6. Gantt table horizontal scroll

**Current:** `.gantt-table { min-width: 760px }` — the table is wider than any phone screen.

**Gantt table:** Already handled — `template.html.j2` wraps the Gantt table in
`<div style="overflow-x:auto">` (line 88). No change needed here.

**QPR table and Drinking History table:** Both use `.qpr-table-wrap`, which currently has
`overflow: hidden` — this clips content instead of allowing scroll. Change to `overflow-x: auto`
in `dashboard.css` (not the media query — this is a fix for all viewports):
```css
.qpr-table-wrap {
  overflow-x: auto;   /* was: overflow: hidden */
}
```
This single change covers both the QPR Analysis tab and the Drinking History tab, since both
tables are wrapped in `.qpr-table-wrap`.

### 7. Wine Profile cards — no change needed

`.card-grid` already uses `repeat(auto-fill, minmax(340px, 1fr))`, which collapses to a
single column on screens narrower than ~356px. No mobile override required.

### 8. Section padding

**Current:** `.section { padding: 72px 24px 48px }` — 24px side padding is fine on mobile
but can be tightened slightly if needed. Low priority; address only if layout feels cramped
after other fixes.

---

## Suggested execution order

1. Add all `@media (max-width: 600px)` rules to the bottom of `dashboard.css`
2. Fix the Gantt/QPR table wrapper in `template.html.j2` if needed
3. Run `python3 generate_dashboard.py` to rebuild
4. Open the Netlify URL on an actual phone (or Chrome DevTools device emulation at 375px)
   and verify each fix in order: nav → stat grid → charts → drawer → tables
5. Iterate on anything that looks off before signing off

---

## Files to edit

| File | Change |
|------|--------|
| `dashboard.css` | Add `@media (max-width: 600px)` block at the bottom |
| `template.html.j2` | No changes needed (Gantt wrapper already has `overflow-x:auto`) |

**Do not edit** `generate_dashboard.py`, `wines.json`, or any generated HTML file.

---

## Verification

After rebuilding, check the following on a 375px-wide viewport:

- [ ] All five nav tabs are reachable (scrollable or otherwise)
- [ ] Stat cards are readable (2-column layout)
- [ ] Charts stack vertically
- [ ] Edit drawer fills the screen width
- [ ] Drawer form fields are full-width single column
- [ ] Drinking Windows table scrolls horizontally without clipping
- [ ] QPR table scrolls horizontally without clipping
- [ ] No horizontal overflow on the main page body (no sideways scroll on the page itself)
