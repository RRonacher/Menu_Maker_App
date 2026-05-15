"""
Epic 7 — Custom Recipe Integration Test

Tests the full lifecycle of a custom recipe:
  1. Insert a custom recipe with raw ingredients + instructions
  2. Parse ingredients via parse_raw_ingredients()
  3. Store parsed ingredients in Recipe_Ingredients
  4. Fetch and verify the stored recipe and ingredients
  5. Clean up: delete the test recipe and its ingredients

Run with:  python tools/test_custom_recipe.py

Requires:
  - SUPABASE_URL and SUPABASE_ANON_KEY environment variables set
  - The Recipes table has recipe_type and instructions columns
    (run the migration SQL first)
"""

import sys
import os
import traceback

# Ensure the app module is importable from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import get_database
from app.utils.shopping import parse_raw_ingredients

# ── Test Data ──────────────────────────────────────────────────────────────
TEST_RECIPE = {
    'title': 'Epic7 Test Recipe — DELETE AFTER TESTING',
    'calories': 350,
    'carbs': 30.0,
    'protein': 25.0,
    'fat': 12.0,
    'category': 'Dinner',
    'source': 'Custom Recipe',
    'url': '',
    'recipe_type': 'custom',
    'is_submitted_recipe': 1,  # backward-compat column — custom recipes ARE user-submitted
    'ingredients_raw_text': (
        '1 tbsp olive oil\n'
        '1 onion, diced\n'
        '2 cloves garlic, minced\n'
        '400 g ground beef\n'
        '1 can diced tomatoes\n'
        '2 tbsp chili powder\n'
        '1 can kidney beans, drained\n'
        'Salt to taste'
    ),
    'instructions': (
        '1. Heat olive oil in a large pot over medium heat. '
        'Add diced onion and cook until softened, about 5 minutes. '
        'Add minced garlic and cook 1 minute more.\n'
        '2. Add ground beef and cook until browned, breaking it apart. '
        'Drain excess fat.\n'
        '3. Stir in diced tomatoes, chili powder, and kidney beans. '
        'Bring to a simmer.\n'
        '4. Reduce heat and simmer for 20 minutes, stirring occasionally. '
        'Season with salt to taste.\n'
        '5. Serve hot.'
    ),
}


def report(step: str, passed: bool, detail: str = ''):
    """Print a pass/fail line for a test step."""
    status = 'PASS' if passed else 'FAIL'
    icon = '✓' if passed else '✗'
    print(f'  {icon} [{status}] {step}')
    if detail and not passed:
        print(f'       {detail}')


