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

import io
import json
import os
import re
import sys
import argparse
import zipfile
import urllib.request
import urllib.error
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
        html_consumed_map = {w['id']: w for w in html_consumed}
        new_adhoc_ids = {i for i in new_consumed_ids if html_consumed_map.get(i, {}).get('adhoc')}
        new_regular_consumed_ids = new_consumed_ids - new_adhoc_ids
        if new_regular_consumed_ids:
            print('  New consumed: ' + ', '.join(str(i) for i in sorted(new_regular_consumed_ids)))
        if new_adhoc_ids:
            print('  New tastings (ad-hoc, no data quality check needed): ' + ', '.join(str(i) for i in sorted(new_adhoc_ids)))
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
_parser.add_argument('--pull-forms', action='store_true',
                     help='Pull pending Netlify Forms tasting submissions into wines.json.')
_args = _parser.parse_args()

if _args.sync:
    _sync_from_html(_args.sync)

# ── Netlify helpers (used by both --pull-forms and deploy) ───────────────────
def _load_netlify_env():
    """Read NETLIFY_SITE_ID and NETLIFY_TOKEN from netlify.env in the project folder."""
    env_path = os.path.join(DIR, 'netlify.env')
    if not os.path.isfile(env_path):
        return None, None
    cfg = {}
    with open(env_path, 'r', encoding='utf-8') as _f:
        for line in _f:
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                key, _, val = line.partition('=')
                cfg[key.strip()] = val.strip()
    site_id = cfg.get('NETLIFY_SITE_ID', '')
    token = cfg.get('NETLIFY_TOKEN', '')
    return site_id, token

