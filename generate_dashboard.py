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

Curated narrative text lives in OVERVIEW_PARAS and EXPLORATION_ITEMS below.
Update those when the collection changes significantly.
"""

import argparse
import glob
import io
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

_eastern = ZoneInfo('America/New_York')
def _today():
    return datetime.now(_eastern).date()

def _now_iso():
    return datetime.now(_eastern).isoformat(timespec='seconds')

def _sku_key(e):
    """Normalized producer+wine+vintage key used to merge form-added bottles into an existing SKU."""
    return ((e.get('producer') or '').strip().lower(),
            (e.get('wine') or '').strip().lower(),
            str(e.get('vintage', '')).strip().lower())

# ── locate files ──────────────────────────────────────────────────────────────
DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(DIR, 'wines.json')
STATE_PATH = os.path.join(DIR, 'netlify_forms_state.json')

def _load_data():
    """Return (wines, consumed) from wines.json; a legacy flat array counts as wines-only."""
    if not os.path.exists(JSON_PATH):
        return [], []
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, list):
        return raw, []
    return raw.get('wines', []), raw.get('consumed', [])

def _save_data(wines, consumed):
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump({'wines': wines, 'consumed': consumed}, f, indent=2, ensure_ascii=False)

def _load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

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
    m_build = re.search(r'const BUILD_TS = "([^"]*)";', html)
    build_ts = m_build.group(1) if m_build else None

    json_wines, json_consumed = _load_data()

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

    # Warn if this export predates the last form pull: form-added entries the export
    # never saw would be dropped by the wholesale write below. Warning only — no retention.
    _st = _load_state()
    _last_pull, _merge_log = _st.get('last_pull_at'), _st.get('merge_log', [])
    if build_ts and _last_pull and _last_pull > build_ts:
        _html_ids = html_wine_ids | html_consumed_ids
        _at_risk = [e for e in json_wines + json_consumed
                    if e.get('source') == 'form' and e['id'] not in _html_ids
                    and (e.get('addedDate') or '') > build_ts]
        _at_risk_merges = [m for m in _merge_log if m.get('at', '') > build_ts]
        if _at_risk or _at_risk_merges:
            print('  WARNING: this export (built ' + build_ts + ') predates the last form pull ('
                  + _last_pull + '). Form changes it never saw will be reverted by this sync:')
            for e in _at_risk:
                print('    - dropped: id ' + str(e['id']) + ' ' + str(e.get('producer')) + ' ' + str(e.get('wine'))
                      + ' (' + str(e.get('vintage')) + ')' + (' [consumed]' if 'removedDate' in e else ''))
            for m in _at_risk_merges:
                print('    - qty +' + str(m['qty_added']) + ' undone: id ' + str(m['id']) + ' ' + m['label'])
            print('  Re-apply them after sync, or re-export from a freshly opened dashboard.')

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
    _save_data(html_wines, html_consumed)
    print('  Updated: ' + JSON_PATH)

# ── parse args ────────────────────────────────────────────────────────────────
_parser = argparse.ArgumentParser(description='Generate wine cellar dashboard HTML.')
_parser.add_argument('--sync', metavar='HTML_FILE',
                     help='Sync wines.json from an exported dashboard HTML before generating.')
_parser.add_argument('--pull-forms', action='store_true',
                     help='Pull pending Netlify Forms tasting submissions into wines.json.')
_parser.add_argument('--no-deploy', action='store_true',
                     help='Skip the Netlify deploy step (useful for data-quality review before publishing).')
_parser.add_argument('--only-if-new', action='store_true',
                     help='With --pull-forms: exit before regenerating/deploying if no new entries were pulled.')
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
    """Fetch new Netlify Forms submissions (tastings and bottles) and merge them into wines.json.
    Returns the number of entries added or merged (0 if nothing changed)."""
    site_id, token = _load_netlify_env()
    if not site_id or not token or token == 'YOUR_TOKEN_HERE':
        print('--pull-forms: netlify.env missing or token not set — skipping.')
        return 0

    # Step 1 — Load state
    _state = _load_state()
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
        return 0
    form_id = None
    for frm in forms:
        if frm.get('name') == 'tasting-log':
            form_id = frm['id']
            break
    if not form_id:
        print('--pull-forms: "tasting-log" form not found yet (deploy log.html first).')
        return 0

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
        return 0

    _wines2, _consumed2 = _load_data()

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

    sku_index = {_sku_key(w): w for w in _wines2}
    _cy = _today().year

    new_entries = []
    new_bottles = []      # new SKUs added to wines
    merged_bottles = []   # (existing entry, qty added)
    new_processed_ids = []
    for sub in new_submissions:
        data = sub.get('data', {})
        removed_date = data.get('date') or sub.get('created_at', '')[:10]
        vintage_raw = _parse_int_or_none(data.get('vintage'))
        vintage = vintage_raw if vintage_raw is not None else 'NV'

        # ── Bottle addition (entryType == "bottle"); absent/other → tasting ──
        if data.get('entryType') == 'bottle':
            qty = _parse_int_or_none(data.get('qty')) or 1
            purchase_price = _parse_float_or_none(data.get('purchasePrice'))
            candidate = {'producer': data.get('producer', ''), 'wine': data.get('wine', ''), 'vintage': vintage}
            existing = sku_index.get(_sku_key(candidate))
            if existing is not None:
                existing['qty'] = (existing.get('qty') or 0) + qty
                if purchase_price is not None and existing.get('purchasePrice') is None:
                    existing['purchasePrice'] = purchase_price
                    existing['purchasePriceEff'] = purchase_price
                elif purchase_price is not None and existing.get('purchasePrice') != purchase_price:
                    print('  Note: ' + existing['producer'] + ' ' + existing['wine'] + ' submitted at $'
                          + str(purchase_price) + ' — keeping existing purchase price $' + str(existing['purchasePrice']))
                merged_bottles.append((existing, qty))
            else:
                market_price = _parse_float_or_none(data.get('marketPrice'))
                pairings = _parse_json_or_none(data.get('pairings'))
                has_scan = bool(pairings)
                entry = {
                    'id': next_id,
                    'producer': data.get('producer', ''),
                    'wine': data.get('wine', ''),
                    'appellation': data.get('appellation', ''),
                    'country': data.get('country', ''),
                    'region': data.get('region', '') or data.get('country', ''),
                    'vintage': vintage,
                    'qty': qty,
                    'varietal': data.get('varietal', ''),
                    'style': data.get('style', 'red'),
                    'purchasePrice': purchase_price,
                    'marketPrice': market_price or purchase_price or 0,
                    'score': _parse_int_or_none(data.get('score')) or 88,
                    'drinkFrom': _parse_int_or_none(data.get('drinkFrom')) or _cy,
                    'drinkTo': _parse_int_or_none(data.get('drinkTo')) or (_cy + 5),
                    'pairings': pairings if has_scan else ['Pending enrichment'],
                    'summary': data.get('summary') or 'Added via mobile form — pending enrichment.',
                    'purchasePriceEff': purchase_price,
                    'qprRaw': None,
                    'qprIndex': None,
                    'pending': True,
                    'source': 'form',
                    'addedDate': _now_iso(),
                    'purchaseDate': removed_date,
                }
                _wines2.append(entry)
                sku_index[_sku_key(entry)] = entry
                new_bottles.append(entry)
                next_id += 1
            new_processed_ids.append(sub['id'])
            continue
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
            'source': 'form',
            'addedDate': _now_iso(),
        }
        new_entries.append(entry)
        new_processed_ids.append(sub['id'])
        existing_keys.add(dedup_key)
        next_id += 1

    changed = len(new_entries) + len(new_bottles) + len(merged_bottles)
    if not changed:
        print('--pull-forms: all new submissions were duplicates — nothing added.')
    else:
        # Step 5 — Merge and write
        _consumed2.extend(new_entries)
        _save_data(_wines2, _consumed2)
        if new_entries:
            print('Pulled ' + str(len(new_entries)) + ' tasting submission(s) from Netlify Forms.')
            for e in new_entries:
                print('  → ' + e['producer'] + ' ' + e['wine'] + ' (' + str(e['removedDate']) + ')')
        if new_bottles:
            print('Added ' + str(len(new_bottles)) + ' new bottle SKU(s) to the collection (pending enrichment).')
            for e in new_bottles:
                print('  + id ' + str(e['id']) + ': ' + e['producer'] + ' ' + e['wine'] + ' (' + str(e['vintage']) + ') ×' + str(e['qty']))
        if merged_bottles:
            print('Merged ' + str(len(merged_bottles)) + ' bottle submission(s) into existing SKUs.')
            for e, q in merged_bottles:
                print('  ↑ id ' + str(e['id']) + ': ' + e['producer'] + ' ' + e['wine'] + ' (' + str(e['vintage']) + ') +' + str(q) + ' → qty ' + str(e['qty']))
        _state['last_pull_at'] = _now_iso()
        _log = _state.get('merge_log', [])
        for e, q in merged_bottles:
            _log.append({'id': e['id'], 'qty_added': q, 'at': _state['last_pull_at'],
                         'label': e['producer'] + ' ' + e['wine'] + ' (' + str(e['vintage']) + ')'})
        _state['merge_log'] = _log[-50:]

    # Step 6 — Update state
    processed_ids.update(new_processed_ids)
    _state['processed_ids'] = sorted(processed_ids)
    with open(STATE_PATH, 'w', encoding='utf-8') as _f:
        json.dump(_state, _f, indent=2)
    return changed

if _args.pull_forms:
    _pulled = _pull_netlify_forms()
    if _args.only_if_new and not _pulled:
        print('--only-if-new: nothing new — skipping regenerate/deploy.')
        sys.exit(0)

wines, consumed = _load_data()

# ── current year (embedded as a JS constant, also used in stats below) ───────
# Per-wine derived fields (drinkStatus, qprRaw, qprIndex, purchasePriceEff) are
# computed in the browser at page load — see recomputeDerivedFields() in
# dashboard.js. The Python build step does not touch derived fields and does
# not write back to wines.json; wines.json is mutated only by --sync.
CY = _today().year

# ── compute stats ─────────────────────────────────────────────────────────────
total_bottles = sum(w['qty'] for w in wines)
sku_count = len(wines)
_country_counts = Counter(w['country'] for w in wines)
country_count = len(_country_counts)
france_count = _country_counts.get('France', 0)
usa_count = _country_counts.get('USA', 0)
italy_count = _country_counts.get('Italy', 0)
germany_count = _country_counts.get('Germany', 0)
market_value = sum(w['marketPrice'] * w['qty'] for w in wines)
mv_str = ('$' + str(round(market_value / 1000, 1)) + 'k') if market_value >= 1000 else ('$' + str(round(market_value)))
vintages = [w['vintage'] for w in wines if isinstance(w['vintage'], int)]
vintage_span = (str(min(vintages)) + '\u2013' + str(max(vintages))) if vintages else '\u2014'

style_counts = Counter()
for w in wines:
    style_counts[w['style']] += w['qty']
red_count = style_counts['red']
sparkling_count = style_counts['sparkling']
white_count = style_counts['white']
rose_count = style_counts['rosé']

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

multi_btl = sorted([w for w in wines if w['qty'] > 1], key=lambda w: -w['qty'])
multi_btl_str = ', '.join(
    w['producer'] + ' ' + w['wine'].split('(')[0].strip() + ' (' + str(w['qty']) + ' btls)' for w in multi_btl
) if multi_btl else 'none'

priced_count = sum(1 for w in wines if w.get('purchasePrice'))
total_count = len(wines)

_scored = [w['score'] for w in wines if w.get('score')]
avg_score = round(sum(_scored) / len(_scored), 1) if _scored else 0
_priced_eff = [w['purchasePriceEff'] for w in wines if w.get('purchasePriceEff')]
price_min = min(_priced_eff) if _priced_eff else 0
price_max = max(_priced_eff) if _priced_eff else 0
rndc_count = sum(1 for w in wines if w.get('purchasePriceEff') == 18)

# ── consumed stats ────────────────────────────────────────────────────────────
consumed_count = len(consumed)
_sat_order = ['faulty', 'poor', 'acceptable', 'good', 'very good', 'outstanding']
_style_order = ['red', 'white', 'sparkling', 'rosé', 'dessert', 'orange']

# ── consumed split: bottles depleted from the cellar vs ad-hoc tastings ───────
def _group_stats(entries):
    """Rating/style summary strings and top-rated entry for a slice of consumed."""
    rated = [c for c in entries if c.get('myRating')]
    dist, styles = {}, {}
    for c in rated:
        dist[c['myRating']] = dist.get(c['myRating'], 0) + 1
    for c in entries:
        styles[c['style']] = styles.get(c['style'], 0) + 1
    return {
        'count': len(entries),
        'rated': len(rated),
        'rating_str': ', '.join(str(dist[l]) + ' ' + l for l in _sat_order if dist.get(l)) or 'none rated yet',
        'styles_str': ', '.join(str(styles[s]) + ' ' + s for s in _style_order if styles.get(s)),
        'top': max(rated, key=lambda c: _sat_order.index(c['myRating'])) if rated else None,
    }

depleted_stats = _group_stats([c for c in consumed if not c.get('adhoc')])
tasted_stats = _group_stats([c for c in consumed if c.get('adhoc')])

# ── Worth Restocking ──────────────────────────────────────────────────────────
# Fully computed: a wine qualifies if (1) it is NOT in the current active
# collection, (2) it HAS been consumed/tasted before (regular or ad-hoc), and
# (3) it was rated 'very good' or 'outstanding' ('good' deliberately excluded —
# the bar for the collection is higher than everyday drinking).
# Matching normalizes producer+wine (lowercase, strip non-alphanumeric) so
# punctuation variants ('Riesling "RR"' vs 'Riesling RR') don't break it.
def _norm_key(e):
    s = str(e.get('producer', '')) + ' ' + str(e.get('wine', ''))
    return re.sub(r'[^a-z0-9]', '', s.lower())

_active_keys = set(_norm_key(w) for w in wines)
_HIGH = ('very good', 'outstanding')

# Rolling window: only depletions from the last ~6 months qualify. Un-acted-on
# candidates age out, keeping the list a *current* shopping aid.
_restock_cutoff = (_today() - timedelta(days=183)).strftime('%Y-%m-%d')

# (wine, vintage) pairs ever depleted from the cellar (any rating). Vintage-
# aware on purpose: a full-bottle verdict only supersedes pours of the SAME
# vintage (Keller RR: the 2025 bottle's 'good' doesn't silence the 2022 pour's
# 'very good'). The active-collection exclusion stays vintage-blind so that
# re-buying any vintage still counts as acting on a candidate.
_depletion_keys = set((_norm_key(c), str(c.get('vintage')))
                      for c in consumed if not c.get('adhoc'))

_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
           'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _mk_item(c, times=1):
    date = c.get('removedDate') or ''
    if date:
        _y, _m = date.split('-')[0], date.split('-')[1]
        date_label = _months[int(_m) - 1] + ' ’' + _y[2:]
    else:
        date_label = '—'
    return {
        'producer': c.get('producer', ''),
        'wine': c.get('wine', ''),
        'vintage': c.get('vintage') if not isinstance(c.get('vintage'), str) else 'NV',
        'rating': c.get('myRating', ''),
        'date_label': date_label,
        'times': times,
        'context': ' · '.join(x for x in [
            c.get('subRegion') or c.get('region') or None,
            c.get('tier') or None,
            c.get('varietal') or None,
        ] if x),
        'note': (c.get('myNote') or '').strip().replace('\n', '<br>'),
    }


# ── main list: depletion rows only, judged on their OWN rating ───────────────
# A pour (adhoc row) never qualifies a wine for restocking, and never overrides
# a lukewarm full-bottle verdict (e.g. Keller RR: pour 'very good', owned
# bottle 'good' → not restock-worthy).
_restock_by_key = {}
for c in consumed:
    if c.get('adhoc'):
        continue
    if c.get('myRating') not in _HIGH:
        continue
    if (c.get('removedDate') or '') < _restock_cutoff:
        continue
    k = _norm_key(c)
    if k in _active_keys:
        continue
    slot = _restock_by_key.get(k)
    if slot is None:
        _restock_by_key[k] = {'entry': c, 'times': 1, 'date': c.get('removedDate') or ''}
    else:
        slot['times'] += 1
        if (c.get('removedDate') or '') > slot['date']:
            slot['entry'] = c
            slot['date'] = c.get('removedDate') or ''

restock_items = [_mk_item(s['entry'], s['times'])
                 for s in sorted(_restock_by_key.values(),
                                 key=lambda s: s['date'], reverse=True)]

# ── secondary list: tasted (ad-hoc) very good+, never stocked ────────────────
# Outstanding pours are shown inline and exempt from the window (rare,
# high-signal); very-good pours collapse behind a toggle and age out with the
# same 6-month window as the main list.
_tasted_best = {}
for c in consumed:
    if not c.get('adhoc') or c.get('myRating') not in _HIGH:
        continue
    k = _norm_key(c)
    if k in _active_keys or (k, str(c.get('vintage'))) in _depletion_keys:
        continue
    prev = _tasted_best.get(k)
    if prev is None or (
        (_sat_order.index(c['myRating']), c.get('removedDate') or '')
        > (_sat_order.index(prev['myRating']), prev.get('removedDate') or '')
    ):
        _tasted_best[k] = c

tasted_outstanding = []
tasted_vg = []
for c in sorted(_tasted_best.values(),
                key=lambda c: c.get('removedDate') or '', reverse=True):
    if c['myRating'] == 'outstanding':
        tasted_outstanding.append(_mk_item(c))
    elif (c.get('removedDate') or '') >= _restock_cutoff:
        tasted_vg.append(_mk_item(c))

# Palate-verified active SKUs: active wines whose producer+wine appears in the
# drinking history in any form (used in the Overview value paragraph).
_consumed_keys = set(_norm_key(c) for c in consumed)
verified_count = len([w for w in wines if _norm_key(w) in _consumed_keys])

# ── curated narrative (update when collection changes significantly) ───────────
def _fmt_price(v):
    """Render a price without a trailing .0 but with cents when they exist."""
    return ('%d' % v) if float(v) == int(v) else ('%.2f' % v)

OVERVIEW_PARAS = [
    ('The collection sits at {sku} SKUs ({bottles} bottles) across {countries} countries, with vintages '
     'spanning {vmin}&ndash;{vmax}. France ({france}) and the U.S. ({usa}) still form the backbone, but the '
     'shape has changed: Burgundy is now the largest single region at 19 SKUs, and the September harvest trip '
     'is written all over it &mdash; six Domaine Collotte bottlings anchored in Marsannay (Blanc, Ros&eacute;, '
     'Le Boivin, Champs Salomon) sitting beneath a Premier Cru spine that runs Chablis Mont&eacute;e de '
     'Tonnerre, Beaune Clos des Ursules, two Volnays, three Nuits-Saint-Georges and Gevrey-Chambertin Clos '
     'Saint-Jacques. The American side remains Napa and Sonoma Cabernet and Pinot Noir (Heitz, Littorai, '
     'V&eacute;rit&eacute;). Italy ({italy}) now stretches from Barolo to Etna; Germany ({germany}) is Keller '
     'and the Mosel. The newest footholds are the furthest afield yet &mdash; Hambledon\'s Hampshire chalk '
     'from England, and Env&iacute;nate\'s ungrafted List&aacute;n Blanco from Tenerife.'
    ).format(sku=sku_count, bottles=total_bottles, countries=country_count,
             vmin=(min(vintages) if vintages else ''), vmax=(max(vintages) if vintages else ''),
             france=france_count, usa=usa_count, italy=italy_count, germany=germany_count),

    ('Buying stays disciplined &mdash; {rndc} SKUs came from the RNDC Wine Library at $18 each, effective '
     'per-bottle cost runs ${pmin}&ndash;${pmax}, and the average critic score is {avg_score}. The caveat is '
     'unchanged, and the Burgundy build makes it sharper: only {verified} of {sku} active SKUs have a '
     'palate-verified counterpart in the drinking history, and the Premier Cru spine &mdash; the most '
     'expensive concentration in the cellar &mdash; is almost entirely unproven against this palate. What '
     'evidence exists is encouraging but thin: Jadot\'s 2004 Chapelle-Chambertin and Leroux\'s '
     'Savigny-l&egrave;s-Beaune both very good, Collotte\'s Cuv&eacute;e Vieilles Vignes merely good. Market '
     'price and critic score stay proxies until the cork comes out.'
    ).format(rndc=rndc_count, avg_score=avg_score,
             pmin=_fmt_price(price_min), pmax=_fmt_price(price_max),
             verified=verified_count, sku=sku_count),

    ('Style-wise the cellar still skews red ({reds} of {bottles} bottles), but sparkling ({sparkling}) is '
     'deeper than it looks &mdash; three Champagnes, three Domaine Carneros, an Ultramarine, a Bugey Cerdon '
     'and now an English Classic Cuv&eacute;e &mdash; alongside ros&eacute; ({rose}), white ({white}) and a '
     'small dessert corner. Most bottles are 2018 or newer; older anchors stay rare &mdash; a 1988 Rieussec, '
     'a 2004 Tarlant, a 2006 d\'Yquem and 2012s from Trimbach and Tondonia (oldest: {oldest}). Single bottles '
     'are still the rule, but multiples have doubled to six &mdash; {multi}. {urgent_note}'
    ).format(
        reds=red_count, bottles=total_bottles, sparkling=sparkling_count,
        rose=rose_count, white=white_count,
        oldest=oldest_label, multi=multi_btl_str, urgent_note=urgent_note,
    ),
]

# -- For Further Exploration ---------------------------------------------------
# Exploration status is measured by TASTING HISTORY (consumed, incl. ad-hoc
# Log Tasting entries), not by what sits on the shelf - owning an unopened
# bottle proves nothing about whether a region suits the palate. Each item is
# (name, status, evidence) where status is 'untouched' (zero tastings anywhere)
# or 'partial' (tasted, verdict unresolved). Hand-curated, but every evidence
# claim below was verified against wines.json - re-verify before editing.
# Last verified: 2026-09-18.
EXPLORATION_ITEMS = [
    ('Northern Rh&ocirc;ne', 'untouched',
     'Hermitage, Cornas, C&ocirc;te-R&ocirc;tie, Condrieu &mdash; no footprint anywhere; the two Southern '
     'Rh&ocirc;ne bottles (Sablet, Ch&acirc;teauneuf) don\'t answer for the north'),
    ('Portugal', 'untouched',
     'no Douro, D&atilde;o, Bairrada, or Vinho Verde has ever appeared in the collection or tasting log'),
    ('Nebbiolo', 'untouched',
     'one Barolo on the shelf (Chiarlo Tortoniano 2021), never opened; the entire Piedmont tasting record '
     'is two Barberas'),
    ('White Burgundy', 'untouched',
     'the only Chassagne-Montrachet in the drinking history is Bichot\'s red &mdash; and a Chablis Premier '
     'Cru, a Pernand-Vergelesses blanc and two Marsannay blancs now sit unopened; Meursault and Puligny '
     'untasted'),
    ('Spain beyond Rioja', 'untouched',
     'Ribera del Duero, Priorat, Bierzo &mdash; zero tastings anywhere; Env&iacute;nate\'s Canary List&aacute;n '
     'Blanco and a Mallorcan rosat are on the shelf, both untasted'),
    ('Washington', 'untouched',
     'two bottles on the shelf, zero ever tasted; Walla Walla Syrah has no footprint at all'),
    ('Rioja', 'partial',
     '3 tastings, all positive &mdash; 2&times; Kirkland Reserva (good) and Murrieta Castillo Ygay Blanco '
     'Gran Reserva 1986 (outstanding, ad-hoc pour) &middot; the one bottle owned, Tondonia Reserva 2012, '
     'is still untasted'),
    ('Loire beyond Saumur', 'partial',
     '4 tastings &mdash; Chidaine Montlouis &times;2 (Les Bournais good, Les Choisilles very good), Montcy '
     'Cour-Cheverny unrated, Boudignon Ros&eacute; de Loire acceptable &middot; Saveni&egrave;res Roche aux '
     'Moines now on hand, Vouvray untasted'),
    ('Oregon', 'partial',
     'six casual-tier tastings (best: Constant Crush Pinot Noir, very good) &middot; benchmarks '
     'Drouhin, Eyrie, Cristom untasted'),
]

# ── output path + versioning ──────────────────────────────────────────────────
# Rule: one active dashboard in the folder at a time.
#   - Same day as existing file  → overwrite in place (no archive)
#   - Newer day than existing    → move old file to Archive/, write new dated file
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
# Compact JSON; '</' is escaped so no string can close the inline <script>.
def _embed(data):
    return json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
wines_json = _embed(wines)
consumed_json = _embed(consumed)

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
_env = Environment(
    loader=FileSystemLoader(DIR),
    autoescape=False,           # output is treated as raw HTML; values from
                                # OVERVIEW_PARAS / EXPLORATION_ITEMS contain
                                # HTML entities and tags that must pass through.
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
    exploration_items=EXPLORATION_ITEMS,
    restock_items=restock_items,
    tasted_outstanding=tasted_outstanding,
    tasted_vg=tasted_vg,
    # drinking notes (conditional block)
    consumed_count=consumed_count,
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
    build_ts=_now_iso(),
    cy=CY,
)

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(_html)

print('Written: ' + out_path)
print('  ' + str(sku_count) + ' SKUs, ' + str(total_bottles) + ' bottles, ' + str(country_count) + ' countries')
print('  Market value: ' + mv_str)
print('  Vintage span: ' + vintage_span)

# ── deploy to Netlify (if netlify.env is configured) ─────────────────────────
_CELLAR_FIELDS = ['producer', 'wine', 'vintage', 'qty', 'style', 'country', 'region',
                  'subRegion', 'tier', 'varietal', 'score', 'drinkFrom', 'drinkTo',
                  'pairings', 'summary']

def _cellar_json():
    """Compact active-collection snapshot for chat queries (served at /cellar.json)."""
    return json.dumps({
        'generatedAt': _now_iso(),
        'wines': [{k: w.get(k) for k in _CELLAR_FIELDS} for w in wines],
    }, ensure_ascii=False, indent=1)

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
        zf.writestr('cellar.json', _cellar_json())
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

if not _args.no_deploy:
    _deploy_to_netlify(out_path)
else:
    print('Netlify: skipped (--no-deploy)')
