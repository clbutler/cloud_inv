#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 14 22:52:18 2025

@author: chrisbutler
"""

from bs4 import BeautifulSoup
import requests
import pandas as pd


munro = 'Ben-Lomond'


#get the websites html
url = 'https://www.mountain-forecast.com/peaks/{}'.format(munro)
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')


height_data = soup.find('span', class_= 'height')

if height_data:
    height_cell = height_data.text
    print(height_cell)
else:
    print("could not find height of {}".format(munro))    
    
#    

#create table 

height_dict = {'Munro Name':[munro], 'Height (M)': [height_cell]}  
  
heights_df  = pd.DataFrame(height_dict)

print(heights_df.head())