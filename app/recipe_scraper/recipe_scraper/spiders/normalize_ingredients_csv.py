import pandas as pd
import json
import os
import sys

# ensure project root is on path when run standalone
try:
    from app.utils.shopping import normalize_ingredient, canonicalize_ingredient, normalize_ingredient_structured
except Exception:
    # try relative import fallback
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
    from app.utils.shopping import normalize_ingredient, canonicalize_ingredient, normalize_ingredient_structured

INPUT = 'recipes_with_ingredients.csv'
OUTPUT = 'recipes_with_ingredients_normalized.csv'


def main(input_path=None, output_path=None, inplace=False):
    """Recompute normalized and canonical ingredient columns.

    If `inplace` is True the input CSV will be backed up and overwritten.
    Otherwise a new output CSV is written.
    """
    inp = input_path or INPUT
    outp = output_path or OUTPUT
    if not os.path.exists(inp):
        print(f"Input file not found: {inp}")
        return
    df = pd.read_csv(inp)
    if 'ingredients' not in df.columns:
        print('No ingredients column found in CSV')
        return

    def parse_ingredients_cell(cell):
        if pd.isna(cell):
            return [], [], []
        if isinstance(cell, list):
            items = cell
        else:
            try:
                items = json.loads(cell)
            except Exception:
                # fallback: split on line breaks
                items = [l.strip() for l in str(cell).splitlines() if l.strip()]
        parsed = [normalize_ingredient_structured(i) for i in items if i]
        normalized = [p['normalized'] for p in parsed if p and p.get('normalized')]
        canonical = [p['canonical'] for p in parsed if p and p.get('canonical')]
        return normalized, canonical, parsed

    new_ings = []
    new_canon = []
    new_parsed = []
    for idx, row in df.iterrows():
        cell = row.get('ingredients', '')
        normalized, canonical, parsed = parse_ingredients_cell(cell)
        new_ings.append(json.dumps(normalized, ensure_ascii=False))
        new_canon.append(json.dumps(canonical, ensure_ascii=False))
        # parsed is a list of dicts; ensure_ascii=False to preserve unicode
        new_parsed.append(json.dumps(parsed, ensure_ascii=False))

    df['ingredients_normalized'] = new_ings
    df['ingredients_canonical'] = new_canon
    # new structured parsed column: JSON list of {quantity, unit, quantity_metric, unit_metric, normalized, canonical, body}
    df['ingredients_parsed'] = new_parsed
    # write either in-place (with backup) or to an output path
    if inplace:
        bak = inp + '.recanon.bak.' + pd.Timestamp.now().strftime('%Y%m%d%H%M%S')
        try:
            os.replace(inp, bak)
            print(f'Backed up original to {bak}')
        except Exception:
            # fallback to copy
            import shutil

            shutil.copyfile(inp, bak)
            print(f'Copied backup to {bak}')
        # write new file to original path
        df.to_csv(inp, index=False)
        print(f'Wrote updated CSV in-place to {inp}')
    else:
        df.to_csv(outp, index=False)
        print(f'Wrote {outp}')


if __name__ == '__main__':
    # allow simple CLI usage: --inplace to overwrite the input CSV with a backup
    import argparse

    p = argparse.ArgumentParser(description='Normalize ingredients CSV')
    p.add_argument('--input', '-i', help='Input CSV path', default=INPUT)
    p.add_argument('--output', '-o', help='Output CSV path', default=OUTPUT)
    p.add_argument('--inplace', action='store_true', help='Overwrite input CSV (creates backup)')
    args = p.parse_args()
    main(input_path=args.input, output_path=args.output, inplace=args.inplace)
