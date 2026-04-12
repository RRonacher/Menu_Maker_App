from flask import Blueprint, render_template, request, flash, redirect, url_for, session
import json
from app.utils.helpers import select_recipes
from app.menu_calculator.menu_maker import get_all_recipes, make_menu, get_menu_with_recipes, recipes_needed
from app.menu_calculator import nutrition as menu_nutrition
from app.utils import shopping

menu_bp = Blueprint('menu', __name__, url_prefix='/menu')

def get_keep_status():
    return session.get('keep_status', {})

def set_keep_status(keep_status):
    session['keep_status'] = keep_status


@menu_bp.route('/', methods=['GET', 'POST'])
def menu():
    menu_recipes = None
    keep_status = get_keep_status()
    # Provide list of all available titles for client-side replacement UI
    all_titles = []
    if request.method == 'POST':
        # Toggle keep status if requested
        if 'toggle_keep' in request.form:
            title = request.form.get('toggle_keep')
            keep_status[title] = not keep_status.get(title, False)
            set_keep_status(keep_status)
            # Do not regenerate the recipes dataframe when toggling keep.
            # Instead, update the last generated menu stored in session so the UI
            # reflects the toggled value immediately.
            last_menu = session.get('last_menu')
            if last_menu:
                # Update the keep flag for the matching recipe(s)
                for r in last_menu:
                    if r.get('title') == title:
                        r['keep'] = keep_status.get(title, False)
                # Save updated menu back to session and render it
                session['last_menu'] = last_menu
                menu_recipes = last_menu
                # Do not flash or regenerate data
                return render_template('menu.html', menu_recipes=menu_recipes)
            # If no last_menu available, fall through to generate a new menu as fallback
        # Generate new menu, keeping recipes marked as keep
        df = get_all_recipes()
        # Create an empty menu and seed it with any recipes the user has marked keep
        menu_obj = menu_nutrition.Menu()
        try:
            kept_titles = [t for t, v in keep_status.items() if v]
        except Exception:
            kept_titles = []
        if kept_titles:
            try:
                keep_df = df[df['title'].isin(kept_titles)].copy()
                # Cap kept recipes to the menu size to avoid selection logic issues
                keep_df = keep_df.head(recipes_needed)
                keep_df.loc[:, 'keep'] = True
                menu_obj.recipes_df = keep_df
            except Exception:
                # if something goes wrong seeding keep, fallback to empty menu
                menu_obj.recipes_df = menu_obj.recipes_df if hasattr(menu_obj, 'recipes_df') else []

        # Populate the rest of the menu while preserving kept recipes
        menu_obj = get_menu_with_recipes(menu_obj, df)
        if hasattr(menu_obj, 'recipes_df'):
            recipes_df = menu_obj.recipes_df.copy()
            # Ensure 'keep' column exists
            recipes_df['keep'] = recipes_df['title'].map(lambda t: keep_status.get(t, False))
            # Limit to max 4 recipes
            recipes_df = recipes_df.head(4)
            menu_recipes = []
            for _, row in recipes_df.iterrows():
                nutrition_info = {
                    'Calories': int(row.get('calories', 0)) if row.get('calories', '') != '' else 0,
                    'Carbs': float(row.get('carbs', 0.0)) if row.get('carbs', '') != '' else 0.0,
                    'Fat': float(row.get('fat', 0.0)) if row.get('fat', '') != '' else 0.0,
                    'Protein': float(row.get('protein', 0.0)) if row.get('protein', '') != '' else 0.0
                }
                # parse canonical ingredients if present (stored as JSON string), fall back to ingredients
                ingredients = []
                try:
                    raw_ing = row.get('ingredients_canonical') if 'ingredients_canonical' in row.index else row.get('ingredients', '')
                    if isinstance(raw_ing, str) and raw_ing.strip():
                        try:
                            ingredients = json.loads(raw_ing)
                        except Exception:
                            # maybe it's a single-line ingredient
                            ingredients = [raw_ing]
                except Exception:
                    ingredients = []

                menu_recipes.append({
                    'title': str(row.get('title', '')),
                    'keep': bool(row.get('keep', False)),
                    'url': str(row.get('url', '')),
                    'nutrition': nutrition_info,
                    'ingredients': ingredients
                })
        # Save the generated menu to session so future toggles won't require regenerating
        # Ensure we never store None in the session; store empty list instead.
        session['last_menu'] = menu_recipes if menu_recipes is not None else []

        # Compute nutrition totals for the rendered menu
        def _safe_num(val):
            try:
                return float(val)
            except Exception:
                return 0.0

        nutrition_totals = {
            'Calories': 0.0,
            'Carbs': 0.0,
            'Fat': 0.0,
            'Protein': 0.0
        }
        if menu_recipes:
            print("[DEBUG] Menu items used for nutrition calculation during menu creation:")
            for idx, r in enumerate(menu_recipes):
                print(f"  {idx+1}: {r.get('title', '')} | Nutrition: {r.get('nutrition', {})}")
                nut = r.get('nutrition', {})
                nutrition_totals['Calories'] += _safe_num(nut.get('Calories', 0))
                nutrition_totals['Carbs'] += _safe_num(nut.get('Carbs', 0))
                nutrition_totals['Fat'] += _safe_num(nut.get('Fat', 0))
                nutrition_totals['Protein'] += _safe_num(nut.get('Protein', 0))
            print(f"[DEBUG] Nutrition totals: {nutrition_totals}")

        # Attach totals to session for potential later use and pass to template
        session['last_menu_totals'] = nutrition_totals if menu_recipes else None
        flash('Menu created successfully.')
    # get full list of titles to let the user choose replacements
    try:
        df_all = get_all_recipes()
        all_titles = df_all['title'].tolist()
    except Exception:
        all_titles = []

    # If the user explicitly requested a fresh menu (from home: ?fresh=1), show an empty menu
    fresh = request.args.get('fresh')
    # Only honor the fresh flag on GET requests. If the page is POSTed (Create Menu)
    # with fresh=1 in the URL, we must allow the POST handling to generate and
    # render the real menu instead of returning an empty menu.
    if request.method == 'GET' and fresh == '1':
        return render_template('menu.html', menu_recipes=[], nutrition_totals=None, all_titles=all_titles)

    # Prefer session-stored menu for rendering so replacements/toggles show immediately
    if session.get('last_menu'):
        menu_recipes = session.get('last_menu')

    return render_template('menu.html', menu_recipes=menu_recipes, nutrition_totals=session.get('last_menu_totals'), all_titles=all_titles)


