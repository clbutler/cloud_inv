#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 15 21:04:29 2025

@author: chrisbutler
"""


import pandas as pd

####### PreStep 1 Create the munro shapefile  #########

from shapefile_create_function import shapefile_create

STARTING_FILE = '../data/munrotab_v8.0.1.csv'
munro_shapefile = shapefile_create(STARTING_FILE)
munro_shapefile.to_file('../outputs/munro.shp')

               
####### Step 2 Fetch the weather forecast and save it #########

from openmeteo_function import munro_locations, fetch_forecast, save_forecast

locations = munro_locations(munro_shapefile)
forecast_df, sunrise_df = fetch_forecast(locations) # Met Office model via Open-Meteo, 7 days hourly
run_time = save_forecast(forecast_df, sunrise_df, locations, '../outputs/forecasts.db')
print('Saved {} forecast rows for {} munros (run {})'.format(len(forecast_df), len(locations), run_time))


####### Step 3 Score each morning for a cloud inversion #########

from inversion_score_function import score_run, save_scores

scores_df = score_run('../outputs/forecasts.db', run_time)
save_scores(scores_df, '../outputs/forecasts.db')
print(scores_df.pivot_table(index = 'date', columns = 'rag', values = 'munro_id', aggfunc = 'count', fill_value = 0))



######### Step 4 cloudflip website data #########

from site_export_function import export_site_data

export_site_data('../outputs/forecasts.db', STARTING_FILE, '../site/data/scores.js')
print('Website data saved to site/data/scores.js; open site/index.html in a browser')


######### Step 5 Keep the database small #########

from openmeteo_function import prune_forecasts

pruned = prune_forecasts('../outputs/forecasts.db', keep_days = 7) # scores are kept forever
print('Pruned forecasts from {} runs older than 7 days'.format(pruned))