# ── pull Netlify Forms submissions (--pull-forms flag) ───────────────────────
def _pull_netlify_forms():
    """Fetch new Netlify Forms tasting submissions and append them to wines.json."""
    site_id, token = _load_netlify_env()
    if not site_id or not token or token == 'YOUR_TOKEN_HERE':
        print('--pull-forms: netlify.env missing or token not set — skipping.')
        return

    state_path = os.path.join(DIR, 'netlify_forms_state.json')

    # Step 1 — Load state
    if os.path.exists(state_path):
        with open(state_path, 'r', encoding='utf-8') as _f:
            _state = json.load(_f)
    else:
        _state = {}
    processed_ids = set(_state.get('processed_ids', []))

    headers = {'Authorization': 'Bearer ' + token}

    def _netlify_get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))

    # Step 2 — Discover form ID
    try:
        forms = _netlify_get('https://api.netlify.com/api/v1/sites/' + site_id + '/forms')
    except Exception as e:
        print('--pull-forms: could not list forms: ' + str(e))
        return
    form_id = None
    for frm in forms:
        if frm.get('name') == 'tasting-log':
            form_id = frm['id']
            break
    if not form_id:
        print('--pull-forms: "tasting-log" form not found yet (deploy log.html first).')
        return

    # Step 3 — Fetch submissions with pagination
    all_submissions = []
    page = 1
    while True:
        try:
            page_data = _netlify_get(
                'https://api.netlify.com/api/v1/forms/' + form_id + '/submissions?page=' + str(page)
            )
        except Exception as e:
            print('--pull-forms: error fetching submissions page ' + str(page) + ': ' + str(e))
            break
        if not page_data:
            break
        all_submissions.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1

    new_submissions = [s for s in all_submissions if s['id'] not in processed_ids]
    if not new_submissions:
        print('--pull-forms: 0 new submissions.')
        return

    # Load current wines.json
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as _f:
            _raw2 = json.load(_f)
        if isinstance(_raw2, list):
            _wines2, _consumed2 = _raw2, []
        else:
            _wines2 = _raw2.get('wines', [])
            _consumed2 = _raw2.get('consumed', [])
    else:
        _wines2, _consumed2 = [], []

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

    # Step 4 — Convert to consumed entries
    all_ids = [w['id'] for w in _wines2] + [c['id'] for c in _consumed2]
    next_id = (max(all_ids) if all_ids else 0) + 1

    # Secondary dedup: set of (producer, wine, vintage, removedDate) already in consumed
    existing_keys = set()
    for c in _consumed2:
        existing_keys.add((
            (c.get('producer') or '').lower(),
            (c.get('wine') or '').lower(),
            str(c.get('vintage', '')),
            str(c.get('removedDate', '')),
        ))

    new_entries = []
    new_processed_ids = []
    for sub in new_submissions:
        data = sub.get('data', {})
        removed_date = data.get('date') or sub.get('created_at', '')[:10]
        vintage_raw = _parse_int_or_none(data.get('vintage'))
        vintage = vintage_raw if vintage_raw is not None else 'NV'
        dedup_key = (
            (data.get('producer') or '').lower(),
            (data.get('wine') or '').lower(),
            str(vintage),
            str(removed_date),
        )
        if dedup_key in existing_keys:
            print('  Skipping duplicate: ' + str(data.get('producer')) + ' ' + str(data.get('wine')) + ' (' + str(removed_date) + ')')
            new_processed_ids.append(sub['id'])
            continue
        entry = {
            'id': next_id,
            'producer': data.get('producer', ''),
            'wine': data.get('wine', ''),
            'vintage': vintage,
            'country': data.get('country', ''),
            'style': data.get('style', 'red'),
            'qty': 1,
            'removedDate': removed_date,
            'myRating': data.get('myRating') or None,
            'myNote': data.get('myNote') or None,
            'adhoc': True,
            'purchasePrice': None,
            'purchasePriceEff': None,
            'qprRaw': None,
            'qprIndex': None,
            'varietal': data.get('varietal', ''),
            'appellation': data.get('appellation', ''),
            'region': data.get('region', ''),
            'score': _parse_int_or_none(data.get('score')),
            'marketPrice': _parse_float_or_none(data.get('marketPrice')),
            'drinkFrom': _parse_int_or_none(data.get('drinkFrom')),
            'drinkTo': _parse_int_or_none(data.get('drinkTo')),
            'pairings': _parse_json_or_none(data.get('pairings')),
            'summary': data.get('summary', ''),
        }
        new_entries.append(entry)
        new_processed_ids.append(sub['id'])
        existing_keys.add(dedup_key)
        next_id += 1

    if not new_entries:
        print('--pull-forms: all new submissions were duplicates — nothing added.')
    else:
        # Step 5 — Merge and write
        _consumed2.extend(new_entries)
        with open(JSON_PATH, 'w', encoding='utf-8') as _f:
            json.dump({'wines': _wines2, 'consumed': _consumed2}, _f, indent=2, ensure_ascii=False)
        print('Pulled ' + str(len(new_entries)) + ' tasting submission(s) from Netlify Forms.')
        for e in new_entries:
            print('  → ' + e['producer'] + ' ' + e['wine'] + ' (' + str(e['removedDate']) + ')')

    # Step 6 — Update state
    processed_ids.update(new_processed_ids)
    _state['processed_ids'] = sorted(processed_ids)
    with open(state_path, 'w', encoding='utf-8') as _f:
        json.dump(_state, _f, indent=2)

if _args.pull_forms:
    _pull_netlify_forms()

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

urgent_wines = [w for w in wines if w.get('drinkTo') and w['drinkTo'] <= CY]
urgent_count = len(urgent_wines)
urgent_examples = ', '.join(
    w['producer'] + ' ' + str(w['vintage']) for w in urgent_wines
) if urgent_wines else 'none'
if urgent_count == 0:
    urgent_note = 'No bottles are at or past the end of their drinking window.'
elif urgent_count == 1:
    urgent_note = ('One bottle is at the end of its drinking window this year ('
                   + urgent_examples + ') and should be opened soon.')
