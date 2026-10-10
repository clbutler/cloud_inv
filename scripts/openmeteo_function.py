#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 27 2026

@author: chrisbutler
"""

import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests


API_URL = 'https://api.open-meteo.com/v1/forecast'
HISTORICAL_URL = 'https://historical-forecast-api.open-meteo.com/v1/forecast' #past forecasts; the met office
                                                                             #pressure levels start 2024-08-13
PRESSURE_LEVELS = [1000, 975, 950, 925, 900, 850] #hPa, roughly 100 m to 1500 m
SURFACE_VARIABLES = ['temperature_2m', 'dew_point_2m', 'relative_humidity_2m', 'cloud_cover_low', 'cloud_cover_mid',
                     'cloud_cover_high', 'wind_speed_10m', 'pressure_msl']
LEVEL_VARIABLES = ['temperature', 'relative_humidity', 'geopotential_height', 'cloud_cover', 'wind_speed']
HOURLY_VARIABLES = SURFACE_VARIABLES + ['{}_{}hPa'.format(v, p) for p in PRESSURE_LEVELS for v in LEVEL_VARIABLES]
RETRY_WAITS = [60, 120, 300, 300] #seconds; the free tier's limit is per IP, and GitHub's shared runners often start over it


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


def get_with_retries(params, api_url = API_URL):
    '''requests the forecast, waiting and trying again after a rate limit, server error or timeout'''
    for wait in RETRY_WAITS + [None]:
        try:
            response = requests.get(api_url, params = params, timeout = 120)
            if response.status_code != 429 and response.status_code < 500:
                return response
            problem = 'Open-Meteo returned {}'.format(response.status_code)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as error:
            response = None
            problem = 'Open-Meteo request failed ({})'.format(type(error).__name__)
        if wait is None: #no point waiting after the last try
            break
        print('{}, waiting {} seconds'.format(problem, wait))
        time.sleep(wait)
    if response is None:
        raise RuntimeError('{} after {} tries'.format(problem, len(RETRY_WAITS) + 1))
    return response


def fetch_forecast(locations, model = 'ukmo_seamless', batch_size = 50, start_date = None, end_date = None,
                   api_url = API_URL):
    '''fetches the hourly open-meteo forecast for every munro, one row per munro per hour,
    plus the sunrise time for each munro and day.
    elevation=nan turns off open-meteo's lapse-rate adjustment, so values are the model's own.
    With start_date and end_date (and HISTORICAL_URL) it fetches those past days instead of the next 7'''
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
            'timezone': 'GMT',
            **({'start_date': start_date, 'end_date': end_date} if start_date else {'forecast_days': 7})
            }
        response = get_with_retries(params, api_url) #open-meteo has a per-minute limit, and each munro counts as a call
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
    '''saves the munros table (replaced each run) and appends this run's forecast and sunrise times'''
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
        old_sunrise = None
        columns = [c[1] for c in conn.execute('PRAGMA table_info(sunrise)')]
        if columns and 'run_time' not in columns: #older databases kept only the latest run's sunrise times
            old_sunrise = pd.read_sql('SELECT munro_id, date, sunrise FROM sunrise', conn)
            old_sunrise.insert(0, 'run_time', conn.execute('SELECT MAX(run_time) FROM forecasts').fetchone()[0])
            conn.execute('DROP TABLE sunrise')
        conn.execute('''CREATE TABLE IF NOT EXISTS sunrise (run_time TEXT, munro_id INTEGER, date TEXT, sunrise TEXT,
                        PRIMARY KEY (run_time, munro_id, date))''')
        if old_sunrise is not None:
            old_sunrise.to_sql('sunrise', conn, if_exists = 'append', index = False)
        sunrise = sunrise_df.copy()
        sunrise.insert(0, 'run_time', run_time)
        sunrise.to_sql('sunrise', conn, if_exists = 'append', index = False)

        variable_columns = ', '.join('{} REAL'.format(v) for v in HOURLY_VARIABLES)
        conn.execute('''CREATE TABLE IF NOT EXISTS forecasts (run_time TEXT, munro_id INTEGER, model TEXT,
                        valid_time TEXT, {},
                        PRIMARY KEY (run_time, model, munro_id, valid_time))'''.format(variable_columns))
        forecasts.to_sql('forecasts', conn, if_exists = 'append', index = False)
    return run_time


def prune_forecasts(db_path, keep_days = 7):
    '''deletes forecast rows from runs older than keep_days, then shrinks the file; scores and sunrise times are kept forever so old runs can be re-exported'''
    cutoff = (datetime.now(timezone.utc) - timedelta(days = keep_days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    with sqlite3.connect(db_path) as conn:
        deleted = conn.execute('SELECT COUNT(DISTINCT run_time) FROM forecasts WHERE run_time < ?', (cutoff,)).fetchone()[0]
        conn.execute('DELETE FROM forecasts WHERE run_time < ?', (cutoff,))
        conn.commit()
        conn.execute('VACUUM') #SQLite doesn't shrink the file on DELETE
    return deleted
