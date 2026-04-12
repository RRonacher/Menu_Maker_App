import pandas as pd

# Paths to your files
main_csv = "app/recipe_scraper/recipe_scraper/spiders/recipes.csv"
backup_csv = "app/recipe_scraper/recipe_scraper/spiders/recipes.csv.bak.20251106192629"
output_csv = "app/recipe_scraper/recipe_scraper/spiders/recipes_merged.csv"

# Read both CSVs
main_df = pd.read_csv(main_csv)
backup_df = pd.read_csv(backup_csv)


# Nutrition columns to check/fill
nutr_cols = ['calories', 'carbs', 'fat', 'protein', 'nutrition']

def is_missing(row):
    return any(pd.isna(row[col]) or row[col] in [0, '', '0', '0.0'] for col in nutr_cols)

# Fill missing nutrition from backup
for idx, row in main_df.iterrows():
    # if is_missing(row):
    title = row['title']
    match = backup_df[backup_df['title'] == title]
    if not match.empty:
        for col in nutr_cols:
            main_df.at[idx, col] = match.iloc[0][col]

# Save to new CSV
main_df.to_csv(output_csv, index=False)
print(f"Merged CSV written to {output_csv}")
