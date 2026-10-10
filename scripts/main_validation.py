#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Oct 10 2026

@author: chrisbutler

The evidence tables for the README, rebuilt from the hand checks in data/. Run from scripts/:
    python main_validation.py    # about 5 minutes: re-reads every hand-checked satellite view
Three questions:
    1. Can a person tell an inversion from a satellite view? Ground photos against the satellite-view answers.
    2. How good is the automatic labeller? Its label (as it is now) against the satellite-view answers.
    3. How good is the site's forecast? The site's verdict against the satellite-view answers (batch 2), and against
       the labeller on every scored day (outputs/backcast_vs_satellite.csv, from main_backcast.py compare).
Writes outputs/validation_labels.csv and prints the tables as markdown.
"""

from concurrent.futures import ThreadPoolExecutor

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client

from openmeteo_function import munro_locations
from satellite_function import STAC_URL, Resampling, label_box, munro_grids, read_box, terrain

OUTPUT_CSV = '../outputs/validation_labels.csv'
RAG_WORDS = {'Green': 'Likely', 'Amber': 'Possible', 'Red': 'Unlikely'}


def table(df, rows, columns, row_order, column_order):
    '''a markdown count table with totals'''
    t = pd.crosstab(df[rows], df[columns]).reindex(index = row_order, columns = column_order, fill_value = 0)
    lines = ['| | ' + ' | '.join(column_order) + ' | total |', '|---' * (len(column_order) + 2) + '|']
    for r in row_order:
        lines.append('| {} | {} | {} |'.format(r, ' | '.join(str(v) for v in t.loc[r]), t.loc[r].sum()))
    return '\n'.join(lines)


def share(k, n, z = 1.96):
    '''k/n as a percentage with its 95 % (Wilson) range, which is honest about small counts'''
    if n == 0:
        return 'none to count'
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return '{}/{} = {:.0%} (95 % range {:.0%}–{:.0%})'.format(k, n, p, centre - half, centre + half)


def counts(said, truth):
    '''true positives, false positives, false negatives and true negatives of a yes/no call'''
    return (said & truth).sum(), (said & ~truth).sum(), (~said & truth).sum(), (~said & ~truth).sum()


def rates(df, said, truth):
    '''precision and recall of a yes/no call against the hand check'''
    tp, fp, fn, _ = counts(said, truth)
    return 'precision {:.1%} ({}/{}), recall {:.1%} ({}/{})'.format(
        tp / max(tp + fp, 1), tp, tp + fp, tp / max(tp + fn, 1), tp, tp + fn)


####### The hand-checked views #########

munros = munro_locations(gpd.read_file('../outputs/munro.shp')).astype({'munro_id': int}) #the shapefile stores the id as text
views = []
for batch in ['batch1', 'batch2']:
    b = pd.read_csv('../data/satellite_{}_checks.csv'.format(batch), dtype = {'visible': str, 'photo_shows': str})
    b = b.merge(munros[['munro_id', 'lat', 'lon']], on = 'munro_id')
    views.append(b.assign(site_id = 'munro-' + b['munro_id'].astype(str), source = batch, low_drop_m = 300.0))
photo = pd.read_csv('../outputs/satellite_vs_sightings.csv') #from main_satellite_sightings.py
photo = photo[photo['scene_id'].notna()].assign(image = lambda d: d['date'] + '_' + d['site_id'] + '.png')
checks = pd.read_csv('../data/satellite_image_checks.csv', dtype = str, keep_default_na = False)
photo = photo.merge(checks[['image', 'visible', 'photo_inversion']], on = 'image')
views.append(photo.assign(source = 'photo route', held_out = photo['date'] >= '2022-01-01',
                          photo_shows = photo['photo_inversion']))
columns = ['source', 'image', 'site_id', 'date', 'lat', 'lon', 'height_m', 'low_drop_m', 'scene_id', 'held_out',
           'label', 'visible', 'photo_shows', 'rag'] #label: the labeller's verdict when the card was picked
views = pd.concat([v.reindex(columns = columns) for v in views], ignore_index = True)
views['held_out'] = views['held_out'].astype(str) == 'True'


####### Re-label each view with the labeller as it is now #########

grids = munro_grids(views.drop_duplicates('site_id')[['site_id', 'lat', 'lon']]).set_index('site_id')
dem = terrain(grids.reset_index(), id_col = 'site_id')
collection = pystac_client.Client.open(STAC_URL, modifier = planetary_computer.sign_inplace).get_collection('sentinel-2-l2a')

def relabel(row):
    scl = read_box(collection.get_item(row.scene_id).assets['SCL'].href, grids.at[row.site_id, 'transform'],
                   Resampling.nearest)
    return None if scl is None else label_box(scl, dem[row.site_id], row.height_m, row.low_drop_m)['label']

with ThreadPoolExecutor(8) as pool:
    views['rule'] = list(pool.map(relabel, views.itertuples()))
views.to_csv(OUTPUT_CSV, index = False)
answered = views[views['visible'].isin(['Y', 'N'])]
answered = answered.drop_duplicates(['date', 'site_id']) #a site-day checked in two batches counts once


####### 1. Ground photos against satellite-view answers #########

both = views[views['visible'].isin(['Y', 'N']) & views['photo_shows'].isin(['Y', 'N'])]
both = both.assign(photo = both['photo_shows'].map({'Y': 'photo: inversion', 'N': 'photo: none'}),
                   satellite = both['visible'].map({'Y': 'satellite view: inversion', 'N': 'satellite view: none'}))
print('### 1. Ground photo against the satellite-view answer\n')
print(table(both, 'photo', 'satellite', ['photo: inversion', 'photo: none'],
            ['satellite view: inversion', 'satellite view: none']))
said, shown = both['visible'] == 'Y', both['photo_shows'] == 'Y'
agree = (said == shown).mean()
chance = said.mean() * shown.mean() + (1 - said.mean()) * (1 - shown.mean())
print('\n- {} views on {} days; agreement {:.0%}, Cohen\'s kappa {:.2f}'.format(len(both), both['date'].nunique(), agree,
      (agree - chance) / (1 - chance)))
print('- satellite-view yes, photo agrees: ' + share((said & shown).sum(), said.sum()))
print('- photo shows none, satellite view agrees: ' + share((~said & ~shown).sum(), (~shown).sum()))
print('- photo shows one, satellite view sees it: ' + share((said & shown).sum(), shown.sum()) + '\n')

lab = views[views['photo_shows'].isin(['Y', 'N']) & views['rule'].notna() & (views['rule'] != 'no_data')]
said, shown = lab['rule'] == 'inversion', lab['photo_shows'] == 'Y'
print('### 1b. Ground photo against the labeller, with no person in between ({} views)\n'.format(len(lab)))
print('- labeller says inversion, photo agrees: ' + share((said & shown).sum(), said.sum()))
print('- photo shows none, labeller agrees: ' + share((~said & ~shown).sum(), (~shown).sum()))
print('- photo shows one, labeller sees it: ' + share((said & shown).sum(), shown.sum()) + '\n')


####### 2. The labeller against satellite-view answers #########

rule = answered.assign(rule_says = answered['rule'].map(lambda l: 'labeller: inversion' if l == 'inversion'
                                                        else 'labeller: other'),
                       you = answered['visible'].map({'Y': 'checked: inversion', 'N': 'checked: none'}))
print('### 2. The labeller against the satellite-view answer\n')
print(table(rule, 'you', 'rule_says', ['checked: inversion', 'checked: none'], ['labeller: inversion', 'labeller: other']))
print()
for name, part in [('All', rule), ('Held-out days', rule[rule['held_out']]), ('Other days', rule[~rule['held_out']])]:
    print('- {} ({} views, {} days): {}'.format(name, len(part), part['date'].nunique(),
          rates(part, part['rule'] == 'inversion', part['visible'] == 'Y')))
print()


####### 3. The site's forecast against satellite-view answers (batch 2) #########

site = views[(views['source'] == 'batch2') & views['visible'].isin(['Y', 'N'])]
# every Likely and Possible day was picked, but Unlikely days only at random or because the labeller then called them
# an inversion, so the two kinds of Unlikely card are shown apart
flagged = (site['rag'] == 'Red') & (site['label'] == 'inversion')
site = site.assign(verdict = site['rag'].map(RAG_WORDS).mask(site['rag'] == 'Red', 'Unlikely (random)').mask(
                       flagged, 'Unlikely (labeller flagged)'),
                   you = site['visible'].map({'Y': 'checked: inversion', 'N': 'checked: none'}))
print('### 3. The site\'s morning verdict against the satellite-view answer\n')
print(table(site, 'verdict', 'you', ['Likely', 'Possible', 'Unlikely (random)', 'Unlikely (labeller flagged)'],
            ['checked: inversion', 'checked: none']))


####### 4. The site's verdict against the labeller, every scored day #########

backcast = pd.read_csv('../outputs/backcast_vs_satellite.csv')
backcast = backcast[backcast['label'] != 'snow'] #no verdict on a snowy view
print('\n### 4. The site\'s morning verdict against the labeller ({} munro-days, {} days)\n'.format(
    len(backcast), backcast['date'].nunique()))
print('| site\'s verdict | labeller saw an inversion | held-out months | other months |\n|---|---|---|---|')
for rag in ['Green', 'Amber', 'Red']:
    cells = [backcast[backcast['rag'] == rag]] + [backcast[(backcast['rag'] == rag) & (backcast['held_out'] == h)]
                                                 for h in (True, False)]
    print('| {} | {} | {} | {} |'.format(RAG_WORDS[rag], *['{}/{} ({:.1%})'.format(
        (c['label'] == 'inversion').sum(), len(c), (c['label'] == 'inversion').mean()) for c in cells]))

flagged, seen = backcast['rag'].isin(['Green', 'Amber']), backcast['label'] == 'inversion'
tp, fp, fn, tn = counts(flagged, seen)
print('\nConfusion matrix (Likely or Possible counts as yes):\n')
print('| | labeller saw an inversion | labeller saw none |\n|---|---|---|')
print('| **cloudflip said Likely or Possible** | **{}** true positives | **{}** false positives |'.format(tp, fp))
print('| **cloudflip said Unlikely** | **{}** false negatives | **{:,}** true negatives |'.format(fn, tn))
print('\n- all months: ' + rates(backcast, flagged, seen))
for h, idx in backcast.groupby('held_out').groups.items():
    print('- {}: '.format('held-out months' if h else 'other months') + rates(backcast.loc[idx], flagged[idx], seen[idx]))
print('- accuracy {:.1%}; saying Unlikely every day would score {:.1%}'.format((tp + tn) / max(len(backcast), 1),
      1 - seen.mean()))
print('- inversions on {:.2%} of mornings; Likely or Possible makes one {:.1f} times as likely'.format(
    seen.mean(), tp / max(tp + fp, 1) / max(seen.mean(), 1e-9)))
print('- Likely on its own: ' + share((backcast['rag'] == 'Green').where(seen, False).sum(), (backcast['rag'] == 'Green').sum()))
