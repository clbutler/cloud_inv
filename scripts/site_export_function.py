#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 27 2026

@author: chrisbutler

Exports the latest run's scores for the cloudflip website (site/).
The data is written as a small script (window.CLOUDFLIP = {...}) rather than JSON, because browsers
block fetch() on pages opened straight from disk, but a <script> tag works both locally and when hosted.
"""

import json
import sqlite3

import pandas as pd


def hill_links(hills_csv):
    '''hill-bagging.co.uk page for each munro, from the hills database'''
    hills = pd.read_csv(hills_csv, encoding = 'latin1')
    hills = hills[hills['2021'] == 'MUN']
    return dict(zip(hills['DoBIH Number'].astype(int), hills['Hill-bagging'])) #the csv stores the id as text


def clean(value, digits = 1):
    '''rounds a number for the json, turning missing values into null'''
    return None if pd.isna(value) else round(float(value), digits)


def export_site_data(db_path, hills_csv, output_file, run_time = None):
    '''writes the munros and each day's scores for one run (the latest by default) to a js data file'''
    with sqlite3.connect(db_path) as conn:
        if run_time is None:
            run_time = conn.execute('SELECT MAX(run_time) FROM scores').fetchone()[0]
        scores = pd.read_sql('SELECT * FROM scores WHERE run_time = ?', conn, params = (run_time,))
        munros = pd.read_sql('SELECT * FROM munros', conn)
        sunrise = pd.read_sql('SELECT date, MIN(sunrise) AS sunrise FROM sunrise GROUP BY date', conn)

    links = hill_links(hills_csv)
    munro_list = [{'id': int(r['munro_id']), 'name': r['name'], 'h': clean(r['height_m'], 0),
                   'lat': r['lat'], 'lon': r['lon'], 'ground': clean(r['model_elevation_m'], 0),
                   'link': links.get(int(r['munro_id']))} for _, r in munros.iterrows()]

    sunrise = dict(zip(sunrise['date'], sunrise['sunrise']))
    days = []
    for date, day in scores.groupby('date'):
        day_scores = {}
        for _, r in day.iterrows():
            day_scores[int(r['munro_id'])] = {
                'r': int(r['rag_value']), 't': r['best_hour'],
                'g': [int(r['lid_grade']), int(r['moisture_grade']), int(r['clear_top_grade']), int(r['wind_grade'])],
                'lapse': clean(r['lid_lapse_c_per_km']), 'top': clean(r['lid_top_m'], 0),
                'rhb': clean(r['below_max_rh'], 0), 'clb': clean(r['below_max_cloud'], 0),
                'rhs': clean(r['summit_rh'], 0), 'mh': clean(r['mid_high_cloud'], 0),
                'wb': clean(r['below_max_wind_kmh'], 0), 'ws': clean(r['summit_wind_kmh'], 0),
                'p': clean(r['pressure_msl'], 0)}
        days.append({'date': date, 'sunrise': sunrise.get(date), 'scores': day_scores})

    data = {'meta': {'run_time': run_time, 'model': scores['model'].iloc[0]}, 'munros': munro_list, 'days': days}
    with open(output_file, 'w') as f:
        f.write('window.CLOUDFLIP = ')
        json.dump(data, f, separators = (',', ':'))
        f.write(';\n')
    return data
