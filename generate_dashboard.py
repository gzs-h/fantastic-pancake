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
from datetime import date

# ── locate files ──────────────────────────────────────────────────────────────
DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(DIR, 'wines.json')

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    wines = json.load(f)

# ── compute stats ─────────────────────────────────────────────────────────────
CY = date.today().year
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

past_count = sum(1 for w in wines if w.get('drinkStatus') == 'past')
urgent_count = sum(1 for w in wines if w.get('drinkStatus') == 'urgent')

# ── curated narrative (update when collection changes significantly) ───────────
OVERVIEW_PARAS = [
    ('This is a {bottles}-bottle collection of genuine range and ambition &mdash; but it reads less like a '
     'systematic cellar and more like a highly curious taster\'s working library. The backbone is French: '
     'Burgundy (Marsannay through Chapelle-Chambertin Grand Cru), Bordeaux (Kirkland value plays through a '
     '1988 Rieussec), Loire (excellent Chenin Blanc representation across Saumur, Montlouis, and '
     'Cour-Cheverny), Jura, Beaujolais, Bandol, and Rh&ocirc;ne. The American side is equally strong, '
     'anchored by a well-chosen clutch of Littorai Sonoma Coast wines plus serious Napa Cabernet (Heitz '
     'Martha\'s Vineyard, Heitz Trailside, Nickel &amp; Nickel, Spring Mountain Elivette).'
    ).format(bottles=total_bottles),

    ('Several bottles from the RNDC Wine Library &mdash; acquired at ~$18/btl &mdash; include genuinely '
     'iconic wines: Torbreck RunRig (97 pts, $244 market), Don Melchor (96 pts, $150 market), Heitz '
     'Martha\'s Vineyard (97 pts, $318 market). These make the collection\'s market value significantly '
     'exceed its acquisition cost. A 3-bottle position in V&eacute;rit&eacute; Le Diamant ($175/btl market) '
     'represents the largest white wine holding (~$525).'),

    ('The collection skews heavily red ({reds} of {skus} SKUs) with good sparkling coverage ({sparkling} '
     'bottles) but thinner white wine depth. Age balance is a mild concern: {past} wine{past_s} '
     '{past_are} past {past_their} window and {urgent} are urgent, including the 1988 Rieussec and the '
     '2004 Jadot Grand Cru. The oldest bottle &mdash; Spring Mountain Elivette 2001 (3L) &mdash; should '
     'be opened this year.'
    ).format(
        reds=red_count, skus=sku_count, sparkling=sparkling_count,
        past=past_count, past_s=('' if past_count == 1 else 's'),
        past_are=('is' if past_count == 1 else 'are'),
        past_their=('its' if past_count == 1 else 'their'),
        urgent=urgent_count,
    ),
]

GAP_ITEMS = [
    ('Whites underrepresented',
     'With only ' + str(white_count) + ' white SKUs vs. ' + str(red_count) + ' reds, an expansion into white '
     'Burgundy (Meursault, Puligny), Alsace, or more Loire (Vouvray, Saveni&egrave;res) would be natural.'),
    ('Northern Rh&ocirc;ne absent',
     'Hermitage, Cornas, Crozes-Hermitage, and Condrieu (Viognier) are missing &mdash; a gap for a collection '
     'this adventurous. The Southern Rh&ocirc;ne is represented but the North is a blank.'),
    ('Spain completely absent',
     'No Rioja, Ribera del Duero, Priorat, or Bierzo &mdash; regions that would complement the existing '
     'Menc&iacute;a presence (Hiyu) and offer excellent QPR.'),
    ('Very limited aged inventory',
     'Outside 1988 Rieussec, 2004 Jadot, 2004 Tarlant Champagne, and 2001 Spring Mountain, nearly all wines '
     'are 2018 or newer. No mid-tier aged reds (2010&ndash;2015 Burgundy, Bordeaux, Barolo) for near-term drinking.'),
    ('Oregon / Pacific Northwest thin',
     'Only two Washington bottles; Oregon (Willamette Valley Pinot Noir) is entirely absent despite being a '
     'natural complement to the Littorai program.'),
    ('Almost exclusively single-bottle positions',
     'Nearly all SKUs are one bottle. Very limited ability to track a wine\'s evolution, serve multiples, or '
     'compare vintages &mdash; except V&eacute;rit&eacute; Le Diamant (3), Madone Beaujolais (2), Hartford '
     'Zin (2 vintages), Littorai Wendling (2).'),
]

# ── output path + versioning ──────────────────────────────────────────────────
# Rule: one active dashboard in the folder at a time.
#   - Same day as existing file  → overwrite in place (no archive)
#   - Newer day than existing    → move old file to Archive/, write new dated file
import glob, shutil

today_str = date.today().strftime('%Y%m%d')
out_path = os.path.join(DIR, today_str + '_Wine Cellar Dashboard.html')

existing = [f for f in glob.glob(os.path.join(DIR, '*_Wine Cellar Dashboard.html'))
            if os.path.basename(f) != os.path.basename(out_path)]
for old_file in existing:
    archive_dir = os.path.join(DIR, 'Archive')
    os.makedirs(archive_dir, exist_ok=True)
    shutil.move(old_file, os.path.join(archive_dir, os.path.basename(old_file)))
    print('Archived: ' + os.path.basename(old_file))

# ── embed WINES array ─────────────────────────────────────────────────────────
wines_json = json.dumps(wines, ensure_ascii=False, indent=2)

# ── build HTML ────────────────────────────────────────────────────────────────
p = []

