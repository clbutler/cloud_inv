#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May  8 20:48:01 2025

@author: chrisbutler
"""

import pandas as pd

#cloud dictionary score
cloud_score_dictionary = {'light rain': 0, 'rain shwrs': 0, 'mod. rain' : 0, 'heavy rain': 0, 'cloudy': 1, 'clear': 2, 'some clouds': 3}


def rag_creation(i):
    '''this function takes the output raw weather pulls and starts to collate a RAG rating based on wind speed, temperatures and cloud cover'''
    munro = i[i['Time'] != 'night'].copy() #remove night
    columns_numeric = ['Max Temperature (°C)', 'Min Temperature (°C)', 'Base Max Temperature (°C)', 'Base Min Temperature (°C)' ]
    for c in columns_numeric:
        munro[c] = pd.to_numeric(munro[c], errors = 'coerce')
    munro['average_temp_top'] = munro[['Max Temperature (°C)', 'Min Temperature (°C)']].mean(axis = 1) #average temp at top
    munro['average_temp_bottom'] = munro[['Base Max Temperature (°C)', 'Base Min Temperature (°C)']].mean(axis = 1) #avg temp at bottom
    munro['cloud_score'] = munro['Cloud Cover'].apply(lambda x: cloud_score_dictionary[x])
    for index, row in munro.iterrows():
        if row['average_temp_top'] > row['average_temp_bottom']:
            munro.loc[index, 'temp_score'] = 5
        else: 
            munro.loc[index, 'temp_score'] = 0
    munro['RAG rating'] = munro['temp_score'] + munro['cloud_score']  
    return munro      
            

def create_datetime(j):
    current_date = pd.to_datetime('today') 
    dates = []
    for i, time_period in enumerate(j['Time']):
        if i == 0:
            dates.append(current_date)
        elif time_period == 'AM':
            current_date += pd.Timedelta(days=1)
            dates.append(current_date)
        else:  # For 'PM' and any other case after the first row
            dates.append(current_date)
    j['Pull Date'] = dates   
    return j     
    

 


        
            
        