else:
    urgent_note = (str(urgent_count) + ' bottles are at the end of their drinking window this year ('
                   + urgent_examples + ') and should be opened soon.')

int_vintage_wines = [w for w in wines if isinstance(w['vintage'], int)]
oldest = min(int_vintage_wines, key=lambda w: w['vintage']) if int_vintage_wines else None
oldest_label = (oldest['producer'] + ' ' + oldest['wine'] + ' ' + str(oldest['vintage'])) if oldest else 'the oldest bottle'

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

# ── consumed split: bottles depleted from the cellar vs ad-hoc tastings ───────
def _group_stats(entries):
    rated = [c for c in entries if c.get('myRating')]
    dist = {}
    for c in rated:
        dist[c['myRating']] = dist.get(c['myRating'], 0) + 1
    parts = []
    for level in _sat_order:
        if dist.get(level, 0) > 0:
            parts.append(str(dist[level]) + ' ' + level)
    rating_str = ', '.join(parts) if parts else 'none rated yet'
    styles = {}
    for c in entries:
        styles[c['style']] = styles.get(c['style'], 0) + 1
    style_parts = []
    for s in ['red', 'white', 'sparkling', 'rosé', 'dessert', 'orange']:
        if styles.get(s, 0) > 0:
            style_parts.append(str(styles[s]) + ' ' + s)
    styles_str = ', '.join(style_parts)
    top = max(rated, key=lambda c: _sat_order.index(c['myRating'])) if rated else None
    return {
        'count': len(entries),
        'rated': len(rated),
        'rating_str': rating_str,
        'styles_str': styles_str,
        'top': top,
    }

depleted_stats = _group_stats([c for c in consumed if not c.get('adhoc')])
tasted_stats = _group_stats([c for c in consumed if c.get('adhoc')])