p.append('<!DOCTYPE html>\n')
p.append('<html lang="en" data-theme="dark">\n')
p.append('<head>\n')
p.append('<meta charset="UTF-8">\n')
p.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
p.append('<title>Wine Cellar Dashboard</title>\n')
p.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>\n')
p.append('<style>\n')
p.append("""  :root {
    --bg:#0f0a0e;--surface:#1a1118;--surface2:#231820;--border:#3a2535;
    --burgundy:#7c2d3f;--gold:#c9a84c;--gold-light:#e8c97a;--cream:#f0e6d3;
    --text:#e8ddd0;--muted:#9b8a7a;
    --past:#6a4a4a;--urgent:#e07830;--drinknow:#4caf7a;--soon:#5090c8;--wait:#7a6a7a;
  }
  /* \u2500\u2500 LIGHT MODE \u2500\u2500 */
  [data-theme="light"] {
    --bg:#f5ede0;--surface:#ffffff;--surface2:#ede3d5;--border:#d4c4b0;
    --burgundy:#7c2d3f;--gold:#8b5a1a;--gold-light:#6b3d0a;--cream:#2c1606;
    --text:#3a2010;--muted:#8a7060;
    --past:#c0392b;--urgent:#c95000;--drinknow:#1e7a42;--soon:#1a5c8a;--wait:#6a7a8a;
  }
  [data-theme="light"] body{background:var(--bg)}
  [data-theme="light"] nav{background:rgba(245,237,224,.97)}
  [data-theme="light"] .s-past{background:rgba(192,57,43,.1);color:#c0392b;border-color:#c0392b}
  [data-theme="light"] .s-urgent{background:rgba(201,80,0,.1);color:#c95000;border-color:#c95000}
  [data-theme="light"] .s-now{background:rgba(30,122,66,.1);color:#1e7a42;border-color:#1e7a42}
  [data-theme="light"] .s-soon{background:rgba(26,92,138,.1);color:#1a5c8a;border-color:#1a5c8a}
  [data-theme="light"] .s-wait{background:rgba(106,122,138,.15);color:#5a6a7a;border-color:#8a9aaa}
  [data-theme="light"] .q-hi{color:#1e7a42}
  [data-theme="light"] .q-mid{color:#8b5a1a}
  [data-theme="light"] .q-lo{color:var(--muted)}
  [data-theme="light"] .bar-track{background:rgba(212,196,176,.5)}
  [data-theme="light"] .bar-now{background:rgba(44,22,6,.35)}
  [data-theme="light"] .gantt-table th{background:var(--surface)}
  [data-theme="light"] .gantt-table tr:hover td{background:var(--surface2)}
  [data-theme="light"] .qpr-table tr:hover td{background:var(--surface2)}
  [data-theme="light"] .qpr-fill{background:var(--gold)}
  /* toggle button */
  .theme-toggle{
    margin-left:auto;display:flex;align-items:center;gap:8px;
    background:var(--surface2);border:1px solid var(--border);
    border-radius:20px;padding:4px 5px 4px 10px;cursor:pointer;
    transition:background .2s,border-color .2s;flex-shrink:0;
  }
  .theme-toggle:hover{border-color:var(--gold)}
  .theme-toggle-label{font-size:11px;letter-spacing:1px;font-variant:small-caps;color:var(--muted);transition:color .2s;user-select:none}
  .theme-toggle:hover .theme-toggle-label{color:var(--gold)}
  .toggle-pill{
    width:36px;height:20px;border-radius:10px;
    background:var(--border);position:relative;transition:background .25s;
  }
  [data-theme="light"] .toggle-pill{background:#c9a84c}
  .toggle-knob{
    position:absolute;top:2px;left:2px;width:16px;height:16px;
    border-radius:50%;background:#fff;transition:left .25s,background .25s;
    display:flex;align-items:center;justify-content:center;font-size:9px;
  }
  [data-theme="light"] .toggle-knob{left:18px}
  /* \u2500\u2500 EDIT DRAWER \u2500\u2500 */
  .edit-btn{margin-left:12px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:6px 14px;cursor:pointer;font-size:11px;letter-spacing:1px;font-variant:small-caps;color:var(--muted);transition:border-color .2s,color .2s;flex-shrink:0;display:flex;align-items:center;gap:6px;font-family:Georgia,serif}
  .edit-btn:hover{border-color:var(--gold);color:var(--gold)}
  .drawer-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:200;display:none}
  .drawer-overlay.open{display:block}
  .drawer{position:fixed;top:0;right:0;bottom:0;width:480px;background:var(--surface);border-left:1px solid var(--border);z-index:201;transform:translateX(100%);transition:transform .3s ease;display:flex;flex-direction:column}
  .drawer.open{transform:translateX(0)}
  .drawer-hdr{display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--border);flex-shrink:0}
  .drawer-title{font-size:13px;letter-spacing:1.5px;font-variant:small-caps;color:var(--gold)}
  .drawer-close{background:none;border:none;color:var(--muted);cursor:pointer;font-size:20px;padding:2px 8px;border-radius:4px;line-height:1;transition:color .2s;font-family:Georgia,serif}
  .drawer-close:hover{color:var(--cream)}
  .drawer-tabs{display:flex;border-bottom:1px solid var(--border);flex-shrink:0}
  .drawer-tab{padding:10px 16px;font-size:12px;letter-spacing:1px;font-variant:small-caps;color:var(--muted);cursor:pointer;border-bottom:2px solid transparent;transition:color .2s,border-color .2s}
  .drawer-tab:hover{color:var(--cream)}
  .drawer-tab.active{color:var(--gold);border-bottom-color:var(--gold)}
  .drawer-body{flex:1;overflow-y:auto;padding:20px}
  .drawer-panel{display:none}
  .drawer-panel.active{display:block}
  .form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .form-group{display:flex;flex-direction:column;gap:5px}
  .form-group label{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
  .form-group input,.form-group select{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:7px 10px;border-radius:4px;font-size:13px;font-family:Georgia,serif;outline:none}
  .form-group input:focus,.form-group select:focus{border-color:var(--gold)}
  .btn-primary{background:var(--burgundy);border:1px solid var(--burgundy);color:var(--cream);padding:8px 18px;border-radius:4px;cursor:pointer;font-size:12px;letter-spacing:1px;font-variant:small-caps;transition:background .2s;font-family:Georgia,serif}
  .btn-primary:hover{background:#a03050}
  .btn-secondary{background:var(--surface2);border:1px solid var(--border);color:var(--muted);padding:8px 18px;border-radius:4px;cursor:pointer;font-size:12px;letter-spacing:1px;font-variant:small-caps;transition:border-color .2s,color .2s;font-family:Georgia,serif}
  .btn-secondary:hover{border-color:var(--gold);color:var(--gold)}
  .inv-search{width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:7px 10px;border-radius:4px;font-size:13px;font-family:Georgia,serif;outline:none;margin-bottom:12px}
  .inv-search:focus{border-color:var(--gold)}
  .inv-list{display:flex;flex-direction:column;gap:4px}
  .inv-row{display:flex;align-items:center;gap:8px;padding:8px 10px;background:var(--surface2);border-radius:4px;border:1px solid transparent;transition:border-color .2s}
  .inv-row:hover{border-color:var(--border)}
  .inv-info{flex:1;min-width:0}
  .inv-name{font-size:12px;color:var(--cream);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .inv-sub{font-size:10px;color:var(--muted)}
  .qty-ctrl{display:flex;align-items:center;gap:4px;flex-shrink:0}
  .qty-btn{width:22px;height:22px;background:var(--surface);border:1px solid var(--border);color:var(--muted);border-radius:3px;cursor:pointer;font-size:15px;display:flex;align-items:center;justify-content:center;padding:0;line-height:1;transition:border-color .2s,color .2s;font-family:Georgia,serif}
  .qty-btn:hover{border-color:var(--gold);color:var(--gold)}
  .qty-val{width:26px;text-align:center;font-size:13px;color:var(--cream)}
  .qty-zero{opacity:.4}
  .remove-btn{background:none;border:1px solid transparent;color:var(--muted);cursor:pointer;padding:3px 7px;border-radius:3px;font-size:11px;transition:border-color .2s,color .2s;flex-shrink:0;font-family:Georgia,serif}
  .remove-btn:hover{border-color:#e05050;color:#e05050}
  .change-log{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:10px;min-height:80px;max-height:180px;overflow-y:auto;font-size:11px;color:var(--muted);font-family:monospace,monospace;line-height:1.6}
  .change-entry{padding:2px 0;border-bottom:1px solid rgba(58,37,53,.3)}
  .export-section h3{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);margin-bottom:8px}
  .pending-badge{display:inline-block;background:rgba(201,168,76,.1);border:1px solid var(--gold);color:var(--gold);font-size:9px;letter-spacing:1px;text-transform:uppercase;padding:1px 5px;border-radius:2px}
  .add-note{font-size:11px;color:var(--muted);margin-top:12px;line-height:1.55}
  /* \u2500\u2500 CORE LAYOUT \u2500\u2500 */
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:Georgia,serif;min-height:100vh}
  nav{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(15,10,14,.96);backdrop-filter:blur(8px);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 24px;height:56px}
  .nav-brand{font-size:14px;font-variant:small-caps;letter-spacing:2px;color:var(--gold);margin-right:32px;white-space:nowrap}
  .nav-tabs{display:flex}
  .nav-tab{padding:0 18px;height:56px;display:flex;align-items:center;cursor:pointer;font-size:13px;letter-spacing:1px;font-variant:small-caps;color:var(--muted);border-bottom:2px solid transparent;transition:color .2s,border-color .2s}
  .nav-tab:hover{color:var(--cream)}
  .nav-tab.active{color:var(--gold);border-bottom-color:var(--gold)}
  .section{display:none;padding:72px 24px 48px;max-width:1200px;margin:0 auto}
  .section.active{display:block}
  .stat-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:28px}
  .stat-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;text-align:center}
  .stat-val{font-size:26px;color:var(--gold)}
  .stat-label{font-size:11px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-top:4px}
  .charts-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}
  .chart-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px}
  .chart-card.full{grid-column:1/-1}
  .chart-title{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);margin-bottom:14px}
  canvas{max-height:260px}
  .narrative{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:22px;margin-bottom:20px;line-height:1.75;font-size:14px;color:var(--cream)}
  .narrative h2{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gold);margin-bottom:10px}
  .gap-item{background:var(--surface2);border-left:3px solid var(--gold);padding:8px 14px;margin-bottom:8px;border-radius:0 4px 4px 0;font-size:13px;color:var(--cream);line-height:1.55}
  .gap-label{font-size:10px;letter-spacing:1px;text-transform:uppercase;color:var(--gold);display:block;margin-bottom:2px}
  .gantt-controls{display:flex;gap:16px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
  .gantt-legend{display:flex;gap:14px;flex-wrap:wrap}
  .legend-item{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
  .legend-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0}
  .gantt-table{width:100%;border-collapse:collapse;font-size:13px;min-width:760px}
  .gantt-table th{text-align:left;padding:8px 6px;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--gold);border-bottom:1px solid var(--border);font-weight:normal;background:var(--surface)}
  .gantt-table td{padding:5px 6px;border-bottom:1px solid rgba(58,37,53,.4);vertical-align:middle}
  .gantt-table tr:hover td{background:var(--surface2)}
  .wine-name{font-size:13px;color:var(--cream)}
  .wine-producer{font-size:11px;color:var(--muted)}
  .status-badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:11px;white-space:nowrap}
  .s-past{background:rgba(106,74,74,.3);color:#e05050;border:1px solid #e05050}
  .s-urgent{background:rgba(224,120,48,.2);color:#e07830;border:1px solid #e07830}
  .s-now{background:rgba(76,175,122,.15);color:#4caf7a;border:1px solid #4caf7a}
  .s-soon{background:rgba(80,144,200,.15);color:#5090c8;border:1px solid #5090c8}
  .s-wait{background:rgba(122,106,122,.2);color:#7a6a7a;border:1px solid #7a6a7a}
  .bar-track{position:relative;height:16px;background:rgba(58,37,53,.3);border-radius:3px;width:100%;min-width:180px}
  .bar-fill{position:absolute;height:100%;border-radius:3px;top:0;opacity:.7}
  .bar-now{position:absolute;top:0;width:2px;height:100%;background:rgba(232,221,208,.6);z-index:2}
  .bar-lbl{position:absolute;right:4px;top:50%;transform:translateY(-50%);font-size:10px;color:rgba(255,255,255,.45);white-space:nowrap}
  .filter-bar{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px;margin-bottom:18px;display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end}
  .filter-group{display:flex;flex-direction:column;gap:4px}
  .filter-group label{font-size:10px;color:var(--muted);letter-spacing:1px;text-transform:uppercase}
  .filter-bar select,.filter-bar input{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:4px;font-size:13px;outline:none;font-family:Georgia,serif}
  .filter-bar select:focus,.filter-bar input:focus{border-color:var(--gold)}
  .res-count{font-size:12px;color:var(--muted);align-self:flex-end;padding-bottom:6px}
  .card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
  .wine-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;display:flex;flex-direction:column;gap:10px;transition:border-color .2s}
  .wine-card:hover{border-color:var(--gold)}
  .card-hdr{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
  .card-producer{font-size:11px;color:var(--muted);letter-spacing:.5px;text-transform:uppercase}
  .card-wine{font-size:14px;color:var(--cream);line-height:1.3;margin:3px 0}
  .card-app{font-size:12px;color:var(--muted)}
  .card-score{font-size:22px;color:var(--gold);text-align:center;background:var(--surface2);border-radius:6px;padding:5px 10px;flex-shrink:0;line-height:1}
  .card-score span{display:block;font-size:9px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-top:2px}
  .card-meta{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  .meta-tag{background:var(--surface2);border:1px solid var(--border);padding:2px 7px;border-radius:3px;font-size:11px;color:var(--muted)}
  .card-sum{font-size:13px;color:var(--text);line-height:1.6}
  .card-pair{font-size:12px;color:var(--muted)}
  .card-pair strong{color:var(--gold-light)}
  .card-foot{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
  .qpr-bar{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted)}
  .qpr-track{width:60px;height:4px;background:var(--border);border-radius:2px}
  .qpr-fill{height:100%;border-radius:2px;background:var(--gold)}
  .qpr-table-wrap{background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden;margin-top:20px}
  .qpr-table{width:100%;border-collapse:collapse;font-size:13px}
  .qpr-table th{padding:9px 12px;font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--gold);background:var(--surface2);text-align:left;font-weight:normal;border-bottom:1px solid var(--border)}
  .qpr-table td{padding:8px 12px;border-bottom:1px solid rgba(58,37,53,.4)}
  .qpr-table tr:hover td{background:var(--surface2)}
  .qval{font-size:15px;font-weight:bold;padding:1px 6px;border-radius:3px}
  .q-hi{color:#4caf7a}.q-mid{color:var(--gold)}.q-lo{color:var(--muted)}
  ::-webkit-scrollbar{width:5px;height:5px}
  ::-webkit-scrollbar-track{background:var(--bg)}
  ::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
  .scan-fab{display:none}
  @media(max-width:768px){.stat-grid{grid-template-columns:repeat(3,1fr)}.charts-grid{grid-template-columns:1fr}.nav-brand{display:none}.nav .edit-btn.scan-nav{display:none}.drawer{width:100%}.form-grid{grid-template-columns:1fr}.scan-fab{display:flex;position:fixed;bottom:24px;right:24px;z-index:200;width:56px;height:56px;border-radius:50%;background:var(--gold);color:var(--bg);font-size:24px;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(0,0,0,.4);text-decoration:none;border:none;cursor:pointer}}
""")
p.append('  .scan-btn-full{width:100%;padding:10px 14px;background:var(--surface2);border:1px solid var(--gold);color:var(--gold);border-radius:6px;cursor:pointer;font-family:Georgia,serif;font-size:13px;letter-spacing:.5px;display:flex;align-items:center;justify-content:center;gap:8px;transition:background .2s,opacity .2s;margin-bottom:6px}\n')
p.append('  .scan-btn-full:hover{background:rgba(201,168,76,.08)}\n')
p.append('  .scan-btn-full:disabled{border-color:var(--border);color:var(--muted);cursor:not-allowed;opacity:.5}\n')
p.append('  .scan-status-line{font-size:11px;color:var(--muted);min-height:16px;margin:0 0 8px;text-align:center}\n')
p.append('  .scan-status-line.ok{color:#4caf7a}\n')
p.append('  .scan-status-line.err{color:#e07830}\n')
p.append('  .key-area-inner{background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:10px;margin-bottom:8px}\n')
p.append('  .key-row{display:flex;gap:6px;align-items:center}\n')
p.append('  .key-row input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:5px 8px;border-radius:4px;font-size:12px;font-family:Georgia,serif;outline:none}\n')
p.append('  .key-row input:focus{border-color:var(--gold)}\n')
p.append('  .scan-footer-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;font-size:11px}\n')
p.append('  .key-link{color:var(--muted);cursor:pointer;text-decoration:underline;text-underline-offset:2px}\n')
p.append('  .key-link:hover{color:var(--gold)}\n')
p.append('  .scan-divider{border:none;border-top:1px solid var(--border);margin:0 0 14px}\n')
p.append('  @keyframes _spin{to{transform:rotate(360deg)}}\n')
p.append('  .spin{display:inline-block;width:11px;height:11px;border:2px solid var(--border);border-top-color:var(--gold);border-radius:50%;animation:_spin .8s linear infinite;vertical-align:middle;margin-right:4px}\n')
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
p.append('  </div>\n')
p.append('  <div class="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">\n')
p.append('    <span class="theme-toggle-label" id="themeLabel">Light</span>\n')
p.append('    <div class="toggle-pill"><div class="toggle-knob" id="toggleKnob">&#9728;</div></div>\n')
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
p.append('    <p>QPR Index (1&ndash;10) = <em>(critic score) &divide; (purchase price paid)</em>, normalized across the collection. For wines where purchase price is unknown, market price is used as a conservative proxy &mdash; their true QPR may be higher. RNDC Wine Library bottles bought at ~$18 dominate the top rankings. Bubble size in the chart reflects discount to market (larger = bought further below market price).</p>\n')
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
p.append('const CY = ' + str(CY) + ';\n\n')