def run_test() -> bool:
    """Run the custom recipe lifecycle test. Returns True if all steps pass."""
    all_passed = True

    print('\n=== Epic 7 Custom Recipe Integration Test ===\n')

    # ── Step 1: Insert the test recipe ──────────────────────────────────────
    print('Step 1: Insert test custom recipe into Supabase...')
    try:
        db = get_database()
        result = db.add_user_recipe(TEST_RECIPE)
    except Exception as e:
        report('Insert recipe', False, f'Exception: {e}')
        return False

    if not result:
        report('Insert recipe', False, 'add_user_recipe returned None')
        return False

    # Get the primary key of the inserted recipe (field name varies)
    recipe_id = (result.get('PK') or result.get('id') or
                 result.get('ID') or result.get('Id'))
    if not recipe_id:
        report('Insert recipe', False,
               f'No PK in returned record: {result}')
        return False

    report('Insert recipe', True, f'PK={recipe_id}')

    # ── Step 2: Verify recipe_type and instructions ────────────────────────
    print('\nStep 2: Verify recipe_type and instructions fields...')
    try:
        fetch_result = db.client.table('Recipes') \
            .select('recipe_type, instructions, title, calories, protein, fat, carbs') \
            .eq('PK', recipe_id).execute()
        fetched = fetch_result.data[0] if fetch_result.data else None
    except Exception as e:
        report('Fetch recipe', False, f'Exception: {e}')
        # Continue to cleanup
        all_passed = False
        fetched = None

    if fetched:
        recipe_type_ok = fetched.get('recipe_type') == 'custom'
        instructions_ok = bool(fetched.get('instructions'))
        macro_fields = ['calories', 'protein', 'fat', 'carbs']
        macros_ok = all(fetched.get(f) is not None for f in macro_fields)

        report('recipe_type == "custom"', recipe_type_ok,
               f'Got: {fetched.get("recipe_type")}')
        report('instructions stored', instructions_ok)
        report('Macro fields present', macros_ok,
               f'Values: { {f: fetched.get(f) for f in macro_fields} }')

        if not all([recipe_type_ok, instructions_ok, macros_ok]):
            all_passed = False
    else:
        all_passed = False

    # ── Step 3: Parse ingredients from raw text ────────────────────────────
    print('\nStep 3: Parse ingredients from raw text...')
    raw_text = TEST_RECIPE['ingredients_raw_text']
    ingredient_rows = parse_raw_ingredients(raw_text)

    if not ingredient_rows:
        report('Parse ingredients', False, 'No rows returned')
        all_passed = False
    else:
        report('Parse ingredients', True, f'{len(ingredient_rows)} rows parsed')
        # Show a sample
        for i, row in enumerate(ingredient_rows[:3]):
            print(f'         [{i+1}] raw="{row.get("raw_text","")[:40]}..." '
                  f'canonical="{row.get("canonical_text","")}"')

    # ── Step 4: Store parsed ingredients ───────────────────────────────────
    print('\nStep 4: Store parsed ingredients in Recipe_Ingredients...')
    if ingredient_rows:
        try:
            stored = db.add_recipe_ingredients(recipe_id, ingredient_rows)
            marked = db.mark_recipe_ingredients_parsed(recipe_id, True)
            report('Store ingredients', stored)
            report('Mark ingredients_parsed', marked)
            if not stored or not marked:
                all_passed = False
        except Exception as e:
            report('Store ingredients', False, f'Exception: {e}')
            all_passed = False
    else:
        report('Store ingredients', False, 'Skipped (no rows to store)')
        all_passed = False

    # ── Step 5: Verify stored ingredients ──────────────────────────────────
    print('\nStep 5: Verify stored ingredients via get_ingredients_for_recipes...')
    try:
        stored_ingredients = db.get_ingredients_for_recipes([recipe_id])
        if stored_ingredients:
            report('Fetch ingredients', True,
                   f'{len(stored_ingredients)} rows returned')
        else:
            report('Fetch ingredients', False, 'Empty result')
            all_passed = False
    except Exception as e:
        report('Fetch ingredients', False, f'Exception: {e}')
        all_passed = False

    # ── Step 6: Cleanup — delete the test record and ingredients ───────────
    print('\nStep 6: Cleanup — delete test recipe and ingredients...')
    cleanup_db = db
    service_db = None
    if os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
        try:
            service_db = get_database(service_role=True)
            cleanup_db = service_db
        except Exception as e:
            print(f'Warning: unable to initialize service role client for cleanup: {e}')
            print('Falling back to anon client for cleanup.')

    if cleanup_db is db:
        print('Warning: SUPABASE_SERVICE_ROLE_KEY not set; cleanup may be blocked by Supabase policies.')

    try:
        # Delete ingredients first (child rows)
        cleanup_db.client.table('Recipe_Ingredients') \
            .delete().eq('recipe_id', recipe_id).execute()
        # Delete the recipe itself
        cleanup_db.client.table('Recipes') \
            .delete().eq('PK', recipe_id).execute()

        # Verify that both the recipe and ingredient rows are gone.
        verify_recipe = cleanup_db.client.table('Recipes') \
            .select('PK').eq('PK', recipe_id).execute()
        remaining_ingredients = cleanup_db.get_ingredients_for_recipes([recipe_id])
        recipe_deleted = not verify_recipe.data
        ingredients_deleted = not remaining_ingredients

        if recipe_deleted and ingredients_deleted:
            report('Cleanup', True, f'Removed recipe PK={recipe_id} and ingredients')
        else:
            report('Cleanup', False,
                   f'Recipe present after delete={not recipe_deleted}, '
                   f'ingredients present after delete={not ingredients_deleted}')
            all_passed = False
    except Exception as e:
        report('Cleanup', False, f'Exception: {e}')
        all_passed = False

    # ── Summary ────────────────────────────────────────────────────────────
    print()
    if all_passed:
        print('✓ ALL TESTS PASSED')
    else:
        print('✗ SOME TESTS FAILED — see details above')
    print()

    return all_passed


if __name__ == '__main__':
    success = run_test()
    sys.exit(0 if success else 1)