#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan 26 17:53:41 2025

@author: chrisbutler
"""

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import os

script_dir = os.path.dirname(os.path.abspath(__file__))


munros_input = '../data/munrotab_v8.0.1.csv'
munros_output = '../outputs/munro.shp'

def shapefile_create(input_file, output_file):
    """ this function takes a csv file with x and y coordinates and converts it into a shapefile """
    shapefile = pd.read_csv(input_file, encoding = 'latin1') #import the file
    shapefile = shapefile[['Name', 'Height (m)', 'xcoord', 'ycoord', '2021']] #data clean
    shapefile = shapefile[shapefile['2021'] == 'MUN' ].reset_index(drop = True) 
    shapefile = shapefile.drop('2021', axis = 1)
    geometry = [Point(xy) for xy in zip(shapefile['xcoord'], shapefile['ycoord'])] #export as a shapefile
    shapefile = gpd.GeoDataFrame(shapefile, geometry = geometry)
    shapefile = shapefile.set_crs(epsg=27700) #align to correct CRS
    shapefile.to_file(output_file)


if __name__ == "__main__":
    shapefile_create(munros_input, munros_output)
    

   