p.append("""function show(id, el) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if (id === 'overview') buildCharts();
  if (id === 'windows') renderWindows();
  if (id === 'profiles') renderProfiles();
  if (id === 'qpr') renderQPR();
}

// CHARTS
let _charts = {};
function buildCharts() {
  Object.values(_charts).forEach(function(c){if(c)c.destroy();});
  _charts = {};
  const def = { plugins:{ legend:{ labels:{ color:'#9b8a7a', font:{family:'Georgia'} } } }, scales:{ x:{ ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} }, y:{ ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} } } };

  // Country
  const cc = {}; WINES.forEach(w => cc[w.country] = (cc[w.country]||0)+w.qty);
  const cs = Object.entries(cc).sort((a,b)=>b[1]-a[1]);
  _charts.cc = new Chart(document.getElementById('countryChart'), { type:'bar', data:{ labels:cs.map(e=>e[0]), datasets:[{ data:cs.map(e=>e[1]), backgroundColor:['#7c2d3f','#c9a84c','#9b5a6a','#5a7c9b','#7c9b5a','#9b7c5a','#6a5a9b'], borderWidth:0 }] }, options:{ ...def, plugins:{ legend:{display:false} } } });

  // Style donut
  const sc = {}; WINES.forEach(w => sc[w.style]=(sc[w.style]||0)+w.qty);
  const scols = { red:'#7c2d3f', white:'#c9a84c', sparkling:'#5a8c9b', "ros\u00e9":'#c97a8a', dessert:'#9b7c3a', orange:'#c97a3a' };
  _charts.sc = new Chart(document.getElementById('styleChart'), { type:'doughnut', data:{ labels:Object.keys(sc).map(s=>s[0].toUpperCase()+s.slice(1)), datasets:[{ data:Object.values(sc), backgroundColor:Object.keys(sc).map(s=>scols[s]||'#777'), borderWidth:0, hoverOffset:6 }] }, options:{ plugins:{ legend:{ position:'right', labels:{ color:'#9b8a7a', font:{family:'Georgia'}, padding:12 } } }, cutout:'55%' } });

  // Varietal
  const vm = {};
  const vn = v => {
    if (v.includes('Pinot Noir')) return 'Pinot Noir';
    if (v.includes('Chardonnay')) return 'Chardonnay';
    if (v.includes('Cabernet Sauvignon')) return 'Cabernet Sauvignon';
    if (v.includes('Chenin Blanc')) return 'Chenin Blanc';
    if (v.includes('Gamay')) return 'Gamay';
    if (v.includes('Shiraz')||v.includes('Syrah')||v.includes('Mourv\u00e8dre')) return 'Shiraz / Mourv\u00e8dre';
    if (v.includes('Sangiovese')) return 'Sangiovese';
    if (v.includes('Nebbiolo')) return 'Nebbiolo';
    if (v.includes('Zinfandel')) return 'Zinfandel';
    if (v.includes('Merlot')||v.includes('Cab Franc')||v.includes('Cabernet Franc')) return 'Bordeaux Blend';
    if (v.includes('Sauvignon Blanc')||v.includes('S\u00e9millon')) return 'Sauvignon Blanc';
    return 'Other / Rare';
  };
  WINES.forEach(w => { const k=vn(w.varietal); vm[k]=(vm[k]||0)+w.qty; });
  const vs = Object.entries(vm).sort((a,b)=>b[1]-a[1]);
  _charts.vc = new Chart(document.getElementById('varietalChart'), { type:'bar', data:{ labels:vs.map(e=>e[0]), datasets:[{ data:vs.map(e=>e[1]), backgroundColor:'#7c2d3f', borderWidth:0, hoverBackgroundColor:'#c9a84c' }] }, options:{ indexAxis:'y', plugins:{ legend:{display:false} }, scales:{ x:{ ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} }, y:{ ticks:{color:'#e8ddd0', font:{size:12}}, grid:{color:'rgba(58,37,53,.2)'} } } } });
}
buildCharts();

// WINDOWS
const GSTART=2000, GEND=2048;
const sColor = { past:'#e05050', urgent:'#e07830', now:'#4caf7a', soon:'#5090c8', wait:'#7a6a7a' };
const sLabel = { past:'Past window', urgent:'Open urgently', now:'Drink now', soon:'Open soon', wait:'Needs time' };

function renderWindows() {
  const sort = document.getElementById('wSort').value;
  const order = { past:0, urgent:1, now:2, soon:3, wait:4 };
  const data = [...WINES].sort((a,b) => {
    if (sort==='status') return order[a.drinkStatus]-order[b.drinkStatus];
    if (sort==='vintage') { const av=typeof a.vintage==='number'?a.vintage:9999, bv=typeof b.vintage==='number'?b.vintage:9999; return av-bv; }
    if (sort==='country') return a.country.localeCompare(b.country);
    if (sort==='style') return a.style.localeCompare(b.style);
    return 0;
  });
  const range = GEND-GSTART;
  const nowPct = (CY-GSTART)/range*100;
  document.getElementById('wBody').innerHTML = data.map(w => {
    const fp = Math.max(0,Math.min(100,(w.drinkFrom-GSTART)/range*100));
    const tp = Math.max(0,Math.min(100,(w.drinkTo-GSTART)/range*100));
    const wp = Math.max(1,tp-fp);
    const vd = typeof w.vintage==='string'?'NV':w.vintage;
    return '<tr>'
      + '<td style="max-width:220px"><div class="wine-name">'+w.wine+'</div><div class="wine-producer">'+w.producer+'</div></td>'
      + '<td style="color:var(--muted);white-space:nowrap">'+vd+'</td>'
      + '<td style="color:var(--muted)">'+w.country+'</td>'
      + '<td><span class="status-badge s-'+w.drinkStatus+'">'+sLabel[w.drinkStatus]+'</span></td>'
      + '<td style="width:100%;padding-right:12px"><div class="bar-track">'
      + '<div class="bar-fill" style="left:'+fp+'%;width:'+wp+'%;background:'+sColor[w.drinkStatus]+'"></div>'
      + '<div class="bar-now" style="left:'+nowPct+'%"></div>'
      + '<span class="bar-lbl">'+w.drinkFrom+'\u2013'+w.drinkTo+'</span>'
      + '</div></td></tr>';
  }).join('');
}

// PROFILES
const eStyle = { red:'\U0001F377', white:'\U0001F942', sparkling:'\u2728', 'ros\u00e9':'\U0001F338', dessert:'\U0001F36F', orange:'\U0001F34A' };

function renderProfiles() {
  const q = document.getElementById('sSearch').value.toLowerCase();
  const st = document.getElementById('sStyle').value;
  const co = document.getElementById('sCountry').value;
  const ss = document.getElementById('sStatus').value;
  const f = WINES.filter(w => {
    if (st && w.style!==st) return false;
    if (co && w.country!==co) return false;
    if (ss && w.drinkStatus!==ss) return false;
    if (q) { const h=[w.producer,w.wine,w.appellation,w.varietal,w.country].join(' ').toLowerCase(); if (!h.includes(q)) return false; }
    return true;
  });
  document.getElementById('resCount').textContent = f.length + ' wine' + (f.length!==1?'s':'');
  document.getElementById('cardGrid').innerHTML = f.map(w => {
    const qp = (w.qprIndex-1)/9*100;
    const vd = typeof w.vintage==='string'?'NV':w.vintage;
    const pp = w.purchasePrice ? '$'+w.purchasePrice+' paid \u00b7 $'+w.marketPrice+' market' : '$'+w.marketPrice+' market';
    const disc = w.purchasePrice ? Math.round((1-w.purchasePrice/w.marketPrice)*100) : 0;
    const pb = w.pending ? '<span class="pending-badge" style="margin-left:4px">pending enrichment</span>' : '';
    return '<div class="wine-card">'
      + '<div class="card-hdr"><div>'
      + '<div class="card-producer">'+w.producer+' \u00b7 '+vd+'</div>'
      + '<div class="card-wine">'+w.wine+'</div>'
      + '<div class="card-app">'+w.appellation+'</div>'
      + '</div><div><div class="card-score">'+w.score+'<span>pts</span></div></div></div>'
      + '<div class="card-meta">'
      + '<span class="meta-tag">'+(eStyle[w.style]||'')+' '+w.style+'</span>'
      + '<span class="meta-tag">'+w.country+'</span>'
      + '<span class="meta-tag">'+w.varietal.split(',')[0]+'</span>'
      + '<span class="status-badge s-'+w.drinkStatus+'">'+sLabel[w.drinkStatus]+'</span>'+pb
      + '</div>'
      + '<div style="font-size:12px;color:var(--muted)"><strong style="color:var(--cream)">Drink:</strong> '+w.drinkFrom+'\u2013'+w.drinkTo+'</div>'
      + '<div class="card-sum">'+w.summary+'</div>'
      + '<div class="card-pair"><strong>Pairings:</strong> '+w.pairings.join(' \u00b7 ')+'</div>'
      + '<div class="card-foot">'
      + '<div class="qpr-bar"><span>QPR</span><div class="qpr-track"><div class="qpr-fill" style="width:'+qp+'%"></div></div><span style="color:var(--gold)">'+w.qprIndex+'/10</span></div>'
      + '<div style="font-size:11px;color:var(--muted)">'+pp+(disc>0?' \u00b7 '+disc+'% off':'')+'</div>'
      + '</div></div>';
  }).join('');
}

// QPR
let qprChart = null;
function renderQPR() {
  if (qprChart) { qprChart.destroy(); qprChart = null; }
  const scols2 = { red:'rgba(124,45,63,.8)', white:'rgba(201,168,76,.8)', sparkling:'rgba(90,140,155,.8)', 'ros\u00e9':'rgba(201,122,138,.8)', dessert:'rgba(155,124,58,.8)', orange:'rgba(201,122,58,.8)' };
  const styleKeys = [...new Set(WINES.map(w=>w.style))];
  qprChart = new Chart(document.getElementById('qprScatter'), {
    type:'bubble',
    data:{ datasets: styleKeys.map(st => ({
      label: st[0].toUpperCase()+st.slice(1),
      data: WINES.filter(w=>w.style===st).map(w=>({
        x: w.purchasePriceEff, y: w.score,
        r: Math.max(4, Math.min(18, w.purchasePrice ? (1-w.purchasePrice/w.marketPrice)*16+5 : 5)),
        label: w.producer+' \u2014 '+w.wine.substring(0,30),
        paid: w.purchasePriceEff, market: w.marketPrice, score: w.score
      })),
      backgroundColor: scols2[st]||'rgba(128,128,128,.7)', borderWidth:1
    })).filter(d=>d.data.length) },
    options:{
      plugins:{
        legend:{ labels:{ color:'#9b8a7a', font:{family:'Georgia'} } },
        tooltip:{ callbacks:{ label: ctx => ctx.raw.label+' | Paid: $'+ctx.raw.paid+' | Market: $'+ctx.raw.market+' | Score: '+ctx.raw.score } }
      },
      scales:{
        x:{ title:{display:true,text:'Purchase Price ($)',color:'#9b8a7a'}, ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} },
        y:{ title:{display:true,text:'Score',color:'#9b8a7a'}, min:85, ticks:{color:'#9b8a7a'}, grid:{color:'rgba(58,37,53,.4)'} }
      }
    }
  });
  const sorted = [...WINES].sort((a,b)=>b.qprIndex-a.qprIndex);
  document.getElementById('qprBody').innerHTML = sorted.map(w => {
    const paid = w.purchasePriceEff || w.marketPrice;
    const disc = (w.marketPrice && paid < w.marketPrice) ? Math.round((1-paid/w.marketPrice)*100) : 0;
    const qc = w.qprIndex>=7?'q-hi':w.qprIndex>=4?'q-mid':'q-lo';
    const vd = typeof w.vintage==='string'?'NV':w.vintage;
    return '<tr>'
      + '<td><div style="font-size:13px;color:var(--cream)">'+w.wine+'</div><div style="font-size:11px;color:var(--muted)">'+w.producer+' \u00b7 '+w.appellation+'</div></td>'
      + '<td style="color:var(--muted)">'+vd+'</td>'
      + '<td style="color:var(--gold);text-align:center">'+w.score+'</td>'
      + '<td style="color:var(--cream)">$'+paid+'</td>'
      + '<td style="color:var(--muted)">$'+w.marketPrice+'</td>'
      + '<td style="color:'+(disc>0?'#4caf7a':'var(--muted)')+'">'+(disc>0?disc+'% off':'\u2014')+'</td>'
      + '<td><span class="qval '+qc+'">'+w.qprIndex+'</span></td>'
      + '</tr>';
  }).join('');
}

renderWindows();
renderProfiles();

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  document.getElementById('themeLabel').textContent = isDark ? 'Dark' : 'Light';
  document.getElementById('toggleKnob').textContent = isDark ? '\U0001F319' : '\u2600';
  setTimeout(() => {
    const activeId = document.querySelector('.section.active')?.id;
    if (activeId === 'qpr') renderQPR();
    else buildCharts();
  }, 50);
}

// \u2500\u2500 EDIT DRAWER
let _editChanges = [];
function openDrawer() {
  document.getElementById("editDrawer").classList.add("open");
  document.getElementById("drawerOverlay").classList.add("open");
  renderInvList();
}
function closeDrawer() {
  document.getElementById("editDrawer").classList.remove("open");
  document.getElementById("drawerOverlay").classList.remove("open");
  refreshStats();
}
function switchEditTab(tab, el) {
  document.querySelectorAll(".drawer-tab").forEach(function(t){t.classList.remove("active");});
  document.querySelectorAll(".drawer-panel").forEach(function(p){p.classList.remove("active");});
  el.classList.add("active");
  document.getElementById("panel-" + tab).classList.add("active");
  if (tab === "inventory") renderInvList();
  if (tab === "export") renderChangeLog();
  if (tab === "add") _updateKeyStatus();
}
function renderInvList() {
  var q = (document.getElementById("invSearch").value || "").toLowerCase();
  var wines = WINES.filter(function(w) {
    if (!q) return true;
    return [w.producer, w.wine, w.appellation, w.varietal || ""].join(" ").toLowerCase().indexOf(q) !== -1;
  });
  document.getElementById("invList").innerHTML = wines.map(function(w) {
    var vd = typeof w.vintage === "string" ? "NV" : w.vintage;
    var zc = w.qty === 0 ? " qty-zero" : "";
    var pb = w.pending ? " <span class=\\"pending-badge\\">pending</span>" : "";
    return '<div class="inv-row" id="inv-' + w.id + '">'
      + '<div class="inv-info">'
      + '<div class="inv-name">' + w.producer + ' \u2014 ' + w.wine + '</div>'
      + '<div class="inv-sub">' + vd + ' \u00b7 ' + w.appellation + pb + '</div>'
      + '</div>'
      + '<div class="qty-ctrl">'
      + '<button class="qty-btn" onclick="adjustQty(' + w.id + ',-1)">\u2212</button>'
      + '<span class="qty-val' + zc + '">' + w.qty + '</span>'
      + '<button class="qty-btn" onclick="adjustQty(' + w.id + ',1)">+</button>'
      + '</div>'
      + '<button class="remove-btn" onclick="removeWine(' + w.id + ')" title="Remove">\u2715</button>'
      + '</div>';
  }).join("");
}
function adjustQty(id, delta) {
  var w = WINES.find(function(w){return w.id===id;});
  if (!w) return;
  var prev = w.qty;
  w.qty = Math.max(0, w.qty + delta);
  if (w.qty === prev) return;
  _logChange((delta > 0 ? "\u25b2" : "\u25bc") + " " + w.producer + " \u2014 " + w.wine
    + " (" + (typeof w.vintage === "string" ? "NV" : w.vintage) + "): qty " + prev + " \u2192 " + w.qty);
  renderInvList();
}
function removeWine(id) {
  var idx = WINES.findIndex(function(w){return w.id===id;});
  if (idx === -1) return;
  var w = WINES[idx];
  if (!confirm("Remove \\"" + w.producer + " \u2014 " + w.wine + "\\" from your collection?")) return;
  _logChange("\u2715 Removed: " + w.producer + " \u2014 " + w.wine
    + " (" + (typeof w.vintage === "string" ? "NV" : w.vintage) + ")");
  WINES.splice(idx, 1);
  _recomputeQPR();
  renderInvList();
  refreshStats();
}
function addWine() {
  var producer = document.getElementById("f-producer").value.trim();
  var wine = document.getElementById("f-wine").value.trim();
  var country = document.getElementById("f-country").value;
  var style = document.getElementById("f-style").value;
  var qty = parseInt(document.getElementById("f-qty").value) || 1;
  var msg = document.getElementById("add-msg");
  if (!producer || !wine || !country || !style) {
    msg.style.color = "#e05050";
    msg.textContent = "Producer, Wine, Country and Style are required.";
    return;
  }
  var appellation = document.getElementById("f-appellation").value.trim() || "";
  var region = document.getElementById("f-region").value.trim() || country;
  var varietal = document.getElementById("f-varietal").value.trim() || "";
  var vintageRaw = document.getElementById("f-vintage").value;
  var vintage = vintageRaw ? parseInt(vintageRaw) : "NV";
  var purchasePrice = parseFloat(document.getElementById("f-purchase").value) || null;
  var marketPrice = parseFloat(document.getElementById("f-market").value) || null;
  var score = parseInt(document.getElementById("f-score").value) || 88;
  var drinkFrom = parseInt(document.getElementById("f-from").value) || CY;
  var drinkTo = parseInt(document.getElementById("f-to").value) || (CY + 5);
  var purchasePriceEff = purchasePrice || marketPrice || 25;
  var drinkStatus;
  if (drinkTo < CY) drinkStatus = "past";
  else if (drinkFrom <= CY) drinkStatus = (drinkTo - CY <= 2) ? "urgent" : "now";
  else if (drinkFrom <= CY + 2) drinkStatus = "soon";
  else drinkStatus = "wait";
  var newId = WINES.length ? Math.max.apply(null, WINES.map(function(w){return w.id;})) + 1 : 1;
  WINES.push({
    id: newId, producer: producer, wine: wine, appellation: appellation,
    country: country, region: region, vintage: vintage, qty: qty,
    varietal: varietal, style: style,
    purchasePrice: purchasePrice, marketPrice: marketPrice || purchasePrice || 0,
    score: score, drinkFrom: drinkFrom, drinkTo: drinkTo, drinkStatus: drinkStatus,
    pairings: (window._scanPending && window._scanPending.pairings && window._scanPending.pairings.length) ? window._scanPending.pairings : ["Pending enrichment"],
    summary: (window._scanPending && window._scanPending.summary) ? window._scanPending.summary : "Added manually \u2014 bring this file to Claude to complete tasting notes, pairings, and vintage context.",
    purchasePriceEff: purchasePriceEff, qprRaw: score / purchasePriceEff, qprIndex: 5,
    pending: !(window._scanPending && window._scanPending.pairings && window._scanPending.pairings.length)
  });
  window._scanPending = null;
  _recomputeQPR();
  _logChange("+ Added: " + producer + " \u2014 " + wine
    + " (" + (typeof vintage === "string" ? "NV" : vintage) + ") \u00d7" + qty);
  clearAddForm();
  msg.style.color = "#4caf7a";
  msg.textContent = "\u2713 Added \\"" + wine + "\\" \u2014 switch to Inventory to verify.";
  setTimeout(function(){msg.textContent="";}, 4000);
}
function clearAddForm() {
  ["f-producer","f-wine","f-appellation","f-varietal","f-region"].forEach(function(id){document.getElementById(id).value="";});
  ["f-country","f-style"].forEach(function(id){document.getElementById(id).value="";});
  ["f-vintage","f-purchase","f-market","f-score","f-from","f-to"].forEach(function(id){document.getElementById(id).value="";});
  document.getElementById("f-qty").value = "1";
  window._scanPending = null;
  var ss = document.getElementById("scanStatus");
  if (ss) { ss.className = "scan-status-line"; ss.textContent = ""; }
}
function _recomputeQPR() {
  var raws = WINES.map(function(w){return w.score / (w.purchasePriceEff || 25);});
  var mn = Math.min.apply(null, raws), mx = Math.max.apply(null, raws);
  WINES.forEach(function(w, i) {
    w.qprRaw = raws[i];
    w.qprIndex = mn === mx ? 5.0 : Math.round(((raws[i]-mn)/(mx-mn)*9+1)*10)/10;
  });
}
function refreshStats() {
  var bottles = WINES.reduce(function(s,w){return s+w.qty;},0);
  var skus = WINES.length;
  var ctSet = {}; WINES.forEach(function(w){ctSet[w.country]=1;});
  var countries = Object.keys(ctSet).length;
  var mv = WINES.reduce(function(s,w){return s+(w.marketPrice*w.qty);},0);
  var vints = WINES.map(function(w){return typeof w.vintage==="number"?w.vintage:null;}).filter(Boolean);
  var spanStr = vints.length ? Math.min.apply(null,vints)+"\u2013"+Math.max.apply(null,vints) : "\u2014";
  var cards = document.querySelectorAll(".stat-card .stat-val");
  if (cards[0]) cards[0].textContent = bottles;
  if (cards[1]) cards[1].textContent = skus;
  if (cards[2]) cards[2].textContent = countries;
  if (cards[3]) cards[3].textContent = "$"+(mv>=1000?(mv/1000).toFixed(1)+"k":Math.round(mv));
  if (cards[4]) cards[4].textContent = spanStr;
  var activeId = (document.querySelector(".section.active")||{}).id;
  if (activeId === "overview") buildCharts();
  else if (activeId === "windows") renderWindows();
  else if (activeId === "profiles") renderProfiles();
  else if (activeId === "qpr") renderQPR();
}
function _logChange(msg) {
  var now = new Date();
  var ts = now.getHours().toString().padStart(2,"0")+":"+now.getMinutes().toString().padStart(2,"0");
  _editChanges.push("["+ts+"] "+msg);
  renderChangeLog();
}
function renderChangeLog() {
  var el = document.getElementById("changeLog");
  if (!el) return;
  if (!_editChanges.length) {
    el.innerHTML = '<span style="font-style:italic">No changes yet this session.</span>';
  } else {
    el.innerHTML = _editChanges.slice().reverse().map(function(e){
      return '<div class="change-entry">'+e+'</div>';
    }).join("");
  }
}
function exportHTML() {
  var src = '<!DOCTYPE html>\\n' + document.documentElement.outerHTML;
  src = src.replace(/class="drawer-overlay open"/g, 'class="drawer-overlay"');
  src = src.replace(/class="drawer open"/g, 'class="drawer"');
  var winesStr = 'const WINES = ' + JSON.stringify(WINES, null, '\\n') + ';';
  src = src.replace(/const WINES = [\\s\\S]*?;/, winesStr);
  _dlBlob('wine_cellar_dashboard.html', src, 'text/html');
  _logChange('\\u2193 Exported wine_cellar_dashboard.html');
}
function exportJSON() {
  _dlBlob('wines.json', JSON.stringify(WINES, null, 2), 'application/json');
  _logChange('\\u2193 Exported wines.json');
}
function _dlBlob(filename, content, type) {
  var blob = new Blob([content], {type: type});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(a.href);
}
""")

