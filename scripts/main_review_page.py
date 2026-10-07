#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 8 2026

@author: chrisbutler

Writes outputs/satellite_images/review.html, a local page for filling in data/satellite_image_checks.csv:
each satellite image with its details, the Geograph photos, and buttons for whether an inversion is visible.
Answers are kept in the browser as you go; 'Download CSV' saves the finished sheet. Run from scripts/ after
main_satellite_images.py:
    python main_review_page.py
then open ../outputs/satellite_images/review.html and copy the downloaded csv over data/satellite_image_checks.csv
"""

import json

import pandas as pd

CHECKS_CSV = '../data/satellite_image_checks.csv'
PAGE = '../outputs/satellite_images/review.html'


checks = pd.read_csv(CHECKS_CSV, dtype = str, keep_default_na = False)
data = json.dumps({'columns': list(checks.columns), 'rows': checks.to_dict('records')})

html = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Satellite image review</title>
<style>
:root { --ink:#1f2a3a; --paper:#f7f5f0; --line:#d8d3c8; --gold:#f5b700; --muted:#6b7380; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.4 -apple-system, system-ui, sans-serif; color:var(--ink); background:var(--paper); }
header { position:sticky; top:0; z-index:1; background:var(--ink); color:#fff; padding:10px 16px;
         display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
header h1 { font-size:17px; margin:0; }
header button { font:inherit; padding:6px 12px; border:0; border-radius:6px; background:var(--gold); color:var(--ink);
                font-weight:600; cursor:pointer; }
header label { font-size:14px; }
main { max-width:1100px; margin:0 auto; padding:16px; display:grid; gap:16px; }
.card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:12px; display:grid;
        grid-template-columns:minmax(0, 480px) minmax(0, 1fr); gap:16px; }
.card.done { border-color:#9bbf8a; }
.card img { width:100%; height:auto; border-radius:6px; }
.meta p { margin:4px 0; }
.meta .muted { color:var(--muted); font-size:13px; }
.buttons { display:flex; gap:8px; flex-wrap:wrap; margin:12px 0 8px; }
.buttons button { font:inherit; padding:8px 14px; border:1px solid var(--line); border-radius:6px; background:#fff;
                  cursor:pointer; min-width:64px; }
.buttons button.on { background:var(--ink); color:#fff; border-color:var(--ink); }
input.notes { width:100%; font:inherit; padding:6px 8px; border:1px solid var(--line); border-radius:6px; }
@media (max-width:800px) { .card { grid-template-columns:minmax(0, 1fr); } }
</style></head>
<body>
<header><h1>Can you see an inversion in the satellite image?</h1><span id="count"></span>
<label><input type="checkbox" id="todo"> only show unanswered</label>
<button id="download">Download CSV</button></header>
<main id="cards"></main>
<script>
const DATA = ''' + data + ''';
const CHOICES = ['Y', 'N', 'maybe', 'unclear'];
const KEY = 'satellite-image-checks';
let saved = {};
try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
for (const row of DATA.rows) {
  const s = saved[row.image];
  if (s) { row.visible = s.visible; row.notes = s.notes; }
}
function store() {
  const out = {};
  for (const row of DATA.rows) out[row.image] = {visible: row.visible, notes: row.notes};
  try { localStorage.setItem(KEY, JSON.stringify(out)); } catch (e) {}
}
function count() {
  const done = DATA.rows.filter(r => r.visible).length;
  document.getElementById('count').textContent = done + ' of ' + DATA.rows.length + ' answered';
}
function render() {
  const todo = document.getElementById('todo').checked;
  const main = document.getElementById('cards');
  main.innerHTML = '';
  DATA.rows.forEach((row, i) => {
    if (todo && row.visible) return;
    const card = document.createElement('section');
    card.className = 'card' + (row.visible ? ' done' : '');
    const links = (row.links || '').split(' ').filter(Boolean)
      .map((l, j) => '<a href="' + l + '" target="_blank" rel="noopener">photo ' + (j + 1) + '</a>').join(' · ');
    card.innerHTML = '<a href="' + row.image + '" target="_blank"><img src="' + row.image + '" alt="" loading="lazy"></a>' +
      '<div class="meta"><p><strong>' + (i + 1) + '. ' + row.name + '</strong>, ' + row.country + '</p>' +
      '<p>' + row.date + ', pass ' + row.overpass_time.slice(11) + ' UTC</p>' +
      '<p>Photo check: <strong>' + row.photo_inversion + '</strong> · Satellite labeller: <strong>' +
      row.satellite_label + '</strong></p><p>Geograph: ' + links + '</p>' +
      '<div class="buttons"></div><input class="notes" placeholder="notes (optional)">' +
      '<p class="muted">' + row.image + '</p></div>';
    const buttons = card.querySelector('.buttons');
    for (const c of CHOICES) {
      const b = document.createElement('button');
      b.textContent = c;
      if (row.visible === c) b.className = 'on';
      b.onclick = () => { row.visible = row.visible === c ? '' : c; store(); count(); render(); };
      buttons.appendChild(b);
    }
    const notes = card.querySelector('.notes');
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
  a.download = 'satellite_image_checks.csv';
  a.click();
};
document.getElementById('todo').onchange = render;
count();
render();
</script></body></html>
'''

with open(PAGE, 'w', encoding = 'utf-8') as f:
    f.write(html)
print('Open {} in a browser; {} images, {} already answered'.format(PAGE, len(checks), (checks['visible'] != '').sum()))
