#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May  8 20:48:01 2025

@author: chrisbutler
"""

import pandas as pd
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

all_scrapes = pd.read_csv(os.path.join(script_dir, '../outputs/munro_scrapes/Ben-Lomond_scrape.csv'), index_col= 0)

all_scrapes.dtypes

all_scrapes['mean_temp at top'] = all_scrapes.apply(lambda i: i.iloc[[2,3]].mean(), axis = 1)

                                                  
print(all_scrapes.head())