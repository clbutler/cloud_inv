#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May  8 20:48:01 2025

@author: chrisbutler
"""

import pandas as pd

munro = pd.read_csv('../outputs/munro_weather.csv', index_col = 0)

munro.head()
munro.dtypes

##########################

#remove night

munro = munro[munro['Time'] != 'night']

#create an average temperature at the top!

munro['average_temp_top'] = munro[['Max Temperature (°C)', 'Min Temperature (°C)']].mean(axis = 1)

##############
munro['Cloud Cover'].unique()

cloud_score_dictionary = {'light rain': 0, 'rain shwrs': 0, 'mod. rain' : 0, 'cloudy': 1, 'clear': 2, 'some clouds': 3}

munro['cloud_score'] = munro['Cloud Cover'].apply(lambda x: cloud_score_dictionary[x])
