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
        # Determine recipe type from form
        recipe_type = request.form.get('recipe_type', 'submitted')

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

        # ── Front-gate ingredient validation for custom recipes ──────────
        # Parse ingredients BEFORE any database write. If parsing fails,
        # return False immediately — no recipe is ever saved to Supabase.
        ingredient_rows = None
        if recipe_type == 'custom':
            raw_ingredients_text = request.form.get('ingredients', '')
            ingredient_rows = shopping.parse_raw_ingredients(raw_ingredients_text)
            if not ingredient_rows:
                print(f"Custom recipe '{request.form.get('title')}' has no valid ingredients; rejected before save.")
                return False
        # ─────────────────────────────────────────────────────────────────

        # Format data for Supabase insertion (matches actual Recipes table schema)
        # NOTE: is_submitted_recipe is kept for backward compatibility until the
        # column is dropped from the database (post-deploy migration step).
        # Both 'submitted' (URL-based) and 'custom' recipes are user-submitted,
        # so they both get is_submitted_recipe = 1.
        is_submitted = 1 if recipe_type in ('submitted', 'custom') else 0
        recipe_data = {
            'calories': calories,
            'carbs': carbs,
            'category': 'Dinner',  # Default category
            'fat': fat,
            'protein': protein,
            'title': request.form.get('title'),
            'recipe_type': recipe_type,
            'is_submitted_recipe': is_submitted,
        }

        if recipe_type == 'custom':
            # Custom recipes: url is optional, source is auto-set
            recipe_data['source'] = 'Custom Recipe'
            recipe_data['url'] = request.form.get('url', '')  # may be empty
            # Store ingredients raw text and instructions
            recipe_data['ingredients_raw_text'] = request.form.get('ingredients', '')
            recipe_data['instructions'] = request.form.get('instructions', '')
        else:
            # Scraped/submitted: url and source required
            recipe_data['source'] = request.form.get('source')
            recipe_data['url'] = request.form.get('url')
            recipe_data['instructions'] = request.form.get('instructions', '')

        # Validate required fields
        required = ['calories', 'carbs', 'fat', 'protein', 'title']
        if recipe_type != 'custom':
            required.extend(['source', 'url'])
        if not all(recipe_data.get(field) for field in required):
            print(f"Missing required fields: {required}")
            return False

        # Write to Supabase and parse ingredients
        db = get_database()
        recipe_record = db.add_user_recipe(recipe_data)
        if not recipe_record:
            print("Failed to save recipe to Supabase")
            return False

        recipe_id = recipe_record.get('PK') or recipe_record.get('id') or recipe_record.get('ID') or recipe_record.get('Id')
        if recipe_id:
            if ingredient_rows is None:
                # Scraped/submitted recipe: parse from URL
                ingredient_rows = shopping.parse_recipe_ingredients(recipe_data['url'])

            if ingredient_rows:
                saved = db.add_recipe_ingredients(recipe_id, ingredient_rows)
                if saved:
                    db.mark_recipe_ingredients_parsed(recipe_id, True)
                    print(f"Recipe '{recipe_data['title']}' successfully saved to Supabase (PK={recipe_id})")
                    return True
                else:
                    print(f"Failed to save ingredient rows for recipe {recipe_id}")
                    return False
            else:
                print(f"No ingredients parsed for recipe {recipe_data.get('title', recipe_id)}. "
                      "Scraped recipe saved but excluded from menu generation until parsing succeeds.")
        else:
            print("Warning: Recipe saved without returned ID; ingredient parsing was skipped.")

        print(f"Recipe '{recipe_data['title']}' successfully saved to Supabase")
        return True

    except (ValueError, KeyError) as e:
        print(f"Error saving recipe: {str(e)}")  # For debugging
        return False