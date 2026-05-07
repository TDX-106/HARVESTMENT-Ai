import pandas as pd
import numpy as np

df = pd.read_csv('final_merged_crop_weather_soil_irrigation_data.csv')
df = df[df['Yield'] > 0]

print('=== DATASET OVERVIEW ===')
print('Total rows:', len(df))
col_year = 'Year' if 'Year' in df.columns else None
if col_year:
    print('Year range:', df[col_year].min(), '-', df[col_year].max())

print()
print('=== YIELD STATS BY CROP (t/ha) ===')
stats = df.groupby('Crop')['Yield'].agg(['mean','std','min','max','count']).round(2)
print(stats.sort_values('mean', ascending=False).to_string())

print()
print('=== EXTREME OUTLIERS (Yield > 200 t/ha) ===')
outliers = df[df['Yield'] > 200][['Crop','district','Yield']]
print('Rows with yield > 200:', len(outliers))
print(outliers.head(10).to_string())

print()
print('=== DATA QUALITY ===')
key_cols = ['Yield','soil_fertility_score','irrigation_score']
key_cols = [c for c in key_cols if c in df.columns]
print('Null counts:')
print(df[key_cols].isnull().sum())

print()
print('=== CROP COUNT PER DISTRICT (top crops) ===')
print(df.groupby('Crop').size().sort_values(ascending=False).head(15))
