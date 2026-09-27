#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 21:59:03 2025

@author: chrisbutler

Builds the cloudflip map: every munro coloured by its inversion RAG, one layer per morning.
Each popup has a side-on picture of the hill drawn from its own forecast, a plain-English verdict
and the four checks with icons. A "How does this work?" panel explains the checks.
"""

import sqlite3

import folium
import pandas as pd


RAG_COLOURS = {'Green': '#2e9e5b', 'Amber': '#f0a202', 'Red': '#d64541'}
RAG_WORDS = {'Green': 'Likely', 'Amber': 'Possible', 'Red': 'Unlikely'}
GRADE_MARKS = {2: ('&#10003;', '#2e9e5b'), 1: ('~', '#d08c00'), 0: ('&#10007;', '#d64541')} #tick, partial, cross

LOGO_SVG = '''<svg width="44" height="44" viewBox="0 0 48 48" aria-hidden="true">
  <path d="M6 34 L16 11 L24 23 L32 11 L42 34" fill="none" stroke="#2b3a55" stroke-width="4.5"
        stroke-linejoin="round" stroke-linecap="round"/>
  <path d="M3 40 a6 6 0 0 1 8.5-6.5 a7.5 7.5 0 0 1 12.5-3 a7.5 7.5 0 0 1 12.5 3 a6 6 0 0 1 8.5 6.5 z"
        fill="#ffffff" stroke="#8fb3d9" stroke-width="2" stroke-linejoin="round"/>
</svg>'''

# icons for the four checks, defined once in the page and reused by every popup with <use href="#icon-...">
ICON_SYMBOLS = '''<svg width="0" height="0" style="position:absolute" aria-hidden="true">
  <symbol id="icon-lid" viewBox="0 0 24 24">
    <rect x="9" y="3" width="6" height="13" rx="3" fill="none" stroke="#e07b00" stroke-width="2"/>
    <circle cx="12" cy="18" r="4" fill="#e07b00"/><rect x="11" y="8" width="2" height="9" fill="#e07b00"/>
    <path d="M17 7 h5 M17 11 h4" stroke="#e07b00" stroke-width="1.6" stroke-dasharray="2 1.5"/>
  </symbol>
  <symbol id="icon-cloud" viewBox="0 0 24 24">
    <path d="M6 18 a4 4 0 0 1 0-8 a5.5 5.5 0 0 1 10.5-1.5 a4 4 0 0 1 1.5 9.5 z" fill="#dfe8f2" stroke="#6f8fb3" stroke-width="1.6"/>
  </symbol>
  <symbol id="icon-summit" viewBox="0 0 24 24">
    <circle cx="18" cy="6" r="3.2" fill="#f5b800"/>
    <path d="M2 21 L10 8 L14 14 L16 11 L22 21 z" fill="#6b7f6a"/>
  </symbol>
  <symbol id="icon-wind" viewBox="0 0 24 24">
    <path d="M3 8 h11 a3 3 0 1 0 -3-3 M3 13 h15 a3 3 0 1 1 -3 3 M3 18 h7" fill="none" stroke="#5a6b7b"
          stroke-width="1.8" stroke-linecap="round"/>
  </symbol>
</svg>'''

CHECK_NAMES = [('icon-lid', 'Warm lid'), ('icon-cloud', 'Cloud below'),
               ('icon-summit', 'Clear summit'), ('icon-wind', 'Still air')]


def to_uk_time(utc_text, fmt):
    '''converts a UTC time string from the database to UK local time text'''
    time = pd.Timestamp(utc_text)
    if time.tzinfo is None: #forecast times are stored without the Z, run times with it
        time = time.tz_localize('UTC')
    return time.tz_convert('Europe/London').strftime(fmt)


def check_values(row):
    '''short plain-English value for each of the four checks'''
    if pd.isna(row['lid_lapse_c_per_km']):
        lid = 'not enough forecast levels below the top to tell'
    elif row['lid_lapse_c_per_km'] > 0:
        lid = 'warmer layer at ~{:.0f} m'.format(row['lid_top_m'])
    elif row['lid_grade'] == 1:
        lid = 'weak, air barely cools with height'
    else:
        lid = 'none, air cools with height'
    cloud = 'damp air ({:.0f}% humidity)'.format(row['below_max_rh']) if pd.notna(row['below_max_rh']) else 'nothing to check'
    summit = 'dry ({:.0f}% humidity)'.format(row['summit_rh']) if row['clear_top_grade'] == 2 else \
             'hazy ({:.0f}% humidity)'.format(row['summit_rh']) if row['clear_top_grade'] == 1 else \
             'in cloud ({:.0f}% humidity)'.format(row['summit_rh'])
    wind = '{:.0f} km/h below the top'.format(row['below_max_wind_kmh'])
    return [lid, cloud, summit, wind]


def verdict(row):
    '''one plain-English sentence summing up the morning'''
    if row['rag'] == 'Green':
        return 'Good chance of standing above a sea of cloud.'
    if row['rag'] == 'Amber':
        return 'Some chance of a cloud sea below the summit, worth keeping an eye on.'
    good = []
    if row['lid_grade'] == 2:
        good.append('a warm lid sits at ~{:.0f} m'.format(row['lid_top_m']))
    if row['moisture_grade'] == 2:
        good.append('the glens are damp')
    if row['clear_top_grade'] == 2:
        good.append('the summit should be clear')
    if pd.isna(row['lid_lapse_c_per_km']):
        bad = 'the forecast can\'t show a warm lid this far below the summit'
    elif row['lid_grade'] == 0:
        bad = 'there is no warm lid to trap cloud in the glens'
    elif row['moisture_grade'] == 0:
        bad = 'the air below the summit is too dry for a cloud sea'
    elif row['clear_top_grade'] == 0:
        bad = 'the summit is likely to be in the cloud, not above it'
    else:
        bad = '{:.0f} km/h winds would probably break the cloud up'.format(row['below_max_wind_kmh'])
    if not good:
        return bad[0].upper() + bad[1:] + '.'
    good_text = ', '.join(good[:-1]) + ' and ' + good[-1] if len(good) > 1 else good[0]
    return '{}, but {}.'.format(good_text[0].upper() + good_text[1:], bad)


def hill_picture(row):
    '''a side-on picture of the hill drawn from its forecast: cloud sea, warm lid, wind and a sunny or cloudy top'''
    ground, summit = row['model_elevation_m'], row['height_m']
    top_y, base_y = 34, 128

    def y_of(height_m):
        '''converts a height in metres to a y position, glen floor at the bottom and summit near the top'''
        fraction = (height_m - ground) / max(summit - ground, 1)
        return base_y - min(max(fraction, 0), 1) * (base_y - top_y)

    parts = ['<rect width="280" height="140" rx="8" fill="#e8f3fc"/>']
    if row['clear_top_grade'] == 2:
        parts.append('<circle cx="236" cy="26" r="11" fill="#f5b800"/>')
    parts.append('<path d="M20 {b} L78 86 L100 98 L140 {t} L186 92 L206 84 L262 {b} Z" fill="#7b8f79"/>'.format(
        b = base_y, t = top_y))
    parts.append('<path d="M126 {0} L140 {1} L154 {0} Z" fill="#a9b8a7"/>'.format(top_y + 16, top_y))

    # cloud sea: up to the lid if there is one below the summit, otherwise about halfway up
    if row['moisture_grade'] > 0:
        lid_below = pd.notna(row['lid_top_m']) and row['lid_top_m'] < summit
        sea_y = y_of(row['lid_top_m']) if lid_below else (base_y + top_y) / 2 + 12
        opacity = 0.95 if row['moisture_grade'] == 2 else 0.55
        waves = ''.join(' q 10 -7 20 0 q 10 7 20 0' for _ in range(7))
        parts.append('<path d="M0 {y:.0f}{w} V140 H0 Z" fill="#ffffff" opacity="{o}"/>'.format(
            y = sea_y, w = waves, o = opacity))

    if row['lid_grade'] > 0 and pd.notna(row['lid_top_m']):
        lid_y = y_of(row['lid_top_m']) - 4
        parts.append('<line x1="8" x2="272" y1="{y:.0f}" y2="{y:.0f}" stroke="#e07b00" stroke-width="2" '
                     'stroke-dasharray="6 4" opacity="{o}"/>'.format(y = lid_y, o = 1 if row['lid_grade'] == 2 else 0.5))
        parts.append('<text x="10" y="{y:.0f}" font-size="10" fill="#b35f00" stroke="#e8f3fc" stroke-width="3" paint-order="stroke">warm lid ~{h:.0f} m</text>'.format(
            y = lid_y - 4, h = row['lid_top_m']))

    if row['clear_top_grade'] == 0: #summit in the cloud
        parts.append('<path d="M112 {y} a9 9 0 0 1 12 -9 a12 12 0 0 1 22 -2 a9 9 0 0 1 16 11 z" fill="#c9d3dc"/>'.format(
            y = top_y + 8))

    streaks = 0 if row['wind_grade'] == 2 else 1 if row['wind_grade'] == 1 else 3
    for i in range(streaks):
        y = 100 + i * 9
        parts.append('<path d="M{x} {y} h26 l-5 -3 m5 3 l-5 3" fill="none" stroke="#3d4b58" stroke-width="1.6" '
                     'stroke-linecap="round"/>'.format(x = 196 + (i % 2) * 14, y = y))
    if streaks:
        parts.append('<text x="194" y="{y}" font-size="10" fill="#3d4b58" stroke="#e8f3fc" stroke-width="3" paint-order="stroke">{w:.0f} km/h</text>'.format(
            y = 94, w = row['below_max_wind_kmh']))

    parts.append('<text x="140" y="{y}" font-size="10" text-anchor="middle" fill="#2b3a55">{h:.0f} m</text>'.format(
        y = top_y - 6, h = summit))
    return '<svg viewBox="0 0 280 140" width="100%" style="display:block;border-radius:8px">{}</svg>'.format(''.join(parts))


def popup_html(row):
    '''the popup shown when a munro is clicked'''
    checks = ''
    grades = [row['lid_grade'], row['moisture_grade'], row['clear_top_grade'], row['wind_grade']]
    for (icon, name), grade, value in zip(CHECK_NAMES, grades, check_values(row)):
        mark, colour = GRADE_MARKS[grade]
        checks += '''<div style="display:flex;gap:6px;align-items:flex-start;margin:3px 0">
            <svg width="18" height="18" style="flex:none"><use href="#{icon}"/></svg>
            <div><b>{name}</b> <span style="color:{colour};font-weight:700">{mark}</span><br>
            <span style="color:#555">{value}</span></div></div>'''.format(
            icon = icon, name = name, colour = colour, mark = mark, value = value)
    return '''<div style="font-family:system-ui,sans-serif;font-size:12px;width:280px">
        <div style="font-size:15px;font-weight:600">{name}</div>
        <div style="color:#555;margin-bottom:4px">{height:.0f} m &middot; best time {hour} &middot;
            <span style="color:{colour};font-weight:700">{word}</span></div>
        {picture}
        <div style="margin:6px 0 4px;font-style:italic">{verdict}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;column-gap:8px">{checks}</div>
        <div style="margin-top:4px;color:#777">Wind on the summit itself {wind:.0f} km/h &middot; pressure {pmsl:.0f} hPa</div>
        </div>'''.format(name = row['name'], height = row['height_m'], hour = to_uk_time(row['best_hour'], '%H:%M'),
                         colour = RAG_COLOURS[row['rag']], word = RAG_WORDS[row['rag']], picture = hill_picture(row),
                         verdict = verdict(row), checks = checks, wind = row['summit_wind_kmh'], pmsl = row['pressure_msl'])


EXPLAINER_PICTURE = '''<svg viewBox="0 0 320 170" width="100%" style="display:block;border-radius:8px" aria-hidden="true">
  <rect width="320" height="170" rx="8" fill="#e8f3fc"/>
  <circle cx="272" cy="30" r="13" fill="#f5b800"/>
  <path d="M10 160 L90 100 L120 112 L170 38 L220 106 L240 98 L310 160 Z" fill="#7b8f79"/>
  <path d="M154 60 L170 38 L186 60 Z" fill="#a9b8a7"/>
  <path d="M0 112 q 10 -7 20 0 q 10 7 20 0 q 10 -7 20 0 q 10 7 20 0 q 10 -7 20 0 q 10 7 20 0 q 10 -7 20 0 q 10 7 20 0
           q 10 -7 20 0 q 10 7 20 0 q 10 -7 20 0 q 10 7 20 0 q 10 -7 20 0 q 10 7 20 0 q 10 -7 20 0 q 10 7 20 0 V170 H0 Z"
        fill="#ffffff" opacity="0.95"/>
  <line x1="6" x2="314" y1="100" y2="100" stroke="#e07b00" stroke-width="2" stroke-dasharray="6 4"/>
  <text x="8" y="95" font-size="10" fill="#b35f00" stroke="#e8f3fc" stroke-width="3" paint-order="stroke">warm lid: warmer air above traps the cold, damp air below</text>
  <text x="14" y="140" font-size="10" fill="#4a6078">cloud sea: fog and low cloud filling the glens</text>
  <text x="194" y="62" font-size="10" fill="#2b3a55">summit in sunshine</text>
</svg>'''


def explainer_html():
    '''the "How does this work?" button and panel'''
    rows = [
        ('icon-lid', 'Warm lid', 'Normally air gets colder as you climb. Sometimes a layer of warmer air sits part-way up '
                                 'the hill, like a lid. Cold, damp air is trapped underneath it.'),
        ('icon-cloud', 'Cloud below', 'There needs to be enough moisture under the lid for fog or low cloud to form in the '
                                      'glens (humidity of 95% or more).'),
        ('icon-summit', 'Clear summit', 'The summit has to poke out above the lid into dry air, otherwise you are standing '
                                        'inside the cloud rather than above it.'),
        ('icon-wind', 'Still air', 'Wind in the glens stirs the layers together and breaks the lid. Light winds '
                                   '(about 11 km/h or less) let the cloud sea settle.'),
        ]
    items = ''.join('''<div style="display:flex;gap:8px;margin:8px 0">
        <svg width="26" height="26" style="flex:none"><use href="#{}"/></svg>
        <div><b>{}</b><br>{}</div></div>'''.format(*r) for r in rows)
    return '''
    <button onclick="document.getElementById('cf-explainer').hidden=false"
        style="margin-top:8px;border:1px solid #8fb3d9;background:#f2f7fc;color:#2b3a55;border-radius:6px;
               padding:4px 10px;font:inherit;cursor:pointer">How does this work?</button>
    <div id="cf-explainer" hidden style="position:fixed;inset:0;z-index:2000;background:rgba(20,30,45,0.45);
        display:flex;align-items:center;justify-content:center;padding:16px"
        onclick="if(event.target===this)this.hidden=true">
      <div style="background:#fff;border-radius:12px;max-width:520px;width:100%;max-height:90vh;overflow:auto;
                  padding:16px 18px;box-shadow:0 6px 24px rgba(0,0,0,0.3);font-size:13px;color:#333">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div style="font-size:18px;font-weight:700;color:#2b3a55">What is a cloud inversion?</div>
          <button onclick="document.getElementById('cf-explainer').hidden=true" aria-label="Close"
              style="border:none;background:none;font-size:22px;cursor:pointer;color:#555">&times;</button>
        </div>
        <p>On the best mornings you climb out of the fog in the glen and stand in sunshine above a sea of cloud.
           cloudflip checks the Met Office forecast for four things that make that happen:</p>
        {picture}
        {items}
        <p><b>Colours:</b> <span style="color:#2e9e5b;font-weight:700">Likely</span> = all four look good;
           <span style="color:#d08c00;font-weight:700">Possible</span> = all four are at least borderline;
           <span style="color:#d64541;font-weight:700">Unlikely</span> = at least one is missing.
           Each Munro is scored for the hours around sunrise, when inversions are most common.</p>
        <p style="color:#666">Inversions are hard to forecast, and the models often get the exact height wrong,
           so treat this as a guide rather than a promise.</p>
      </div>
    </div>'''.format(picture = EXPLAINER_PICTURE, items = items)


def header_html(run_time):
    '''the cloudflip title box with the data timestamp, colour key, explainer and credits'''
    key = ''.join('<span style="display:inline-flex;align-items:center;margin-right:10px">'
                  '<span style="width:11px;height:11px;border-radius:50%;background:{};margin-right:4px;'
                  'border:1px solid #fff;box-shadow:0 0 0 1px #999"></span>{}</span>'.format(RAG_COLOURS[rag], word)
                  for rag, word in RAG_WORDS.items())
    return '''{symbols}
    <div style="position:fixed;top:12px;left:56px;z-index:1000;max-width:calc(100vw - 80px);
                background:rgba(255,255,255,0.95);border-radius:10px;padding:10px 14px;
                box-shadow:0 2px 8px rgba(0,0,0,0.2);font-family:system-ui,sans-serif;font-size:12px;color:#333">
        <div style="display:flex;align-items:center;gap:8px">
            {logo}
            <div>
                <div style="font-size:22px;font-weight:700;color:#2b3a55;line-height:1">cloudflip</div>
                <div style="color:#555">Cloud inversion outlook for Scotland's Munros</div>
            </div>
        </div>
        <div style="margin-top:8px">{key}</div>
        <div style="margin-top:6px;color:#555">Forecast fetched {fetched} &middot; pick a morning top right</div>
        <div style="margin-top:4px;color:#777">Developed by Dr Chris Butler &middot; Weather data by
            <a href="https://open-meteo.com/" target="_blank">Open-Meteo.com</a> (Met Office model)
            &middot; Hill data: Database of British and Irish Hills</div>
        {explainer}
        </div>'''.format(symbols = ICON_SYMBOLS, logo = LOGO_SVG, key = key,
                         fetched = to_uk_time(run_time, '%a %d %b %H:%M'), explainer = explainer_html())


def build_map(db_path, output_file, run_time = None):
    '''creates the cloudflip html map from the scores table (the latest run by default)'''
    with sqlite3.connect(db_path) as conn:
        if run_time is None:
            run_time = conn.execute('SELECT MAX(run_time) FROM scores').fetchone()[0]
        scores = pd.read_sql('''SELECT s.*, m.name, m.height_m, m.lat, m.lon, m.model_elevation_m FROM scores s
                                JOIN munros m USING (munro_id) WHERE s.run_time = ?''', conn, params = (run_time,))

    m = folium.Map([57.0, -4.6], zoom_start = 7, tiles = None)
    folium.TileLayer( #OSM's servers block pages opened from a local file, and CARTO now needs an API key
        tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        attr = 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, USGS, OpenStreetMap contributors, and the GIS User Community',
        control = False).add_to(m)

    for i, (date, day) in enumerate(scores.groupby('date')):
        counts = day['rag'].value_counts()
        label = '{} &nbsp;<span style="color:#777">({} green, {} amber)</span>'.format(
            pd.Timestamp(date).strftime('%a %d %b'), counts.get('Green', 0), counts.get('Amber', 0))
        layer = folium.FeatureGroup(name = label, overlay = False, show = (i == 0)) #overlay=False makes it a one-at-a-time choice
        for _, row in day.sort_values('rag_value').iterrows(): #reds first, so greens draw on top
            folium.CircleMarker(
                location = [row['lat'], row['lon']], radius = 7, weight = 1, color = '#ffffff',
                fill = True, fill_color = RAG_COLOURS[row['rag']], fill_opacity = 0.9,
                tooltip = '{} ({})'.format(row['name'], RAG_WORDS[row['rag']]),
                popup = folium.Popup(popup_html(row), max_width = 300)
                ).add_to(layer)
        layer.add_to(m)

    folium.LayerControl(collapsed = False, position = 'topright').add_to(m)
    m.get_root().header.add_child(folium.Element('<title>cloudflip</title><style>[hidden]{display:none!important}</style>'))
    m.get_root().html.add_child(folium.Element(header_html(run_time)))
    m.save(output_file)
    return scores
