#!/usr/bin/env python3
"""
Migration script: convert the `nutrition` column in recipes.csv to JSON strings.
Backs up the original CSV to recipes.csv.bak.TIMESTAMP before writing.
"""
import os
import pandas as pd
import json
import ast
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(__file__))
RECIPE_CSV = os.path.join(ROOT, 'recipe_scraper', 'recipe_scraper', 'spiders', 'recipes.csv')

if not os.path.exists(RECIPE_CSV):
    print('recipes.csv not found at expected path:', RECIPE_CSV)
    raise SystemExit(1)

bak_name = RECIPE_CSV + '.bak.' + datetime.now().strftime('%Y%m%d%H%M%S')
print('Backing up', RECIPE_CSV, '->', bak_name)
os.replace(RECIPE_CSV, bak_name)

# Read backup, transform, and write new CSV
print('Reading backup...')
df = pd.read_csv(bak_name)

# helper to parse existing nutrition cell

def parse_nut_cell(cell, row):
    if pd.isna(cell):
        return None
    if isinstance(cell, dict):
        return cell
    val = str(cell).strip()
    # try json
    try:
        return json.loads(val)
    except Exception:
        pass
    # try literal_eval
    try:
        return ast.literal_eval(val)
    except Exception:
        pass
    # crude extraction
    nut = {}
    m = re.search(r"(\d+)\s*calor", val, re.IGNORECASE)
    if m:
        nut['calories'] = int(m.group(1))
    else:
        try:
            nut['calories'] = int(float(row.get('calories', 0)))
        except Exception:
            nut['calories'] = 0
    m = re.search(r"(\d+\.?\d*)\s*carb", val, re.IGNORECASE)
    if m:
        nut['carbs'] = float(m.group(1))
    else:
        try:
            nut['carbs'] = float(row.get('carbs', 0))
        except Exception:
            nut['carbs'] = 0.0
    m = re.search(r"(\d+\.?\d*)\s*protein", val, re.IGNORECASE)
    if m:
        nut['protein'] = float(m.group(1))
    else:
        try:
            nut['protein'] = float(row.get('protein', 0))
        except Exception:
            nut['protein'] = 0.0
    m = re.search(r"(\d+\.?\d*)\s*fat", val, re.IGNORECASE)
    if m:
        nut['fat'] = float(m.group(1))
    else:
        try:
            nut['fat'] = float(row.get('fat', 0))
        except Exception:
            nut['fat'] = 0.0
    return nut

print('Transforming nutrition column...')
new_rows = []
for idx, row in df.iterrows():
    cell = row.get('nutrition', None) if 'nutrition' in df.columns else None
    nut = parse_nut_cell(cell, row)
    if nut is None:
        # fallback to columns
        try:
            calories = int(float(row.get('calories', 0)))
        except Exception:
            calories = 0
        try:
            carbs = float(row.get('carbs', 0))
        except Exception:
            carbs = 0.0
        try:
            protein = float(row.get('protein', 0))
        except Exception:
            protein = 0.0
        try:
            fat = float(row.get('fat', 0))
        except Exception:
            fat = 0.0
        nut = {'calories': calories, 'carbs': carbs, 'protein': protein, 'fat': fat}
    # ensure types
    try:
        nut['calories'] = int(float(nut.get('calories', 0)))
    except Exception:
        nut['calories'] = 0
    try:
        nut['carbs'] = float(nut.get('carbs', 0))
    except Exception:
        nut['carbs'] = 0.0
    try:
        nut['protein'] = float(nut.get('protein', 0))
    except Exception:
        nut['protein'] = 0.0
    try:
        nut['fat'] = float(nut.get('fat', 0))
    except Exception:
        nut['fat'] = 0.0

    # set nutrition JSON
    row['nutrition'] = json.dumps(nut)
    # also ensure calories/carbs/protein/fat columns consistent
    row['calories'] = nut['calories']
    row['carbs'] = nut['carbs']
    row['protein'] = nut['protein']
    row['fat'] = nut['fat']
    new_rows.append(row)

new_df = pd.DataFrame(new_rows)
print('Writing updated CSV to', RECIPE_CSV)
new_df.to_csv(RECIPE_CSV, index=False)
print('Migration complete. Backup saved at', bak_name)
