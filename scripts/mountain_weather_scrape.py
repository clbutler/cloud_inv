#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 16 19:55:24 2025

@author: chrisbutler
"""


from bs4 import BeautifulSoup
import requests
import pandas as pd

#get the websites html
url = "https://www.mountain-forecast.com/peaks/Ben-Lomond/forecasts/974"
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

#find the day and date

forecast_table = soup.find('table', class_=['forecast-table__table', 'forecast-table__table--content'])

if forecast_table:
    thead = forecast_table.find('thead')
    header_rows = thead.find_all('tr')
    day_header_row = header_rows[1]
    day_cells = day_header_row.find_all('td', class_='forecast-table-days__cell')

    day_dates = []
    for cell in day_cells:
        day_name_div = cell.find('div', class_='forecast-table-days__content').find('div', class_='forecast-table-days__name')
        date_div = cell.find('div', class_='forecast-table-days__content').find('div', class_='forecast-table-days__date')
        day = day_name_div.text.strip() if day_name_div else None
        date = date_div.text.strip() if date_div else None
        day_dates.append((day, date))

    print("Day and Dates:", day_dates)

else:
    print("Could not find the forecast table.")
    

# Find the time row
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
            # If the span isn't directly in the cell, try one level deeper
            container_div = cell.find('div', class_='forecast-table__container')
            if container_div:
                time_span_in_div = container_div.find('span', class_='en')
                time_periods.append(time_span_in_div.text.strip() if time_span_in_div else None)
            else:
                time_periods.append(None)
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
    print("Cloud Cover Descriptions:", cloud_cover_descriptions)
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
    print("Max Temperatures:", max_temp_values)
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
    print("Min Temperatures:", min_temp_values)
else:
    print("Could not find the 'temperature-min' row.")
    
 ##

# Separate days and dates
days = [item[0] for item in day_dates]
dates = [item[1] for item in day_dates]


# Create the dictionary for the DataFrame
data = {
    'Day': days,
    'Date': dates,
    'Time': time_periods,
    'Cloud Cover': cloud_cover_descriptions,
    'Max Temperature (°C)': max_temp_values,
    'Min Temperature (°C)': min_temp_values
}

# Create the Pandas DataFrame
df = pd.DataFrame(data)

# Print the DataFrame
print(df)   