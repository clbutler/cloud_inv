#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 2026

@author: chrisbutler

Builds a batch of satellite views to label. Run from scripts/:
    python main_review_batch.py           # batch 1: random days from main_satellite_scan.py
    python main_review_batch.py batch2    # batch 2: past days the site scored, from main_backcast.py
then open ../outputs/satellite_<batch>/review.html and copy the downloaded csv over data/satellite_<batch>_checks.csv.

Batch 1: the rule picks the candidates (MIX: likely inversions, near misses, clear or overcast).
Batch 2: every day the site rated Likely or Possible, a share of those the rule called an inversion but the site
didn't, and a small random share of the rest. Each is picked by a hash of its date and munro, so re-running after
main_backcast.py has added more days only adds cards. The page never shows the site's or the rule's verdict, and
the cards are shuffled, so neither can sway your answer. Where Geograph has a photo taken near the
munro that day (rare on an ordinary day), the card gets a second step: the photo is only revealed after you
answer from the satellite view. held_out marks the days kept for the fair test: from 2022 in batch 1, every third month in batch 2.
Re-running keeps the answers already in the checks csv.
"""

import hashlib
import json
import os
import sys

import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

from geograph_function import photos_on_day
from openmeteo_function import munro_locations
from satellite_function import GRID_CRS, RADIUS_M, munro_grids, terrain, true_colour

BATCH = sys.argv[1] if len(sys.argv) > 1 else 'batch1'
SCAN_CSV = '../outputs/satellite_scan.csv'
BACKCAST_CSV = '../outputs/backcast_vs_satellite.csv'
CHECKS_CSV = '../data/satellite_{}_checks.csv'.format(BATCH)
BATCH_DIR = '../outputs/satellite_{}'.format(BATCH)
MIX = {'inversion': 40, 'mixed': 17, 'clear': 5, 'summit_cloud': 5} #batch 1: 60 / 25 / 15 %, scaled to the 40 inversions found
MISSED_SHARE = 0.25 #batch 2: share of 'rule says inversion, site says Unlikely' days to check
RANDOM_SHARE = 0.015 #batch 2: share of all other days, so about 1 card in 5 is a random one
PHOTO_KM = 10 #a photo counts if it was taken this close to the summit
PHOTO_CACHE = '../outputs/geograph_days' #each day's geograph photos, so a rebuild only asks about new days
ANSWER_COLUMNS = ['visible', 'photo_shows', 'notes'] #filled in on the review page


def draw_lots(df, salt):
    '''a number from 0 to 1 for each munro-day that never changes, so adding rows never changes earlier picks'''
    keys = df['date'] + '_' + df['munro_id'].astype(str) + salt
    return keys.map(lambda k: int(hashlib.md5(k.encode()).hexdigest()[:8], 16) / 16 ** 8)


####### Step 1 Pick the candidates #########

rng = np.random.default_rng(1010)
munros = munro_locations(gpd.read_file('../outputs/munro.shp')).astype({'munro_id': int}) #the shapefile stores the id as text
if BATCH == 'batch1':
    scan = pd.read_csv(SCAN_CSV)
    scan = scan[scan['label'].isin(MIX)].astype({'munro_id': int})
    picked = []
    for label, n in MIX.items():
        pool = scan[scan['label'] == label].sample(frac = 1, random_state = rng.integers(1e9))
        pool = pool.assign(repeat = pool.groupby('date').cumcount()).sort_values('repeat', kind = 'stable') #new days first
        picked.append(pool.head(n).drop(columns = 'repeat'))
    cards = pd.concat(picked).sample(frac = 1, random_state = rng.integers(1e9)).reset_index(drop = True) #shuffled
else:
    days = pd.read_csv(BACKCAST_CSV)
    days = days[days['label'] != 'snow'].astype({'munro_id': int}) #no verdict to check on a snowy view
    lots = draw_lots(days, 'pick')
    site_likely = days['rag'].isin(['Green', 'Amber'])
    missed = ~site_likely & (days['label'] == 'inversion') & (lots < MISSED_SHARE)
    other = ~site_likely & (days['label'] != 'inversion') & (lots < RANDOM_SHARE)
    cards = days[site_likely | missed | other].drop(columns = 'height_m', errors = 'ignore')
    cards = cards.merge(munros[['munro_id', 'height_m']], on = 'munro_id').assign(low_drop_m = 300.0)
    cards = cards.assign(order = draw_lots(cards, 'order')).sort_values('order').drop(columns = 'order')
    cards = cards.reset_index(drop = True)
cards = cards.merge(munros[['munro_id', 'name', 'lat', 'lon']], on = 'munro_id', how = 'left')
cards['image'] = cards['date'] + '_munro-' + cards['munro_id'].astype(str) + '.png'
print('{} cards on {} days, {} held out'.format(len(cards), cards['date'].nunique(), cards['held_out'].sum()))


####### Step 2 Geograph photos taken near each munro that day #########

grids = munro_grids(cards)
to_grid = Transformer.from_crs('EPSG:4326', GRID_CRS, always_xy = True)
cards['photo_links'] = ''
os.makedirs(PHOTO_CACHE, exist_ok = True)
for date in sorted(cards['date'].unique()):
    cached = os.path.join(PHOTO_CACHE, date + '.csv')
    if os.path.exists(cached): #a past day's photos rarely change, and geograph can be slow to answer
        photos = pd.read_csv(cached)
    else:
        try:
            photos = photos_on_day(date)
        except (requests.exceptions.RequestException, RuntimeError) as error:
            print('No Geograph photos for {} this time ({})'.format(date, type(error).__name__))
            continue
        photos.to_csv(cached, index = False)
    px, py = to_grid.transform(photos['lon'].values, photos['lat'].values)
    for i in cards.index[cards['date'] == date]:
        km = np.hypot(px - grids.at[i, 'easting'], py - grids.at[i, 'northing']) / 1000
        near = photos.assign(km = km)[km <= PHOTO_KM].sort_values('km').head(3) #the closest three are plenty
        cards.at[i, 'photo_links'] = ' '.join('https://www.geograph.org.uk/photo/' + near['id'].astype(str))
cards['photo_step'] = cards['photo_links'] != '' #every card with a photo: they're too rare to leave any out
old = pd.read_csv(CHECKS_CSV, dtype = str, keep_default_na = False) if os.path.exists(CHECKS_CSV) else None
print('{} cards have a Geograph photo within {} km for the photo step'.format(cards['photo_step'].sum(), PHOTO_KM))


####### Step 3 Draw each satellite view, with nothing that gives the rule's verdict away #########

os.makedirs(BATCH_DIR, exist_ok = True)
drawn = lambda image: os.path.exists(os.path.join(BATCH_DIR, image))
to_draw = grids[~grids['image'].map(drawn)]
dem = terrain(to_draw) if len(to_draw) else {}
extent = [-RADIUS_M / 1000, RADIUS_M / 1000] * 2 #km from the summit
for i, row in to_draw.iterrows():
    path = os.path.join(BATCH_DIR, row['image'])
    rgb = true_colour(row['scene_id'], row)
    if rgb is None:
        print('Could not read {}; run again to retry'.format(row['image']))
        continue
    fig, ax = plt.subplots(figsize = (5, 5))
    ax.imshow(rgb, extent = extent)
    ax.contour(dem[row['munro_id']][::-1], levels = [row['height_m'] - row['low_drop_m']], colors = '#f5b700',
               linewidths = 0.8, extent = extent)
    ax.plot(0, 0, marker = '^', color = '#e8590c', markersize = 8, markeredgecolor = 'black')
    ax.set_xticks([]), ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi = 110)
    plt.close(fig)


####### Step 4 The checks csv, keeping any answers already given #########

missing = ~cards['image'].map(drawn)
if missing.any(): #left off the page until a re-run draws them, rather than shown as a broken image
    print('{} cards left out until their image can be read'.format(missing.sum()))
columns = ['image', 'date', 'munro_id', 'name', 'height_m', 'scene_id', 'overpass_time', 'held_out', 'label',
           'summit_cloud', 'low_cloud', 'photo_step', 'photo_links'] + (['rag'] if 'rag' in cards else []) + ANSWER_COLUMNS
checks = cards[~missing].reindex(columns = columns).fillna('').astype(str)
if old is not None: #a card already in the csv keeps its row as it was when picked, answers and all, even if it
                    #would no longer be picked (the labeller changed, or the scan grew); new cards are added after it
    checks = pd.concat([old.reindex(columns = columns), checks[~checks['image'].isin(old['image'])]], ignore_index = True)
checks = checks.fillna('')
checks.to_csv(CHECKS_CSV, index = False)


####### Step 5 The review page #########

data = json.dumps({'columns': columns, 'rows': checks.astype(str).to_dict('records')})
html = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Satellite view review</title>
<style>
:root { --ink:#1f2a3a; --paper:#f7f5f0; --line:#d8d3c8; --gold:#f5b700; --muted:#6b7380; --sky:#eaf2fa; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.4 -apple-system, system-ui, sans-serif; color:var(--ink); background:var(--paper); }
header { position:sticky; top:0; z-index:1; background:var(--ink); color:#fff; padding:10px 16px;
         display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
header h1 { font-size:17px; margin:0; }
header button { font:inherit; padding:6px 12px; border:0; border-radius:6px; background:var(--gold); color:var(--ink);
                font-weight:600; cursor:pointer; }
header label { font-size:14px; }
.key { max-width:1100px; margin:12px auto 0; padding:0 16px; color:var(--muted); font-size:14px; }
main { max-width:1100px; margin:0 auto; padding:16px; display:grid; gap:16px; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:12px; display:grid;
        grid-template-columns:minmax(0, 480px) minmax(0, 1fr); gap:16px; }
.card.done { border-color:#9bbf8a; }
.card img { width:100%; height:auto; border-radius:6px; }
.meta p { margin:4px 0; }
.muted { color:var(--muted); font-size:13px; }
.step { margin:12px 0; }
.step h3 { font-size:15px; margin:0 0 6px; }
.buttons { display:flex; gap:8px; flex-wrap:wrap; }
.buttons button { font:inherit; padding:8px 14px; border:1px solid var(--line); border-radius:6px; background:#fff;
                  cursor:pointer; min-width:64px; }
.buttons button.on { background:var(--ink); color:#fff; border-color:var(--ink); }
.buttons button:disabled { cursor:default; opacity:.6; }
.photo { background:var(--sky); border-radius:8px; padding:8px 10px; }
input.notes { width:100%; font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px; }
@media (max-width:800px) { .card { grid-template-columns:minmax(0, 1fr); } }
</style></head>
<body>
<header><h1>Satellite views, __BATCH__</h1><span id="count"></span>
<label><input type="checkbox" id="todo"> only show unfinished</label>
<button id="download">Download CSV</button></header>
<p class="key">Each view is 8 km across, centred on the summit (triangle). The gold line is where low ground starts,
300 m below the summit. An inversion: cloud filling the low ground, the top clear. Cloud in the sky casts a
shadow beside it and ignores the terrain; a cloud sea follows the glens and casts none. Answer from the satellite view
alone; on some cards a ground photo is revealed afterwards, and your first answer is then locked.</p>
<main id="cards"></main>
<script>
const DATA = __DATA__;
const KEY = 'satellite-__BATCH__-checks';
const ANSWERS = ['visible', 'photo_shows', 'notes'];
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
for (const row of DATA.rows) {
  const s = saved[row.image] || {};
  for (const a of ANSWERS) if (s[a] && !row[a]) row[a] = s[a]; //the csv wins; the browser only fills its gaps
}
function store() {
  const out = {};
  for (const row of DATA.rows) out[row.image] = Object.fromEntries(ANSWERS.map(a => [a, row[a]]));
  try { localStorage.setItem(KEY, JSON.stringify(out)); } catch (e) {}
}
const needsPhoto = row => row.photo_step === 'True';
const finished = row => row.visible && (!needsPhoto(row) || row.photo_shows);
function count() {
  const done = DATA.rows.filter(finished).length;
  document.getElementById('count').textContent = done + ' of ' + DATA.rows.length + ' done';
}
function buttons(row, field, choices, locked) {
  const box = document.createElement('div');
  box.className = 'buttons';
  for (const [value, text] of choices) {
    const b = document.createElement('button');
    b.textContent = text;
    if (row[field] === value) b.className = 'on';
    b.disabled = locked;
    b.onclick = () => { row[field] = row[field] === value ? '' : value; store(); count(); render(); };
    box.appendChild(b);
  }
  return box;
}
function render() {
  const todo = document.getElementById('todo').checked;
  const main = document.getElementById('cards');
  main.innerHTML = '';
  DATA.rows.forEach((row, i) => {
    if (todo && finished(row)) return;
    const card = document.createElement('section');
    card.className = 'card' + (finished(row) ? ' done' : '');
    card.innerHTML = '<a href="' + row.image + '" target="_blank"><img src="' + row.image + '" alt="" loading="lazy"></a>' +
      '<div class="meta"><p><strong>' + (i + 1) + '. ' + row.name + '</strong> (' + Math.round(row.height_m) + ' m)</p>' +
      '<p>' + row.date + ', pass ' + row.overpass_time.slice(11) + ' UTC</p>' +
      '<div class="step"><h3>Is an inversion visible in the satellite view?</h3></div></div>';
    const meta = card.querySelector('.meta');
    const photoShown = needsPhoto(row) && row.visible;
    meta.querySelector('.step').appendChild(
      buttons(row, 'visible', [['Y', 'Yes'], ['N', 'No'], ['unclear', 'Unclear']], photoShown && !!row.photo_shows));
    if (photoShown) {
      const step = document.createElement('div');
      step.className = 'step photo';
      const links = row.photo_links.split(' ').map((l, j) =>
        '<a href="' + l + '" target="_blank" rel="noopener">photo ' + (j + 1) + '</a>').join(' · ');
      step.innerHTML = '<h3>Ground photo (Geograph, same day, within 10 km): does it show an inversion?</h3><p>' + links + '</p>';
      step.appendChild(buttons(row, 'photo_shows', [['Y', 'Yes'], ['N', 'No'], ['no_view', "Doesn't show the view"]], false));
      meta.appendChild(step);
    } else if (needsPhoto(row)) {
      meta.insertAdjacentHTML('beforeend', '<p class="muted">A ground photo is revealed after you answer.</p>');
    }
    meta.insertAdjacentHTML('beforeend', '<input class="notes" placeholder="notes (optional)">' +
      (row.held_out === 'True' ? '<p class="muted">held-out day</p>' : ''));
    const notes = meta.querySelector('.notes');
    notes.value = row.notes || '';
    notes.oninput = () => { row.notes = notes.value; store(); };
    main.appendChild(card);
  });
}
function csvCell(v) {
  v = v == null ? '' : String(v);
  return /[",\\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}
document.getElementById('download').onclick = () => {
  const lines = [DATA.columns.join(',')].concat(DATA.rows.map(r => DATA.columns.map(c => csvCell(r[c])).join(',')));
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([lines.join('\\n') + '\\n'], {type: 'text/csv'}));
  a.download = 'satellite___BATCH___checks.csv';
  a.click();
};
document.getElementById('todo').onchange = render;
count();
render();
</script></body></html>
""".replace('__DATA__', data).replace('__BATCH__', BATCH)
with open(os.path.join(BATCH_DIR, 'review.html'), 'w', encoding = 'utf-8') as f:
    f.write(html)
print('Open {}/review.html in a browser; {} cards, {} already answered'.format(
    BATCH_DIR, len(checks), (checks['visible'] != '').sum()))
