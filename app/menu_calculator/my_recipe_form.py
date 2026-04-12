import tkinter as tk
from tkinter import *
from app.menu_calculator import nutrition as n
import pandas as pd

def main():
    def submit():
        if entry_source.get() == '':
            entry_source.insert(0, 'myself')
        if entry_rating.get() == '':
            entry_rating.insert(0, 0)
        if entry_reviewCount.get() == '':
            entry_reviewCount.insert(0, 0)
        nutrition = {'calories': entry_calories.get(), 'carbs': entry_carbs.get(),
                     'protein': entry_protein.get(), 'fat': entry_fat.get()}
        d = {'calories': entry_calories.get(), 'carbs': entry_carbs.get(), 'category': entry_category.get(), 'fat': entry_fat.get(),
              'nutrition': str(nutrition), 'protein': entry_protein.get(), 'rating': entry_rating.get(),
              'reviewCount': entry_reviewCount.get(), 'source': entry_source.get(), 'title': entry_title.get(),
              'url': entry_url.get()}
        df = pd.DataFrame(data=d, index=[0])
        recipe = n.Recipe(recipe_df=df, calories=nutrition['calories'], carbs=nutrition['carbs'], protein=nutrition['protein'], fat=nutrition['fat'])
        submitted = recipe.add_to_my_recipes(df)
        if not submitted == 'missing':
            add_window.destroy()
    # ...existing code...
