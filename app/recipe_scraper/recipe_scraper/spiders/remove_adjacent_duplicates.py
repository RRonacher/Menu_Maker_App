#!/usr/bin/env python3
"""Remove adjacent duplicate words/phrases in `recipes.csv`.

This script scans string-like cells in the CSV and removes immediate repeated
words or repeated phrases (up to 5 words) that occur back-to-back, e.g.
"tomato tomato" -> "tomato", "olive oil olive oil" -> "olive oil".

By default it reads `recipes.csv` from the current folder and writes
`recipes_deduped.csv`. Use `--inplace` to overwrite the input file (a
timestamped backup will be created).
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime


def is_json_like(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s2 = s.strip()
    return s2.startswith('[') or s2.startswith('{')


def clean_token(tok: str) -> str:
    return tok.strip().strip('.,;:\"\'()[]{}')


def dedupe_adjacent_phrases(text: str, max_phrase=5) -> str:
    """Remove adjacent repeated phrases up to `max_phrase` words.

    The algorithm works on whitespace-split tokens and compares lowercased,
    punctuation-stripped tokens for equality. When an immediate repetition is
    found (seq followed by same seq), the second occurrence is removed. The
    pass continues until no more adjacent duplicates are present.
    """
    if not isinstance(text, str):
        return text
    tokens = text.split()
    if len(tokens) < 2:
        return text

    # Work in-place on the token list
    i = 0
    changed = False
    while i < len(tokens):
        # maximum phrase length cannot exceed half the remaining tokens
        max_n = min(max_phrase, (len(tokens) - i) // 2)
        found = False
        for n in range(max_n, 0, -1):
            seq = tokens[i:i+n]
            next_seq = tokens[i+n:i+2*n]
            # compare normalized tokens (lowercase, punctuation stripped)
            seq_norm = [clean_token(t).lower() for t in seq]
            next_norm = [clean_token(t).lower() for t in next_seq]
            if seq_norm and seq_norm == next_norm:
                # remove the repeated next_seq
                del tokens[i+n:i+2*n]
                changed = True
                found = True
                # after removal, re-check at same index (to collapse triples)
                break
        if not found:
            i += 1

    if not changed:
        return text

    # Reconstruct a cleaned string (preserve original spacing minimally)
    return ' '.join(tokens)


def process_row(row: dict, string_cols: list) -> (dict, int):
    """Process a CSV row dict, dedupe in-place for columns in string_cols.

    Returns the modified row and number of cells changed.
    """
    changes = 0
    for col in string_cols:
        val = row.get(col)
        if val is None:
            continue
        # Skip JSON-like content or URLs to avoid corrupting structured fields
        if is_json_like(val) or ('http' in str(val).lower()):
            continue
        cleaned = dedupe_adjacent_phrases(str(val))
        if cleaned != val:
            row[col] = cleaned
            changes += 1
    return row, changes


def main(input_path: str, output_path: str = None, inplace: bool = False):
    in_path = input_path
    if not os.path.exists(in_path):
        print(f"Input file not found: {in_path}")
        return 2

    out_path = output_path or (in_path.rstrip('.csv') + '_deduped.csv')

    with open(in_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    # Determine which columns look like plain text (object-like); be conservative
    string_cols = []
    sample_count = min(50, len(rows))
    for col in fieldnames:
        # If any sample cell looks structured JSON, treat as non-text
        looks_text = True
        for r in rows[:sample_count]:
            v = r.get(col)
            if v is None:
                continue
            if is_json_like(v) or ('http' in str(v).lower()):
                looks_text = False
                break
        if looks_text:
            string_cols.append(col)

    total_changes = 0
    rows_changed = 0
    for i, row in enumerate(rows):
        new_row, changes = process_row(row, string_cols)
        if changes:
            rows[i] = new_row
            rows_changed += 1
            total_changes += changes

    # Write output
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Wrote deduped CSV: {out_path}")
    print(f"Rows changed: {rows_changed}, cells changed: {total_changes}")

    if inplace:
        # create backup and replace file
        bak = in_path + '.bak.' + datetime.utcnow().strftime('%Y%m%d%H%M%S')
        os.rename(in_path, bak)
        os.rename(out_path, in_path)
        print(f"Replaced original. Backup at: {bak}")

    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Remove adjacent duplicated words/phrases from recipes CSV')
    ap.add_argument('--input', '-i', default='recipes.csv', help='Input CSV path')
    ap.add_argument('--output', '-o', help='Output CSV path (default: input_deduped.csv)')
    ap.add_argument('--inplace', action='store_true', help='Overwrite input with backup')
    args = ap.parse_args()
    rc = main(args.input, args.output, args.inplace)
    sys.exit(rc)
