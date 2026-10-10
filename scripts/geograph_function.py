#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 6 2026

@author: chrisbutler

Finds dated Geograph photos (geograph.org.uk) of cloud inversions in Britain, as candidate sightings to check the
satellite labels against; those near a munro also check the inversion score. Only the facts (when, where, link) are kept,
never the photos. No API key needed. Geograph records the day a photo was taken but not the time.
"""

import os

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer


API_URL = 'https://api.geograph.org.uk/api-facetql.php'
MATCH = '(inversion|inversions|"cloud sea"|"sea of cloud")' #searches titles, descriptions, tags and categories
FIELDS = ['id', 'takenday', 'title', 'realname', 'grid_reference', 'wgs84_lat', 'wgs84_long', 'vlat', 'vlong',
          'vgrlen', 'place', 'county', 'country']
COUNTRIES = ['Scotland', 'England', 'Wales'] #an inversion looks the same from above anywhere; only the score is scottish
MAX_KM = 15 #photos within this of a munro are matched to it
SINCE = '2017-01-01' #sentinel-2 images start in july 2015, but only every 2-5 days once sentinel-2b joined in 2017


def search_photos(match = MATCH, limit = 5000):
    '''every matching photo in britain and ireland; the whole result fits in one request'''
    response = requests.get(API_URL, timeout = 120, params = {'select': ','.join(FIELDS), 'match': match,
                                                              'limit': limit})
    response.raise_for_status()
    result = response.json()
    if 'rows' not in result:
        raise RuntimeError('Geograph search failed: {}'.format(result))
    return pd.DataFrame(result['rows'])


def photos_on_day(date, country = 'Scotland'):
    '''every photo taken in one country on one day (YYYY-MM-DD), whatever it shows, with lat/lon in degrees: where
    the photographer stood if given, otherwise what was photographed. The api can filter by day and country but not
    by distance, and returns at most 1000 rows, so a busy day across all of britain would be cut short'''
    where = "takenday='{}' and country='{}'".format(date.replace('-', ''), country)
    response = requests.get(API_URL, timeout = 120, params = {'select': ','.join(FIELDS), 'limit': 1000, 'where': where})
    response.raise_for_status()
    result = response.json()
    if 'rows' not in result:
        raise RuntimeError('Geograph search failed: {}'.format(result))
    if int(result['meta']['total_found']) > 1000:
        print('Geograph: {} has more than 1000 photos in {}; only the first 1000 are used'.format(date, country))
    photos = pd.DataFrame(result['rows'] or [], columns = FIELDS)
    has_view = photos['vgrlen'].fillna(0).astype(int) > 0
    return photos.assign(lat = np.degrees(np.where(has_view, photos['vlat'], photos['wgs84_lat']).astype(float)),
                         lon = np.degrees(np.where(has_view, photos['vlong'], photos['wgs84_long']).astype(float)))


def nearest_munro(photos, munros):
    '''adds the nearest munro and its distance, using OS grid metres'''
    to_grid = Transformer.from_crs('EPSG:4326', 'EPSG:27700', always_xy = True)
    px, py = to_grid.transform(photos['lon'].values, photos['lat'].values)
    mx, my = to_grid.transform(munros['lon'].values, munros['lat'].values)
    distance = np.hypot(px[:, None] - mx[None, :], py[:, None] - my[None, :])
    nearest = distance.argmin(axis = 1)
    photos['munro_id'] = munros['munro_id'].values[nearest]
    photos['munro_name'] = munros['name'].values[nearest]
    photos['distance_km'] = (distance[np.arange(len(photos)), nearest] / 1000).round(1)
    return photos


def geograph_sightings(munros, since = SINCE):
    '''one row per candidate photo in britain, taken since a date that has satellite images: date taken, place,
    the nearest munro if within MAX_KM, and a link to the photo page'''
    photos = search_photos()
    photos = photos[photos['country'].isin(COUNTRIES) & ~photos['takenday'].str.endswith('00') #00: day unknown
                    & (photos['takenday'] >= since.replace('-', ''))]
    # where the photographer stood if given (from a hill, looking down on the cloud), otherwise what was photographed;
    # geograph gives both in radians
    has_view = photos['vgrlen'].astype(int) > 0
    photos = photos.assign(lat = np.degrees(np.where(has_view, photos['vlat'], photos['wgs84_lat']).astype(float)),
                           lon = np.degrees(np.where(has_view, photos['vlong'], photos['wgs84_long']).astype(float)))
    photos = nearest_munro(photos.reset_index(drop = True), munros)
    far = photos['distance_km'] > MAX_KM
    photos['munro_id'] = photos['munro_id'].astype('Int64').mask(far)
    photos[['munro_name', 'distance_km']] = photos[['munro_name', 'distance_km']].mask(far)
    return pd.DataFrame({
        'date': pd.to_datetime(photos['takenday'], format = '%Y%m%d').dt.strftime('%Y-%m-%d'),
        'country': photos['country'], 'county': photos['county'], 'place': photos['place'],
        'munro_id': photos['munro_id'], 'munro_name': photos['munro_name'], 'distance_km': photos['distance_km'],
        'lat': photos['lat'].round(4), 'lon': photos['lon'].round(4), 'grid_reference': photos['grid_reference'],
        'source': 'geograph', 'source_id': photos['id'].astype(str), 'title': photos['title'].str.slice(0, 120),
        'photographer': photos['realname'], #geograph photos are CC BY-SA, so credit them if one is ever shown
        'link': 'https://www.geograph.org.uk/photo/' + photos['id'].astype(str),
        }).sort_values('date').reset_index(drop = True)


def update_sightings(new, csv_path):
    '''adds new candidates to the sightings csv, keeping any rows and checks already in it.
    filled in by hand: checked (Y once the photo has been looked at), inversion (Y if it shows a cloud inversion, N if not)
    and notes'''
    columns = list(new.columns) + ['checked', 'inversion', 'notes']
    if os.path.exists(csv_path):
        old = pd.read_csv(csv_path, dtype = {'source_id': str, 'checked': str, 'inversion': str, 'notes': str,
                                             'munro_id': 'Int64'})
        added = (~(new['source'] + new['source_id']).isin(old['source'] + old['source_id'])).sum()
        # existing rows keep their values (and checks); gaps, such as a column added since, are filled from the search
        sightings = (old.set_index(['source', 'source_id'])
                     .combine_first(new.set_index(['source', 'source_id'])).reset_index())
    else:
        sightings, added = new, len(new)
    for column in columns:
        if column not in sightings:
            sightings[column] = ''
    sightings = sightings[columns + [c for c in sightings if c not in columns]]
    sightings = sightings.sort_values(['date', 'source_id'], kind = 'stable').reset_index(drop = True)
    sightings.to_csv(csv_path, index = False)
    return sightings, added
