#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Sep 27 2026

@author: chrisbutler

Scores the chance of standing above a sea of cloud on each munro, each morning.
Four checks are graded 2 (pass), 1 (partial) or 0 (fail):
    A lid        - a layer below the summit where temperature rises with height (partial: cools slower than 3 C/km)
    B moisture   - cloud or near-saturated air below the summit (cloud >= 50% or RH >= 95%; partial RH >= 87%)
    C clear top  - dry air at the summit (RH < 84% and mid+high cloud < 50%; partial RH < 87%)
    D wind       - light wind in the layer below the summit, where the cloud sea forms (<= 11 km/h; partial <= 20 km/h)
Green = all four pass. Amber = all four at least partial. Red = anything else.
The summit wind is saved too, as a walker's warning, but isn't scored: strong wind above the lid doesn't break it.
Thresholds and sources are listed in CLAUDE.md.
"""

import sqlite3

import numpy as np
import pandas as pd

from openmeteo_function import PRESSURE_LEVELS


RAG_NAMES = {2: 'Green', 1: 'Amber', 0: 'Red'}


def grade(value, pass_test, partial_test):
    '''returns 2 if the pass test holds, 1 if the partial test holds, otherwise 0'''
    if pass_test(value):
        return 2
    if partial_test(value):
        return 1
    return 0


def score_hour(row, summit_m, ground_m):
    '''scores one forecast hour for one munro, returning each check's value and grade'''
    heights = np.array([row['geopotential_height_{}hPa'.format(p)] for p in PRESSURE_LEVELS])
    temps = np.array([row['temperature_{}hPa'.format(p)] for p in PRESSURE_LEVELS])
    rhs = np.array([row['relative_humidity_{}hPa'.format(p)] for p in PRESSURE_LEVELS])
    clouds = np.array([row['cloud_cover_{}hPa'.format(p)] for p in PRESSURE_LEVELS])
    winds = np.array([row['wind_speed_{}hPa'.format(p)] for p in PRESSURE_LEVELS])
    above_ground = heights >= ground_m #levels below the model's ground are extrapolated, not real air

    # A: the most stable layer between two levels, both above the model's ground and below the summit
    lid_lapse, lid_top = np.nan, np.nan
    for i in range(len(PRESSURE_LEVELS) - 1):
        if above_ground[i] and heights[i + 1] < summit_m:
            lapse = (temps[i + 1] - temps[i]) / (heights[i + 1] - heights[i]) * 1000 #C per km, positive = inversion
            if np.isnan(lid_lapse) or lapse > lid_lapse:
                lid_lapse, lid_top = lapse, heights[i + 1]
    a = 0 if np.isnan(lid_lapse) else grade(lid_lapse, lambda x: x > 0, lambda x: x > -3)

    # B: the wettest level below the summit
    below = above_ground & (heights < summit_m)
    below_rh = rhs[below].max() if below.any() else np.nan
    below_cloud = clouds[below].max() if below.any() else np.nan
    if below.any() and (below_cloud >= 50 or below_rh >= 95):
        b = 2
    else:
        b = 0 if np.isnan(below_rh) else grade(below_rh, lambda x: False, lambda x: x >= 87)

    # C: interpolated to the summit height
    summit_rh = np.interp(summit_m, heights, rhs)
    mid_high_cloud = row['cloud_cover_mid'] + row['cloud_cover_high']
    c = 2 if summit_rh < 84 and mid_high_cloud < 50 else grade(summit_rh, lambda x: False, lambda x: x < 87)

    # D: the strongest wind between the model's ground and the summit, which would mix the layer
    below_wind = max([row['wind_speed_10m']] + list(winds[below]))
    d = grade(below_wind, lambda x: x <= 11, lambda x: x <= 20)
    summit_wind = np.interp(summit_m, heights, winds)

    if min(a, b, c, d) == 2:
        rag = 2
    elif min(a, b, c, d) >= 1:
        rag = 1
    else:
        rag = 0

    return pd.Series({
        'rag_value': rag, 'lid_grade': a, 'moisture_grade': b, 'clear_top_grade': c, 'wind_grade': d,
        'lid_lapse_c_per_km': round(lid_lapse, 1), 'lid_top_m': lid_top,
        'below_max_rh': below_rh, 'below_max_cloud': below_cloud,
        'summit_rh': round(summit_rh, 1), 'mid_high_cloud': mid_high_cloud,
        'below_max_wind_kmh': round(below_wind, 1), 'summit_wind_kmh': round(summit_wind, 1), 'pressure_msl': row['pressure_msl']
        })


def score_run(db_path, run_time = None, hours_before = 1, hours_after = 3):
    '''scores every munro for each morning of a run (the latest run by default), keeping each day's best hour.
    The morning window runs from an hour before sunrise to three hours after'''
    with sqlite3.connect(db_path) as conn:
        if run_time is None:
            run_time = conn.execute('SELECT MAX(run_time) FROM forecasts').fetchone()[0]
        forecasts = pd.read_sql('SELECT * FROM forecasts WHERE run_time = ?', conn, params = (run_time,))
        munros = pd.read_sql('SELECT munro_id, height_m, model_elevation_m FROM munros', conn)
        sunrise = pd.read_sql('SELECT * FROM sunrise', conn)

    forecasts['date'] = forecasts['valid_time'].str[:10]
    forecasts = forecasts.merge(munros, on = 'munro_id').merge(sunrise, on = ['munro_id', 'date'])
    valid_time = pd.to_datetime(forecasts['valid_time'])
    sunrise_time = pd.to_datetime(forecasts['sunrise'])
    in_window = (valid_time >= sunrise_time - pd.Timedelta(hours = hours_before)) & \
                (valid_time <= sunrise_time + pd.Timedelta(hours = hours_after))
    morning = forecasts[in_window].reset_index(drop = True)

    scores = morning.apply(lambda row: score_hour(row, row['height_m'], row['model_elevation_m']), axis = 1)
    scores = pd.concat([morning[['run_time', 'model', 'munro_id', 'date', 'valid_time']], scores], axis = 1)

    # best hour per munro per day: highest RAG, then the most checks passed, then the earliest hour
    scores['grade_total'] = scores[['lid_grade', 'moisture_grade', 'clear_top_grade', 'wind_grade']].sum(axis = 1)
    scores = scores.sort_values(['munro_id', 'date', 'rag_value', 'grade_total', 'valid_time'],
                                ascending = [True, True, False, False, True])
    best = scores.drop_duplicates(['munro_id', 'date']).drop(columns = 'grade_total')
    best = best.rename(columns = {'valid_time': 'best_hour'})
    best.insert(best.columns.get_loc('rag_value'), 'rag', best['rag_value'].map(RAG_NAMES))
    return best.reset_index(drop = True)


def save_scores(scores_df, db_path):
    '''appends the scores to the scores table, replacing any earlier scores for the same run'''
    with sqlite3.connect(db_path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS scores (run_time TEXT, model TEXT, munro_id INTEGER, date TEXT,
                        best_hour TEXT, rag TEXT, rag_value INTEGER, lid_grade INTEGER, moisture_grade INTEGER,
                        clear_top_grade INTEGER, wind_grade INTEGER, lid_lapse_c_per_km REAL, lid_top_m REAL,
                        below_max_rh REAL, below_max_cloud REAL, summit_rh REAL, mid_high_cloud REAL,
                        below_max_wind_kmh REAL, summit_wind_kmh REAL, pressure_msl REAL,
                        PRIMARY KEY (run_time, model, munro_id, date))''')
        for run_time in scores_df['run_time'].unique():
            conn.execute('DELETE FROM scores WHERE run_time = ?', (run_time,))
        scores_df.to_sql('scores', conn, if_exists = 'append', index = False)
