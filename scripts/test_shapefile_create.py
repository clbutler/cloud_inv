#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pytest
import pandas as pd
import geopandas as gpd
import os
from shapely.geometry import Point
import shapefile_create  # Import your main script

def test_files():
    assert os.path.exists('../data/munrotab_v8.0.1.csv'), 'could not find the munrotab_v8.0.1.csv'

def test_csv():
    result_shapefile = shapefile_create.shapefile_create('../data/munrotab_v8.0.1.csv', '../outputs/test_munro.shp')
    assert isinstance(result_shapefile, pd.DataFrame), 'munros not loading in the correct format (csv)'

def test_munro_count():
    result_shapefile = shapefile_create.shapefile_create('../data/munrotab_v8.0.1.csv', '../outputs/test_munro.shp')
    assert result_shapefile.shape[0] == 282, 'munro count is not coming back as 282?'

def test_shapefile():
    result_shapefile = shapefile_create.shapefile_create('../data/munrotab_v8.0.1.csv', '../outputs/test_munro.shp')
    assert isinstance(result_shapefile, gpd.GeoDataFrame), 'file was not correctly converted to a GeoDataFrame Object'

def test_crs():
    result_shapefile = shapefile_create.shapefile_create('../data/munrotab_v8.0.1.csv', '../outputs/test_munro.shp')
    assert result_shapefile.crs == 'EPSG:27700', 'file could not be converted to the correct coordinate reference system (27700 - Ordinance Survey System UK'