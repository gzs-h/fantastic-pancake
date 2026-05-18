#!/usr/bin/env python3
"""
generate_dashboard.py
Reads wines.json from this directory and writes YYYYMMDD_Wine Cellar Dashboard.html.

Usage (from 86 Wine folder):
    python3 generate_dashboard.py

Technical rules (read before editing):
  - NO f-strings: use .format() or % or concatenation (f-strings clash with JS ${} in output)
  - Emoji: use \\U0001F377 (8-digit escapes), not surrogate pairs
  - Inline style attributes: always close the quote before > => pattern is  '">'  not  '>'
      CORRECT:  p.append("+ '<td style=\"color:'+(x?'a':'b')+'\">'+val+'</td>'\\n")
      WRONG:    p.append("+ '<td style=\"color:'+(x?'a':'b')+'>'+val+'</td>'\\n")
  - Write output with open(path, 'w', encoding='utf-8')

Curated narrative text lives in OVERVIEW_PARAS and GAP_ITEMS below.
Update those when the collection changes significantly.
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

_eastern = ZoneInfo('America/New_York')
def _today():
    return datetime.now(_eastern).date()

# ── locate files ──────────────────────────────────────────────────────────────
DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(DIR, 'wines.json')

# ── sync from HTML (--sync flag) ─────────────────────────────────────────────
def _sync_from_html(html_path):
    """Extract WINES/CONSUMED from an exported HTML, diff against wines.json, write updated JSON."""
    if not os.path.isfile(html_path):
        sys.exit('ERROR: file not found: ' + html_path)
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Extract arrays — matches the format produced by this script and the browser exportHTML()
    m_wines = re.search(r'const WINES = (\[[\s\S]*?\]);\s*const CONSUMED', html)
    m_consumed = re.search(r'const CONSUMED = (\[[\s\S]*?\]);\s*', html)
    if not m_wines:
        sys.exit('ERROR: could not extract WINES array from ' + html_path)
    if not m_consumed:
        sys.exit('ERROR: could not extract CONSUMED array from ' + html_path)

    html_wines = json.loads(m_wines.group(1))
    html_consumed = json.loads(m_consumed.group(1))

    # Load current wines.json for diffing
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, list):
            json_wines, json_consumed = raw, []
        else:
            json_wines = raw.get('wines', [])
            json_consumed = raw.get('consumed', [])
    else:
        json_wines, json_consumed = [], []

    # Diff
    json_wine_ids = {w['id'] for w in json_wines}
    json_consumed_ids = {w['id'] for w in json_consumed}
    html_wine_ids = {w['id'] for w in html_wines}
    html_consumed_ids = {w['id'] for w in html_consumed}

    new_wine_ids = html_wine_ids - json_wine_ids - json_consumed_ids
    removed_ids = json_wine_ids - html_wine_ids  # moved to consumed or deleted
    new_consumed_ids = html_consumed_ids - json_consumed_ids

    # Qty changes (wines present in both)
    json_qty = {w['id']: w['qty'] for w in json_wines}
    qty_changes = []
    for w in html_wines:
        if w['id'] in json_wine_ids and w['qty'] != json_qty.get(w['id']):
            qty_changes.append((w['id'], json_qty[w['id']], w['qty']))

    # Report
    print('Sync: ' + html_path)
    if new_wine_ids:
        print('  New wines: ' + ', '.join(str(i) for i in sorted(new_wine_ids)))
    if new_consumed_ids:
        print('  New consumed: ' + ', '.join(str(i) for i in sorted(new_consumed_ids)))
    if removed_ids:
        moved = removed_ids & html_consumed_ids
        gone = removed_ids - html_consumed_ids
        if moved:
            print('  Moved to consumed: ' + ', '.join(str(i) for i in sorted(moved)))
        if gone:
            print('  Removed (not in consumed): ' + ', '.join(str(i) for i in sorted(gone)))
    if qty_changes:
        for wid, old, new in qty_changes:
            print('  Qty change id ' + str(wid) + ': ' + str(old) + ' -> ' + str(new))
    if not (new_wine_ids or new_consumed_ids or removed_ids or qty_changes):
        print('  No changes detected.')

    # ID collision check: IDs must be unique across both arrays
    all_ids = html_wine_ids | html_consumed_ids
    max_id = max(all_ids) if all_ids else 0
    seen = set()
    for w in html_consumed:
        seen.add(w['id'])
    for w in html_wines:
        if w['id'] in seen:
            old_id = w['id']
            max_id += 1
            w['id'] = max_id
            print('  ID collision: wine id ' + str(old_id) + ' reassigned to ' + str(max_id))
        seen.add(w['id'])

    # Preserve myRating/myNote from existing consumed entries (in case HTML lost them)
    existing_consumed_map = {c['id']: c for c in json_consumed}
    for c in html_consumed:
        if c['id'] in existing_consumed_map:
            prev = existing_consumed_map[c['id']]
            if 'myRating' not in c and 'myRating' in prev:
                c['myRating'] = prev['myRating']
            if 'myNote' not in c and 'myNote' in prev:
                c['myNote'] = prev['myNote']

    # Write updated wines.json
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump({'wines': html_wines, 'consumed': html_consumed}, f, indent=2, ensure_ascii=False)
    print('  Updated: ' + JSON_PATH)

# ── parse args ────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(description='Generate wine cellar dashboard HTML.')
_parser.add_argument('--sync', metavar='HTML_FILE',
                     help='Sync wines.json from an exported dashboard HTML before generating.')
_args = _parser.parse_args()

if _args.sync:
    _sync_from_html(_args.sync)

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    _raw = json.load(f)

# Support both flat array (legacy) and two-array format
if isinstance(_raw, list):
    wines = _raw
    consumed = []
else:
    wines = _raw.get('wines', [])
    consumed = _raw.get('consumed', [])

# ── current year (embedded as a JS constant, also used in stats below) ───────
# Per-wine derived fields (drinkStatus, qprRaw, qprIndex, purchasePriceEff) are
# computed in the browser at page load — see recomputeDerivedFields() in
# dashboard.js. The Python build step does not touch derived fields and does
# not write back to wines.json; wines.json is mutated only by --sync.
CY = _today().year

# ── compute stats ─────────────────────────────────────────────────────────────
total_bottles = sum(w['qty'] for w in wines)
sku_count = len(wines)
countries = sorted(set(w['country'] for w in wines))
country_count = len(countries)
market_value = sum(w['marketPrice'] * w['qty'] for w in wines)
mv_str = ('$' + str(round(market_value / 1000, 1)) + 'k') if market_value >= 1000 else ('$' + str(round(market_value)))
vintages = [w['vintage'] for w in wines if isinstance(w['vintage'], int)]
vintage_span = (str(min(vintages)) + '\u2013' + str(max(vintages))) if vintages else '\u2014'

style_counts = {}
for w in wines:
    style_counts[w['style']] = style_counts.get(w['style'], 0) + w['qty']
red_count = style_counts.get('red', 0)
sparkling_count = style_counts.get('sparkling', 0)
white_count = style_counts.get('white', 0)

late_wines = [w for w in wines if w.get('drinkTo') and w['drinkTo'] < CY]
late_count = len(late_wines)
late_wine_examples = ', '.join(
    w['producer'] + ' ' + str(w['vintage']) for w in late_wines
) if late_wines else 'none identified'

int_vintage_wines = [w for w in wines if isinstance(w['vintage'], int)]
oldest = min(int_vintage_wines, key=lambda w: w['vintage']) if int_vintage_wines else None
oldest_label = (oldest['wine'] + ' ' + str(oldest['vintage'])) if oldest else 'the oldest bottle'

pre2010 = sorted(
    [w for w in wines if isinstance(w['vintage'], int) and w['vintage'] < 2010],
    key=lambda w: w['vintage']
)
pre2010_names = ', '.join(w['producer'] + ' ' + str(w['vintage']) for w in pre2010) \
    if pre2010 else 'essentially none'

multi_btl = sorted([w for w in wines if w['qty'] > 1], key=lambda w: -w['qty'])
multi_btl_str = ', '.join(
    w['wine'].split('(')[0].strip() + ' (' + str(w['qty']) + ' btls)' for w in multi_btl
) if multi_btl else 'none'

priced_wines = [w for w in wines if w.get('purchasePrice')]
priced_count = len(priced_wines)
total_count = len(wines)

# ── consumed stats ────────────────────────────────────────────────────────────
consumed_count = len(consumed)
rated_consumed = [c for c in consumed if c.get('myRating')]
rated_count = len(rated_consumed)

_sat_order = ['faulty', 'poor', 'acceptable', 'good', 'very good', 'outstanding']
rating_dist = {}
for c in rated_consumed:
    r = c.get('myRating', '')
    rating_dist[r] = rating_dist.get(r, 0) + 1

# Build rating distribution string in SAT order
rating_parts = []
for level in _sat_order:
    n = rating_dist.get(level, 0)
    if n > 0:
        rating_parts.append(str(n) + ' ' + level)
rating_dist_str = ', '.join(rating_parts) if rating_parts else 'none rated yet'

# Top-rated bottle
top_rated = None
if rated_consumed:
    top_rated = max(rated_consumed, key=lambda c: _sat_order.index(c.get('myRating', 'faulty')))
top_rated_str = ''
if top_rated:
    top_rated_str = (top_rated['producer'] + ' ' + top_rated['wine'] + ' '
                     + str(top_rated['vintage']) + ' (' + top_rated['myRating'] + ')')

# Consumed styles
consumed_styles = {}
for c in consumed:
    consumed_styles[c['style']] = consumed_styles.get(c['style'], 0) + 1
consumed_style_parts = []
for s in ['red', 'white', 'sparkling', 'rosé', 'dessert', 'orange']:
    n = consumed_styles.get(s, 0)
    if n > 0:
        consumed_style_parts.append(str(n) + ' ' + s)
consumed_styles_str = ', '.join(consumed_style_parts) if consumed_style_parts else ''

# ── curated narrative (update when collection changes significantly) ───────────
OVERVIEW_PARAS = [
    ('This is a {bottles}-bottle collection of genuine range and ambition &mdash; a highly curious taster\'s '
     'working library spanning eight countries and five decades of vintages. The French backbone is broad: '
     'Burgundy from village-level Marsannay (Domaine Collotte) through Premier Cru Nuits-Saint-Georges '
     '(Albert Bichot, Esprit de Leflaive) and Grand Cru Gevrey-Chambertin (Louis Jadot Clos Saint-Jacques), '
     'Bordeaux (Kirkland value plays and a 1988 Rieussec), '
     'Alsace (Trimbach Cuvée Fr&eacute;d&eacute;ric Emile in magnum), Loire (Saumur Blanc, Cour-Cheverny), '
     'Jura (Domaine Labet), Beaujolais, Bandol, Ch&acirc;teauneuf-du-Pape, Provence, and a well-stocked '
     'Champagne shelf including Laherte Fr&egrave;res and Tarlant. '
     'The American contingent is equally serious: a deep Littorai program spanning Pinot Noir, Chardonnay, '
     'Chenin Blanc, and Vin Gris; weighty Napa Cabernet (Heitz Martha\'s, Heitz Trailside, Nickel &amp; Nickel, '
     'Ashes &amp; Diamonds); Ultramarine and Domaine Carneros on the sparkling side; and Pacific Northwest '
     'coverage via Amity, Ch&acirc;teau La Caille, Hiyu Wine Farm, and Fossil &amp; Fawn.'
    ).format(bottles=total_bottles),

    ('A standout thread is the RNDC Wine Library &mdash; bottles acquired at ~$18/btl that include '
     'genuinely trophy-level wine: Torbreck RunRig (97 pts, $244 market), Don Melchor (96 pts, $150 '
     'market), and Stags\' Leap 125th Anniversary Cabernet (95 pts, $58 market). These, alongside '
     'direct acquisitions such as Heitz Martha\'s Vineyard (97 pts, $318 market, paid $223) and '
     'Heitz Trailside (93 pts, paid $63), make the collection\'s market value considerably exceed '
     'its acquisition cost. '
     'V&eacute;rit&eacute; Le Diamant 2024 ($175/btl market) '
     'anchors the white wine side alongside the Littorai Chardonnays, Weingut Keller Alte Reben Reserve (Pinot Blanc/Chardonnay), '
     'and the Trimbach magnum. A Hungarian outlier &mdash; Tokaj Oremus Asz&uacute; 5 Puttonyos 2018 &mdash; '
     'adds dessert depth beyond the Sauternes.'),

    ('The collection skews heavily red ({reds} of {skus} SKUs) with solid sparkling depth ({sparkling} '
     'bottles across Champagne, Domaine Carneros, Cruse, Ultramarine, Hammerling, and Bugey Cerdon) '
     'and growing ros&eacute; coverage ({rose} bottles including Domaine Tempier, Clos Cibonne, Littorai Vin Gris, '
     'and Ultramarine Heintz). White coverage has strengthened but remains the thinnest category. '
     'Age balance deserves attention: {late} bottle{late_s} {late_are} past {late_their} drinking window '
     '({late_examples}). The oldest bottle &mdash; {oldest} &mdash; warrants priority.'
    ).format(
        reds=red_count, skus=sku_count, sparkling=sparkling_count,
        rose=style_counts.get('rosé', 0),
        late=late_count, late_s=('' if late_count == 1 else 's'),
        late_are=('is' if late_count == 1 else 'are'),
        late_their=('its' if late_count == 1 else 'their'),
        late_examples=late_wine_examples,
        oldest=oldest_label,
    ),
]

GAP_ITEMS = [
    ('Whites still the thinnest category',
     'Now ' + str(white_count) + ' white SKUs &mdash; up from earlier, with Littorai Chardonnays, '
     'Haven Chenin Blanc, Keller Alte Reben Reserve, Domaine Labet, Fossil &amp; Fawn, and V&eacute;rit&eacute; '
     'Le Diamant filling gaps. But white Burgundy (Meursault, Puligny-Montrachet) and Loire '
     '(Vouvray, Saveni&egrave;res) remain unrepresented.'),
    ('Northern Rh&ocirc;ne absent',
     'Hermitage, Cornas, Crozes-Hermitage, and Condrieu are missing &mdash; a meaningful gap for a '
     'collection this geographically ambitious. The Southern Rh&ocirc;ne has Ch&acirc;teauneuf '
     '(Berthet-Rayne) and Pasquiers Prebayon, but the North remains a blank.'),
    ('Spain completely absent',
     'No Rioja, Ribera del Duero, Priorat, or Bierzo &mdash; regions that complement the existing '
     'Menc&iacute;a and Grenache threads and typically offer strong QPR.'),
    ('Very limited aged inventory',
     'Pre-2010 bottles: ' + pre2010_names + '. Nearly all other wines are 2018 or newer. '
     'Mid-tier aged reds (2010&ndash;2015 Burgundy, Bordeaux, Barolo, or Rioja) for near-term '
     'drinking are largely absent.'),
    ('Pacific Northwest expanding but still selective',
     'Oregon now has Amity and Fossil &amp; Fawn; Washington has Ch&acirc;teau La Caille and '
     'Hiyu Wine Farm. But Willamette Valley heavyweights (Domaine Drouhin, Eyrie, Ponzi, Cristom) '
     'remain absent, as does any Columbia Valley Syrah.'),
    ('Almost exclusively single-bottle positions',
     'Nearly all SKUs are one bottle. Very limited ability to track evolution or serve multiples &mdash; '
     'multi-bottle positions: ' + multi_btl_str + '.'),
]

# ── output path + versioning ──────────────────────────────────────────────────
# Rule: one active dashboard in the folder at a time.
#   - Same day as existing file  → overwrite in place (no archive)
#   - Newer day than existing    → move old file to Archive/, write new dated file
import glob, shutil

today_str = _today().strftime('%Y%m%d')
out_path = os.path.join(DIR, today_str + '_Wine Cellar Dashboard.html')

existing = [f for f in glob.glob(os.path.join(DIR, '*_Wine Cellar Dashboard.html'))
            if os.path.basename(f) != os.path.basename(out_path)]
for old_file in existing:
    archive_dir = os.path.join(DIR, 'Archive')
    os.makedirs(archive_dir, exist_ok=True)
    shutil.move(old_file, os.path.join(archive_dir, os.path.basename(old_file)))
    print('Archived: ' + os.path.basename(old_file))

# ── embed WINES and CONSUMED arrays ──────────────────────────────────────────
wines_json = json.dumps(wines, ensure_ascii=False, indent=2)
consumed_json = json.dumps(consumed, ensure_ascii=False, indent=2)

# ── load external CSS and JS ──────────────────────────────────────────────────
# Stylesheet and dashboard logic live in their own files so they can be edited
# as proper CSS / JS (with syntax highlighting and linting) rather than as
# Python string literals. They are inlined into the output HTML at build time.
with open(os.path.join(DIR, 'dashboard.css'), 'r', encoding='utf-8') as _f:
    _css = _f.read()
with open(os.path.join(DIR, 'dashboard.js'), 'r', encoding='utf-8') as _f:
    _js = _f.read()

# ── build HTML ────────────────────────────────────────────────────────────────
p = []

p.append('<!DOCTYPE html>\n')
p.append('<html lang="en" data-theme="light">\n')
p.append('<head>\n')
p.append('<meta charset="UTF-8">\n')
p.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
p.append('<title>Wine Cellar Dashboard</title>\n')
p.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n')
p.append('<style>\n')
p.append(_css)
p.append('</style>\n')
p.append('</head>\n')
p.append('<body>\n')

# ── nav ───────────────────────────────────────────────────────────────────────
p.append('<nav>\n')
p.append('  <div class="nav-brand">&#9670; Cellar</div>\n')
p.append('  <div class="nav-tabs">\n')
p.append('    <div class="nav-tab active" onclick="show(\'overview\',this)">Overview</div>\n')
p.append('    <div class="nav-tab" onclick="show(\'windows\',this)">Drinking Windows</div>\n')
p.append('    <div class="nav-tab" onclick="show(\'profiles\',this)">Wine Profiles</div>\n')
p.append('    <div class="nav-tab" onclick="show(\'qpr\',this)">QPR Analysis</div>\n')
p.append('    <div class="nav-tab" onclick="show(\'history\',this)">Drinking History</div>\n')
p.append('  </div>\n')
p.append('  <div class="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">\n')
p.append('    <span class="theme-toggle-label" id="themeLabel">Dark</span>\n')
p.append('    <div class="toggle-pill"><div class="toggle-knob" id="toggleKnob">\U0001F319</div></div>\n')
p.append('  </div>\n')
p.append('  <button class="edit-btn scan-nav" onclick="openScanDrawer()">&#128247;&nbsp;Scan Label</button>\n')
p.append('  <button class="edit-btn" onclick="openDrawer()">&#9998;&nbsp;Edit</button>\n')
p.append('</nav>\n\n')

# ── overview ──────────────────────────────────────────────────────────────────
p.append('<!-- OVERVIEW -->\n')
p.append('<div id="overview" class="section active">\n')
p.append('  <div class="stat-grid">\n')
p.append('    <div class="stat-card"><div class="stat-val">' + str(total_bottles) + '</div><div class="stat-label">Bottles</div></div>\n')
p.append('    <div class="stat-card"><div class="stat-val">' + str(sku_count) + '</div><div class="stat-label">SKUs</div></div>\n')
p.append('    <div class="stat-card"><div class="stat-val">' + str(country_count) + '</div><div class="stat-label">Countries</div></div>\n')
p.append('    <div class="stat-card"><div class="stat-val">' + mv_str + '</div><div class="stat-label">Market Value</div></div>\n')
p.append('    <div class="stat-card"><div class="stat-val">' + vintage_span + '</div><div class="stat-label">Vintage Span</div></div>\n')
p.append('  </div>\n')
p.append('  <div class="narrative">\n')
p.append('    <h2>Collection Overview</h2>\n')
for i, para in enumerate(OVERVIEW_PARAS):
    style = ' style="margin-top:10px"' if i > 0 else ''
    p.append('    <p' + style + '>' + para + '</p>\n')
p.append('  </div>\n')
p.append('  <div class="charts-grid">\n')
p.append('    <div class="chart-card"><div class="chart-title">Geographic Distribution (bottles)</div><canvas id="countryChart"></canvas></div>\n')
p.append('    <div class="chart-card"><div class="chart-title">Style Distribution</div><canvas id="styleChart"></canvas></div>\n')
p.append('    <div class="chart-card full"><div class="chart-title">Varietal Breakdown</div><canvas id="varietalChart"></canvas></div>\n')
p.append('  </div>\n')
p.append('  <div class="chart-card" style="margin-bottom:0">\n')
p.append('    <div class="chart-title">Collection Gaps &mdash; Neutral Assessment</div>\n')
p.append('    <div style="margin-top:4px">\n')
for label, text in GAP_ITEMS:
    p.append('      <div class="gap-item"><span class="gap-label">' + label + '</span>' + text + '</div>\n')
p.append('    </div>\n')
p.append('  </div>\n')

# ── drinking notes (mechanically generated from consumed array) ──────────────
if consumed_count > 0:
    p.append('  <div class="narrative" style="margin-top:20px">\n')
    p.append('    <h2>Drinking Notes</h2>\n')
    dn_line1 = (str(consumed_count) + ' bottle' + ('' if consumed_count == 1 else 's')
                + ' consumed so far')
    if rated_count > 0:
        dn_line1 += (', ' + str(rated_count) + ' rated: ' + rating_dist_str + '.')
    else:
        dn_line1 += '.'
    p.append('    <p>' + dn_line1 + '</p>\n')
    if consumed_styles_str:
        p.append('    <p style="margin-top:8px">Styles explored: ' + consumed_styles_str + '.</p>\n')
    if top_rated:
        p.append('    <p style="margin-top:8px">Highest-rated consumption: '
                 + top_rated['producer'] + ' &mdash; ' + top_rated['wine'] + ' '
                 + str(top_rated['vintage']) + ' ('
                 + top_rated['myRating'] + ').</p>\n')
    p.append('  </div>\n')

p.append('</div>\n\n')

# ── drinking windows ──────────────────────────────────────────────────────────
p.append('<!-- DRINKING WINDOWS -->\n')
p.append('<div id="windows" class="section">\n')
p.append('  <div class="gantt-controls">\n')
p.append('    <div class="gantt-legend">\n')
p.append('      <div class="legend-item"><div class="legend-dot" style="background:#e05050"></div>Past window</div>\n')
p.append('      <div class="legend-item"><div class="legend-dot" style="background:#e07830"></div>Open urgently</div>\n')
p.append('      <div class="legend-item"><div class="legend-dot" style="background:#4caf7a"></div>Drink now</div>\n')
p.append('      <div class="legend-item"><div class="legend-dot" style="background:#5090c8"></div>Open in 1&ndash;2 yrs</div>\n')
p.append('      <div class="legend-item"><div class="legend-dot" style="background:#7a6a7a"></div>Needs time (3+ yrs)</div>\n')
p.append('    </div>\n')
p.append('    <select id="wSort" onchange="renderWindows()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:4px;font-size:12px;font-family:Georgia,serif">\n')
p.append('      <option value="status">Sort by urgency</option>\n')
p.append('      <option value="vintage">Sort by vintage</option>\n')
p.append('      <option value="country">Sort by country</option>\n')
p.append('      <option value="style">Sort by style</option>\n')
p.append('    </select>\n')
p.append('  </div>\n')
p.append('  <div style="overflow-x:auto">\n')
p.append('    <table class="gantt-table">\n')
p.append('      <thead><tr>\n')
p.append('        <th style="width:220px">Wine</th>\n')
p.append('        <th style="width:68px">Vintage</th>\n')
p.append('        <th style="width:80px">Country</th>\n')
p.append('        <th style="width:96px">Status</th>\n')
p.append('        <th>Drinking Window (2000 &mdash; 2048)</th>\n')
p.append('      </tr></thead>\n')
p.append('      <tbody id="wBody"></tbody>\n')
p.append('    </table>\n')
p.append('  </div>\n')
p.append('</div>\n\n')

# ── profiles ──────────────────────────────────────────────────────────────────
p.append('<!-- PROFILES -->\n')
p.append('<div id="profiles" class="section">\n')
p.append('  <div class="filter-bar">\n')
p.append('    <div class="filter-group"><label>Search</label><input type="text" id="sSearch" placeholder="Producer, wine, region&hellip;" style="width:200px" oninput="renderProfiles()"></div>\n')
p.append('    <div class="filter-group"><label>Style</label>\n')
p.append('      <select id="sStyle" onchange="renderProfiles()">\n')
p.append('        <option value="">All</option><option value="red">Red</option><option value="white">White</option>\n')
p.append('        <option value="sparkling">Sparkling</option><option value="ros&eacute;">Ros&eacute;</option>\n')
p.append('        <option value="dessert">Dessert</option><option value="orange">Orange</option>\n')
p.append('      </select>\n')
p.append('    </div>\n')
p.append('    <div class="filter-group"><label>Country</label>\n')
p.append('      <select id="sCountry" onchange="renderProfiles()">\n')
p.append('        <option value="">All</option><option value="France">France</option><option value="USA">USA</option>\n')
p.append('        <option value="Italy">Italy</option><option value="Germany">Germany</option>\n')
p.append('        <option value="Argentina">Argentina</option><option value="Chile">Chile</option><option value="Australia">Australia</option>\n')
p.append('      </select>\n')
p.append('    </div>\n')
p.append('    <div class="filter-group"><label>Status</label>\n')
p.append('      <select id="sStatus" onchange="renderProfiles()">\n')
p.append('        <option value="">All</option><option value="past">Past window</option><option value="urgent">Open urgently</option>\n')
p.append('        <option value="now">Drink now</option><option value="soon">Open soon</option><option value="wait">Needs time</option>\n')
p.append('      </select>\n')
p.append('    </div>\n')
p.append('    <div class="res-count" id="resCount"></div>\n')
p.append('  </div>\n')
p.append('  <div class="card-grid" id="cardGrid"></div>\n')
p.append('</div>\n\n')

# ── QPR ───────────────────────────────────────────────────────────────────────
p.append('<!-- QPR -->\n')
p.append('<div id="qpr" class="section">\n')
p.append('  <div class="narrative" style="margin-bottom:20px">\n')
p.append('    <h2>QPR Methodology</h2>\n')
p.append('    <p>QPR Index (1&ndash;10) = <em>(critic score) &divide; (purchase price paid)</em>, normalized across wines where a purchase price was recorded. ' + str(priced_count) + ' of ' + str(total_count) + ' wines have a recorded price and appear below; the remainder are excluded rather than estimated. RNDC Wine Library bottles acquired at ~$18 dominate the top rankings. Bubble size reflects discount to market (larger = bought further below market price).</p>\n')
p.append('  </div>\n')
p.append('  <div class="chart-card" style="margin-bottom:20px">\n')
p.append('    <div class="chart-title">Score vs. Purchase Price &mdash; hover for details</div>\n')
p.append('    <canvas id="qprScatter" style="max-height:380px"></canvas>\n')
p.append('  </div>\n')
p.append('  <div class="qpr-table-wrap">\n')
p.append('    <table class="qpr-table">\n')
p.append('      <thead><tr>\n')
p.append('        <th>Wine</th><th>Vintage</th><th>Score</th><th>Paid</th><th>Market</th><th>Discount</th><th>QPR</th>\n')
p.append('      </tr></thead>\n')
p.append('      <tbody id="qprBody"></tbody>\n')
p.append('    </table>\n')
p.append('  </div>\n')
p.append('</div>\n\n')

# ── drinking history ─────────────────────────────────────────────────────────
p.append('<!-- DRINKING HISTORY -->\n')
p.append('<div id="history" class="section">\n')
p.append('  <div class="narrative" style="margin-bottom:20px">\n')
p.append('    <h2>Drinking History</h2>\n')
p.append('    <p>Wines removed from the collection, recorded in order of consumption. Date reflects when the bottle was logged as consumed in the dashboard.</p>\n')
p.append('    <p style="margin-top:8px;font-size:13px;color:var(--muted)">Ratings use the WSET SAT quality scale (faulty through outstanding), weighing intensity, complexity, balance, finish, and typicity.</p>\n')
p.append('  </div>\n')
p.append('  <div id="historyEmpty" style="display:none;color:var(--muted);font-size:14px;padding:20px 0">No bottles consumed yet.</div>\n')
p.append('  <div class="qpr-table-wrap" id="historyWrap">\n')
p.append('    <table class="qpr-table">\n')
p.append('      <thead><tr>\n')
p.append('        <th>Date Consumed</th><th>Wine</th><th>Vintage</th><th>Style</th><th>Score</th><th>My Rating</th>\n')
p.append('      </tr></thead>\n')
p.append('      <tbody id="historyBody"></tbody>\n')
p.append('    </table>\n')
p.append('  </div>\n')
p.append('</div>\n\n')

# ── rating modal ─────────────────────────────────────────────────────────────
p.append('<!-- RATING MODAL -->\n')
p.append('<div class="rate-overlay" id="rateOverlay">\n')
p.append('  <div class="rate-dialog">\n')
p.append('    <div class="rate-title">Rate This Wine</div>\n')
p.append('    <div class="rate-wine-name" id="rateWineName"></div>\n')
p.append('    <div class="rate-section-label">Quality Assessment (WSET SAT)</div>\n')
p.append('    <div class="rate-btns" id="rateBtns">\n')
p.append('      <button class="rate-btn" data-val="faulty">Faulty</button>\n')
p.append('      <button class="rate-btn" data-val="poor">Poor</button>\n')
p.append('      <button class="rate-btn" data-val="acceptable">Acceptable</button>\n')
p.append('      <button class="rate-btn" data-val="good">Good</button>\n')
p.append('      <button class="rate-btn" data-val="very good">Very Good</button>\n')
p.append('      <button class="rate-btn" data-val="outstanding">Outstanding</button>\n')
p.append('    </div>\n')
p.append('    <div class="rate-section-label">Tasting Note (optional)</div>\n')
p.append('    <textarea class="rate-note" id="rateNote" placeholder="Acidity, tannin, body, finish — what stood out?"></textarea>\n')
p.append('    <div class="rate-actions">\n')
p.append('      <button class="btn-secondary" id="rateCancelBtn">Cancel</button>\n')
p.append('      <button class="btn-primary" id="rateConfirmBtn">Confirm Removal</button>\n')
p.append('    </div>\n')
p.append('  </div>\n')
p.append('</div>\n\n')

# ── edit drawer ───────────────────────────────────────────────────────────────
p.append('<!-- EDIT DRAWER -->\n')
p.append('<div class="drawer-overlay" id="drawerOverlay" onclick="closeDrawer()"></div>\n')
p.append('<div class="drawer" id="editDrawer">\n')
p.append('  <div class="drawer-hdr">\n')
p.append('    <span class="drawer-title">&#9670; Edit Collection</span>\n')
p.append('    <button class="drawer-close" onclick="closeDrawer()">&#x2715;</button>\n')
p.append('  </div>\n')
p.append('  <div class="drawer-tabs">\n')
p.append('    <div class="drawer-tab active" onclick="switchEditTab(\'inventory\',this)">Inventory</div>\n')
p.append('    <div class="drawer-tab" onclick="switchEditTab(\'add\',this)">Add Wine</div>\n')
p.append('    <div class="drawer-tab" onclick="switchEditTab(\'export\',this)">Save &amp; Export</div>\n')
p.append('  </div>\n')
p.append('  <div class="drawer-body">\n')
p.append('    <div class="drawer-panel active" id="panel-inventory">\n')
p.append('      <input class="inv-search" type="text" id="invSearch" placeholder="Search wines&#8230;" oninput="renderInvList()">\n')
p.append('      <div class="inv-list" id="invList"></div>\n')
p.append('    </div>\n')
p.append('    <div class="drawer-panel" id="panel-add">\n')
p.append('      <button class="scan-btn-full" id="scanBtn" onclick="scanLabel()">&#128247;&nbsp;Scan Label</button>\n')
p.append('      <input type="file" id="scanInput" accept="image/*" capture="environment" style="display:none" onchange="handleScanFile(this)">\n')
p.append('      <div class="scan-status-line" id="scanStatus"></div>\n')
p.append('      <div id="keyArea" style="display:none">\n')
p.append('        <div class="key-area-inner">\n')
p.append('          <div class="key-row">\n')
p.append('            <input type="password" id="keyInput" placeholder="Paste Gemini API key\u2026">\n')
p.append('            <button class="btn-secondary" onclick="saveKey()" style="padding:5px 10px;font-size:11px">Save</button>\n')
p.append('            <button class="btn-secondary" onclick="clearKey()" style="padding:5px 10px;font-size:11px;color:#e05050">Clear</button>\n')
p.append('          </div>\n')
p.append('        </div>\n')
p.append('      </div>\n')
p.append('      <div class="scan-footer-row">\n')
p.append('        <span id="keyStatusLine" style="color:var(--muted)">\u2014</span>\n')
p.append('        <span class="key-link" onclick="toggleKeyArea()">&#9881;&nbsp;API key</span>\n')
p.append('      </div>\n')
p.append('      <hr class="scan-divider">\n')
p.append('      <div class="form-grid">\n')
p.append('        <div class="form-group"><label>Producer *</label><input type="text" id="f-producer" placeholder="e.g. Domaine Leflaive"></div>\n')
p.append('        <div class="form-group"><label>Wine Name *</label><input type="text" id="f-wine" placeholder="e.g. Puligny-Montrachet"></div>\n')
p.append('        <div class="form-group"><label>Appellation</label><input type="text" id="f-appellation" placeholder="e.g. Puligny-Montrachet"></div>\n')
p.append('        <div class="form-group"><label>Country *</label>\n')
p.append('          <select id="f-country">\n')
p.append('            <option value="">Select&#8230;</option>\n')
p.append('            <option>France</option><option>USA</option><option>Italy</option>\n')
p.append('            <option>Germany</option><option>Argentina</option><option>Chile</option>\n')
p.append('            <option>Australia</option><option>Spain</option><option>Other</option>\n')
p.append('          </select>\n')
p.append('        </div>\n')
p.append('        <div class="form-group"><label>Style *</label>\n')
p.append('          <select id="f-style">\n')
p.append('            <option value="">Select&#8230;</option>\n')
p.append('            <option value="red">Red</option><option value="white">White</option>\n')
p.append('            <option value="sparkling">Sparkling</option><option value="ros\u00e9">Ros\u00e9</option>\n')
p.append('            <option value="dessert">Dessert</option><option value="orange">Orange</option>\n')
p.append('          </select>\n')
p.append('        </div>\n')
p.append('        <div class="form-group"><label>Varietal</label><input type="text" id="f-varietal" placeholder="e.g. Chardonnay"></div>\n')
p.append('        <div class="form-group"><label>Vintage</label><input type="number" id="f-vintage" placeholder="e.g. 2019" min="1900" max="2030"></div>\n')
p.append('        <div class="form-group"><label>Quantity *</label><input type="number" id="f-qty" value="1" min="1" max="100"></div>\n')
p.append('        <div class="form-group"><label>Purchase Price ($)</label><input type="number" id="f-purchase" placeholder="what you paid" min="0" step="0.01"></div>\n')
p.append('        <div class="form-group"><label>Market Price ($)</label><input type="number" id="f-market" placeholder="current market" min="0" step="0.01"></div>\n')
p.append('        <div class="form-group"><label>Score (pts)</label><input type="number" id="f-score" placeholder="e.g. 92" min="50" max="100"></div>\n')
p.append('        <div class="form-group"><label>Region</label><input type="text" id="f-region" placeholder="e.g. Burgundy"></div>\n')
p.append('        <div class="form-group"><label>Drink From</label><input type="number" id="f-from" placeholder="e.g. 2024" min="2000" max="2060"></div>\n')
p.append('        <div class="form-group"><label>Drink To</label><input type="number" id="f-to" placeholder="e.g. 2032" min="2000" max="2060"></div>\n')
p.append('      </div>\n')
p.append('      <p class="add-note">Fields marked * are required. Pairings and tasting notes will show as <span class="pending-badge">pending enrichment</span> &#8212; bring this file back to Claude to complete them.</p>\n')
p.append('      <div style="display:flex;gap:8px;margin-top:16px">\n')
p.append('        <button class="btn-primary" onclick="addWine()">Add to Collection</button>\n')
p.append('        <button class="btn-secondary" onclick="clearAddForm()">Clear</button>\n')
p.append('      </div>\n')
p.append('      <div id="add-msg" style="margin-top:10px;font-size:12px;min-height:18px"></div>\n')
p.append('    </div>\n')
p.append('    <div class="drawer-panel" id="panel-export">\n')
p.append('      <div class="export-section">\n')
p.append('        <h3>Session Changes</h3>\n')
p.append('        <div class="change-log" id="changeLog"><span style="font-style:italic">No changes yet this session.</span></div>\n')
p.append('      </div>\n')
p.append('      <div class="export-section" style="margin-top:20px">\n')
p.append('        <h3>Save Dashboard</h3>\n')
p.append('        <p style="font-size:12px;color:var(--muted);margin-bottom:10px;line-height:1.55">Downloads an updated copy of this file with your changes baked in. Replace your existing file with the downloaded version.</p>\n')
p.append('        <button class="btn-primary" onclick="exportHTML()" style="width:100%">&#8595;&nbsp;Download Updated Dashboard (.html)</button>\n')
p.append('      </div>\n')
p.append('      <div class="export-section" style="margin-top:16px">\n')
p.append('        <h3>Export Data</h3>\n')
p.append('        <p style="font-size:12px;color:var(--muted);margin-bottom:10px;line-height:1.55">Portable data file for backup or for use in future Claude sessions.</p>\n')
p.append('        <button class="btn-secondary" onclick="exportJSON()" style="width:100%">&#8595;&nbsp;Download wines.json</button>\n')
p.append('      </div>\n')
p.append('    </div>\n')
p.append('  </div>\n')
p.append('</div>\n\n')

# ── JavaScript ────────────────────────────────────────────────────────────────
p.append('<script>\n')
p.append('const WINES = ')
p.append(wines_json)
p.append(';\n')
p.append('const CONSUMED = ')
p.append(consumed_json)
p.append(';\n')
p.append('const CY = ' + str(CY) + ';\n\n')

p.append(_js)
p.append('</script>\n')
p.append('<button class="scan-fab" onclick="openScanDrawer()" title="Scan wine label">&#128247;</button>\n')
p.append('</body>\n')
p.append('</html>\n')

# ── write output ──────────────────────────────────────────────────────────────
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(''.join(p))

print('Written: ' + out_path)
print('  ' + str(sku_count) + ' SKUs, ' + str(total_bottles) + ' bottles, ' + str(country_count) + ' countries')
print('  Market value: ' + mv_str)
print('  Vintage span: ' + vintage_span)
