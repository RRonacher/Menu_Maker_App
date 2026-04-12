#!/usr/bin/env python3
"""Deduplicate adjacent repeated words/phrases inside JSON-array columns.

This complements `remove_adjacent_duplicates.py` by specifically parsing
JSON-like list columns (e.g. `ingredients`, `ingredients_normalized`,
`ingredients_canonical`) and applying the same adjacent-phrase de-duplication
to each list item.

Usage: run from the `spiders` folder. By default it runs inplace and creates
a timestamped backup of `recipes.csv`.
"""
import os
import sys
import argparse
import json
import pandas as pd
from datetime import datetime


def clean_token(tok: str) -> str:
    return tok.strip().strip('.,;:\"\'()[]{}')


def dedupe_adjacent_phrases(text: str, max_phrase=5) -> str:
    if not isinstance(text, str):
        return text
    tokens = text.split()
    if len(tokens) < 2:
        return text
    i = 0
    changed = False
    while i < len(tokens):
        max_n = min(max_phrase, (len(tokens) - i) // 2)
        found = False
        for n in range(max_n, 0, -1):
            seq = tokens[i:i+n]
            next_seq = tokens[i+n:i+2*n]
            seq_norm = [clean_token(t).lower() for t in seq]
            next_norm = [clean_token(t).lower() for t in next_seq]
            if seq_norm and seq_norm == next_norm:
                del tokens[i+n:i+2*n]
                changed = True
                found = True
                break
        if not found:
            i += 1
    if not changed:
        return text
    return ' '.join(tokens)


def process_list_cell(cell):
    # cell may be a JSON string, a Python list, or NA
    if pd.isna(cell):
        return cell
    if isinstance(cell, list):
        arr = cell
    else:
        try:
            arr = json.loads(cell)
        except Exception:
            # fallback: treat as newline-separated
            arr = [l.strip() for l in str(cell).splitlines() if l.strip()]
    out = []
    for item in arr:
        try:
            s = str(item)
            s2 = dedupe_adjacent_phrases(s)
            out.append(s2)
        except Exception:
            out.append(item)
    return json.dumps(out, ensure_ascii=False)


def main(infile='recipes.csv', inplace=True):
    if not os.path.exists(infile):
        print(f"Input not found: {infile}")
        return 2
    df = pd.read_csv(infile, dtype=str)

    cols_to_fix = [c for c in ['ingredients', 'ingredients_normalized', 'ingredients_canonical'] if c in df.columns]
    if not cols_to_fix:
        print('No ingredient JSON columns found to process.')
        return 0

    changes = 0
    for col in cols_to_fix:
        newcol = []
        for i, cell in df[col].items():
            newcell = process_list_cell(cell)
            newcol.append(newcell)
            if newcell != cell:
                changes += 1
        df[col] = newcol

    outpath = infile.rstrip('.csv') + '_jsondeduped.csv'
    df.to_csv(outpath, index=False)
    print(f'Wrote: {outpath}  (cells changed: {changes})')

    if inplace:
        bak = infile + '.bak.' + datetime.utcnow().strftime('%Y%m%d%H%M%S')
        os.rename(infile, bak)
        os.rename(outpath, infile)
        print(f'Replaced original. Backup: {bak}')

    return 0


if __name__ == '__main__':
    rc = main()
    sys.exit(rc)
