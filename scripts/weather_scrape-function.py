#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 16 19:55:24 2025

@author: chrisbutler
"""


from bs4 import BeautifulSoup
import requests
import pandas as pd


def get_weather_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    forecast_table = soup.find('table', class_=['forecast-table__table', 'forecast-table__table--content'])
    thead = forecast_table.find('thead')

    # Find the time row
    time_row = thead.find('tr', {'data-row': 'time'})
    time_periods = []
    if time_row:
        time_cells = time_row.find_all('td', class_='forecast-table__cell')
        for cell in time_cells:
            time_span = cell.find('span', class_='en')
            if time_span:
                time_periods.append(time_span.text.strip())
            else:
                time_periods.append(None)
        return(time_periods)
    else:
        print("Could not find the 'time' row.")
    
    
    # find the cloud cover
    phrase_row = forecast_table.find('tr', {'data-row': 'phrases'})
    
    if phrase_row:
        phrase_cells = phrase_row.find_all('td', class_='forecast-table__cell')
        cloud_cover_descriptions = []
        for cell in phrase_cells:
            phrase_span = cell.find('span', class_=['forecast-table__phrase', 'forecast-table__phrase--en'])
            if phrase_span:
                cloud_cover_descriptions.append(phrase_span.text.strip())
            else:
                cloud_cover_descriptions.append(None)
        return(cloud_cover_descriptions)
    else:
        print("Could not find the 'phrases' row in the forecast table.")
        
    
     #find the max temperature
    max_temp_row = forecast_table.find('tr', {'data-row': 'temperature-max'})
    max_temp_values = []
    if max_temp_row:
        temp_cells = max_temp_row.find_all('td', class_='forecast-table__cell')
        for cell in temp_cells:
            temp_div = cell.find('div', class_='temp-value')
            if temp_div:
                max_temp_values.append(temp_div.text)
            else:
                max_temp_values.append(None)
        return(max_temp_values)
    else:
        print("Could not find the 'temperature-max' row.")
        
        
     #find the min temperature
    min_temp_row = forecast_table.find('tr', {'data-row': 'temperature-min'})
    min_temp_values = []
    if min_temp_row:
        temp_cells = min_temp_row.find_all('td', class_='forecast-table__cell')
        for cell in temp_cells:
            temp_div = cell.find('div', class_='temp-value')
            if temp_div:
                min_temp_values.append(temp_div.text)
            else:
                min_temp_values.append(None)
            return(min_temp_values)
    else:
        print("Could not find the 'temperature-min' row.")
        
     ##


