#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 15 21:04:29 2025

@author: chrisbutler
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd




def get_mountain_name(url):
    '''this function returns the mountain name as aligned with mountain forecast.com'''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    mountain_name = region_soup.find_all('span', class_= ["b-list-table__item-name"," b-list-table__item-name--detail"])
    mountain_names_list = []
    for i in mountain_name:
        mn = i.text.strip()
        if mn:
            mountain_names_list.append(mn)
        else:
            print ("no mountain name found")
    return mountain_names_list
        
def get_mountain_height(url):
    '''this function returns the mountain height in meters as aligned with mountain forecast.com'''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    mountain_height = region_soup.find_all('span', class_= ["b-list-table__item-height"])
    mountain_height_list = []
    for i in mountain_height:
        mh = i.text.strip()
        if mh:
            mountain_height_list.append(mh)
        else:
            print ("no mountain height found")
    return mountain_height_list
    
            
                
             
#######
region_list =['grampions', 'northwest-highlands']

all_mountain_names = []
all_mountain_heights = []

for i in region_list:
    url = 'https://www.mountain-forecast.com/subranges/{}/locations'.format(i)
    current_mountain_names = get_mountain_name(url)
    current_mountain_heights = get_mountain_height(url)
    all_mountain_names.extend(current_mountain_names)
    all_mountain_heights.extend(current_mountain_heights)
    


munro_data = pd.DataFrame({'munro name': all_mountain_names, 'munro height (m)': all_mountain_heights})


munro_data['munro height (m)'] = munro_data['munro height (m)'].str.replace('m', '')
munro_data['munro height (m)'] = munro_data['munro height (m)'].astype('int')
munro_data = munro_data[munro_data['munro height (m)'] > 914.4]
