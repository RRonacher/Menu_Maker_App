"""
Recipe routes for Menu Maker App.
"""
from flask import Blueprint, render_template, request, flash, current_app, abort, redirect, url_for, session, jsonify
from app.utils.recipes import submit_recipe
from app.utils.validation import MacroValidator
from app.database import get_database
from app.utils import shopping
import subprocess
import sys
import os
import logging
import json

recipe_bp = Blueprint('recipe', __name__, url_prefix='/recipe')


def get_recipe_by_id(recipe_id):
    """Fetch a single recipe from Supabase by its PK."""
    try:
        db = get_database()
        recipe = db.client.table('Recipes').select('*').eq('PK', recipe_id).execute()
        if recipe.data and len(recipe.data) > 0:
            return recipe.data[0]
    except Exception as e:
        current_app.logger.error(f"Error fetching recipe {recipe_id}: {e}")
    return None


def get_ingredients_for_recipe(recipe_id):
    """Fetch ingredient rows for a recipe from Recipe_Ingredients."""
    try:
        db = get_database()
        rows = db.get_ingredients_for_recipes([recipe_id])
        return rows
    except Exception as e:
        current_app.logger.error(f"Error fetching ingredients for recipe {recipe_id}: {e}")
    return []


@recipe_bp.route('/', methods=['GET', 'POST'])
def recipe():
    """Recipe submission form — supports both scraped (URL) and custom (raw text) recipes."""
    if request.method == 'POST':
        recipe_type = request.form.get('recipe_type', 'submitted')

        # Build required fields based on recipe type
        if recipe_type == 'custom':
            required_fields = ['title', 'calories', 'carbs', 'protein', 'fat', 'ingredients']
        else:
            required_fields = ['title', 'url', 'source', 'calories', 'carbs', 'protein', 'fat']

        if not all(field in request.form for field in required_fields):
            flash('Please fill in all required fields.', 'error')
            session['form_data'] = dict(request.form)
            return redirect(url_for('recipe.recipe'))

        # Validate macro nutrients with comprehensive range checking
        calories = request.form.get('calories')
        protein = request.form.get('protein')
        fat = request.form.get('fat')
        carbs = request.form.get('carbs')

        validation_result = MacroValidator.validate_macros(calories, protein, fat, carbs)
        if not validation_result['valid']:
            errors = MacroValidator.get_validation_errors(validation_result)
            for error in errors:
                flash(error, 'error')
            current_app.logger.warning(f"Recipe validation failed: {errors}")
            session['form_data'] = dict(request.form)
            return redirect(url_for('recipe.recipe'))

        # Save form data into session BEFORE calling submit_recipe so it's
        # always preserved on redirect if the save fails or is rolled back.
        session['form_data'] = dict(request.form)

        try:
            success = submit_recipe()
            if success:
                flash('Recipe successfully added to the database!', 'success')
                # If the recipe was submitted by another tab or repeated
                # submission, form_data may have been popped already, but
                # it's safe to pop again.
                session.pop('form_data', None)
            else:
                flash('Failed to save recipe. Please check your input and try again.', 'error')
                return redirect(url_for('recipe.recipe'))
        except ValueError:
            flash('Please enter valid numbers for nutritional values.', 'error')
            return redirect(url_for('recipe.recipe'))

        # Redirect to GET to prevent form resubmission on refresh
        return redirect(url_for('recipe.recipe'))

    # GET request
    form_data = session.pop('form_data', None)
    return render_template('recipe.html', form_data=form_data)


@recipe_bp.route('/view/<path:recipe_id>')
def view_recipe(recipe_id):
    """Display a single recipe's detail page — used for custom (URL-less) recipes."""
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        abort(404)

    # Gather nutrition info
    nutrition = {
        'calories': recipe.get('calories', 0),
        'carbs': recipe.get('carbs', 0),
        'protein': recipe.get('protein', 0),
        'fat': recipe.get('fat', 0)
    }

    # Gather ingredients from Recipe_Ingredients table
    ingredient_rows = get_ingredients_for_recipe(recipe_id)

    # Build display-friendly ingredient list
    ingredients = []
    for row in ingredient_rows:
        raw = row.get('raw_text', '')
        canonical = row.get('canonical_text', '')
        qty = row.get('quantity', '')
        unit = row.get('unit', '')
        if qty and unit:
            display = f"{qty} {unit} {canonical}" if canonical else f"{qty} {unit} {raw}"
        elif qty:
            display = f"{qty} {canonical}" if canonical else f"{qty} {raw}"
        else:
            display = canonical if canonical else raw
        ingredients.append(display)

    instructions = recipe.get('instructions', '')
    recipe_type = recipe.get('recipe_type', 'scraped')

    return render_template(
        'recipe_view.html',
        recipe=recipe,
        nutrition=nutrition,
        ingredients=ingredients,
        instructions=instructions,
        recipe_type=recipe_type,
        recipe_id=recipe_id
    )


