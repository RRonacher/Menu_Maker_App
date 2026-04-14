"""
menu_maker.py
Module for menu creation, recipe selection, and menu updating logic.
Uses pandas for data manipulation and nutrition module for calculations.
"""

import pandas as pd
from app.menu_calculator import nutrition
import random as rand
import os
import json
import ast
import re
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
    # Try database first
    try:
        from app.database import get_database
        db = get_database()
        print('DB connection successful, fetching recipes...')
        recipe_df = db.get_recipes_df(category_filter='Dinner')
        print(f"Fetched {len(recipe_df)} recipes from database.")
        # block_df = db.get_blocked_recipes_df()
        # my_recipe_df = db.get_user_recipes_df()
    except Exception as e:
        print(f"Database not available: {e}")
        return False   

    # Continue with common logic for both database and CSV
    # Ensure merge columns are all the same type
    merge_cols = ['calories', 'carbs', 'fat', 'protein', 'rating', 'review_count']
    for col in merge_cols:
        if col in recipe_df.columns:
            recipe_df[col] = pd.to_numeric(recipe_df[col], errors='coerce')

    # Filter out blocked recipes
    df_all = recipe_df

    # Exclude recipes that have not successfully parsed ingredients, if the schema contains that marker.
    if 'ingredients_parsed' in df_all.columns:
        try:
            df_all = df_all[df_all['ingredients_parsed'] == True]
        except Exception:
            pass

    unblock_recipe_df = df_all

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
        print(df.head())
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
