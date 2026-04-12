"""
menu_maker.py
Module for menu creation, recipe selection, and menu updating logic.
Uses pandas for data manipulation and nutrition module for calculations.
"""

import pandas as pd
from app.menu_calculator import nutrition
import random as rand
import os
import copy
import json
import ast
import re

recipes_needed = 4

def get_all_recipes():
    """
    Load all recipes, excluding blocked ones, and combine with user recipes.
    Returns:
        pd.DataFrame: DataFrame of unblocked recipes.
    """
    script_dir = os.path.dirname(__file__)
    recipe_df_path = os.path.join(script_dir, '../recipe_scraper/recipe_scraper/spiders/recipes.csv')
    recipe_block_path = os.path.join(script_dir, '../recipe_scraper/recipe_scraper/spiders/master_blocked_recipes.csv')
    my_recipe_df_path = os.path.join(script_dir, 'my_recipes.csv')

    recipe_df = pd.read_csv(recipe_df_path)

    # Normalize nutrition column: attempt to parse JSON, fall back to literal_eval or string extraction
    def _parse_nutrition_cell(cell, row):
        # Try JSON first
        if pd.isna(cell):
            return None
        if isinstance(cell, dict):
            return cell
        try:
            if isinstance(cell, str):
                val = cell.strip()
                # common case: JSON string
                try:
                    parsed = json.loads(val)
                    return parsed
                except Exception:
                    pass
                # fallback: python dict literal
                try:
                    parsed = ast.literal_eval(val)
                    return parsed
                except Exception:
                    pass
                # fallback: crude extraction of numbers from text
                # look for calories, carbs, protein, fat keys
                nut = {}
                # calories
                m = re.search(r"(\d+)\s*calor", val, re.IGNORECASE)
                if m:
                    nut['calories'] = int(m.group(1))
                else:
                    # try to use row calories column
                    try:
                        nut['calories'] = int(float(row.get('calories', 0)))
                    except Exception:
                        nut['calories'] = 0
                # carbs
                m = re.search(r"(\d+\.?\d*)\s*carb", val, re.IGNORECASE)
                if m:
                    nut['carbs'] = float(m.group(1))
                else:
                    try:
                        nut['carbs'] = float(row.get('carbs', 0))
                    except Exception:
                        nut['carbs'] = 0.0
                # protein
                m = re.search(r"(\d+\.?\d*)\s*protein", val, re.IGNORECASE)
                if m:
                    nut['protein'] = float(m.group(1))
                else:
                    try:
                        nut['protein'] = float(row.get('protein', 0))
                    except Exception:
                        nut['protein'] = 0.0
                # fat
                m = re.search(r"(\d+\.?\d*)\s*fat", val, re.IGNORECASE)
                if m:
                    nut['fat'] = float(m.group(1))
                else:
                    try:
                        nut['fat'] = float(row.get('fat', 0))
                    except Exception:
                        nut['fat'] = 0.0
                return nut
        except Exception:
            return None
        return None

    # Apply parsing to nutrition column and ensure numeric columns are populated
    if 'nutrition' in recipe_df.columns:
        parsed = []
        for idx, r in recipe_df.iterrows():
            nut = _parse_nutrition_cell(r.get('nutrition'), r)
            if nut:
                # ensure types
                try:
                    recipe_df.at[idx, 'calories'] = int(float(nut.get('calories', recipe_df.at[idx, 'calories'] if 'calories' in recipe_df.columns else 0)))
                except Exception:
                    pass
                try:
                    recipe_df.at[idx, 'carbs'] = float(nut.get('carbs', recipe_df.at[idx, 'carbs'] if 'carbs' in recipe_df.columns else 0.0))
                except Exception:
                    pass
                try:
                    recipe_df.at[idx, 'protein'] = float(nut.get('protein', recipe_df.at[idx, 'protein'] if 'protein' in recipe_df.columns else 0.0))
                except Exception:
                    pass
                try:
                    recipe_df.at[idx, 'fat'] = float(nut.get('fat', recipe_df.at[idx, 'fat'] if 'fat' in recipe_df.columns else 0.0))
                except Exception:
                    pass

    # Filter for recipes where category contains 'Dinner'
    recipe_df = recipe_df[recipe_df['category'].str.contains('Dinner', case=False, na=False)]
    nutrition.clean_up_recipes(recipe_df)
    block_df = pd.read_csv(recipe_block_path)
    # Ensure merge columns are all the same type (float for calories, carbs, fat, protein, rating, reviewCount)
    merge_cols = ['calories', 'carbs', 'fat', 'protein', 'rating', 'reviewCount']
    for col in merge_cols:
        if col in recipe_df.columns:
            recipe_df[col] = pd.to_numeric(recipe_df[col], errors='coerce')
        if col in block_df.columns:
            block_df[col] = pd.to_numeric(block_df[col], errors='coerce')
    # nutrition, source, title, url, category should be string
    str_cols = ['nutrition', 'source', 'title', 'url', 'category']
    for col in str_cols:
        if col in recipe_df.columns:
            recipe_df[col] = recipe_df[col].astype(str)
        if col in block_df.columns:
            block_df[col] = block_df[col].astype(str)
    df_all = recipe_df.merge(
        block_df.drop_duplicates(),
        on=['calories', 'carbs', 'fat', 'nutrition', 'protein', 'rating', 'reviewCount', 'source', 'title', 'url', 'category'],
        how='left', indicator=True
    )
    unblock_recipe_df = df_all[df_all['_merge'] == 'left_only']
    unblock_recipe_df = unblock_recipe_df.drop('_merge', axis=1).reset_index()

    try:
        my_recipe_df = pd.read_csv(my_recipe_df_path)
        unblock_recipe_df = pd.concat([my_recipe_df, unblock_recipe_df])
        unblock_recipe_df = unblock_recipe_df.reset_index(drop=True).drop(columns='index')
    except Exception:
        pass

    if "Tilapia Veracruz & Spanish Rice" in unblock_recipe_df['title'].values:
        print("Tilapia Veracruz & Spanish Rice is in the unblock_recipe_df")
    else:
        print("Tilapia Veracruz & Spanish Rice is not in the unblock_recipe_df")

    return unblock_recipe_df

