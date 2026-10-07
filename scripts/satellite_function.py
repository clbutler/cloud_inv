#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 6 2026

@author: chrisbutler

Labels what Sentinel-2 actually saw around each munro (or any hill), to check the inversion score against.
An inversion from above: cloud fills the low ground but the ground near the summit is clear.
"""

import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT


STAC_URL = 'https://planetarycomputer.microsoft.com/api/stac/v1'
SCOTLAND_BBOX = [-7.8, 55.9, -2.5, 58.7] #lon/lat box around all 282 munros
GRID_CRS = 'EPSG:27700'
PIXEL_M = 40 #SCL is 20 m; 40 m reads the overview, a quarter of the download, and is plenty for glens
RADIUS_M = 4000 #half-width of the box read around each summit
LOW_GROUND_M = 300 #low ground is at least this far below the summit (less on small hills, see fit_hills)
SUMMIT_DROP_M = 100 #the summit area is the top: no more than this below the summit (a third of the low-ground drop)...
SUMMIT_RADIUS_M = 1000 #...and this close to it. A cloud sea laps up the slopes in between, so that band isn't counted
LOW_CLOUD_MIN = 0.1 #share of the low ground that must be cloud for an inversion. A cloud sea filling only the
                    #valley floors covers little of an 8 km box: chosen on the hand-checked images before 2022
                    #(0.07-0.2 all equal there), then 10 of 10 found and 0 of 21 false alarms on those since
SCL_NODATA = [0, 1] #no data, saturated or defective
SCL_CLOUD = [8, 9] #cloud medium and high probability; fog and stratus tops land here
SCL_CIRRUS = 10

# make GDAL read only the bytes it needs from the cloud-optimised GeoTIFFs
os.environ.setdefault('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
os.environ.setdefault('GDAL_HTTP_MERGE_CONSECUTIVE_RANGES', 'YES')
os.environ.setdefault('GDAL_HTTP_MAX_RETRY', '3')


def munro_grids(munros_df):
    '''adds each munro's (or site's) OS grid easting/northing and the transform of the box read around it'''
    to_grid = Transformer.from_crs('EPSG:4326', GRID_CRS, always_xy = True)
    grids = munros_df.copy()
    grids['easting'], grids['northing'] = to_grid.transform(grids['lon'].values, grids['lat'].values)
    grids['transform'] = [from_origin(e - RADIUS_M, n + RADIUS_M, PIXEL_M, PIXEL_M)
                          for e, n in zip(grids['easting'], grids['northing'])]
    return grids


def read_box(href, transform, resampling, pixel_m = PIXEL_M, bands = 1):
    '''reads one raster into the box described by transform, in OS grid; returns None if it fails.
    bands is a band number (gives a 2d array) or a list of them (gives bands x rows x columns)'''
    size = 2 * RADIUS_M // pixel_m
    try:
        with rasterio.open(href) as src, WarpedVRT(src, crs = GRID_CRS, transform = transform, width = size,
                                                   height = size, resampling = resampling, nodata = 0) as vrt:
            return vrt.read(bands)
    except rasterio.errors.RasterioIOError as error:
        print('Could not read {}: {}'.format(href.split('?')[0], error))
        return None


def search(collection, datetime = None, bbox = SCOTLAND_BBOX):
    '''returns the signed STAC items covering bbox (lon/lat), scotland by default'''
    catalog = pystac_client.Client.open(STAC_URL, modifier = planetary_computer.sign_inplace)
    return list(catalog.search(collections = [collection], bbox = bbox, datetime = datetime).items())


def sites_bbox(grids, margin = 0.1):
    '''lon/lat box around every site'''
    return [grids['lon'].min() - margin, grids['lat'].min() - margin,
            grids['lon'].max() + margin, grids['lat'].max() + margin]


def terrain(grids, threads = 8, id_col = 'munro_id'):
    '''returns {site id: height grid in metres} from the Copernicus 30 m DEM; a box can span two DEM tiles'''
    dem_items = search('cop-dem-glo-30', bbox = sites_bbox(grids))
    def one(row):
        box = np.zeros((2 * RADIUS_M // PIXEL_M,) * 2, dtype = np.float32)
        lon, lat = row['lon'], row['lat']
        for item in dem_items:
            west, south, east, north = item.bbox
            if west - 0.1 < lon < east + 0.1 and south - 0.1 < lat < north + 0.1:
                part = read_box(item.assets['data'].href, row['transform'], Resampling.bilinear)
                if part is not None:
                    box = np.where(box == 0, part, box)
        return row[id_col], box
    with ThreadPoolExecutor(threads) as pool:
        return dict(pool.map(one, [row for _, row in grids.iterrows()]))


def near_centre(size):
    '''true for the pixels within SUMMIT_RADIUS_M of the middle of the box'''
    offset = (np.arange(size) - (size - 1) / 2) * PIXEL_M
    return np.hypot(*np.meshgrid(offset, offset)) <= SUMMIT_RADIUS_M


def fit_hills(grids, dem, id_col = 'munro_id'):
    '''sets each site's summit height and low-ground drop. A munro keeps its listed height and the full
    LOW_GROUND_M. Any other site (say where a photo was taken) uses the highest ground within SUMMIT_RADIUS_M,
    and on a small hill low ground starts halfway down to the floor of the box (its lowest 5 % of land),
    because 300 m below a 277 m hill would be under the sea'''
    grids = grids.copy()
    if 'height_m' not in grids:
        grids['height_m'] = np.nan
    heights, drops = [], []
    for _, row in grids.iterrows():
        box = dem[row[id_col]]
        if pd.notna(row['height_m']):
            heights.append(row['height_m'])
            drops.append(LOW_GROUND_M)
            continue
        top = float(box[near_centre(box.shape[0])].max())
        floor = float(np.percentile(box[box > 0], 5)) if (box > 0).any() else 0.0
        heights.append(top)
        drops.append(min(LOW_GROUND_M, max(top - floor, 0) / 2))
    grids['height_m'], grids['low_drop_m'] = heights, drops
    return grids


def label_box(scl, dem, summit_m, low_drop_m = LOW_GROUND_M):
    '''turns one site's scene classes and heights into cloud fractions and a label'''
    summit_drop_m = low_drop_m * SUMMIT_DROP_M / LOW_GROUND_M
    near_summit = (dem >= summit_m - summit_drop_m) & near_centre(dem.shape[0])
    low = (dem > 0) & (dem < summit_m - low_drop_m) #dem 0 is sea or missing
    valid = ~np.isin(scl, SCL_NODATA)
    cloud = np.isin(scl, SCL_CLOUD)
    def fraction(mask, of):
        n = (of & valid).sum()
        return float((mask & of & valid).sum() / n) if n else np.nan
    obs = {
        'summit_valid': float((near_summit & valid).sum() / max(near_summit.sum(), 1)),
        'low_valid': float((low & valid).sum() / max(low.sum(), 1)),
        'summit_cloud': fraction(cloud, near_summit),
        'low_cloud': fraction(cloud, low),
        'cirrus': fraction(scl == SCL_CIRRUS, near_summit | low),
        }
    if obs['summit_valid'] < 0.5 or obs['low_valid'] < 0.5:
        obs['label'] = 'no_data'
    elif obs['summit_cloud'] >= 0.5:
        obs['label'] = 'summit_cloud'
    elif obs['summit_cloud'] <= 0.1 and obs['low_cloud'] >= LOW_CLOUD_MIN:
        obs['label'] = 'inversion' #cloud confined to low ground: cumulus would cover the high ground too
    elif obs['summit_cloud'] <= 0.1 and obs['low_cloud'] <= 0.05:
        obs['label'] = 'clear'
    else:
        obs['label'] = 'mixed'
    return obs


def observe(munros_df, start, end, threads = 8, id_col = 'munro_id', dem = None):
    '''one row per sentinel-2 scene x munro (or site) inside it, with cloud fractions and a label.
    A site needs id_col, lat and lon; without height_m its summit is found from the terrain (fit_hills).
    Pass dem (from terrain) to reuse heights already read'''
    grids = munro_grids(munros_df)
    if dem is None:
        print('Reading terrain for {} sites'.format(len(grids)))
        dem = terrain(grids, threads, id_col)
    grids = fit_hills(grids, dem, id_col)
    scenes = search('sentinel-2-l2a', '{}/{}'.format(start, end), sites_bbox(grids))
    print('Found {} Sentinel-2 scenes from {} to {}'.format(len(scenes), start, end))
    jobs = []
    for item in scenes:
        west, south, east, north = item.bbox
        inside = grids[grids['lon'].between(west, east) & grids['lat'].between(south, north)]
        jobs += [(item, row) for _, row in inside.iterrows()]
    def one(job):
        item, row = job
        scl = read_box(item.assets['SCL'].href, row['transform'], Resampling.nearest)
        if scl is None or not (~np.isin(scl, SCL_NODATA)).any(): #site sits in the scene's empty corner
            return None
        return {id_col: row[id_col], 'scene_id': item.id,
                'overpass_time': item.datetime.strftime('%Y-%m-%dT%H:%M'),
                'date': item.datetime.strftime('%Y-%m-%d'),
                'scene_cloud_pct': item.properties.get('eo:cloud_cover'),
                'height_m': row['height_m'], 'low_drop_m': row['low_drop_m'],
                **label_box(scl, dem[row[id_col]], row['height_m'], row['low_drop_m'])}
    print('Reading cloud classes for {} site x scene pairs'.format(len(jobs)))
    with ThreadPoolExecutor(threads) as pool:
        rows = [r for r in pool.map(one, jobs) if r is not None]
    obs = pd.DataFrame(rows)
    # tiles overlap, so a site can appear in two scenes from the same pass: keep the one that saw most
    if len(obs):
        obs['seen'] = obs['summit_valid'] + obs['low_valid']
        obs = (obs.sort_values('seen', ascending = False).drop_duplicates([id_col, 'date'])
               .drop(columns = 'seen').sort_values(['date', id_col]).reset_index(drop = True))
    return obs


def save_observations(obs_df, db_path):
    '''replaces any earlier observations for the same munro and date'''
    with sqlite3.connect(db_path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS satellite_obs (munro_id INTEGER, date TEXT, scene_id TEXT,
                        overpass_time TEXT, scene_cloud_pct REAL, summit_valid REAL, low_valid REAL,
                        summit_cloud REAL, low_cloud REAL, cirrus REAL, label TEXT, PRIMARY KEY (munro_id, date))''')
        conn.executemany('DELETE FROM satellite_obs WHERE munro_id = ? AND date = ?',
                         obs_df[['munro_id', 'date']].itertuples(index = False, name = None))
        columns = [c[1] for c in conn.execute('PRAGMA table_info(satellite_obs)')]
        obs_df[columns].to_sql('satellite_obs', conn, if_exists = 'append', index = False)


def compare(obs_df, forecast_db):
    '''joins each observation to the score from the latest run made before the overpass'''
    with sqlite3.connect(forecast_db) as conn:
        scores = pd.read_sql('SELECT run_time, munro_id, date, rag, best_hour FROM scores', conn)
    joined = obs_df.merge(scores, on = ['munro_id', 'date'])
    joined = joined[joined['run_time'] < joined['overpass_time']]
    joined = joined.sort_values('run_time').drop_duplicates(['munro_id', 'date'], keep = 'last')
    joined['lead_days'] = (pd.to_datetime(joined['date']) - pd.to_datetime(joined['run_time'].str[:10])).dt.days
    return joined.reset_index(drop = True)


def true_colour(scene_id, row, pixel_m = 20):
    '''the sentinel-2 true-colour image (red, green, blue) of one site's box, as rows x columns x 3'''
    catalog = pystac_client.Client.open(STAC_URL, modifier = planetary_computer.sign_inplace)
    item = catalog.get_collection('sentinel-2-l2a').get_item(scene_id)
    transform = from_origin(row['easting'] - RADIUS_M, row['northing'] + RADIUS_M, pixel_m, pixel_m)
    rgb = read_box(item.assets['visual'].href, transform, Resampling.average, pixel_m, [1, 2, 3])
    return None if rgb is None else rgb.transpose(1, 2, 0)
