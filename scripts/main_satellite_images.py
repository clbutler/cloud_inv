#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 6 2026

@author: chrisbutler

Draws what Sentinel-2 saw for each checked sighting that had a pass (from main_satellite_sightings.py):
the true-colour image, with the line where 'low ground' starts (300 m below the summit, less on small hills).
Run from scripts/ after main_satellite_sightings.py:
    python main_satellite_images.py            # the photo only
    python main_satellite_images.py --classes  # plus the scene classes the labeller used, to see why it got one wrong
Images go to outputs/satellite_images/ (git-ignored), numbered, one per site-day, plus contact_sheet.png.
"""

import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import planetary_computer
import pystac_client
from matplotlib.colors import ListedColormap

from satellite_function import RADIUS_M, STAC_URL, Resampling, munro_grids, read_box, terrain, true_colour

RESULTS_CSV = '../outputs/satellite_vs_sightings.csv'
IMAGE_DIR = '../outputs/satellite_images'
# sentinel-2 scene classes 0-11: no data, defective, dark/shadow, cloud shadow, vegetation, bare, water,
# unclassified, cloud medium, cloud high, thin cirrus, snow
SCL_COLOURS = ListedColormap(['#000000', '#000000', '#3b3b3b', '#555555', '#6f8f5a', '#b59e7a', '#3c6fa8',
                              '#8a8a8a', '#d9d9d9', '#ffffff', '#a6e1f5', '#f3c6f0'])


def scene(scene_id):
    '''one signed sentinel-2 scene'''
    catalog = pystac_client.Client.open(STAC_URL, modifier = planetary_computer.sign_inplace)
    return catalog.get_collection('sentinel-2-l2a').get_item(scene_id)


def draw(axes, rgb, scl, dem, row, number):
    '''one site-day: true colour, and the scene classes beside it if there is a second axis'''
    extent = [-RADIUS_M / 1000, RADIUS_M / 1000, -RADIUS_M / 1000, RADIUS_M / 1000] #km from the summit
    ax_rgb = axes[0]
    ax_rgb.imshow(rgb, extent = extent)
    if len(axes) > 1:
        axes[1].imshow(scl, cmap = SCL_COLOURS, vmin = 0, vmax = 11, extent = extent, interpolation = 'nearest')
    for ax in axes:
        ax.contour(dem[::-1], levels = [row['height_m'] - row['low_drop_m']], colors = '#f5b700', linewidths = 0.8,
                   extent = extent)
        ax.plot(0, 0, marker = '^', color = '#e8590c', markersize = 7, markeredgecolor = 'black')
        ax.set_xticks([]), ax.set_yticks([])
    ax_rgb.set_title('{}. {} {}, pass {} UTC\nyou: {}  satellite: {} (summit cloud {:.0%}, low cloud {:.0%})'.format(
        number, row['date'], str(row['name'])[:28], row['overpass_time'][11:], row['inversion'], row['label'], row['summit_cloud'],
        row['low_cloud']), fontsize = 9, loc = 'left')


results = pd.read_csv(RESULTS_CSV, dtype = {'inversion': str})
results = results[results['scene_id'].notna()].sort_values(['date', 'site_id']).reset_index(drop = True)
grids = munro_grids(results.drop_duplicates('site_id')[['site_id', 'lat', 'lon']])
dem = terrain(grids, id_col = 'site_id')
os.makedirs(IMAGE_DIR, exist_ok = True)
for old in os.listdir(IMAGE_DIR): #images from an earlier run
    if old.endswith('.png'):
        os.remove(os.path.join(IMAGE_DIR, old))
panels = 2 if '--classes' in sys.argv else 1
columns = 4 // panels

rows = -(-len(results) // columns)
sheet, axes = plt.subplots(rows, columns * panels, figsize = (4.6 * columns * panels, 4.6 * rows), squeeze = False)
for ax in axes.flat:
    ax.axis('off')
for i, row in results.iterrows():
    grid = grids[grids['site_id'] == row['site_id']].iloc[0]
    rgb = true_colour(row['scene_id'], grid)
    scl = None
    if panels == 2:
        scl = read_box(scene(row['scene_id']).assets['SCL'].href, grid['transform'], Resampling.nearest)
    number = i + 1
    print('{:3d} {} {}: you {}, satellite {}'.format(number, row['date'], row['name'], row['inversion'], row['label']))
    sheet_axes = axes[i // columns, (i % columns) * panels:(i % columns + 1) * panels]
    for ax in sheet_axes:
        ax.axis('on')
    draw(sheet_axes, rgb, scl, dem[row['site_id']], row, number)
    single, single_axes = plt.subplots(1, panels, figsize = (4.6 * panels, 4.6), squeeze = False)
    draw(single_axes[0], rgb, scl, dem[row['site_id']], row, number)
    single.tight_layout()
    single.savefig('{}/{:03d}_{}_{}.png'.format(IMAGE_DIR, number, row['date'], row['site_id']), dpi = 110)
    plt.close(single)

sheet.tight_layout()
sheet.savefig('{}/contact_sheet.png'.format(IMAGE_DIR), dpi = 60)
print('Saved {} images and contact_sheet.png to {}'.format(len(results), IMAGE_DIR))
