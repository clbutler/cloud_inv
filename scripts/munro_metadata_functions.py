#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 18 13:05:19 2025

@author: chrisbutler
"""


from bs4 import BeautifulSoup
import requests


def get_mountain_name(url):
    '''this function returns the mountain name as aligned with mountain forecast.com'''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    mountain_name = region_soup.find_all('span', class_= ["b-list-table__item-name"," b-list-table__item-name--detail"])
    mountain_names_list = []
    for i in mountain_name:
        mn = i.text.strip()
        if mn:
            mountain_names_list.append(mn)
        else:
            print ("no mountain name found")
    return mountain_names_list
        
def get_mountain_height(url):
    '''this function returns the mountain height in meters as aligned with mountain forecast.com'''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    mountain_height = region_soup.find_all('span', class_= ["b-list-table__item-height"])
    mountain_height_list = []
    for i in mountain_height:
        mh = i.text.strip()
        if mh:
            mountain_height_list.append(mh)
        else:
            print ("no mountain height found")
    return mountain_height_list

def get_mountain_url(url):
    '''this function returns the mountain url where the actual weather data of mountain forecast is stored'''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    mountain_url = region_soup.find_all('span', class_= ["b-list-table__item-name"," b-list-table__item-name--detail"])
    mountain_url_list = []
    for i in mountain_url:
        murl = i.find('a')
        if murl:
            relative_url = murl['href']
            full_url = requests.compat.urljoin(url, relative_url)
            mountain_url_list.append(full_url)
        else:
            print("no mountain url found")
    return mountain_url_list

def get_mountain_base(url):
    '''this function returns the mountain base in meters'''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    base_link = region_soup.find('a', attrs = {'data-elevation-group': 'bot'})
    mountain_base = base_link.find('span', class_='height')
    if mountain_base:
        return mountain_base.text.strip()
    else:
        print("no mountain base found")

def get_mountain_base_url(url):
    '''this function returns the mountain url reporting the weather data at the bottom of the mountain '''
    region = requests.get(url)
    region_soup = BeautifulSoup(region.content, 'html.parser')
    base_link = region_soup.find('a', attrs = {'data-elevation-group': 'bot'})
    relative_mountain_base_url = base_link.get('href')
    mountain_base_url = requests.compat.urljoin(url, relative_mountain_base_url)
    return mountain_base_url


    
     