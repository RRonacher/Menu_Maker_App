"""
Recipe form utilities for Menu Maker App.
"""

import pandas as pd
from flask import request
import os
import json

def submit_recipe():
    """
    Process and save a recipe submission from the form.
    Format: calories,carbs,category,fat,nutrition,protein,rating,reviewCount,source,title,url
    Returns:
        bool: True if submission was successful, False otherwise
    """
    try:
        # Get and validate form data
        # calories should be integer per requirements
        calories = int(request.form.get('calories'))
        carbs = float(request.form.get('carbs'))
        protein = float(request.form.get('protein'))
        fat = float(request.form.get('fat'))

        # Create nutrition dictionary (keep numeric types)
        nutrition = {
            'calories': calories,
            'carbs': carbs,
            'protein': protein,
            'fat': fat
        }

        # Format data in correct order with defaults
        recipe_data = {
            'calories': calories,
            'carbs': carbs,
            'category': 'Dinner',  # Default category
            'fat': fat,
            'nutrition': json.dumps(nutrition),  # Store as JSON string
            'protein': protein,
            'rating': 0.1,  # Default rating
            'reviewCount': 0.1,  # Default review count
            'source': request.form.get('source'),
            'title': request.form.get('title'),
            'url': request.form.get('url')
        }

        # Validate required fields
        if not all(str(v).strip() for v in recipe_data.values()):
            return False

        # Create a DataFrame row with correct column order
        df_new = pd.DataFrame([recipe_data])

        # Get path to recipes.csv
        recipes_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                  'recipe_scraper', 'recipe_scraper', 'spiders', 'recipes.csv')

        # Append to existing CSV or create new one
        if os.path.exists(recipes_path):
            df_new.to_csv(recipes_path, mode='a', header=False, index=False)
        else:
            df_new.to_csv(recipes_path, index=False)

        return True
    except (ValueError, KeyError, OSError) as e:
        print(f"Error saving recipe: {str(e)}")  # For debugging
        return False