@menu_bp.route('/calc', methods=['POST'])
def calc_menu():
    # Alias to POST /menu to support standardized endpoint `/menu/calc`
    return menu()


@menu_bp.route('/replace', methods=['POST'])
def replace():
    # Expect form: original_title, new_title
    orig = request.form.get('original_title')
    new = request.form.get('new_title')
    last_menu = session.get('last_menu', []) or []
    if not orig or not new:
        flash('Invalid replacement request.')
        return redirect(url_for('menu.menu'))

    # find new recipe details from full dataset
    df_all = get_all_recipes()
    new_row = df_all[df_all['title'] == new]
    if new_row.empty:
        flash('Replacement recipe not found.')
        return redirect(url_for('menu.menu'))

    new_row = new_row.iloc[0]
    new_item = {
        'title': str(new_row.get('title', '')),
        'keep': False,
        'url': str(new_row.get('url', '')),
        'ingredients': [],
        'nutrition': {
            'Calories': int(new_row.get('calories', 0)) if new_row.get('calories', '') != '' else 0,
            'Carbs': float(new_row.get('carbs', 0.0)) if new_row.get('carbs', '') != '' else 0.0,
            'Fat': float(new_row.get('fat', 0.0)) if new_row.get('fat', '') != '' else 0.0,
            'Protein': float(new_row.get('protein', 0.0)) if new_row.get('protein', '') != '' else 0.0
        }
    }
    # populate ingredients from df row if available
    try:
        raw_ing = new_row.get('ingredients_canonical') if 'ingredients_canonical' in new_row.index else new_row.get('ingredients', '')
        if isinstance(raw_ing, str) and raw_ing.strip():
            try:
                new_item['ingredients'] = json.loads(raw_ing)
            except Exception:
                new_item['ingredients'] = [raw_ing]
    except Exception:
        new_item['ingredients'] = []

    replaced = False
    for i, r in enumerate(last_menu):
        if r.get('title') == orig:
            last_menu[i] = new_item
            replaced = True
            break

    if replaced:
        session['last_menu'] = last_menu
        # Logging: print menu items being used for nutrition calculation
        print("[DEBUG] Menu items used for nutrition calculation after replacement:")
        for idx, item in enumerate(last_menu):
            print(f"  {idx+1}: {item.get('title', '')} | Nutrition: {item.get('nutrition', {})}")
        # Recompute totals and update session
        session['last_menu_totals'] = {
            'Calories': sum(float(r.get('nutrition', {}).get('Calories', 0)) for r in last_menu),
            'Carbs': sum(float(r.get('nutrition', {}).get('Carbs', 0)) for r in last_menu),
            'Fat': sum(float(r.get('nutrition', {}).get('Fat', 0)) for r in last_menu),
            'Protein': sum(float(r.get('nutrition', {}).get('Protein', 0)) for r in last_menu)
        }
        print(f"[DEBUG] Nutrition totals: {session['last_menu_totals']}")
        flash(f'Replaced "{orig}" with "{new}"')
    else:
        flash('Original recipe not found in current menu.')

    return redirect(url_for('menu.menu'))


@menu_bp.route('/shopping_list', methods=['GET'])
def shopping_list():
    # Build shopping list from recipes marked as keep in session
    last_menu = session.get('last_menu', []) or []
    kept = [r for r in last_menu if r.get('keep')]
    if not kept:
        flash('No recipes marked as Kept. Please mark recipes to keep before generating a shopping list.')
        return redirect(url_for('menu.menu'))

    # Ensure each kept item has title/url; try to use existing ingredients if present
    recipe_inputs = []
    for r in kept:
        recipe_inputs.append({
            'title': r.get('title'),
            'url': r.get('url'),
            'ingredients': r.get('ingredients')  # optional pre-populated list
        })

    result = shopping.aggregate_shopping_list(recipe_inputs)

    # Pass aggregated list and per-recipe breakdown to template
    aggregated = result.get('aggregated', {})
    per_recipe = result.get('per_recipe', [])
    return render_template('shopping_list.html', aggregated=aggregated, per_recipe=per_recipe)


@menu_bp.route('/shopping', methods=['GET'])
def shopping_alias():
    # Alias for standardized `/shopping` endpoint
    return shopping_list()
