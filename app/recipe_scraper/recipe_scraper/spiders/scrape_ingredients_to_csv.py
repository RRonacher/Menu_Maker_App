import pandas as pd
import json
import time
from app.utils.shopping import scrape_ingredients_from_url

MAIN_CSV = "recipes.csv"
OUT_CSV = "recipes_with_ingredients.csv"
DELAY = 1.0  # seconds between requests to be polite


def main():
    df = pd.read_csv(MAIN_CSV)
    # create ingredients column if not present
    if 'ingredients' not in df.columns:
        df['ingredients'] = ''

    for idx, row in df.iterrows():
        try:
            title = row.get('title')
            existing = row.get('ingredients')
            if isinstance(existing, str) and existing.strip():
                print(f"Skipping '{title}': already has ingredients")
                continue
            url = row.get('url')
            if not url or not isinstance(url, str) or url.strip() == '':
                print(f"Skipping '{title}': no URL")
                continue
            print(f"Scraping ingredients for '{title}' from {url}")
            ingr = scrape_ingredients_from_url(url)
            if ingr:
                df.at[idx, 'ingredients'] = json.dumps(ingr)
                print(f"  Found {len(ingr)} ingredients")
            else:
                print(f"  No ingredients found for '{title}'")
        except Exception as e:
            print(f"Error scraping {title}: {e}")
        time.sleep(DELAY)

    df.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")


if __name__ == '__main__':
    main()
