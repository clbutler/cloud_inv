#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 26 17:53:41 2025

@author: chrisbutler
"""

import pandas as pd
import pytest
import os 
import geopandas as gpd
from shapely.geometry import Point

#import the file 

def test_files():
    assert os.path.exists('../data/munrotab_v8.0.1.csv'), 'could not find the munrotab_v8.0.1.csv'


shapefile = pd.read_csv('../data/munrotab_v8.0.1.csv', encoding='latin1')



#data clean 
def test_csv():
    assert isinstance(shapefile, pd.DataFrame), 'munros not loading in the correct format (csv)'
    
shapefile = shapefile[['Name', 'Height (m)', 'xcoord', 'ycoord', '2021']]
shapefile = shapefile[shapefile['2021'] == 'MUN' ].reset_index(drop = True)   

def test_munro_count():
    assert shapefile.shape[0] == 282, 'munro count is not coming back as 282?'
    
shapefile = shapefile.drop('2021', axis = 1)

#export as a shapefile 

geometry = [Point(xy) for xy in zip(shapefile['xcoord'], shapefile['ycoord'])]

shapefile = gpd.GeoDataFrame(shapefile, geometry = geometry)

def test_shapefile():
    assert isinstance(shapefile, gpd.GeoDataFrame), 'file was not correctly converted to a GeoDataFrame Object'
    
#align to correct CRS
shapefile = shapefile.set_crs(epsg=3857)

def test_crs():
    assert shapefile.crs == 'EPSG:3857', 'file could not be converted to the correct coordinate reference system (3857)'
    
#save file 
shapefile.to_file('../outputs/munro.shp') 
   
