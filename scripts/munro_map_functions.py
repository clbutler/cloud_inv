#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 27 21:59:03 2025

@author: chrisbutler
"""


import folium 
import os
import geopandas as gpd
import pandas as pd

script_dir = os.path.dirname(os.path.abspath(__file__))


#munros_input = '../outputs/munro.shp'
#munros_output = '../outputs/munros.html'

def munro_join(shapefile, rag_file):
    '''combines the RAG rating with the coordinate data'''
    munro_map = gpd.read_file(shapefile)
    munro_map = munro_map.to_crs(epsg = 4326)
    joined = munro_map.merge(rag_file, how = 'left', left_on = 'Name', right_on = 'Munro Name')
    return joined

  
    
    


def munro_map(input_file, output_file):
    '''creates a folium map of the munros and outputs it as a html'''
    munros = gpd.read_file(input_file)
    munros = munros.to_crs(epsg=4326)
    ycoord = munros.geometry.y.mean() #create a folium plot
    xcoord = munros.geometry.x.mean()  
    m = folium.Map([ycoord, xcoord], zoom_start=7) # Create a Folium map centered around the mean latitude and longitude
    # Add a Choropleth layer to the map
    folium.Choropleth(
        geo_data=munros.to_json(),              # GeoJSON data
        data=munros,                 # DataFrame with the data
        columns=['Name','Height (m)'], # Columns to use
        key_on='feature.properties.Name',
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
    m.save(output_file)
    return munros
    
if __name__ == "__main__" :
    munro_map(munros_input, munros_output)
    


