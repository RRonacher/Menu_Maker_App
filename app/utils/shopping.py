import requests
from bs4 import BeautifulSoup
import json
import re
from fractions import Fraction
from typing import Dict

# map common unicode fractions to ascii forms
_FRACTION_MAP = {
    '¼': '1/4', '½': '1/2', '¾': '3/4', '⅓': '1/3', '⅔': '2/3', '⅛': '1/8', '⅜': '3/8', '⅝': '5/8', '⅞': '7/8'
}


def _normalize_fractions(s: str) -> str:
    if not s:
        return s
    # replace replacement characters and normalize unicode fractions
    s = s.replace('\ufffd', ' ')
    s = s.replace('�', ' ')
    for k, v in _FRACTION_MAP.items():
        if k in s:
            s = s.replace(k, ' ' + v + ' ')
    # collapse spaces that replacement created
    s = re.sub(r"\s+", ' ', s).strip()
    return s

# normalize common plural units to singular for stable prefix matching
_UNIT_SINGULAR = {
    'cups': 'cup', 'tablespoons': 'tablespoon', 'tablespoons.': 'tablespoon', 'tbsp': 'tablespoon', 'tbsps': 'tablespoon',
    'teaspoons': 'teaspoon', 'tsp': 'teaspoon', 'tsps': 'teaspoon', 'ounces': 'ounce', 'oz': 'ounce', 'lbs': 'lb', 'pounds': 'pound',
    'cloves': 'clove', 'slices': 'slice', 'packages': 'package', 'cans': 'can'
}


# normalize unit abbreviations and plural forms throughout a string
_UNIT_NORMALIZE = {
    'tbsp.': 'tablespoon', 'tbsp': 'tablespoon', 'tbsps': 'tablespoon', 'tablespoons': 'tablespoon',
    'tsp.': 'teaspoon', 'tsp': 'teaspoon', 'tsps': 'teaspoon', 'teaspoons': 'teaspoon',
    'cups': 'cup', 'cup.': 'cup', 'oz': 'ounce', 'ounces': 'ounce', 'lbs': 'lb', 'pounds': 'pound',
    'cloves': 'clove', 'slices': 'slice', 'pkg': 'package', 'pkgs': 'package'
}


