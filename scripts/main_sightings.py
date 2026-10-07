#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 6 2026

@author: chrisbutler

Collects candidate cloud inversion sightings into data/inversion_sightings.csv. Run from scripts/:
    python main_sightings.py
Re-running adds new photos and keeps the checked/notes columns you have filled in. Sightings from other
places (instagram, walkhighlands) can be added to the csv by hand with their own source.
"""

import geopandas as gpd

from geograph_function import geograph_sightings, update_sightings
from openmeteo_function import munro_locations

SIGHTINGS_CSV = '../data/inversion_sightings.csv'


munros = munro_locations(gpd.read_file('../outputs/munro.shp')).astype({'munro_id': int}) #the shapefile stores the id as text
found = geograph_sightings(munros)
sightings, added = update_sightings(found, SIGHTINGS_CSV)
print('Found {} Geograph photos on {} different days; {} new, {} rows in {}'.format(
      len(found), found['date'].nunique(), added, len(sightings), SIGHTINGS_CSV))
print('{} still to check'.format(sightings['checked'].ne('Y').sum()))
print(found.groupby('country').agg(photos = ('date', 'size'), days = ('date', 'nunique'),
                                   near_a_munro = ('munro_id', 'count')).to_string())