# ── curated narrative (update when collection changes significantly) ───────────
OVERVIEW_PARAS = [
    ('This is a {bottles}-bottle collection of real range and ambition &mdash; a highly curious taster\'s '
     'working library spanning {countries} countries and vintages from {vmin} to {vmax}. The French backbone is '
     'the broadest thread: Burgundy from village Marsannay and Fixin (Domaine Collotte) and '
     'Hautes-C&ocirc;tes de Nuits (JJ Archambaud) up through Premier Cru Nuits-Saint-Georges '
     '(Albert Bichot Ch&acirc;teau Gris Monopole, Esprit de Leflaive) and the storied Gevrey-Chambertin '
     'Clos Saint-Jacques 1er Cru (Louis Jadot); Bordeaux (Kirkland Pauillac and Saint-&Eacute;milion, plus a '
     '1988 Rieussec Sauternes); Alsace (Trimbach Cuv&eacute;e Fr&eacute;d&eacute;ric &Eacute;mile in magnum); '
     'the Loire (Clotilde Legrand Saumur Blanc and Thibaud Boudignon ros&eacute;); the Jura (Domaine Labet); '
     'a deep Beaujolais shelf (Domaine de la Madone and Pierre-Marie Chermette Brouilly); Bandol (Domaine Tempier); '
     'the Rh&ocirc;ne (Pasquiers Sablet and Berthet-Rayne Ch&acirc;teauneuf-du-Pape); Champagne (Laherte Fr&egrave;res, '
     'Tarlant, Caz&eacute;-Thibaut); and a Bugey Cerdon. '
     'Italy now runs seven SKUs &mdash; Cesari Amarone, Michele Chiarlo Barolo, Lamole di Lamole Chianti Classico, '
     'Campo al Mare Bolgheri, Cantina del Pino Barbera d\'Asti, and a Frank Cornelissen Etna pair (Munjebel and Susucaru). '
     'Germany has deepened to four: Weingut Keller (Rheinhessen), two Mosel Rieslings (Vollenweider, Weiser-K&uuml;nstler), '
     'and Wasenhaus Sp&auml;tburgunder (Baden). '
     'The American contingent is the largest single block: a deep Littorai program (Pinot Noir, Chardonnay, '
     'Chenin Blanc, and Vin Gris across the Sonoma Coast, Russian River, and Alexander Valley); serious Napa Cabernet '
     '(Heitz Martha\'s and Trailside, Nickel &amp; Nickel, Ashes &amp; Diamonds Cab Franc, Stags\' Leap 125th, '
     'Rutherford Ranch); V&eacute;rit&eacute; Le Diamant on the white side; California sparkling from Domaine Carneros, '
     'Ultramarine, Cruse, and Hammerling; Hartford old-vine Zinfandel; Enfield and Calstar from the broader California field; '
     'and Pacific Northwest coverage via Amity (Oregon), Ch&acirc;teau La Caille and Hiyu Wine Farm (Washington). '
     'Maryland appears twice &mdash; Black Ankle Syrah and a Sister Farms ros&eacute; &mdash; as a regional outlier. '
     'The rest of the world fills in around the edges: Don Melchor (Chile), Torbreck RunRig (Australia), '
     'Finca Adalgisa and Malma/Chacra (Argentina), Kirkland Rioja and Bodega Can Feliu (Spain), '
     'Tokaj Oremus (Hungary), and an Arnsdorfer ros&eacute; (Austria).'
    ).format(bottles=total_bottles, countries=country_count,
             vmin=(min(vintages) if vintages else ''), vmax=(max(vintages) if vintages else '')),

    ('A standout thread is the RNDC Wine Library &mdash; bottles acquired at ~$18 that include genuinely '
     'trophy-level wine: Torbreck RunRig (97 pts, $225 market), Don Melchor (96 pts, $150 market), and the '
     'Stags\' Leap 125th Anniversary Cabernet (95 pts, $59 market). Alongside direct buys like Heitz Martha\'s '
     'Vineyard (97 pts, $322 market, paid $223) and Heitz Trailside (93 pts, paid $63), the collection\'s market '
     'value sits well above its acquisition cost. '
     'Whites have become a real strength rather than an afterthought: V&eacute;rit&eacute; Le Diamant ($175/btl) and the '
     'Littorai Chardonnays anchor the top end, with Weingut Keller\'s Alte Reben Reserve, the Trimbach Fr&eacute;d&eacute;ric '
     '&Eacute;mile magnum, Domaine Labet\'s old-vine Jura Chardonnay, and two Mosel Rieslings adding range. On the sweet '
     'side, Tokaj Oremus Asz&uacute; 5 Puttonyos joins the 1988 Rieussec for genuine dessert depth.'),

    ('The collection still skews red ({reds} of {bottles} bottles) but carries solid sparkling depth ({sparkling} '
     'bottles across Champagne, Domaine Carneros, Cruse, Ultramarine, and Hammerling) and a genuine ros&eacute; shelf '
     '({rose} bottles &mdash; Domaine Tempier, Littorai Vin Gris, Thibaud Boudignon, Enfield Foot Tread, '
     'Bodega Can Feliu, Sister Farms, and Arnsdorfer). White coverage ({white} bottles) is no longer the weak spot '
     'it once was. On age, most bottles are 2018 or newer, but a handful of older anchors have arrived '
     '(Jadot Gevrey 2016, Trimbach 2012, Calstar 2015, Tarlant 2004, Rieussec 1988); the oldest bottle is {oldest}. '
     '{urgent_note}'
    ).format(
        reds=red_count, bottles=total_bottles, sparkling=sparkling_count,
        rose=style_counts.get('rosé', 0), white=white_count,
        oldest=oldest_label, urgent_note=urgent_note,
    ),
]

