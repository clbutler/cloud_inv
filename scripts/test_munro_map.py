#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 23 15:21:33 2025

@author: chrisbutler
"""


import folium 
import munro_map

def test_munros():
    assert isinstance(munros, gpd.GeoDataFrame), 'munros is not a GeoDataFrame'
    
def test_crs():
    assert munros.crs == 'EPSG:4326', 'file could not be converted to the correct coordinate reference system (4326)'    