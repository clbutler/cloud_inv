#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 2026

@author: chrisbutler

Finds usable Sentinel-2 passes over the munros to put on the review page, before anyone labels anything.
Every pass is too many (about 8,000 scenes a year over Scotland), so it samples: the same number of days
from each calendar month, spread over every year since 2017, and a few random munros on each day.
Each site-day gets the labeller's verdict, so the rule can pick candidates from them. Run from scripts/:
    python main_satellite_scan.py        # 40 days a month
    python main_satellite_scan.py 60     # more days a month
Re-running skips the days already in the csv, so a stopped scan carries on where it left off.
"""

import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from openmeteo_function import munro_locations
from satellite_function import munro_grids, observe, search, terrain

SCAN_CSV = '../outputs/satellite_scan.csv'
SCENES_CSV = '../outputs/satellite_scan_scenes.csv'
COLUMNS = ['munro_id', 'scene_id', 'overpass_time', 'date', 'scene_cloud_pct', 'height_m', 'low_drop_m', 'summit_valid',
           'low_valid', 'summit_cloud', 'low_cloud', 'cirrus', 'label', 'held_out']
FIRST_YEAR, LAST_YEAR = 2017, 2026
HELD_OUT_FROM = '2022-01-01' #days from here on are kept for the fair test, every site on them together
MUNROS_PER_SCENE = 2 #random munros checked in each scene of a sampled day...
SCENES_PER_DAY = 2 #...and at most this many scenes (tiles) a day, so no one morning dominates
USABLE = {'eo:cloud_cover': {'gte': 5, 'lte': 95}, 's2:nodata_pixel_percentage': {'lte': 50}} #no cloud can't be an
                                                                  #inversion, all cloud can't show one; half-empty tiles waste reads

days_per_month = int(sys.argv[1]) if len(sys.argv) > 1 else 40
rng = np.random.default_rng(10)
munros = munro_locations(gpd.read_file('../outputs/munro.shp')).astype({'munro_id': int}) #the shapefile stores the id as text


####### Step 1 List the usable scenes in every year #########

if os.path.exists(SCENES_CSV): #kept so a re-run samples the same days, and skips the slow search
    scenes = pd.read_csv(SCENES_CSV)
else:
    scenes = []
    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        items = search('sentinel-2-l2a', '{}-01-01/{}-12-31'.format(year, year), query = USABLE)
        scenes += [dict(zip(['date', 'west', 'south', 'east', 'north'], [i.datetime.strftime('%Y-%m-%d'), *i.bbox]))
                   for i in items]
        print('{}: {} usable scenes'.format(year, len(items)))
    scenes = pd.DataFrame(scenes)
    scenes.to_csv(SCENES_CSV, index = False)


####### Step 2 Sample days evenly across the calendar, then munros within each day #########

done = set(pd.read_csv(SCAN_CSV)['date']) if os.path.exists(SCAN_CSV) else set()
all_days = pd.Series(sorted(scenes['date'].unique()))
picked = (all_days.groupby(all_days.str[5:7])
          .apply(lambda d: d.sample(min(days_per_month, len(d)), random_state = rng.integers(1e9)))
          .sort_values())
todo = [d for d in picked if d not in done]
print('Sampled {} days, {} still to scan'.format(len(picked), len(todo)))

plan = []
for date in todo:
    day = scenes[scenes['date'] == date]
    day = day.sample(min(SCENES_PER_DAY, len(day)), random_state = rng.integers(1e9))
    ids = set()
    for west, south, east, north in day[['west', 'south', 'east', 'north']].itertuples(index = False):
        inside = munros[munros['lon'].between(west, east) & munros['lat'].between(south, north)
                        & ~munros['munro_id'].isin(ids)]
        ids |= set(inside.sample(min(MUNROS_PER_SCENE, len(inside)), random_state = rng.integers(1e9))['munro_id'])
    plan.append((date, sorted(ids)))


####### Step 3 Label each site-day, saving as it goes #########

sites = munros[munros['munro_id'].isin({i for _, ids in plan for i in ids})]
print('Reading terrain for {} munros'.format(len(sites)))
dem = terrain(munro_grids(sites))
for n, (date, ids) in enumerate(plan, 1):
    obs = observe(sites[sites['munro_id'].isin(ids)], date, date, dem = dem) if ids else pd.DataFrame()
    if obs.empty: #no munro in the day's tiles, or every one sat in an empty part of its scene
        obs = pd.DataFrame({'date': [date], 'label': ['no_view']})
    obs['held_out'] = obs['date'] >= HELD_OUT_FROM
    obs = obs.reindex(columns = COLUMNS) #a no_view day has only a few, and the csv needs the same columns every row
    obs.to_csv(SCAN_CSV, mode = 'a', header = not os.path.exists(SCAN_CSV), index = False)
    if n % 25 == 0:
        print('{} of {} days scanned'.format(n, len(plan)))


####### Step 4 Summary #########

scan = pd.read_csv(SCAN_CSV)
scan = scan[~scan['label'].isin(['no_data', 'no_view'])]
print('\n{} usable site-days on {} days'.format(len(scan), scan['date'].nunique()))
print(pd.crosstab(scan['label'], scan['held_out'].map({False: 'before 2022', True: '2022 on'}), margins = True))
print('\nDays with an inversion label by month:')
print(scan[scan['label'] == 'inversion'].groupby(scan['date'].str[5:7])['date'].nunique())
