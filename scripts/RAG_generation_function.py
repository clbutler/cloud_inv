#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May  8 20:48:01 2025

@author: chrisbutler
"""

import pandas as pd
cloud_score_dictionary = {'light rain': 0, 'rain shwrs': 0, 'mod. rain' : 0, 'heavy rain': 0, 'cloudy': 1, 'clear': 2, 'some clouds': 3}


def rag_creation(i):
    '''this function takes the output raw weather pulls and starts to collate a RAG rating based on wind speed, temperatures and cloud cover'''
    munro = pd.read_csv(i, index_col = 0)
    munro = munro[munro['Time'] != 'night'] #remove night
    munro['average_temp_top'] = munro[['Max Temperature (°C)', 'Min Temperature (°C)']].mean(axis = 1) #average temp at top
    munro['average_temp_bottom'] = munro[['Base Max Temperature (°C)', 'Base Min Temperature (°C)']].mean(axis = 1) #avg temp at bottom
    munro['cloud_score'] = munro['Cloud Cover'].apply(lambda x: cloud_score_dictionary[x])
    for index, row in munro.iterrows():
        if row['average_temp_top'] > row['average_temp_bottom']:
            munro.loc[index, 'temp_score'] = 5
        else: 
            munro.loc[index, 'temp_score'] = 0
    munro['RAG rating'] = munro['average_temp_top'] + munro['average_temp_bottom']        
            

###########

# Get today's date
current_date = pd.to_datetime('today')  

# Create an empty list to store the dates
dates = []

# Iterate through the 'Time' column and update the date accordingly
for i, time_period in enumerate(munro['Time']):
    if i == 0:
        dates.append(current_date)
    elif time_period == 'AM':
        current_date += pd.Timedelta(days=1)
        dates.append(current_date)
    else:  # For 'PM' and any other case after the first row
        dates.append(current_date)

munro['Pull Date'] = dates        

################


        
            
        