def _normalize_units(s: str) -> str:
    if not s:
        return s
    # replace whole-word occurrences
    def repl(m):
        w = m.group(0)
        return _UNIT_NORMALIZE.get(w.lower(), w)

    pattern = re.compile(r"\b(" + '|'.join(re.escape(k) for k in _UNIT_NORMALIZE.keys()) + r")\b", flags=re.I)
    return pattern.sub(repl, s)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def _collapse_adjacent_repeats(s, max_ngram=6):
    """Collapse adjacent repeated token sequences in a string.

    Example: '1/2 cup 1/2 cup sugar' -> '1/2 cup sugar'
    Works by searching for adjacent duplicated n-grams and removing duplicates.
    """
    if not s or not isinstance(s, str):
        return s
    toks = s.split()
    if len(toks) < 2:
        return s
    max_ngram = min(max_ngram, len(toks) // 2)
    while True:
        did = False
        i = 0
        L = len(toks)
        while i < L - 1:
            found = False
            for n in range(max_ngram, 0, -1):
                if i + 2 * n <= L and toks[i:i + n] == toks[i + n:i + 2 * n]:
                    del toks[i + n:i + 2 * n]
                    L = len(toks)
                    did = True
                    found = True
                    break
            if not found:
                i += 1
        if not did:
            break
    return ' '.join(toks)


def _collapse_similar_adjacent(s, max_ngram=8):
    """Collapse adjacent n-grams that are equivalent after light normalization.

    This helps catch cases like '1 cup 1 cups' or '2 clove 2 cloves' where tokens
    differ only by simple pluralization or minor punctuation.
    """
    if not s or not isinstance(s, str):
        return s
    toks = s.split()
    if len(toks) < 2:
        return s
    max_ngram = min(max_ngram, len(toks) // 2)

    def norm_token(t):
        t2 = t.lower()
        t2 = re.sub(r"[\W_]", '', t2)
        if t2.endswith('s') and not t2.endswith('ss'):
            t2 = t2[:-1]
        return t2

    while True:
        did = False
        i = 0
        L = len(toks)
        while i < L - 1:
            found = False
            for n in range(max_ngram, 0, -1):
                if i + 2 * n <= L:
                    a = toks[i:i + n]
                    b = toks[i + n:i + 2 * n]
                    if all(norm_token(x) == norm_token(y) for x, y in zip(a, b)):
                        del toks[i + n:i + 2 * n]
                        L = len(toks)
                        did = True
                        found = True
                        break
            if not found:
                i += 1
        if not did:
            break
    return ' '.join(toks)


def _strip_loose_prefix(s: str, prefix: str) -> str:
    """Loosely strip a prefix from the start of s even when spacing/punctuation differs.

    This helps catch cases like '400 g 400g spaghetti' or '400 g 400 gram spaghetti'
    where the remaining string begins with a variant of the prefix.
    
    Strategy: tokenize by spaces, and match tokens one-by-one, accounting for unit variations
    like 'g' vs 'gram', 'tbsp' vs 'tablespoon', etc.
    """
    if not s or not prefix:
        return s
    
    # Tokenize both strings
    prefix_toks = prefix.split()
    s_toks = s.split()
    
    if not prefix_toks or not s_toks:
        return s
    
    # Normalize a token for loose matching (e.g., '400g' -> '400', 'gram' -> 'g', 'tbsp' -> 'tablespoon')
    def normalize_unit_token(tok):
        """Normalize unit tokens to their canonical singular form."""
        t = tok.lower()
        # remove trailing 's' for plurals (grams -> gram, cloves -> clove, etc.)
        if t.endswith('s') and not t.endswith('ss') and len(t) > 1:
            t = t[:-1]
        # compact form mapping: 'tbsp' -> 'tablespoon', 'tsp' -> 'teaspoon', etc.
        compact_map = {
            'tbsp': 'tablespoon',
            'tsp': 'teaspoon',
            'oz': 'ounce',
            'lb': 'pound',
            'ml': 'ml',
            'l': 'liter',
            'g': 'gram',
            'kg': 'kilogram',
        }
        return compact_map.get(t, t)
    
    # Match tokens from the start, accounting for quantity+unit variations
    matched_count = 0
    s_idx = 0
    p_idx = 0
    
    while p_idx < len(prefix_toks) and s_idx < len(s_toks):
        p_tok = prefix_toks[p_idx]
        s_tok = s_toks[s_idx]
        
        # Try to match this prefix token against the remainder token
        if p_tok.lower() == s_tok.lower():
            # Exact match
            matched_count += 1
            p_idx += 1
            s_idx += 1
        elif normalize_unit_token(p_tok) == normalize_unit_token(s_tok):
            # Unit variation match (gram vs g, plural vs singular, etc.)
            matched_count += 1
            p_idx += 1
            s_idx += 1
        elif p_idx == 0 and p_tok.replace('.', '').replace(',', '').isdigit():
            # First token is a number; try to match with compacted quantity+unit in remainder
            # e.g., prefix '400 g' against remainder '400g spaghetti'
            # Attempt to strip digits from start of s_tok
            if s_tok and s_tok[0].isdigit():
                # Extract leading digits from s_tok
                dig_end = 0
                for c in s_tok:
                    if c.isdigit() or c in './-':
                        dig_end += 1
                    else:
                        break
                s_num = s_tok[:dig_end]
                s_unit = s_tok[dig_end:].lower()
                if p_tok == s_num and (s_unit == '' or normalize_unit_token(s_unit) == normalize_unit_token(prefix_toks[p_idx + 1] if p_idx + 1 < len(prefix_toks) else '')):
                    # Matched quantity, check if next prefix token is the unit
                    if p_idx + 1 < len(prefix_toks):
                        p_unit = prefix_toks[p_idx + 1].lower()
                        if s_unit and normalize_unit_token(s_unit) == normalize_unit_token(p_unit):
                            # Quantity and unit matched
                            matched_count += 2
                            p_idx += 2
                            s_idx += 1
                        else:
                            break
                    else:
                        break
                else:
                    break
            else:
                break
        else:
            # No match
            break
    
    # If we matched all prefix tokens, return the remainder
    if p_idx == len(prefix_toks):
        # Return the remaining tokens
        return ' '.join(s_toks[s_idx:])
    
    # If we didn't match everything, return the original string
    return s


def _parse_quantity_to_fraction(q: str):
    """Parse a quantity string into a Fraction.

    Handles mixed numbers like '1 1/2', simple fractions '1/2', decimals '1.25',
    and returns a Fraction. For ranges like '1-2' or '1 to 2' the first value is used.
    """
    if not q:
        return None
    q = str(q).strip()
    # take the first side of a range
    q = re.split(r"\bto\b|-", q)[0].strip()
    # normalize unicode fractions if present
    q = _normalize_fractions(q)
    # mixed number '1 1/2'
    if ' ' in q:
        parts = q.split()
        try:
            whole = int(parts[0])
            frac = Fraction(parts[1])
            return Fraction(whole) + frac
        except Exception:
            pass
    # fraction like '3/4'
    if '/' in q:
        try:
            return Fraction(q)
        except Exception:
            pass
    # decimal or integer
    try:
        if '.' in q:
            return Fraction(str(float(q)))
        return Fraction(int(q))
    except Exception:
        # fallback: try to extract digits
        m = re.search(r"\d+(?:\.\d+)?", q)
        if m:
            return Fraction(str(float(m.group(0))))
    return None


def _convert_quantity_unit_to_metric(qty_str: str, unit: str):
    """Convert a quantity + unit into a metric quantity string and unit.

    Returns (qty_string, metric_unit) or (None, None) if conversion not possible.
    Uses approximate standard mappings: cup=240ml, tablespoon=15ml, teaspoon=5ml,
    kg/g for weight, lb/oz to grams.
    """
    if not qty_str or not unit:
        return None, None
    f = _parse_quantity_to_fraction(qty_str)
    if f is None:
        return None, None
    # normalize unit
    u = unit.lower()
    # volume units -> ml
    VOLUME_TO_ML = {
        'cup': Fraction(240),
        'tablespoon': Fraction(15),
        'teaspoon': Fraction(5),
        'tbsp': Fraction(15),
        'tsp': Fraction(5),
        'ml': Fraction(1),
        'l': Fraction(1000),
    }
    # weight units -> grams
    WEIGHT_TO_G = {
        'g': Fraction(1),
        'gram': Fraction(1),
        'grams': Fraction(1),
        'kg': Fraction(1000),
        'kilogram': Fraction(1000),
        'pound': Fraction(45359237, 100000),
        'lb': Fraction(45359237, 100000),
        'ounce': Fraction(283495, 10000),
        'oz': Fraction(283495, 10000),
    }

    if u in VOLUME_TO_ML:
        conv = f * VOLUME_TO_ML[u]
        # represent as ml unless >=1000 -> liters
        if conv >= 1000:
            # show liters with up to 2 decimals
            val = float(conv) / 1000.0
            qs = (int(val) if float(val).is_integer() else round(val, 2))
            return f"{qs}", 'l'
        else:
            val = float(conv)
            qs = (int(val) if float(val).is_integer() else round(val, 2))
            return f"{qs}", 'ml'
    if u in WEIGHT_TO_G:
        conv = f * WEIGHT_TO_G[u]
        val = float(conv)
        qs = (int(val) if float(val).is_integer() else round(val, 2))
        # Use 'gram' instead of 'g' to match our normalization expansion
        return f"{qs}", 'gram'
    return None, None


def normalize_ingredient(text):
    """Return a grocery-friendly normalized ingredient string.

    Heuristics:
    - Preserve a leading quantity/unit if present (e.g. '2', '1/2 cup').
    - Remove parenthetical notes (weights, "about...").
    - Remove preparation instructions (cut into, finely shredded, diced, etc.).
    - Remove size adjectives (medium, large) and redundant words.
    - Strip measurement fragments like '1/2-inch pieces'.
    - Cut off trailing clauses introduced by commas, dashes, or 'with'.
    """
    if not text:
        return ''
    raw = str(text).strip()
    # preserve original for explicit checkbox detection
    _orig_raw = raw
    # Note: do not drop lines that contain common square/bullet glyphs — they are
    # often just list bullets. We'll strip those characters below instead.
    # remove common bullet/list marker characters anywhere in the text so we don't
    # accidentally treat them as part of the ingredient
    raw = re.sub(r"[\u25a2\u2022\u2023\u25aa\u25ab\u25cf\u2024\u25cb\u25e6\*\u25b6\u25ba\u25c6\u25c7]+", ' ', raw)
    raw = raw.strip()
    # remove parenthetical content early (weights, notes, cooking tips)
    raw = re.sub(r"\([^)]*\)", "", raw)
    # normalize replacement characters and unicode fraction glyphs early
    raw = _normalize_fractions(raw)
    # normalize unit abbreviations early
    raw = _normalize_units(raw)
    low = raw.lower()
    # drop obvious non-ingredient noise (comments, replies, timestamps, long prose)
    noise_tokens = ['reply', 'says:', 'says', 'comment', 'comments', 'posted', 'minutes', 'hands-on', 'hands on', 'beginner-friendly', 'i have not made this yet', 'thanks', 'thank you', 'review', 'rating', 'reads:', 'readers', 'reads']
    if any(tok in low for tok in noise_tokens):
        return ''
    # Drop cooking instruction or promotional sentences that sometimes appear
    # in ingredient lists (e.g. "one-pan baking dinner in one pan makes it mess-free and easy to clean").
    # Heuristics: presence of instruction tokens combined with pronouns or being a short clause
    # Expand instruction tokens (include verbs like 'pat', 'prep')
    instruction_tokens = [
        'preheat', 'prep', 'prepar', 'prepare', 'bake', 'cook', 'simmer', 'serve', 'makes it', 'makes',
        'easy to', 'mess-free', 'clean', 'enjoy', 'toss', 'combine', 'stir', 'heat', 'roast', 'broil',
        'fry', 'pan', 'skillet', 'oven', 'microwave', 'instructions', 'directions', 'step', 'try this',
        'pat ', 'pat the', 'drying off', 'dry off', 'drain and', 'drain the', 'marinade', 'marinate', 'prep preheat',
        # usage / substitution language often appears in prose like "I use skim milk but you can use whole milk"
        'use', 'using', 'used', 'prefer', 'recommend', 'substitut', 'substitute', 'substitutions', 'swap'
    ]
    # Social media / platform tokens to remove (Instagram, Pinterest, Facebook, Twitter, TikTok, etc.)
    social_tokens = ['instagram', 'pinterest', 'facebook', 'twitter', 'tiktok', 'tick tock', 'snapchat', 'youtube', 'linktr.ee', 'linkedin']

    # checkbox / list glyphs often show up: drop if present
    checkbox_glyphs = ['▢', '☐', '□', '✓', '\u2610', '\u2611']

    # temperature regex (e.g. 350ºf, 350 °F, 350f, 180C)
    temp_re = re.compile(r"\b\d{2,3}\s*(?:°|º|deg|degrees)?\s*[fFcC]\b")

    # explicit checkbox glyphs were handled earlier; continue processing

    # If the line contains a temperature or starts with explicit prep/preheat/pat verbs, drop
    if temp_re.search(low) or low.startswith(('prep ', 'preheat', 'pat ', 'pat the ', 'prep preheat')):
        return ''

    # if line contains either instruction tokens OR social tokens and also contains a pronoun or is long, treat as instruction/promotional
    if any(tok in low for tok in instruction_tokens + social_tokens):
        # detect pronouns robustly (word boundaries)
        pronoun_re = re.compile(r"\b(i|you|your|we|it|they|you're|you'll|i'm|i've|me|my)\b", re.I)
        words = low.split()
        # also drop pure social/connect commands like 'connect instagram pinterest facebook twitter tik tok'
        social_phrase = any(tok in low for tok in social_tokens)
        if social_phrase:
            # drop if the line is clearly a social/connect phrase or contains multiple platform names
            platform_hits = sum(1 for tok in social_tokens if tok in low)
            if platform_hits >= 1:
                return ''
        if pronoun_re.search(low) or len(words) > 6:
            return ''
    # drop lines that look like sentences with URLs or long prose
    if ('http' in low or 'www.' in low) or (len(raw) > 120 and raw.count(' ') > 10):
        return ''

    s = raw

    # Pre-process to normalize whole-word units that might be confused with other words
    # Convert "1 loaf/loaves" to "1 WHOLEBREAD_LOAF" so "l" isn't matched as liter unit
    # (using WHOLEBREAD_ prefix ensures it won't match any unit abbreviations)
    s = re.sub(r'\b(\d+)\s+(?:loaf|loaves)\b', r'\1 WHOLEBREAD_LOAF', s, flags=re.I)
    
    # Convert compacted unit formats like '400g' or '1ml' to spaced form for consistent parsing
    # This helps catch entries where quantity and unit are written together without spaces
    s = re.sub(r'(\d+(?:\.\d+)?)(ml|kg|l)\b', r'\1 \2', s, flags=re.I)
    # Special case for 'g' (gram): only convert when followed by a space or end/punctuation, not a letter
    # This avoids converting 'garlic' -> 'gar lic'
    s = re.sub(r'(\d+(?:\.\d+)?)g\b(?![a-z])', r'\1 gram', s, flags=re.I)
    
    # Remove packaging words that appear between quantity and ingredient
    # "100g bag X" -> "100g X", leave just the ingredient
    s = re.sub(r'\s+(bag|container|pouch|box|carton|bottle)(?=\s|$)', '', s, flags=re.I)

    # Try to capture a leading quantity + optional unit (keep as prefix)
    # Avoid matching single 'g' from 'garlic', 'ginger', etc. But do match if followed by non-letter or at end
    qty_re = re.compile(r"^\s*((?:\d+\s*\d*/\d+|\d+/\d+|\d+(?:\.\d+)?)(?:\s*(?:to|-)\s*(?:\d+\s*\d*/\d+|\d+/\d+|\d+(?:\.\d+)?))?)\s*(cups?|tablespoons?|tbsp|teaspoons?|tsp|pounds?|lb|lbs|ounces?|oz|kg|grams?|g(?:\s|$)|ml|liters?|l(?:\s|$)|cloves?|cans?|packages?|pkg|slices?|bunch|stalk|pinch)?\s*(of)?\s*(.*)$",
                        re.I)
    m = qty_re.match(s)
    prefix = ''
    if m:
        qty = m.group(1) or ''
        unit = m.group(2) or ''
        rest = m.group(4) or ''
        # no further validation needed since we removed single 'g' from the pattern
    
    if m:
        # normalize unit to singular form for better duplicate detection
        try:
            unit_norm = _UNIT_SINGULAR.get(unit.lower(), unit)
        except Exception:
            unit_norm = unit
        # handle special preprocessing: convert "LOAF_UNIT" back to "loaf" 
        if unit_norm and 'LOAF_UNIT' in unit_norm.upper():
            unit_norm = unit_norm.replace('LOAF_UNIT', 'loaf').replace('loaf_unit', 'loaf')
        prefix = (qty + ' ' + unit_norm).strip()
        s = rest.strip()
        # also normalize the remainder to convert compacted units like '400g' -> '400 gram'
        # and expand single-letter units to their full names for consistency
        s = re.sub(r'(\d+(?:\.\d+)?)(ml|kg|l)\b', r'\1 \2', s, flags=re.I)
        s = re.sub(r'(\d+(?:\.\d+)?)g\b(?![a-z])', r'\1 gram', s, flags=re.I)
        s = re.sub(r'\b(g)(?:\s|$)', r'gram ', s, flags=re.I)  # convert 'g' or 'g ' to 'gram '
        s = s.strip()
        # also normalize the prefix the same way for consistency
        prefix = re.sub(r'(\d+(?:\.\d+)?)(ml|kg|l)\b', r'\1 \2', prefix, flags=re.I)
        prefix = re.sub(r'(\d+(?:\.\d+)?)g\b(?![a-z])', r'\1 gram', prefix, flags=re.I)
        prefix = re.sub(r'\b(g)(?:\s|$)', r'gram ', prefix, flags=re.I)  # convert 'g' or 'g ' to 'gram '
        # remove any literal/compacted duplicate of the original prefix from remainder
        try:
            s = _strip_loose_prefix(s, prefix)
        except Exception:
            # fallback to previous literal removal
            if s.lower().startswith(prefix.lower()):
                s = s[len(prefix):].strip()
            else:
                pq = re.escape(prefix)
                s = re.sub(rf"^\s*{pq}\b", '', s, flags=re.I).strip()
        # attempt to convert common measurements to metric (ml/g) for consistency
        try:
            conv_qty, conv_unit = _convert_quantity_unit_to_metric(qty, unit_norm)
            if conv_qty and conv_unit:
                prefix = (str(conv_qty) + ' ' + conv_unit).strip()
        except Exception:
            pass
    # if regex match was rejected (m is None), s still contains the raw normalized text
        # attempt to convert common measurements to metric (ml/g) for consistency
        try:
            conv_qty, conv_unit = _convert_quantity_unit_to_metric(qty, unit_norm)
            if conv_qty and conv_unit:
                prefix = (str(conv_qty) + ' ' + conv_unit).strip()
        except Exception:
            pass
        # if rest itself begins with the same quantity/unit phrase (duplicate), strip it
        if prefix:
            # attempt to remove duplicate occurrences of the prefix in the remaining string.
            # use a loose strip that tolerates spacing/punctuation differences (e.g. '400 g' vs '400g')
            try:
                s = _strip_loose_prefix(s, prefix)
            except Exception:
                # fallback to literal checks if something unexpected happens
                if s.lower().startswith(prefix.lower()):
                    s = s[len(prefix):].strip()
                else:
                    pq = re.escape(prefix)
                    s = re.sub(rf"^\s*{pq}\b", '', s, flags=re.I).strip()

    # parenthetical content already removed early in processing
    # remove packaging descriptors (bag, container, pouch, etc)
    s = re.sub(r"\b(bag|container|pouch|box|carton|bottle)\b", '', s, flags=re.I)
    # cut off after comma, dash, em-dash — often preparation follows
    s = re.split(r"[,-\u2013\u2014]", s)[0]
    # cut off at ' with ' to avoid inline accompaniments
    s = re.split(r"\bwith\b", s, flags=re.I)[0]

    # remove specific 'cut into ...' or size/measurement fragments
    s = re.sub(r"cut into .*", '', s, flags=re.I)
    s = re.sub(r"cut (into|in|to).*", '', s, flags=re.I)
    s = re.sub(r"\b\d+[\d/\-]*\s*[-]?\s*(inch|inches|cm|mm)\b", '', s, flags=re.I)
    s = re.sub(r"\b\d+[\d/\-]*\s*(piece|pieces|slice|slices)\b", '', s, flags=re.I)

    # remove common preparation words/adjectives
    prep_pattern = r"\b(chopped|chopping|diced|minced|shredded|shred|shreds|sliced|slice|peeled|peeled and|crushed|ground|mashed|softened|room temperature|trimmed|rinsed|drained|pitted|seeded|julienned|grated|grating|crumbled|beaten|whisked|packed|to taste|for garnish|finely|coarsely|thinly|roughly|halved|quartered|thinly sliced|finely shredded|cut|cut into|pieces)\b"
    s = re.sub(prep_pattern, '', s, flags=re.I)

    # remove explicit weight units left behind
    s = re.sub(r"\b\d+[\d/\-]*\s*(pound|pounds|lb|lbs|oz|ounce|ounces|kg|g)\b", '', s, flags=re.I)
    # remove size adjectives
    s = re.sub(r"\b(medium|large|small|extra-large|extra large|jumbo|fresh|frozen|canned|drained|peeled|trimmed|ripe)\b", '', s, flags=re.I)
    # remove redundant words
    s = re.sub(r"\b(about|approximately|about\s+|each)\b", '', s, flags=re.I)

    # collapse whitespace and strip punctuation
    s = re.sub(r"\s+", ' ', s).strip()
    s = s.strip(' ,.;:')

    # normalize fractions and units again in the post-cleaned portion
    s = _normalize_fractions(s)
    s = _normalize_units(s)
    # collapse adjoining repeated phrases/tokens that survived earlier cleaning
    # use a slightly larger n-gram window to catch longer repeated phrases
    s = _collapse_adjacent_repeats(s, max_ngram=8)

    # If the cleaned string is empty and there's no meaningful prefix, treat as noise
    if not s:
        # if we have a leading quantity/unit but nothing else, try to preserve minimal info
        if not prefix:
            return ''
        # otherwise fall back to the original remainder (already had prefix removed)
        try:
            s = re.sub(r"\s+", ' ', rest).strip()
        except Exception:
            s = re.sub(r"\s+", ' ', str(text)).strip()

    result = (prefix + ' ' + s).strip() if prefix else s
    # final pass: if we had a prefix, ensure the body does not still begin
    # with a compacted or variant form of the same prefix. This catches
    # stubborn cases where earlier removal left a compacted token like
    # '400g' after attaching a normalized prefix '400 g'.
    if prefix:
        # body after the prefix in the current result
        body = result[len(prefix):].lstrip()
        try:
            new_body = _strip_loose_prefix(body, prefix)
            if new_body != body:
                result = (prefix + ' ' + new_body).strip()
        except Exception:
            pass
    # remove any remaining bullet/list glyphs that survived earlier stages
    result = re.sub(r"[\u25a2\u2022\u2023\u25aa\u25ab\u25cf\u2024\u25cb\u25e6\*\u25b6\u25ba\u25c6\u25c7]+", ' ', result)
    result = re.sub(r"\s+", ' ', result).strip()
    # final collapses for any accidental repeats introduced when re-attaching prefix
    result = _collapse_adjacent_repeats(result, max_ngram=8)
    result = _collapse_similar_adjacent(result, max_ngram=8)
    return result


def canonicalize_ingredient(text):
    """Map a normalized ingredient string to a canonical form for aggregation.

    - Lowercases and strips punctuation
    - Applies known synonym mappings (e.g., 'extra virgin olive oil' -> 'olive oil')
    - Marks canned items as 'canned <item>' when a can/container is detected
    - Performs light singularization for simple plurals
    """
    if not text:
        return ''
    s = text.lower().strip()
    # remove leading quantity + unit (e.g. '379.88 gram', '1 cup', '2 tbsp')
    qty_unit_re = r"^\s*(?:\d+(?:[.,]\d+)?(?:\s*(?:to|-)\s*\d+(?:[.,]\d+)?)?)\s*(?:cups?|tablespoons?|tbsp|teaspoons?|tsp|pounds?|lb|lbs|ounces?|oz|kg|grams?|g|ml|l|clove|cloves|can|cans|package|pkg|slice|slices|bunch|stalk|pinch|unit)?\b\s*"
    try:
        s = re.sub(qty_unit_re, '', s, flags=re.I)
    except Exception:
        # fallback: leave s unchanged on unexpected regex errors
        pass
    # remove stray punctuation
    s = re.sub(r'[()\.,;:"]', '', s)

    # normalize fractions and replacement glyphs
    s = _normalize_fractions(s)

    # collapse any accidental repeated tokens in canonical form as well
    s = _collapse_adjacent_repeats(s, max_ngram=8)

    # detect canned/container
    is_canned = False
    if re.search(r"\bcan\b|\bcanned\b|\bjar\b|\bpacket\b|\bpouch\b", s):
        is_canned = True
        # remove the container word
        s = re.sub(r"\b(\d+\s*-?\s*)?(ounce|oz|pound|lb|lbs|kg|g|can|cans|canned|jar|jars|package|pkg|pouch)\b", '', s)
        s = re.sub(r"\bcan(s)?\b|\bcanned\b|\bjar(s)?\b", '', s)

    # synonym map (expand as needed)
    syn = {
        'extra virgin olive oil': 'olive oil',
        'extra-virgin olive oil': 'olive oil',
        'olive oil, extra virgin': 'olive oil',
        'all purpose flour': 'flour',
        'all-purpose flour': 'flour',
        'plain flour': 'flour',
        'scallions': 'green onion',
        'spring onions': 'green onion',
        'spring onion': 'green onion',
        'chicken breast': 'chicken',
        'boneless skinless chicken breasts': 'chicken',
        'ground beef': 'beef',
        'minced beef': 'beef'
    }
    s_key = s.strip()
    # apply synonym exact match first
    if s_key in syn:
        s_key = syn[s_key]
    else:
        # try to replace known phrases appearing inside string
        for k, v in syn.items():
            if k in s_key:
                s_key = s_key.replace(k, v)

    # light singularization: remove trailing s for simple plurals
    if s_key.endswith('s') and not s_key.endswith('ss'):
        s_key = s_key[:-1]

    s_key = re.sub(r"\s+", ' ', s_key).strip()
    # collapse near-duplicate adjacent phrases (handles '2 clove 2 cloves' etc.)
    s_key = _collapse_similar_adjacent(s_key, max_ngram=8)
    if is_canned:
        # prefer 'canned <item>' format
        if not s_key.startswith('canned'):
            s_key = 'canned ' + s_key

    return s_key


# Reusable regex to extract a leading quantity + optional unit from a normalized string.
# Named groups: qty, unit, body
QTY_UNIT_RE = re.compile(
    r"^\s*(?P<qty>(?:\d+\s+\d*/\d+|\d+/\d+|\d+(?:[.,]\d+)?)(?:\s*(?:to|-)\s*(?:\d+\s+\d*/\d+|\d+/\d+|\d+(?:[.,]\d+)?))?)\s*(?P<unit>cups?|tablespoons?|tablespoons?|tablespoon|tbsp|teaspoons?|tsp|pounds?|pound|lb|lbs|ounces?|ounce|oz|kg|kilogram|grams?|gram|g|ml|l(?:\s|$)|liters?|liter|cloves?|cans?|can|packages?|package|pkg|slices?|slice|bunch|stalk|pinch)?\b\s*(?P<body>.*)$",
    re.I
)


def normalize_ingredient_structured(text):
    """Return a structured dict for an ingredient.

    Fields returned:
      - quantity: original leading quantity string (or None)
      - unit: original unit string (or None)
      - quantity_metric: converted metric quantity string (or None)
      - unit_metric: metric unit string (e.g. 'gram' or 'ml') (or None)
      - normalized: the grocery-friendly normalized string (same as `normalize_ingredient`)
      - canonical: canonical aggregation key (same as `canonicalize_ingredient`)
      - body: the normalized ingredient body (without leading qty/unit)

    This function is non-destructive and preserves existing text-normalization behavior,
    while exposing parsed numeric and unit information for safer aggregation.
    """
    norm = normalize_ingredient(text)
    qty = None
    unit = None
    body = norm or ''
    m = None
    try:
        m = QTY_UNIT_RE.match(norm or '')
    except Exception:
        m = None
    if m:
        qty = m.group('qty') or None
        unit = m.group('unit') or None
        body = (m.group('body') or '').strip()

    # Attempt metric conversion if we have a quantity+unit
    quantity_metric = None
    unit_metric = None
    if qty and unit:
        try:
            cq, cu = _convert_quantity_unit_to_metric(qty, unit)
            if cq and cu:
                quantity_metric = cq
                unit_metric = cu
        except Exception:
            quantity_metric = None
            unit_metric = None

    # canonical key (reuses canonicalize_ingredient which already strips leading qty/unit)
    canon = canonicalize_ingredient(norm)

    return {
        'quantity': str(qty) if qty is not None else None,
        'unit': unit if unit else None,
        'quantity_metric': quantity_metric,
        'unit_metric': unit_metric,
        'normalized': norm,
        'canonical': canon,
        'body': body,
    }


def build_ingredient_rows(raw_ingredients):
    """Convert raw ingredient strings into normalized ingredient row dictionaries."""
    rows = []
    for raw_text in raw_ingredients or []:
        if not raw_text or not isinstance(raw_text, str):
            continue
        parsed = normalize_ingredient_structured(raw_text)
        if not parsed or not parsed.get('normalized'):
            continue
        rows.append({
            'raw_text': raw_text.strip(),
            'canonical_text': parsed.get('canonical', ''),
            'quantity': parsed.get('quantity'),
            'unit': parsed.get('unit'),
            'quantity_metric': parsed.get('quantity_metric'),
            'unit_metric': parsed.get('unit_metric')
        })
    return rows


def parse_recipe_ingredients(url, timeout=10):
    """Scrape and parse ingredients from a recipe URL."""
    raw_ingredients = scrape_ingredients_from_url(url, timeout=timeout)
    return build_ingredient_rows(raw_ingredients)


def _extract_json_ld(soup):
    scripts = soup.find_all('script', type='application/ld+json')
    for s in scripts:
        try:
            data = json.loads(s.string)
        except Exception:
            # sometimes there are multiple JSON objects inside
            try:
                txt = s.string or ''
                # try to find the first JSON object
                m = re.search(r"\{.*\}", txt, re.S)
                if m:
                    data = json.loads(m.group(0))
                else:
                    continue
            except Exception:
                continue
        # JSON-LD can be a list
        if isinstance(data, list):
            for item in data:
                if item.get('@type') and item.get('@type').lower() == 'recipe':
                    return item
        elif isinstance(data, dict):
            t = data.get('@type') or data.get('@context')
            if isinstance(t, str) and 'recipe' in t.lower():
                return data
            # sometimes recipe is nested
            for v in data.values():
                if isinstance(v, dict) and v.get('@type') and 'recipe' in str(v.get('@type')).lower():
                    return v
    return None


def _extract_from_html(soup):
    # look for common itemprop patterns
    ingredients = []
    # itemprop="recipeIngredient"
    items = soup.select('[itemprop=recipeIngredient]')
    for it in items:
        txt = it.get_text(separator=' ', strip=True)
        if txt:
            ingredients.append(txt)
    if ingredients:
        return ingredients

    # common classes/ids
    possible_selectors = [
        '.ingredients-list',
        '.ingredients',
        '#ingredients',
        '.recipe-ingredients',
        '.ingredient-list',
        '.recipe__ingredients',
        '.ingredients-section'
    ]
    for sel in possible_selectors:
        nodes = soup.select(sel)
        for n in nodes:
            # find li elements inside
            lis = n.find_all('li')
            for li in lis:
                txt = li.get_text(separator=' ', strip=True)
                if txt:
                    ingredients.append(txt)
        if ingredients:
            return ingredients

    # last resort: look for <li> that contains measurement words or simple heuristics
    lis = soup.find_all('li')
    for li in lis:
        txt = li.get_text(separator=' ', strip=True)
        if not txt:
            continue
        # heuristic: contains digits or measurement words
        if re.search(r"\d|cup|tbsp|tsp|ounce|oz|pound|g|kg|ml|clove|slice", txt, re.I):
            ingredients.append(txt)
    if ingredients:
        # dedupe and return
        seen = []
        for i in ingredients:
            if i not in seen:
                seen.append(i)
        return seen

    return []


def scrape_ingredients_from_url(url, timeout=10):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return []
    try:
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception:
        return []

    # Try JSON-LD first
    jsonld = _extract_json_ld(soup)
    if jsonld:
        # recipeIngredient or ingredients
        ingr = jsonld.get('recipeIngredient') or jsonld.get('ingredients')
        if isinstance(ingr, list):
            return [str(i).strip() for i in ingr if str(i).strip()]
        if isinstance(ingr, str) and ingr.strip():
            # split lines
            lines = [l.strip() for l in ingr.split('\n') if l.strip()]
            return lines

    # Fallback to HTML selectors
    return _extract_from_html(soup)


# Default aisle mapping for common ingredients. Database overrides this at runtime.
DEFAULT_AISLE_MAP = {
    # Produce
    'onion': 'Produce', 'garlic': 'Produce', 'carrot': 'Produce', 'celery': 'Produce',
    'bell pepper': 'Produce', 'pepper': 'Produce', 'tomato': 'Produce', 'potato': 'Produce',
    'lemon': 'Produce', 'lime': 'Produce', 'broccoli': 'Produce', 'spinach': 'Produce',
    'lettuce': 'Produce', 'kale': 'Produce', 'zucchini': 'Produce', 'mushroom': 'Produce',
    'avocado': 'Produce', 'ginger': 'Produce', 'scallion': 'Produce', 'herb': 'Produce',
    'cucumber': 'Produce', 'eggplant': 'Produce', 'sweet potato': 'Produce', 'squash': 'Produce',
    'green bean': 'Produce', 'asparagus': 'Produce', 'cauliflower': 'Produce', 'cabbage': 'Produce',
    'radish': 'Produce', 'jalapeno': 'Produce', 'parsley': 'Produce', 'cilantro': 'Produce',
    'basil': 'Produce', 'mint': 'Produce', 'rosemary': 'Produce', 'thyme': 'Produce',
    'banana': 'Produce', 'apple': 'Produce', 'berry': 'Produce', 'blueberry': 'Produce',
    # Cheese
    'parmesan': 'Cheese', 'cheddar': 'Cheese', 'mozzarella': 'Cheese', 'cheese': 'Cheese',
    'cream cheese': 'Cheese', 'feta': 'Cheese', 'ricotta': 'Cheese', 'provolone': 'Cheese',
    'swiss': 'Cheese', 'gouda': 'Cheese', 'goat cheese': 'Cheese', 'monterey jack': 'Cheese',
    'mascarpone': 'Cheese',
    # Meat
    'chicken': 'Meat', 'beef': 'Meat', 'pork': 'Meat', 'bacon': 'Meat', 'sausage': 'Meat',
    'turkey': 'Meat', 'ham': 'Meat', 'ground beef': 'Meat', 'steak': 'Meat', 'lamb': 'Meat',
    'duck': 'Meat', 'ground pork': 'Meat', 'ground turkey': 'Meat', 'chorizo': 'Meat',
    'salmon': 'Meat', 'fish': 'Meat', 'seafood': 'Meat', 'shrimp': 'Meat', 'tuna': 'Meat',
    'crab': 'Meat', 'lobster': 'Meat', 'scallop': 'Meat', 'tilapia': 'Meat', 'cod': 'Meat',
    # Spices
    'salt': 'Spices', 'cinnamon': 'Spices', 'cumin': 'Spices', 'paprika': 'Spices',
    'oregano': 'Spices', 'thyme': 'Spices',
    'bay leaf': 'Spices', 'chili powder': 'Spices', 'turmeric': 'Spices',
    'vanilla extract': 'Spices', 'vanilla': 'Spices', 'black pepper': 'Spices',
    'red pepper flake': 'Spices', 'coriander': 'Spices', 'nutmeg': 'Spices',
    'garlic powder': 'Spices', 'onion powder': 'Spices', 'italian seasoning': 'Spices',
    # Canned
    'canned tomato': 'Canned', 'canned bean': 'Canned', 'canned corn': 'Canned',
    'canned chicken broth': 'Canned', 'canned coconut milk': 'Canned', 'canned tuna': 'Canned',
    'canned pumpkin': 'Canned', 'canned broth': 'Canned', 'canned': 'Canned',
    'water-packed': 'Canned', 'artichoke': 'Canned', 'canned artichoke': 'Canned',
    # Dry Goods
    'pasta': 'Dry Goods', 'rice': 'Dry Goods', 'flour': 'Dry Goods', 'sugar': 'Dry Goods',
    'bread': 'Dry Goods', 'bread crumb': 'Dry Goods', 'oil': 'Dry Goods', 'olive oil': 'Dry Goods',
    'vinegar': 'Dry Goods', 'soy sauce': 'Dry Goods', 'honey': 'Dry Goods', 'maple syrup': 'Dry Goods',
    'baking powder': 'Dry Goods', 'baking soda': 'Dry Goods', 'cocoa powder': 'Dry Goods',
    'chocolate': 'Dry Goods', 'chocolate chip': 'Dry Goods', 'oat': 'Dry Goods',
    'nut': 'Dry Goods', 'almond': 'Dry Goods', 'peanut butter': 'Dry Goods', 'jam': 'Dry Goods',
    'salsa': 'Dry Goods', 'tortilla': 'Dry Goods', 'chip': 'Dry Goods', 'taco seasoning': 'Dry Goods',
    'rolled oat': 'Dry Goods', 'quick oat': 'Dry Goods', 'cereal': 'Dry Goods', 'cracker': 'Dry Goods',
    'couscous': 'Dry Goods', 'quinoa': 'Dry Goods', 'lentil': 'Dry Goods', 'bean': 'Dry Goods',
    'cornstarch': 'Dry Goods', 'brown sugar': 'Dry Goods', 'powdered sugar': 'Dry Goods',
    'walnut': 'Dry Goods', 'pecan': 'Dry Goods', 'cashew': 'Dry Goods', 'peanut': 'Dry Goods',
    # Stocks and Dressings
    'chicken broth': 'Stocks and Dressings', 'beef broth': 'Stocks and Dressings',
    'vegetable broth': 'Stocks and Dressings', 'broth': 'Stocks and Dressings',
    'stock': 'Stocks and Dressings', 'vinaigrette': 'Stocks and Dressings',
    'salad dressing': 'Stocks and Dressings', 'dressing': 'Stocks and Dressings',
    'worcestershire sauce': 'Stocks and Dressings', 'hot sauce': 'Stocks and Dressings',
    'fish sauce': 'Stocks and Dressings', 'sriracha': 'Stocks and Dressings',
    # Dairy
    'butter': 'Dairy', 'milk': 'Dairy', 'cream': 'Dairy', 'sour cream': 'Dairy',
    'yogurt': 'Dairy', 'egg': 'Dairy', 'heavy cream': 'Dairy', 'half and half': 'Dairy',
    'buttermilk': 'Dairy', 'whipped cream': 'Dairy', 'cream cheese': 'Dairy',
    # Frozen
    'frozen': 'Frozen', 'frozen vegetable': 'Frozen', 'frozen fruit': 'Frozen',
    'frozen spinach': 'Frozen', 'frozen pea': 'Frozen', 'ice cream': 'Frozen',
}

AISLE_ORDER = [
    'Produce', 'Cheese', 'Meat', 'Spices', 'Canned',
    'Dry Goods', 'Stocks and Dressings', 'Dairy', 'Frozen', 'Other'
]


def _load_aisle_map() -> Dict[str, str]:
    """Load aisle assignments from database, falling back to defaults."""
    try:
        from app.database import get_database
        db = get_database()
        db_map = db.get_all_aisle_assignments()
        # Merge: database overrides defaults
        merged = dict(DEFAULT_AISLE_MAP)
        merged.update(db_map)
        return merged
    except Exception:
        return dict(DEFAULT_AISLE_MAP)


def _aisle_sort_key(item: dict) -> tuple:
    """Return sort key for an aggregated item: (aisle_order, canonical_name)."""
    aisle_lookup = _load_aisle_map()
    canon = item.get('canonical', '')
    # Find matching aisle by checking if canonical contains any mapped key
    # Sort keys by length descending so "garlic powder" matches before "garlic"
    aisle = 'Other'
    for key, a in sorted(aisle_lookup.items(), key=lambda x: -len(x[0])):
        if key in canon:
            aisle = a
            break
    order = AISLE_ORDER.index(aisle) if aisle in AISLE_ORDER else 9
    return (order, canon)


def _load_correction_lookup():
    """Load user corrections from the database, returning {raw_text: canonical_text}."""
    try:
        from app.database import get_database
        db = get_database()
        return db.get_all_ingredient_corrections()
    except Exception:
        return {}


def _sum_quantity_metric(qty_str: str) -> float:
    """Parse a quantity_metric string into a float for summing.
    
    Returns 0.0 if parsing fails.
    """
    if not qty_str:
        return 0.0
    try:
        return float(qty_str)
    except (ValueError, TypeError):
        return 0.0


def aggregate_shopping_list(recipes):
    """
    recipes: list of dicts with keys 'title' and 'ingredients' (list) or 'url'
    Returns: dict with 'aggregated' (list of display items with quantities summed)
             and 'per_recipe' (canonical names per recipe)
    """
    # Load user corrections once for the entire aggregation
    corrections = _load_correction_lookup()

    # agg_groups: {canon_key: {'display': str, 'qty_sum': float, 'unit': str, 'count': int}}
    agg_groups = {}
    per_recipe = []
    for r in recipes:
        title = r.get('title')
        ingr_list = r.get('ingredients') or []
        if not ingr_list and r.get('url'):
            ingr_list = scrape_ingredients_from_url(r.get('url'))

        canonical = []
        for item in ingr_list:
            parsed = normalize_ingredient_structured(item)
            if not parsed or not parsed.get('normalized'):
                continue
            # Determine canonical key; user correction always wins
            canon = parsed['canonical']
            canon = corrections.get(canon, canon)

            canonical.append(canon)

            # Initialize group if needed
            if canon not in agg_groups:
                agg_groups[canon] = {
                    'display': canon,
                    'qty_sum': 0.0,
                    'unit': None,
                    'count': 0,
                    'has_metric': False
                }

            group = agg_groups[canon]
            group['count'] += 1

            # Accumulate metric quantities if available and unit matches
            qm = parsed.get('quantity_metric')
            um = parsed.get('unit_metric')
            if qm and um:
                qty_val = _sum_quantity_metric(qm)
                if group['unit'] is None:
                    group['unit'] = um
                    group['qty_sum'] = qty_val
                    group['has_metric'] = True
                elif group['unit'] == um:
                    group['qty_sum'] += qty_val
                else:
                    # Mixed units — clear metric so we fall back to count display
                    group['has_metric'] = False

        per_recipe.append({'title': title, 'ingredients': canonical})

    # Build final display list from aggregated groups, sorted by aisle
    aisle_lookup = _load_aisle_map()
    
    # Assign aisle to each item and create sortable list
    items_with_aisle = []
    for canon, group in agg_groups.items():
        if group['has_metric'] and group['qty_sum'] > 0:
            qty_display = _format_qty(group['qty_sum'])
            display = f"{qty_display} {group['unit']} {canon}"
        else:
            display = canon
        if group['count'] > 1:
            display += f" (used in {group['count']} recipes)"
        
        # Determine aisle — sort keys by length descending so "garlic powder" matches before "garlic"
        aisle = 'Other'
        for key, a in sorted(aisle_lookup.items(), key=lambda x: -len(x[0])):
            if key in canon:
                aisle = a
                break
        aisle_order = AISLE_ORDER.index(aisle) if aisle in AISLE_ORDER else 9
        
        items_with_aisle.append({
            'display': display,
            'canonical': canon,
            'aisle': aisle,
            'aisle_order': aisle_order
        })
    
    # Sort by aisle order, then alphabetically within each aisle
    items_with_aisle.sort(key=lambda x: (x['aisle_order'], x['canonical']))
    
    # Insert aisle section headers
    aggregated_items = []
    seen_aisles = set()
    for item in items_with_aisle:
        if item['aisle'] not in seen_aisles:
            seen_aisles.add(item['aisle'])
            aggregated_items.append({
                'type': 'aisle_header',
                'aisle': item['aisle']
            })
        aggregated_items.append({
            'type': 'item',
            'display': item['display'],
            'canonical': item['canonical'],
            'aisle': item['aisle']
        })

    return {'aggregated': aggregated_items, 'per_recipe': per_recipe}


def _format_qty(val: float) -> str:
    """Format a summed quantity for display: strip .0 for whole numbers, round to 2 decimals."""
    if val == int(val):
        return str(int(val))
    return str(round(val, 2))
