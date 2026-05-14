# Learnings & Implementation Notes

## Item 1.2: Recipe Data Validation

### Validation Requirements (Updated)

**Macro Calorie Consistency** (NEW):
- Macros must add up to approximately the stated calories within ±5% tolerance
- Calculation: expected_calories = (protein × 4) + (carbs × 4) + (fat × 9)
- Example: A recipe claiming 100 calories but only having 1g each of protein/carbs/fat (17 calories) is invalid
- This prevents data entry errors where users incorrectly estimate calorie counts

**Why ±5%?**: Allows for natural variation in actual ingredient density and preparation, but catches gross errors (e.g., stating 100 cal when macros total 17 cal)

---

### Issue 1: Supabase Row-Level Security (RLS) and Anon Role

**Problem**: When submitting recipes using the anon key, we got error:
```
Error adding user recipe: {'message': 'new row violates row-level security policy for table "Recipes"', 'code': '42501'}
```

**Root Cause**: Supabase anon role didn't have INSERT permissions on the `Recipes` table due to RLS policies.

**Solution**: Created an explicit RLS policy allowing inserts:
```sql
ALTER TABLE "Recipes" ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow inserts for recipe submissions" ON "Recipes"
FOR INSERT
WITH CHECK (true);
CREATE POLICY "Allow reads for all users" ON "Recipes"
FOR SELECT
USING (true);
```

**Key Learning**: When using anon keys with RLS-enabled tables, explicit policies are needed. The anon role is useful for protecting against unauthorized access, but you must explicitly allow the operations you want to permit.

---

### Issue 2: Form Auto-Submitting on Page Refresh

**Problem**: After successful form submission, refreshing the page would create a duplicate recipe. The browser was re-posting the same form data.

**Root Cause**: HTML forms default to re-submitting on refresh after a POST request. Without proper handling, users could accidentally create duplicate rows by hitting refresh.

**Solution**: Implemented **Post-Redirect-Get (PRG) pattern**:
1. Form submits via POST
2. Server processes and validates
3. Server responds with HTTP 303 redirect to GET
4. Browser clears POST data from history
5. User sees clean form on GET request
6. Refresh now just re-fetches the empty form (no duplicate insert)

**Additional Safeguards**:
- Form inputs cleared via JavaScript after submission
- Submit button disabled during submission (shows "Submitting...")
- `autocomplete="off"` on form to prevent browser auto-fill
- Combined server-side and client-side protection (defense in depth)

**Key Learning**: PRG pattern is essential for any form that modifies data. Without it, refresh = duplicate row. This is a standard HTTP best practice for POST endpoints.

---

### Issue 3: Table Schema Discrepancy

**Problem**: Initial code tried to insert non-existent columns:
- `nutrition` (JSON field that doesn't exist)
- `rating` and `review_count` (fields with different names or missing from schema)

**Root Cause**: Made assumptions about schema instead of checking actual Supabase table structure.

**Solution**: Inspected actual Supabase schema and adjusted insertion to only include existing columns:
- `calories`, `carbs`, `category`, `fat`, `protein`, `source`, `title`, `url`, `is_submitted_recipe`

**Key Learning**: Always validate against the actual database schema. Supabase error messages (`PGRST204`) are helpful for debugging - they clearly show which column is missing. Use the SQL query mentioned in the error to inspect column names.

---

## Implementation Summary

**Files Created**:
- `app/utils/validation.py` - Centralized macro validation logic
- `tests/test_recipe_validation.py` - 33 unit tests for validation
- `tests/test_recipe_submission_validation.py` - 12 integration tests for form submission

**Files Modified**:
- `app/recipe/routes.py` - Integrated validation, added PRG pattern
- `app/utils/recipes.py` - Direct Supabase insertion with proper field mapping
- `app/templates/recipe.html` - Form safeguards (disabled button, autocomplete off, form reset)
- `app/database.py` - Fixed table name from `user_recipes` to `Recipes`

**Test Coverage**: 45 tests, all passing
- Validation ranges (boundary testing)
- Type conversion (strings to numbers)
- Error message formatting
- Form submission workflows
- Edge cases for all macro fields

---

## Notes for Future Work

1. **User Authentication (Epic 3)**: Once auth is added, associate recipes with user_id
2. **Personal Recipe Library**: Can use `is_submitted_recipe` flag to distinguish user submissions
3. **Bulk Imports**: Reuse `MacroValidator` for CSV imports to maintain data quality
4. **Form Complexity**: If adding more fields, consider moving validation logic to backend-only (current approach has both client and server validation for UX + security)

---

## Project Organization

### Issue 4: SQL Files and Planning Docs Belong in Dedicated Folders

**Problem**: SQL schema files and epic planning markdowns were scattered at the project root, cluttering the directory and making it harder to distinguish source code from documentation.

**Solution**: Organized into dedicated folders:
- `.planning/` — Epic planning documents (EPIC5, EPIC6, etc.) — gitignored
- `supabase/` — SQL schema migration files (supabase_aisle_schema.sql, supabase_recipe_ingredient_schema.sql) — gitignored

**.gitignore entries added**:
```
.planning/
supabase/
```

**Key Learning**: Plan documents are ephemeral artifacts that describe the development process, not the final product. SQL migration files are executed directly in Supabase, not by the app at runtime. Neither should be tracked in the repo. Keeps the root clean and focused on actual production code.