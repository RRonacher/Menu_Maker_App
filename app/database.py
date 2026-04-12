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

    def add_user_recipe(self, recipe_data: Dict[str, Any]) -> bool:
        """Add a user-submitted recipe."""
        try:
            self.client.table('user_recipes').insert(recipe_data).execute()
            return True
        except Exception as e:
            print(f"Error adding user recipe: {e}")
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