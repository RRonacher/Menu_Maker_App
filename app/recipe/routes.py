from flask import Blueprint, render_template, request, flash, current_app, abort
from app.utils.recipes import submit_recipe
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
            return render_template('recipe.html')
            
        try:
            # Try to convert numeric fields (calories must be integer)
            calories_val = int(request.form.get('calories', 0))
            if calories_val < 0:
                flash('Calories cannot be negative.', 'error')
                return render_template('recipe.html')

            for field in ['carbs', 'protein', 'fat']:
                value = float(request.form.get(field, 0))
                if value < 0:
                    flash(f'{field.title()} cannot be negative.', 'error')
                    return render_template('recipe.html')

            success = submit_recipe()
            if success:
                flash('Recipe successfully added to the database!', 'success')
                return render_template('recipe.html')
            else:
                flash('Failed to save recipe. Please try again.', 'error')
        except ValueError:
            flash('Please enter valid numbers for nutritional values.', 'error')
            
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
