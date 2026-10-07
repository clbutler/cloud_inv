#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 6 2026

@author: chrisbutler

Tests the satellite labeller against the hand-checked sightings in data/inversion_sightings.csv:
does it say 'inversion' on the days a photo showed one, and not on the days it didn't? Run from scripts/:
    python main_satellite_sightings.py
A sighting near a munro is checked at that munro. Any other is checked where the photo was taken, with the
highest ground within 1 km as its summit; photos within about 2 km of each other on the same day count once.
"""

import geopandas as gpd
import numpy as np
import pandas as pd

from openmeteo_function import munro_locations
from satellite_function import munro_grids, observe, terrain

SIGHTINGS_CSV = '../data/inversion_sightings.csv'
OUTPUT_CSV = '../outputs/satellite_vs_sightings.csv'
SPOT_DEG = 0.02 #photos not near a munro are grouped into spots this many degrees across, about 2 km


sightings = pd.read_csv(SIGHTINGS_CSV, dtype = {'checked': str, 'inversion': str, 'munro_id': 'Int64'})
sightings = sightings[sightings['checked'] == 'Y']
munros = munro_locations(gpd.read_file('../outputs/munro.shp')).astype({'munro_id': int}) #the shapefile stores the id as text

# a site is a munro, or a ~2 km spot for photos elsewhere
spot_lat = (sightings['lat'] / SPOT_DEG).round() * SPOT_DEG
spot_lon = (sightings['lon'] / SPOT_DEG).round() * SPOT_DEG
sightings['site_id'] = np.where(sightings['munro_id'].notna(), 'munro-' + sightings['munro_id'].astype(str),
                                'spot-' + spot_lat.round(2).astype(str) + '_' + spot_lon.round(2).astype(str))
spots = (sightings[sightings['munro_id'].isna()].assign(lat = spot_lat, lon = spot_lon)
         .groupby('site_id').agg(name = ('place', 'first'), lat = ('lat', 'first'), lon = ('lon', 'first'),
                                 country = ('country', 'first'))
         .reset_index().assign(height_m = np.nan))
munro_sites = (munros[munros['munro_id'].isin(sightings['munro_id'].dropna())]
               .assign(site_id = lambda d: 'munro-' + d['munro_id'].astype(str), country = 'Scotland'))
sites = pd.concat([munro_sites[['site_id', 'name', 'lat', 'lon', 'height_m', 'country']], spots], ignore_index = True)

# one verdict per site and day: Y if any photo of it that day showed an inversion
verdicts = (sightings.groupby(['date', 'site_id'])
            .agg(inversion = ('inversion', lambda x: 'Y' if (x == 'Y').any() else 'N'), photos = ('link', 'size'),
                 links = ('link', ' '.join))
            .reset_index())
print('{} sites, {} site-days ({} Y, {} N) on {} days'.format(len(sites), len(verdicts),
      (verdicts['inversion'] == 'Y').sum(), (verdicts['inversion'] == 'N').sum(), verdicts['date'].nunique()))

print('Reading terrain for {} sites'.format(len(sites)))
dem = terrain(munro_grids(sites), id_col = 'site_id')
results = []
for date, day in verdicts.groupby('date'):
    obs = observe(sites[sites['site_id'].isin(day['site_id'])], date, date, id_col = 'site_id', dem = dem)
    results.append(day.merge(obs, on = ['site_id', 'date'], how = 'left') if len(obs) else day)

results = pd.concat(results, ignore_index = True)
results['label'] = results['label'].fillna('no_pass') #no sentinel-2 scene covered the site that day
results = results.merge(sites[['site_id', 'name', 'country', 'lat', 'lon']], on = 'site_id')
results.to_csv(OUTPUT_CSV, index = False)

print('\nYour verdict (rows) against the satellite label (columns), site-days:')
print(pd.crosstab(results['inversion'], results['label'], margins = True))
seen = results[~results['label'].isin(['no_pass', 'no_data'])]
print('\n{} site-days with a usable satellite view; saved to {}'.format(len(seen), OUTPUT_CSV))
