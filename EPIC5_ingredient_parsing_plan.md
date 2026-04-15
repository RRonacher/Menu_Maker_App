# Epic 5 Ingredient Parsing Plan

## Objective
Build the ingredient database and parsing workflow before adding grocery list enhancements.

## Design Summary
- Add a new child table: `Recipe_Ingredients`
- Parse ingredient data once at recipe submission
- Persist parsed ingredient rows for use in future grocery list aggregation
- Keep recipes with failed ingredient parsing in the database, but exclude them from menu generation
- Defer pricing-dependent features until pricing data exists

## Data Model
### Recipe_Ingredients
- `id` (PK)
- `recipe_id` (FK -> Recipes.id)
- `raw_text` (text)
- `canonical_text` (text)
- `quantity` (text|null)
- `unit` (text|null)
- `quantity_metric` (text|null)
- `unit_metric` (text|null)

### Recipes table flag (optional)
- `ingredients_parsed` (boolean)

> The SQL schema for this work is captured in `supabase_recipe_ingredient_schema.sql`.

## Parsing Workflow
1. User submits a recipe URL and nutrition metadata
2. Save the recipe record in `Recipes`
3. Run a one-time ingredient parse for that recipe URL
4. Insert parsed rows into `Recipe_Ingredients`
5. Mark the recipe as eligible for menus only if parsing produces valid ingredients
6. If parsing fails, keep the recipe but do not include it in menu creation

## Extraction Strategy
1. JSON-LD extraction from the page
2. HTML selector extraction using common recipe ingredient patterns
3. Heuristic fallback for list items and measurement-based lines
4. Optional LLM/API fallback only if all other parsers fail

## Eligibility Rules
- Use recipe in menu generation only if it has one or more `Recipe_Ingredients` rows
- Hide recipes with no parsed ingredients from menu creation

## Initial Implementation Tasks
1. Add `Recipe_Ingredients` table and schema migration plan
2. Add DB methods for inserting and querying ingredient rows
3. Create parser module for ingredient extraction and normalization
4. Hook parsing into recipe submission flow
5. Add menu generation filter for parsed recipes only

## Testing Plan
- Unit test parser extraction on sample recipe pages and HTML snippets
- Test `Recipe_Ingredients` insertion and query behavior
- Test recipe submission flow with both successful and failed parsing
- Test menu generation excludes failed-parse recipes
- Validate that recipes still save when ingredient parsing fails

## Notes
- No order field is required in `Recipe_Ingredients`
- `Recipe_Ingredients` stores only raw and canonical text plus optional parsed metadata
- Parsing is one-time, not repeated during shopping list generation
- Pricing-related grocery list work is deferred until later
