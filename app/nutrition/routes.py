from flask import Blueprint, render_template, request, flash
from app.utils.nutrition import validate_entry_ranges, submit_nutrition, reset_nutrition_targets

nutrition_bp = Blueprint('nutrition', __name__, url_prefix='/nutrition')

@nutrition_bp.route('/', methods=['GET', 'POST'])
def nutrition():
    if request.method == 'POST':
        # Example: validate and submit nutrition targets
        menu_vars = {}  # Replace with actual form data
        entries = {}    # Replace with actual form data
        if validate_entry_ranges(menu_vars):
            success = submit_nutrition(menu_vars, entries)
            if success:
                flash('Nutrition targets set.')
            else:
                flash('Failed to set nutrition targets.')
        else:
            flash('Invalid nutrition entry ranges.')
    return render_template('nutrition.html')
