#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb 16 19:55:24 2025

@author: chrisbutler
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://www.mountain-forecast.com/peaks/Ben-Lomond/forecasts/0"

response = requests.get(url)

soup = BeautifulSoup(response.text, "html.parser")

#print(soup)

#print(soup.prettify())

table = soup.find("table")


# Initialize a list to store the table data
data = []

# Extract the table header (if exists)
header = table.find_all('th')
headers = [th.get_text(strip=True) for th in header]  # Extract the header names

# Extract the table rows
rows = table.find_all('tr')

# Loop through each row and extract the cell data
for row in rows:
    cells = row.find_all('td')
    row_data = [cell.get_text(strip=True) for cell in cells]
    if row_data:  # Avoid empty rows
        data.append(row_data)

# Create a DataFrame (use headers if you have them)
df = pd.DataFrame(data, columns=headers if headers else None)

# Print the DataFrame
print(df)