p.append("""
// \u2500\u2500 SCAN LABEL (client-side Gemini Vision)
window._scanPending = null;

function _scanKey() {
  try { return localStorage.getItem('gemini_api_key') || ''; } catch(e) { return ''; }
}
function _updateKeyStatus() {
  var k = _scanKey();
  var el = document.getElementById('keyStatusLine');
  var btn = document.getElementById('scanBtn');
  if (el) { el.textContent = k ? '\u2713 API key set' : 'No API key'; el.style.color = k ? '#4caf7a' : 'var(--muted)'; }
  if (btn) btn.disabled = !k;
}
function toggleKeyArea() {
  var el = document.getElementById('keyArea');
  if (!el) return;
  var showing = el.style.display !== 'none';
  el.style.display = showing ? 'none' : 'block';
  if (!showing) { var ki = document.getElementById('keyInput'); if (ki) ki.focus(); }
}
function saveKey() {
  var val = (document.getElementById('keyInput') || {}).value || '';
  val = val.trim();
  if (!val) return;
  try { localStorage.setItem('gemini_api_key', val); } catch(e) {}
  document.getElementById('keyInput').value = '';
  document.getElementById('keyArea').style.display = 'none';
  _updateKeyStatus();
}
function clearKey() {
  try { localStorage.removeItem('gemini_api_key'); } catch(e) {}
  var ki = document.getElementById('keyInput');
  if (ki) ki.value = '';
  _updateKeyStatus();
}
function scanLabel() {
  var k = _scanKey();
  if (!k) {
    toggleKeyArea();
    var ss = document.getElementById('scanStatus');
    if (ss) { ss.className = 'scan-status-line err'; ss.textContent = 'Set your Gemini API key first.'; }
    return;
  }
  var inp = document.getElementById('scanInput');
  if (inp) inp.click();
}
function handleScanFile(input) {
  var file = input.files[0];
  if (!file) return;
  var status = document.getElementById('scanStatus');
  var btn = document.getElementById('scanBtn');
  status.className = 'scan-status-line';
  status.innerHTML = '<span class="spin"></span> Identifying wine\u2026';
  btn.disabled = true;
  var reader = new FileReader();
  reader.onload = function(e) {
    var b64 = e.target.result.split(',')[1];
    var mime = file.type || 'image/jpeg';
    _callGeminiVision(b64, mime, status, btn);
  };
  reader.readAsDataURL(file);
  input.value = '';
}
function _callGeminiVision(b64, mime, status, btn) {
  var key = _scanKey();
  var url = 'https://generativelanguage.googleapis.com/v1beta/models/gemma-4-27b-it:generateContent?key=' + key;
  var prompt = 'You are a wine expert examining a wine bottle label photo.\\n\\nExtract every detail you can identify from the label. Then, using your wine knowledge, fill in the remaining fields needed for a wine cellar database.\\n\\nReturn ONLY a JSON object with these exact fields (no markdown, no explanation):\\n{"producer":"...","wine":"...","appellation":"...","country":"...","region":"...","vintage":2023,"varietal":"...","style":"red","purchasePrice":null,"marketPrice":25,"score":88,"drinkFrom":2024,"drinkTo":2030,"pairings":["food1","food2","food3"],"summary":"2-3 sentence tasting note and context."}\\n\\nRules:\\n- vintage must be an integer year, or the string NV for non-vintage\\n- style must be one of: red, white, sparkling, ros\\u00e9, dessert, orange\\n- marketPrice is your best estimate of current US retail price in USD\\n- score is your best estimate of critic consensus (Wine Advocate, Wine Spectator)\\n- drinkFrom and drinkTo are drinking window years\\n- pairings should be 3 specific food pairings\\n- summary should mention the producer, vintage character, and what to expect\\n- purchasePrice should always be null\\n- If you cannot identify the wine at all, set producer to null';
  var body = JSON.stringify({ contents: [{ parts: [
    { inline_data: { mime_type: mime, data: b64 } },
    { text: prompt }
  ]}]});
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: body })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) throw new Error(data.error.message || 'API error');
      var candidates = data.candidates || [];
      var content = (candidates[0] || {}).content || {};
      var parts = content.parts || [];
      var text = ((parts[0] || {}).text || '').trim();
      if (text.indexOf('```') === 0) {
        text = text.split('\\n').slice(1).join('\\n');
        text = text.replace(/```\\s*$/, '').trim();
      }
      var wine = JSON.parse(text);
      if (!wine.producer) throw new Error('Could not identify wine from this image');
      _fillFormFromScan(wine);
      status.className = 'scan-status-line ok';
      status.textContent = '\u2713 Wine identified \u2014 review fields below, then click Add to Collection';
      btn.disabled = false;
    })
    .catch(function(err) {
      status.className = 'scan-status-line err';
      status.textContent = 'Scan failed: ' + err.message;
      btn.disabled = false;
    });
}
function _fillFormFromScan(w) {
  function setVal(id, val) { var el = document.getElementById(id); if (el && val != null) el.value = val; }
  setVal('f-producer', w.producer || '');
  setVal('f-wine', w.wine || '');
  setVal('f-appellation', w.appellation || '');
  setVal('f-varietal', w.varietal || '');
  setVal('f-region', w.region || '');
  setVal('f-vintage', typeof w.vintage === 'number' ? w.vintage : '');
  setVal('f-market', w.marketPrice || '');
  setVal('f-score', w.score || '');
  setVal('f-from', w.drinkFrom || '');
  setVal('f-to', w.drinkTo || '');
  var cEl = document.getElementById('f-country');
  if (cEl && w.country) {
    for (var i = 0; i < cEl.options.length; i++) {
      if (cEl.options[i].value === w.country || cEl.options[i].text === w.country) { cEl.selectedIndex = i; break; }
    }
  }
  var sEl = document.getElementById('f-style');
  if (sEl && w.style) sEl.value = w.style;
  window._scanPending = { pairings: w.pairings || [], summary: w.summary || '' };
}
function openScanDrawer() {
  openDrawer();
  var tabs = document.querySelectorAll('.drawer-tab');
  if (tabs[1]) switchEditTab('add', tabs[1]);
}
_updateKeyStatus();
""")
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