GAP_ITEMS = [
    ('Whites improved, but Burgundy and the dry Loire still thin',
     'Now ' + str(white_count) + ' white bottles, with real German Riesling depth (two Mosel growers plus '
     'Keller in Rheinhessen), the Trimbach Fr&eacute;d&eacute;ric &Eacute;mile magnum, the Littorai '
     'Chardonnays, Haven Chenin Blanc, Domaine Labet, and V&eacute;rit&eacute; Le Diamant. Still '
     'unrepresented: white Burgundy (Meursault, Puligny-Montrachet) and the dry Loire '
     '(Vouvray, Saveni&egrave;res).'),
    ('Northern Rh&ocirc;ne absent',
     'Hermitage, Cornas, C&ocirc;te-R&ocirc;tie, and Condrieu are all missing. The Southern Rh&ocirc;ne is '
     'covered (Berthet-Rayne Ch&acirc;teauneuf-du-Pape, Pasquiers Sablet), but the granite hills of the '
     'north remain a blank &mdash; a meaningful gap for a collection this geographically ambitious.'),
    ('Spain still light',
     'Two Spanish wines now &mdash; Kirkland Rioja Reserva and a Bodega Can Feliu Mallorca ros&eacute; &mdash; '
     'but Ribera del Duero, Priorat, and Bierzo remain absent, regions that would complement the existing '
     'Tempranillo, Menc&iacute;a, and Grenache threads and tend to offer strong QPR.'),
    ('Aged inventory improving but still limited',
     'Older anchors have arrived &mdash; Jadot Gevrey 2016, Trimbach 2012, Calstar 2015, plus the Tarlant 2004 '
     'and Rieussec 1988 (pre-2010: ' + pre2010_names + '). Still, most of the cellar is 2018 or newer, and '
     'ready-to-drink mid-tier reds from 2010&ndash;2016 (Burgundy, Bordeaux, Barolo, Rioja) remain scarce.'),
    ('Pacific Northwest selective',
     'Oregon has Amity; Washington has Ch&acirc;teau La Caille (Columbia Valley) and Hiyu Wine Farm. '
     'Willamette Valley benchmarks (Domaine Drouhin, Eyrie, Cristom, Ponzi) and Walla Walla / Columbia Valley '
     'Syrah are still absent.'),
    ('Almost all single-bottle positions',
     'Nearly every SKU is one bottle, which limits tracking a wine&rsquo;s evolution or serving multiples. '
     'Multi-bottle positions: ' + multi_btl_str + '.'),
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
    depleted_stats=depleted_stats,
    tasted_stats=tasted_stats,
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

# ── deploy to Netlify (if netlify.env is configured) ─────────────────────────
def _deploy_to_netlify(html_path):
    """Zip the generated HTML as index.html and deploy to Netlify via the zip-deploy API."""
    site_id, token = _load_netlify_env()
    if not site_id or not token:
        return  # netlify.env missing or incomplete — skip silently
    if token == 'YOUR_TOKEN_HERE':
        print('Netlify: token not set — edit netlify.env to add your personal access token.')
        return

    # Build zip in memory: index.html + log.html (if present) + _headers
    _headers_content = (
        '/index.html\n  Content-Type: text/html; charset=utf-8\n'
        '/log.html\n  Content-Type: text/html; charset=utf-8\n'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(html_path, 'index.html')
        zf.writestr('_headers', _headers_content)
        log_path = os.path.join(DIR, 'log.html')
        if os.path.exists(log_path):
            zf.write(log_path, 'log.html')
    buf.seek(0)
    payload = buf.read()

    url = 'https://api.netlify.com/api/v1/sites/' + site_id + '/deploys'
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            'Content-Type': 'application/zip',
            'Authorization': 'Bearer ' + token,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        # ssl_url is the stable site URL; deploy_ssl_url is the deploy-specific preview URL
        site_url = result.get('ssl_url') or result.get('url', '')
        state = result.get('state', '')
        print('Netlify: deployed — ' + (site_url or ('state=' + state)))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print('Netlify deploy failed (' + str(e.code) + '): ' + body[:200])
    except Exception as e:
        print('Netlify deploy error: ' + str(e))

_deploy_to_netlify(out_path)