def select_recipes(titles, indexes):
    """
    Select recipe titles by their indexes.
    Args:
        titles (pd.Series): List of recipe titles.
        indexes (list): List of indexes to select.
    Returns:
        list: Selected recipe titles.
    """
    return [titles[index] for index in indexes]


def make_menu(df):
    """
    Create a new menu and populate it with recipes from the DataFrame.
    Args:
        df (pd.DataFrame): DataFrame of recipes.
    Returns:
        nutrition.Menu: Populated menu object.
    """
    menu = nutrition.Menu()
    get_menu_with_recipes(menu, df)
    return menu


def update_menu(menu, df):
    """
    Update an existing menu by keeping selected recipes and recalculating nutrition.
    Args:
        menu (nutrition.Menu): Menu object to update.
        df (pd.DataFrame): DataFrame of recipes.
    Returns:
        tuple: (updated menu, DataFrame)
    """
    print('menu being updated')
    menu.recipes_df = menu.recipes_df.loc[menu.recipes_df['keep'] == True]
    menu.aggregate_nutrition()
    menu.calculate_nutrition_percentages()
    menu.check_is_balanced_menu()
    get_menu_with_recipes(menu, df)
    return menu, df


def get_menu_with_recipes(menu, df):
    """
    Populate a menu with recipes, ensuring it is balanced.
    Args:
        menu (nutrition.Menu): Menu object to populate.
        df (pd.DataFrame): DataFrame of recipes.
    Returns:
        nutrition.Menu: Balanced menu object.
    """
    counter = 0
    while not menu.balanced and counter < 1000:
        try:
            keep_df = menu.recipes_df[menu.recipes_df['keep'] == True]
        except Exception:
            keep_df = []
        menu.reset_nutrition()
        counter += 1
        num_recipes = len(df.index)
        titles = df['title']

        recipe_indexes = []
        while len(recipe_indexes) < recipes_needed - len(keep_df):
            rand_num = rand.randint(0, num_recipes - 1)
            if rand_num not in recipe_indexes:
                recipe_indexes.append(rand_num)
        week_recipes = select_recipes(titles, recipe_indexes)

        new_df = df[df['title'].isin(week_recipes)].copy()
        new_df.loc[:, 'keep'] = False

        try:
            menu.recipes_df = pd.concat([keep_df, new_df])
        except Exception:
            menu.recipes_df = new_df

        menu.aggregate_nutrition()
        menu.calculate_nutrition_percentages()
        menu.check_is_balanced_menu()

    print(f'menu created in {counter} attempts')
    return menu

def get_potential_options(menu):
    """
    Generate potential menu options by including all kept recipes and every other combination.
    Exclude any menu that fails is_balanced_menu.
    Args:
        menu (nutrition.Menu): Current menu object.
    Returns:
        list: List of valid recipe options.
    """
    try:
        keep_df = menu.recipes_df[menu.recipes_df['keep'] == True]
    except Exception:
        keep_df = []

    df = get_all_recipes()
    titles = df['title']
    option_list = []

    if len(keep_df) == 3:
        for i in range(len(df) - len(keep_df) + 1):
            option_list.append(select_recipes(titles, [i])[0])
    else:
        return False

    return_list = []
    for option in option_list:
        temp_menu = copy.copy(menu)
        new_df = df[df['title'].isin([option])].copy()
        new_df.loc[:, 'keep'] = False
        temp_menu.recipes_df = pd.concat([keep_df, new_df])
        temp_menu.reset_nutrition()
        temp_menu.aggregate_nutrition()
        temp_menu.calculate_nutrition_percentages()
        temp_menu.check_is_balanced_menu()
        if temp_menu.balanced:
            return_list.append(option)

    print(option_list)
    print('Option List Generated Successfully')
    return return_list
