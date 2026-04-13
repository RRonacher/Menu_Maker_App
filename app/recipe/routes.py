from flask import Blueprint, render_template, request, flash, current_app, abort, redirect, url_for
from app.utils.recipes import submit_recipe
from app.utils.validation import MacroValidator
import subprocess
import sys
import os

recipe_bp = Blueprint('recipe', __name__, url_prefix='/recipe')

@recipe_bp.route('/', methods=['GET', 'POST'])
def recipe():
    if request.method == 'POST':
        # Validate form data
        required_fields = ['title', 'url', 'source', 'calories', 'carbs', 'protein', 'fat']
        if not all(field in request.form for field in required_fields):
            flash('Please fill in all required fields.', 'error')
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
            return redirect(url_for('recipe.recipe'))
            
        try:
            success = submit_recipe()
            if success:
                flash('Recipe successfully added to the database!', 'success')
            else:
                flash('Failed to save recipe. Please try again.', 'error')
        except ValueError:
            flash('Please enter valid numbers for nutritional values.', 'error')
        
        # Redirect to GET to prevent form resubmission on refresh
        return redirect(url_for('recipe.recipe'))
            
    return render_template('recipe.html')



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
