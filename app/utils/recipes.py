"""
Recipe form utilities for Menu Maker App.
"""

from flask import request
from app.utils.validation import MacroValidator
from app.database import get_database

def submit_recipe():
    """
    Process and save a recipe submission to Supabase.
    
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

        # Validate macros before proceeding
        validation_result = MacroValidator.validate_macros(calories, protein, fat, carbs)
        if not validation_result['valid']:
            errors = MacroValidator.get_validation_errors(validation_result)
            print(f"Validation failed: {errors}")
            return False

        # Format data for Supabase insertion (matches actual Recipes table schema)
        recipe_data = {
            'calories': calories,
            'carbs': carbs,
            'category': 'Dinner',  # Default category
            'fat': fat,
            'protein': protein,
            'source': request.form.get('source'),
            'title': request.form.get('title'),
            'url': request.form.get('url'),
            'is_submitted_recipe': 1  # Mark as user-submitted recipe
        }

        # Validate required fields
        required = ['calories', 'carbs', 'fat', 'protein', 'source', 'title', 'url']
        if not all(recipe_data.get(field) for field in required):
            print("Missing required fields")
            return False

        # Write to Supabase
        db = get_database()
        success = db.add_user_recipe(recipe_data)
        
        if success:
            print(f"Recipe '{recipe_data['title']}' successfully saved to Supabase")
        else:
            print("Failed to save recipe to Supabase")
        
        return success
        
    except (ValueError, KeyError) as e:
        print(f"Error saving recipe: {str(e)}")  # For debugging
        return False

