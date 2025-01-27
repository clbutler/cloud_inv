#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 21:59:03 2025

@author: chrisbutler
"""

import geopandas as gpd
import pytest
import matplotlib.pyplot as plt
import contextily as ctx
import folium 


#import shape file
munros = gpd.read_file('../outputs/munro.shp')

def test_munros():
    assert isinstance(munros, gpd.GeoDataFrame), 'munros is not a GeoDataFrame'
    


munros = munros.to_crs(epsg=4326)
def test_crs():
    assert munros.crs == 'EPSG:4326', 'file could not be converted to the correct coordinate reference system (4326)'    


#create a folium plot
ycoord = munros.geometry.y.mean()
xcoord = munros.geometry.x.mean()  
    
    
# Create a Folium map centered around the mean latitude and longitude
m = folium.Map([ycoord, xcoord], zoom_start=7)

# Add a Choropleth layer to the map
folium.Choropleth(
    geo_data=munros.to_json(),              # GeoJSON data
    data=munros,                 # DataFrame with the data
    columns=['Name','Height (m)'], # Columns to use
    key_on='feature.properties.Name',
    legend_name= 'Height',
    line_width=2                        # Width of borders
).add_to(m)

# Add tooltips with the Name and Height
folium.GeoJson(
    munros.to_json(),
    tooltip=folium.GeoJsonTooltip(
        fields=['Name', 'Height (m)'],    # Fields to show
        aliases=['Munro:', 'Height (m):']
    )
).add_to(m)


m.save('../outputs/munros.html')


