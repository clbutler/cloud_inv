#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 2026

@author: chrisbutler

Scores past mornings with the site's own inversion score, from archived met office forecasts (the pressure levels
start 2024-08-13), and lines them up with what Sentinel-2 saw on the same days. Run from scripts/:
    python main_backcast.py forecast    # fetch and score the archived forecasts, about 2 hours (open-meteo limits)
    python main_backcast.py satellite   # label the satellite passes, about 20 minutes
    python main_backcast.py satellite redo   # the same, first clearing earlier labels (after a labeller change)
    python main_backcast.py compare     # the site's verdict against the satellite's
The two fetches can run at the same time, and each carries on where it left off if stopped.
Uses a spread of SITES munros rather than all 282: the archive counts every day of every munro against the
free daily limit. Months where (year * 12 + month) % 3 == 0 are held out for the fair test.
"""

import sqlite3
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from inversion_score_function import save_scores, score_run
from openmeteo_function import HISTORICAL_URL, fetch_forecast, munro_locations, save_forecast
from satellite_function import munro_grids, observe, save_observations, terrain

BACKCAST_DB = '../outputs/backcast.db'
SATELLITE_DB = '../outputs/satellite.db'
FIRST_DAY = '2024-08-13'
SITES = 40
CHUNK_WAIT = 12 * 60 #seconds between quarters; a quarter of 40 munros is about a fifth of the free hourly limit
USABLE = {'eo:cloud_cover': {'gte': 5, 'lte': 95}, 's2:nodata_pixel_percentage': {'lte': 50}}


def spread(munros, n):
    '''n munros spread across the map: each next one is the farthest from those already picked'''
    grids = munro_grids(munros)
    xy = grids[['easting', 'northing']].values
    picked = [int(np.argmax(xy[:, 1]))] #start in the far north
    gap = np.hypot(*(xy - xy[picked[0]]).T)
    while len(picked) < n:
        picked.append(int(np.argmax(gap)))
        gap = np.minimum(gap, np.hypot(*(xy - xy[picked[-1]]).T))
    return munros.iloc[sorted(picked)].reset_index(drop = True)


def held_out(dates):
    '''true for days in every third month'''
    d = pd.to_datetime(dates)
    return (d.dt.year * 12 + d.dt.month) % 3 == 0


step = sys.argv[1] if len(sys.argv) > 1 else 'compare'
munros = munro_locations(gpd.read_file('../outputs/munro.shp')).astype({'munro_id': int}) #the shapefile stores the id as text
sites = spread(munros, SITES)
yesterday = (pd.Timestamp.now('UTC') - pd.Timedelta(days = 1)).strftime('%Y-%m-%d')
quarters = pd.date_range(FIRST_DAY, yesterday, freq = 'QS').strftime('%Y-%m-%d').tolist()
chunks = list(zip([FIRST_DAY] + quarters, [(pd.Timestamp(q) - pd.Timedelta(days = 1)).strftime('%Y-%m-%d')
                                           for q in quarters] + [yesterday]))


####### Archived forecasts, scored as the site would have #########

if step == 'forecast':
    for n, (start, end) in enumerate(chunks):
        with sqlite3.connect(BACKCAST_DB) as conn:
            have = conn.execute("SELECT name FROM sqlite_master WHERE name = 'scores'").fetchone() and \
                   conn.execute('SELECT COUNT(*) FROM scores WHERE date BETWEEN ? AND ?', (start, end)).fetchone()[0]
        if have:
            continue
        print('Fetching {} to {}'.format(start, end))
        for attempt in range(3): #a quarter's reply is tens of MB, and a dropped connection cuts it short
            try:
                forecast, sunrise = fetch_forecast(sites, batch_size = 20, start_date = start, end_date = end,
                                                   api_url = HISTORICAL_URL)
                break
            except requests.exceptions.JSONDecodeError:
                if attempt == 2:
                    raise
                print('The reply was cut short; trying again in a minute')
                time.sleep(60)
        run_time = save_forecast(forecast, sunrise, sites, BACKCAST_DB)
        save_scores(score_run(BACKCAST_DB, run_time), BACKCAST_DB)
        if n < len(chunks) - 1:
            print('Scored; waiting {} minutes for the open-meteo limit'.format(CHUNK_WAIT // 60))
            time.sleep(CHUNK_WAIT)


####### What the satellite saw on the same days #########

if step == 'satellite':
    if 'redo' in sys.argv:
        with sqlite3.connect(SATELLITE_DB) as conn:
            conn.execute('DELETE FROM satellite_obs WHERE munro_id IN ({}) AND date >= ?'
                         .format(','.join(map(str, sites['munro_id']))), (FIRST_DAY,))
    dem = terrain(munro_grids(sites))
    for start in pd.date_range(FIRST_DAY, yesterday, freq = 'MS').union([pd.Timestamp(FIRST_DAY)]):
        end = min(start + pd.offsets.MonthEnd(0), pd.Timestamp(yesterday))
        with sqlite3.connect(SATELLITE_DB) as conn:
            done = conn.execute("SELECT name FROM sqlite_master WHERE name = 'satellite_obs'").fetchone() and \
                   conn.execute('SELECT COUNT(*) FROM satellite_obs WHERE munro_id IN ({}) AND date BETWEEN ? AND ?'
                                .format(','.join(map(str, sites['munro_id']))),
                                (start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))).fetchone()[0]
        if done:
            continue
        obs = observe(sites, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'), dem = dem, query = USABLE)
        if len(obs):
            save_observations(obs, SATELLITE_DB)


####### The site's verdict against the satellite's #########

if step == 'compare':
    with sqlite3.connect(BACKCAST_DB) as conn:
        scores = pd.read_sql('SELECT munro_id, date, rag, lid_grade, moisture_grade, clear_top_grade, wind_grade '
                             'FROM scores', conn)
    with sqlite3.connect(SATELLITE_DB) as conn:
        obs = pd.read_sql('SELECT * FROM satellite_obs WHERE date >= ?', conn, params = (FIRST_DAY,))
    joined = scores.merge(obs[obs['label'] != 'no_data'], on = ['munro_id', 'date'])
    joined['held_out'] = held_out(joined['date'])
    joined.to_csv('../outputs/backcast_vs_satellite.csv', index = False)
    print('{} munro-days with a score and a usable satellite view, on {} days'.format(len(joined), joined['date'].nunique()))
    print(pd.crosstab(joined['rag'], joined['label'], margins = True).reindex(['Green', 'Amber', 'Red', 'All']))
