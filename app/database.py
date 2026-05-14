from supabase import create_client, Client
from typing import List, Dict, Any, Optional
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()

class SupabaseDatabase:
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_ANON_KEY')

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables must be set")

        self.client: Client = create_client(url, key)

    def get_recipes_df(self, category_filter: Optional[str] = 'Dinner') -> pd.DataFrame:
        """Get recipes as DataFrame, replacing get_all_recipes logic."""
        print("Fetching recipes from Supabase...")
        print('client', self.client)

        try:
            print("Setting Client")
            query = self.client.table('Recipes').select('*')

            
            print("Adding Filter")
            if category_filter:
                query = query.ilike('category', f'%{category_filter}%')

            print("Category filter:", category_filter)
            print("executing query")
            response = query.range(0, 4999).execute()

        except Exception as e:
            print("Error initializing Supabase client. Check environment variables and network connection.")
            print(f"Error initializing Supabase client: {e}")            
            return pd.DataFrame()
        
        try:
            df = pd.DataFrame(response.data)
            print("Fetched num rows: ", len(df))
            print("Converting numeric columns")
            # Convert numeric columns
            numeric_cols = ['calories', 'carbs', 'protein', 'fat', 'rating', 'review_count']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df
        except Exception as e:
            print(f"Error fetching recipes: {e}")
            return pd.DataFrame()

    def get_blocked_recipes_df(self) -> pd.DataFrame:
        """Get blocked recipes as DataFrame."""
        try:
            response = self.client.table('blocked_recipes').select('*').execute()
            return pd.DataFrame(response.data)
        except Exception as e:
            print(f"Error fetching blocked recipes: {e}")
            return pd.DataFrame()

    def get_user_recipes_df(self) -> pd.DataFrame:
        """Get user recipes as DataFrame."""
        try:
            response = self.client.table('user_recipes').select('*').execute()
            return pd.DataFrame(response.data)
        except Exception as e:
            print(f"Error fetching user recipes: {e}")
            return pd.DataFrame()

    def add_blocked_recipe(self, recipe_data: Dict[str, Any]) -> bool:
        """Add a recipe to blocked list."""
        try:
            self.client.table('blocked_recipes').insert(recipe_data).execute()
            return True
        except Exception as e:
            print(f"Error adding blocked recipe: {e}")
            return False

    def add_user_recipe(self, recipe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a user-submitted recipe to the Recipes table.

        Returns the inserted row dict if successful, otherwise None.
        """
        try:
            response = self.client.table('Recipes').insert(recipe_data).execute()
            if hasattr(response, 'data') and isinstance(response.data, list) and response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"Error adding user recipe: {e}")
            return None

    def add_recipe_ingredients(self, recipe_id: Any, ingredient_rows: List[Dict[str, Any]]) -> bool:
        """Insert parsed ingredient rows for a recipe.

        ingredient_rows should be a list of dicts with raw_text, canonical_text, and optional quantity/unit fields.
        """
        if not recipe_id or not ingredient_rows:
            return False

        rows = []
        for row in ingredient_rows:
            row_data = {'recipe_id': recipe_id}
            row_data.update(row)
            rows.append(row_data)

        try:
            self.client.table('Recipe_Ingredients').insert(rows).execute()
            return True
        except Exception as e:
            print(f"Error adding recipe ingredients: {e}")
            return False

    def get_ingredients_for_recipes(self, recipe_ids: List[Any]) -> List[Dict[str, Any]]:
        """Get all ingredient rows for a list of recipe IDs.
        
        Returns all ingredients ordered by recipe_id.
        """
        if not recipe_ids:
            return []
            
        try:
            response = self.client.table('Recipe_Ingredients').select('*').in_('recipe_id', recipe_ids).execute()
            return response.data
        except Exception as e:
            print(f"Error fetching ingredients for recipes: {e}")
            return []
            
    def get_all_ingredient_corrections(self) -> Dict[str, str]:
        """Get all manual ingredient corrections as a lookup dict {raw_text: canonical_text}."""
        try:
            response = self.client.table('ingredient_corrections').select('raw_text, canonical_text').execute()
            return {row['raw_text']: row['canonical_text'] for row in response.data}
        except Exception as e:
            print(f"Error fetching ingredient corrections: {e}")
            return {}
            
    def add_ingredient_correction(self, raw_text: str, canonical_text: str) -> bool:
        """Add or update a manual ingredient correction.
        
        Upserts on raw_text unique constraint.
        """
        if not raw_text or not canonical_text:
            return False
            
        try:
            self.client.table('ingredient_corrections').upsert({
                'raw_text': raw_text.strip(),
                'canonical_text': canonical_text.strip()
            }, on_conflict='raw_text').execute()
            return True
        except Exception as e:
            print(f"Error adding ingredient correction: {e}")
            return False

    def get_all_aisle_assignments(self) -> Dict[str, str]:
        """Get all ingredient-to-aisle mappings as a lookup dict {canonical_name: aisle}."""
        try:
            response = self.client.table('ingredient_aisles').select('canonical_name, aisle').execute()
            return {row['canonical_name']: row['aisle'] for row in response.data}
        except Exception as e:
            print(f"Error fetching aisle assignments: {e}")
            return {}

    def upsert_aisle_assignment(self, canonical_name: str, aisle: str) -> bool:
        """Set or update the aisle for an ingredient."""
        if not canonical_name or not aisle:
            return False
        try:
            self.client.table('ingredient_aisles').upsert({
                'canonical_name': canonical_name.strip(),
                'aisle': aisle.strip()
            }, on_conflict='canonical_name').execute()
            return True
        except Exception as e:
            print(f"Error upserting aisle assignment: {e}")
            return False

    def bulk_insert_aisle_assignments(self, assignments: Dict[str, str]) -> int:
        """Bulk insert default aisle assignments into the ingredient_aisles table.
        
        Returns the number of rows inserted.
        """
        if not assignments:
            return 0
        rows = [{'canonical_name': k.strip(), 'aisle': v.strip()} for k, v in assignments.items()]
        try:
            self.client.table('ingredient_aisles').upsert(
                rows,
                on_conflict='canonical_name',
                ignore_duplicates=False
            ).execute()
            return len(rows)
        except Exception as e:
            print(f"Error bulk inserting aisle assignments: {e}")
            return 0

    def mark_recipe_ingredients_parsed(self, recipe_id: Any, parsed: bool = True) -> bool:
        """Mark a recipe as having successful ingredient parsing."""
        if not recipe_id:
            return False
        try:
            self.client.table('Recipes').update({'ingredients_parsed': parsed}).eq('PK', recipe_id).execute()
            return True
        except Exception as e:
            print(f"Error updating recipe parse status: {e}")
            return False

    def bulk_insert_recipes(self, recipes_df: pd.DataFrame) -> bool:
        """Bulk insert recipes (for scraper/admin use)."""
        try:
            # Convert DataFrame to list of dicts
            recipes_data = recipes_df.to_dict('records')
            self.client.table('Recipes').insert(recipes_data).execute()
            return True
        except Exception as e:
            print(f"Error bulk inserting recipes: {e}")
            return False

# Global instance - initialize only when needed
_db_instance = None

def get_database() -> SupabaseDatabase:
    """Get database instance, creating it if necessary."""
    global _db_instance
    if _db_instance is None:
        _db_instance = SupabaseDatabase()
    return _db_instance