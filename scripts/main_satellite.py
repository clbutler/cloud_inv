#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 6 2026

@author: chrisbutler

Checks the inversion scores against what Sentinel-2 saw. Run from scripts/:
    python main_satellite.py                          # every day the scores cover
    python main_satellite.py 2026-10-01 2026-10-06    # a date range
"""

import sqlite3
import sys

import pandas as pd

from satellite_function import observe, save_observations, compare

FORECAST_DB = '../outputs/forecasts.db'
SATELLITE_DB = '../outputs/satellite.db'
LABELS = ['inversion', 'clear', 'mixed', 'summit_cloud']


with sqlite3.connect(FORECAST_DB) as conn:
    munros = pd.read_sql('SELECT munro_id, name, height_m, lat, lon FROM munros', conn)
    first, last = conn.execute('SELECT min(date), max(date) FROM scores').fetchone()
start, end = sys.argv[1:3] if len(sys.argv) >= 3 else (first, min(last, pd.Timestamp.now('UTC').strftime('%Y-%m-%d')))


####### Step 1 Label what the satellite saw around each munro #########

obs = observe(munros, start, end)
if obs.empty:
    sys.exit('No Sentinel-2 view of any munro from {} to {}'.format(start, end))
save_observations(obs, SATELLITE_DB)
print(obs.pivot_table(index = 'date', columns = 'label', values = 'munro_id', aggfunc = 'count', fill_value = 0))


####### Step 2 Compare with the forecast made before each overpass #########

joined = compare(obs[obs['label'] != 'no_data'], FORECAST_DB)
joined.to_csv('../outputs/satellite_vs_scores.csv', index = False)
print('\n{} munro-days with a clear enough view and a forecast made before the overpass'.format(len(joined)))
print(pd.crosstab(joined['rag'], joined['label']).reindex(index = ['Green', 'Amber', 'Red'], columns = LABELS,
                                                          fill_value = 0))
