import pandas as pd
import os
from datetime import date, timedelta

class Recipe:
    def __init__(self, recipe_df, calories=0, carbs=0, protein=0, fat=0):
        self.calories = calories
        self.carbs = carbs
        self.protein = protein
        self.fat = fat
        self.recipe_df = recipe_df
        pass

    def add_to_my_recipes(self, df, user_name='master'):
        for column in ['title', 'url', 'category', 'source',
                       'calories', 'carbs', 'fat', 'protein',
                       'rating', 'reviewCount']:
            if (df[column] == '')[0]:
                print('missing ' + column)
                return 'missing'
        else:
            script_dir = os.path.dirname(__file__)
            csv = os.path.join(script_dir, 'my_recipes.csv')
            try:
                tmp_df = pd.read_csv(csv)
                tmp_df = pd.concat(objs=(tmp_df, df))
                tmp_df = tmp_df.drop_duplicates()
                tmp_df.to_csv(csv, index=False)
            except:
                df.to_csv(csv, index=False)

class Menu(Recipe):
    def __init__(self, balanced=False):
        super().__init__(recipe_df=pd.DataFrame())
        self.balanced = balanced
        self.carb_pct = 100
        self.protein_pct = 100
        self.fat_pct = 100
        self.recipes_df = []
        self.empty = False
        self.is_vegetarian = False
        self.is_vegan = False
        self.calories_high = 3000
        self.calories_low = 1000
        self.carb_pct_high = .65
        self.carb_pct_low = .45
        self.fat_pct_high = .35
        self.fat_pct_low = .25
        self.protein_pct_high = .3
        self.protein_pct_low = .1
        # self.recipes = self.recipes_df[self.recipes_df['title']]
        pass

    def reset_nutrition(self):
        """
        Reset nutrition-related attributes for the menu.
        """
        self.calories = 0
        self.carbs = 0
        self.protein = 0
        self.fat = 0
        # If recipes_df is a DataFrame, clear keep column
        if isinstance(self.recipes_df, pd.DataFrame) and 'keep' in self.recipes_df.columns:
            self.recipes_df['keep'] = False

    def aggregate_nutrition(self):
        """
        Aggregate nutrition values from recipes_df and update menu attributes.
        Ensure all values are numeric.
        """
        if isinstance(self.recipes_df, pd.DataFrame):
            self.calories = float(pd.to_numeric(self.recipes_df['calories'], errors='coerce').sum())
            self.carbs = float(pd.to_numeric(self.recipes_df['carbs'], errors='coerce').sum())
            self.protein = float(pd.to_numeric(self.recipes_df['protein'], errors='coerce').sum())
            self.fat = float(pd.to_numeric(self.recipes_df['fat'], errors='coerce').sum())

    def calculate_nutrition_percentages(self):
        """
        Calculate the percentage of calories from carbs, protein, and fat.
        Ensure all values are numeric.
        """
        try:
            calories = float(self.calories)
            carbs = float(self.carbs)
            protein = float(self.protein)
            fat = float(self.fat)
        except Exception:
            self.carb_pct = 0
            self.fat_pct = 0
            self.protein_pct = 0
            return
        if calories == 0:
            self.carb_pct = 0
            self.fat_pct = 0
            self.protein_pct = 0
        else:
            self.carb_pct = round((carbs * 4) / calories, 2)
            self.protein_pct = round((protein * 4) / calories, 2)
            self.fat_pct = round((fat * 9) / calories, 2)

    def check_is_balanced_menu(self):
        """
        Check if the menu meets the balanced criteria.
        """
        self.balanced = (
            self.carb_pct_low <= self.carb_pct <= self.carb_pct_high
            and self.fat_pct_low <= self.fat_pct <= self.fat_pct_high
            and self.protein_pct_low <= self.protein_pct <= self.protein_pct_high
            and self.calories_low <= self.calories <= self.calories_high
        )

def clean_up_recipes(df):
    # blocked_words = ['dessert', 'cookie', 'muffin', 'cookie', 'pie', 'cake', 'bread', 'fish']
    approved_categories = ['dinner', 'main-dish', 'main dish', 'lunch', 'main course', 'supper', 'unknown']
    blocked_categories = ['breakfast', 'brunch', 'cocktails', 'dessert', 'desserts', 'drink',
                          'snack', 'starter', 'treat']
    blocked_df = df[df['category'].apply(lambda x: any([k in x.lower() for k in blocked_categories]))]
    blocked_df_2 = df[df['category'].apply(lambda x: any([k in x.lower() for k in approved_categories])) == False]

    block_recipe('cleaning up blocked word recipes ', blocked_df)
    block_recipe('non-dinner recipes', blocked_df_2)

def block_recipe(title, recipe: pd.DataFrame, user_name='master'):
    script_dir = os.path.dirname(__file__)
    recipe_block_path = os.path.join(script_dir,
                                     '../recipe_scraper/recipe_scraper/spiders/master_blocked_recipes.csv')
    try:
        tmp_df = pd.read_csv(recipe_block_path)
        tmp_df = pd.concat(objs=(tmp_df, recipe))
        tmp_df = tmp_df.drop_duplicates()
        tmp_df.to_csv(recipe_block_path, index=False)
    except:
        recipe.to_csv(recipe_block_path, index=False)
