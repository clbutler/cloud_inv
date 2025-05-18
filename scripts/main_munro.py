#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 15 21:04:29 2025

@author: chrisbutler
"""


import pandas as pd

               
####### Step 1 Import the Munro names and Heights  #########

from munro_metadata_functions import get_mountain_height, get_mountain_name, get_mountain_url
region_list =['grampians', 'northwest-highlands']

all_mountain_names = []
all_mountain_heights = []
all_mountain_urls = []

for i in region_list:
    url = 'https://www.mountain-forecast.com/subranges/{}/locations'.format(i)
    current_mountain_names = get_mountain_name(url)
    current_mountain_heights = get_mountain_height(url)
    current_mountain_urls = get_mountain_url(url)
    all_mountain_names.extend(current_mountain_names)
    all_mountain_heights.extend(current_mountain_heights)
    all_mountain_urls.extend(current_mountain_urls)
    


munro_data = pd.DataFrame({'munro name': all_mountain_names, 'munro height (m)': all_mountain_heights, 'URL': all_mountain_urls})


munro_data['munro height (m)'] = munro_data['munro height (m)'].str.replace('m', '')
munro_data['munro height (m)'] = munro_data['munro height (m)'].astype('int')
munro_data = munro_data[munro_data['munro height (m)'] > 914.4]

munro_data.to_csv('../outputs/munro_data.csv')


