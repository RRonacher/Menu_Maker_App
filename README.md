# Menu_Maker_App
Web app for generating a week's grocery menu and grocery list.

## Current Features

### ✅ Epic 1: Database & Data Integrity
- **1.1 - URL Health Check**: Scheduled jobs that ping recipe URLs and flag broken links
- **1.2 - Recipe Data Validation** (NEW): Server-side validation of macro fields (calories, protein, fat, carbs) with plausible ranges to prevent dirty data from skewing macro-balancing algorithm
  - Validation ranges: Calories (50–2500), Protein (0–200g), Fat (0–150g), Carbs (0–400g)
  - Applied at form submission and database insertion points
  - Clear error messages for validation failures
  - Recipes marked with `is_submitted_recipe` flag to distinguish user-submitted from database recipes
  - Full test coverage with 45 unit and integration tests

## Tech Stack
- **Backend**: Python · Flask
- **Database**: Supabase (PostgreSQL)
- **Frontend**: HTML/CSS/JavaScript
- **Testing**: pytest with pytest-flask

## Development Notes
See [Learnings.md](Learnings.md) for notes on implementation challenges and solutions.
