#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 26 17:53:41 2025

@author: chrisbutler
"""

import pandas as pd
import pytest
import os 

#import the file 

def test_files():
    assert os.path.exists('../data/munrotab_v8.0.1.csv'), 'could not find the munrotab_v8.0.1.csv'


shapefile = pd.read_csv('../data/munrotab_v8.0.1.csv', encoding='latin1')
#shapefile.head()


#data clean 
def test_csv():
    assert isinstance(shapefile, pd.DataFrame), 'munros not loading in the correct format (csv)'
    
shapefile = shapefile[['Name', 'Height (m)', 'xcoord', 'ycoord', '2021']]
shapefile = shapefile[shapefile['2021'] == 'MUN' ].reset_index(drop = True)   

def test_munro_count():
    assert shapefile.shape[0] == 282, 'munro count is not coming back as 282?'
    
shapefile = shapefile.drop('2021', axis = 1)