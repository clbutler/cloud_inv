#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 27 2026

@author: chrisbutler
"""

import sqlite3
import time
from datetime import datetime, timezone

import pandas as pd
import requests


API_URL = 'https://api.open-meteo.com/v1/forecast'
PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 850] #hPa, roughly 100 m to 1500 m
SURFACE_VARIABLES = ['temperature_2m', 'dew_point_2m', 'relative_humidity_2m', 'cloud_cover_low', 'cloud_cover_mid',
                     'cloud_cover_high', 'wind_speed_10m', 'pressure_msl']
LEVEL_VARIABLES = ['temperature', 'relative_humidity', 'geopotential_height', 'cloud_cover', 'wind_speed']
HOURLY_VARIABLES = SURFACE_VARIABLES + ['{}_{}hPa'.format(v, p) for p in PRESSURE_LEVELS for v in LEVEL_VARIABLES]


def munro_locations(munro_gdf):
    '''returns the munro id, name, height and lat/lon from the munro shapefile geodataframe'''
    munros = munro_gdf.to_crs(epsg = 4326)
    locations = pd.DataFrame({
        'munro_id': munros['munro_id'],
        'name': munros['Name'],
        'height_m': munros['Height (m)'],
        'lat': munros.geometry.y.round(4),
        'lon': munros.geometry.x.round(4)
        })
    return locations.reset_index(drop = True)


def fetch_forecast(locations, model = 'ukmo_seamless', batch_size = 50):
    '''fetches the hourly open-meteo forecast for every munro, one row per munro per hour,
    plus the sunrise time for each munro and day.
    elevation=nan turns off open-meteo's lapse-rate adjustment, so values are the model's own'''
    forecast_dfs = []
    sunrise_dfs = []
    for start in range(0, len(locations), batch_size):
        batch = locations.iloc[start:start + batch_size]
        params = {
            'latitude': ','.join(batch['lat'].astype(str)),
            'longitude': ','.join(batch['lon'].astype(str)),
            'elevation': ','.join(['nan'] * len(batch)),
            'hourly': ','.join(HOURLY_VARIABLES),
            'daily': 'sunrise',
            'models': model,
            'forecast_days': 7,
            'timezone': 'GMT'
            }
        for attempt in range(3): #open-meteo has a per-minute limit, and each munro counts as a call
            response = requests.get(API_URL, params = params, timeout = 60)
            if response.status_code != 429:
                break
            print('Open-Meteo rate limit hit, waiting 60 seconds')
            time.sleep(60)
        response.raise_for_status()
        results = response.json()
        if isinstance(results, dict): #a single location comes back as a dict, not a list
            if results.get('error'):
                raise RuntimeError('Open-Meteo error: {}'.format(results.get('reason')))
            results = [results]
        for munro_id, result in zip(batch['munro_id'], results):
            df = pd.DataFrame(result['hourly']).rename(columns = {'time': 'valid_time'})
            df.insert(0, 'munro_id', munro_id)
            df.insert(1, 'model', model)
            df.insert(3, 'model_elevation_m', result['elevation'])
            forecast_dfs.append(df)
            sunrise = pd.DataFrame({'munro_id': int(munro_id), 'date': result['daily']['time'],
                                    'sunrise': result['daily']['sunrise']})
            sunrise_dfs.append(sunrise)
    return pd.concat(forecast_dfs, ignore_index = True), pd.concat(sunrise_dfs, ignore_index = True)


def save_forecast(forecast_df, sunrise_df, locations, db_path):
    '''saves the munros and sunrise tables (replaced each run) and appends this run's forecast to the forecasts table'''
    run_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    elevations = forecast_df[['munro_id', 'model_elevation_m']].drop_duplicates('munro_id')
    munros = locations.merge(elevations, on = 'munro_id', how = 'left')
    forecasts = forecast_df.drop(columns = 'model_elevation_m')
    forecasts.insert(0, 'run_time', run_time)

    with sqlite3.connect(db_path) as conn:
        conn.execute('DROP TABLE IF EXISTS munros')
        conn.execute('''CREATE TABLE munros (munro_id INTEGER PRIMARY KEY, name TEXT, height_m REAL,
                        lat REAL, lon REAL, model_elevation_m REAL)''')
        munros.to_sql('munros', conn, if_exists = 'append', index = False)
        sunrise_df.to_sql('sunrise', conn, if_exists = 'replace', index = False)

        variable_columns = ', '.join('{} REAL'.format(v) for v in HOURLY_VARIABLES)
        conn.execute('''CREATE TABLE IF NOT EXISTS forecasts (run_time TEXT, munro_id INTEGER, model TEXT,
                        valid_time TEXT, {},
                        PRIMARY KEY (run_time, model, munro_id, valid_time))'''.format(variable_columns))
        forecasts.to_sql('forecasts', conn, if_exists = 'append', index = False)
    return run_time
