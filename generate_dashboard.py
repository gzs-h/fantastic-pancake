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

# ── render HTML via Jinja2 template ────────────────────────────────────────────
# All HTML structure lives in template.html.j2. This script supplies the
# computed values; Jinja handles the assembly.
from jinja2 import Environment, FileSystemLoader, select_autoescape

_env = Environment(
    loader=FileSystemLoader(DIR),
    autoescape=False,           # output is treated as raw HTML; values from
                                # OVERVIEW_PARAS / GAP_ITEMS contain HTML
                                # entities and tags that must pass through.
    keep_trailing_newline=True,
)
_template = _env.get_template('template.html.j2')

_html = _template.render(
    # stat-card values
    total_bottles=total_bottles,
    sku_count=sku_count,
    country_count=country_count,
    mv_str=mv_str,
    vintage_span=vintage_span,
    # narrative
    overview_paras=OVERVIEW_PARAS,
    gap_items=GAP_ITEMS,
    # drinking notes (conditional block)
    consumed_count=consumed_count,
    rated_count=rated_count,
    rating_dist_str=rating_dist_str,
    consumed_styles_str=consumed_styles_str,
    top_rated=top_rated,
    # QPR methodology
    priced_count=priced_count,
    total_count=total_count,
    # assets
    css=_css,
    js=_js,
    # data
    wines_json=wines_json,
    consumed_json=consumed_json,
    cy=CY,
)

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(_html)

print('Written: ' + out_path)
print('  ' + str(sku_count) + ' SKUs, ' + str(total_bottles) + ' bottles, ' + str(country_count) + ' countries')
print('  Market value: ' + mv_str)
print('  Vintage span: ' + vintage_span)
