"""
Recipe form utilities for Menu Maker App.
"""

from flask import request
from app.utils.validation import MacroValidator
from app.database import get_database
from app.utils import shopping

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

        # Write to Supabase and parse ingredients if the recipe is saved
        db = get_database()
        recipe_record = db.add_user_recipe(recipe_data)
        if not recipe_record:
            print("Failed to save recipe to Supabase")
            return False

        recipe_id = recipe_record.get('PK') or recipe_record.get('id') or recipe_record.get('ID') or recipe_record.get('Id')
        if recipe_id:
            ingredient_rows = shopping.parse_recipe_ingredients(recipe_data['url'])
            if ingredient_rows:
                saved = db.add_recipe_ingredients(recipe_id, ingredient_rows)
                if saved:
                    db.mark_recipe_ingredients_parsed(recipe_id, True)
                else:
                    print(f"Failed to save ingredient rows for recipe {recipe_id}")
            else:
                print(f"No ingredients parsed for recipe {recipe_id}. Recipe will be saved but excluded from menu generation until parsing succeeds.")
        else:
            print("Warning: Recipe saved without returned ID; ingredient parsing was skipped.")

        print(f"Recipe '{recipe_data['title']}' successfully saved to Supabase")
        return True
        
    except (ValueError, KeyError) as e:
        print(f"Error saving recipe: {str(e)}")  # For debugging
        return False