@recipe_bp.route('/edit/<path:recipe_id>', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    """Edit a custom recipe — only for recipe_type='custom'."""
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        abort(404)

    if recipe.get('recipe_type') != 'custom':
        flash('Only custom recipes can be edited directly.', 'error')
        return redirect(url_for('recipe.view_recipe', recipe_id=recipe_id))

    if request.method == 'POST':
        # Collect form data for update
        title = request.form.get('title', recipe.get('title'))
        calories = request.form.get('calories', recipe.get('calories'))
        carbs = request.form.get('carbs', recipe.get('carbs'))
        protein = request.form.get('protein', recipe.get('protein'))
        fat = request.form.get('fat', recipe.get('fat'))
        ingredients_raw = request.form.get('ingredients', '')
        instructions = request.form.get('instructions', '')

        # Validate macros
        validation_result = MacroValidator.validate_macros(calories, protein, fat, carbs)
        if not validation_result['valid']:
            errors = MacroValidator.get_validation_errors(validation_result)
            for error in errors:
                flash(error, 'error')
            return render_template(
                'recipe_edit.html',
                recipe=recipe,
                ingredients_raw=ingredients_raw,
                instructions=instructions
            )

        try:
            db = get_database()
            update_data = {
                'title': title,
                'calories': int(calories),
                'carbs': float(carbs),
                'protein': float(protein),
                'fat': float(fat),
                'instructions': instructions,
                'ingredients_raw_text': ingredients_raw
            }
            db.client.table('Recipes').update(update_data).eq('PK', recipe_id).execute()

            # Re-parse and re-insert ingredients
            ingredient_rows = shopping.parse_raw_ingredients(ingredients_raw)
            if ingredient_rows:
                # Delete old ingredients first
                db.client.table('Recipe_Ingredients').delete().eq('recipe_id', recipe_id).execute()
                # Insert new ones
                db.add_recipe_ingredients(recipe_id, ingredient_rows)
                db.mark_recipe_ingredients_parsed(recipe_id, True)
            else:
                flash('Warning: No valid ingredients could be parsed from your input.', 'error')
                return render_template(
                    'recipe_edit.html',
                    recipe=recipe,
                    ingredients_raw=ingredients_raw,
                    instructions=instructions
                )

            flash('Recipe updated successfully!', 'success')
            return redirect(url_for('recipe.view_recipe', recipe_id=recipe_id))
        except Exception as e:
            current_app.logger.error(f"Error updating recipe {recipe_id}: {e}")
            flash('Failed to update recipe. Please try again.', 'error')

    # GET request — prepopulate form
    ingredient_rows = get_ingredients_for_recipe(recipe_id)
    raw_lines = recipe.get('ingredients_raw_text', '')
    if not raw_lines and ingredient_rows:
        raw_lines = '\n'.join(row.get('raw_text', '') for row in ingredient_rows)
    instructions = recipe.get('instructions', '')

    return render_template(
        'recipe_edit.html',
        recipe=recipe,
        ingredients_raw=raw_lines,
        instructions=instructions
    )


@recipe_bp.route('/delete/<path:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    """Delete a custom recipe and its associated ingredients."""
    recipe = get_recipe_by_id(recipe_id)
    if not recipe:
        abort(404)

    if recipe.get('recipe_type') != 'custom':
        flash('Only custom recipes can be deleted.', 'error')
        return redirect(url_for('menu.menu'))

    try:
        db = get_database()
        # Delete associated ingredients first
        db.client.table('Recipe_Ingredients').delete().eq('recipe_id', recipe_id).execute()
        # Delete the recipe
        db.client.table('Recipes').delete().eq('PK', recipe_id).execute()
        flash('Recipe deleted successfully.', 'success')
    except Exception as e:
        current_app.logger.error(f"Error deleting recipe {recipe_id}: {e}")
        flash('Failed to delete recipe. Please try again.', 'error')

    return redirect(url_for('menu.menu'))


@recipe_bp.route('/validate_ingredients', methods=['POST'])
def validate_ingredients():
    """API endpoint to validate raw ingredient text without saving.
    
    Returns JSON with success/error info for client-side validation.
    """
    raw_text = request.form.get('ingredients', '')
    if not raw_text.strip():
        return jsonify({'valid': False, 'error': 'Please enter at least one ingredient.'})

    rows = shopping.parse_raw_ingredients(raw_text)
    if not rows:
        return jsonify({
            'valid': False,
            'error': "We couldn't parse any ingredients from your list. "
                     "Please format one ingredient per line (e.g., '1 cup flour')."
        })

    return jsonify({'valid': True, 'count': len(rows)})


@recipe_bp.route('/import', methods=['POST'])
def import_recipes():
    """Trigger normalize/import script to recompute normalized/canonical columns.

    This endpoint is intended for developer use and will call the recompute
    script found under `app/recipe_scraper/recipe_scraper/spiders/normalize_ingredients_csv.py`.
    """
    # Protect this developer-only endpoint by config flag
    if not current_app.config.get('ALLOW_DEV_IMPORT', False):
        # pretend the endpoint doesn't exist in production
        abort(404)

    # Locate the normalize script inside the package
    script_path = os.path.join(current_app.root_path, 'recipe_scraper', 'recipe_scraper', 'spiders', 'normalize_ingredients_csv.py')
    if not os.path.exists(script_path):
        flash('Recompute script not found.', 'error')
        return render_template('recipe.html')

    # Run as subprocess to isolate execution from the Flask worker
    cmd = [sys.executable, script_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            flash('Recompute script executed (check spiders output).', 'success')
        else:
            # log stderr to console (or the app logger) and show generic error to user
            try:
                current_app.logger.error('Recompute failed: %s', proc.stderr)
            except Exception:
                print('Recompute failed:', proc.stderr)
            flash('Recompute script failed (see server logs).', 'error')
    except subprocess.TimeoutExpired:
        flash('Recompute timed out.', 'error')
    except Exception as e:
        current_app.logger.exception('Failed to run recompute script')
        flash('Failed to run recompute script.', 'error')

    return render_template('recipe.html')