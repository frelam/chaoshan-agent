#!/usr/bin/env python3
"""
Extract Teochew character + Peng'im pairs from learn-teochew Wiktionary Index JSON
(GitHub Content API format: base64-encoded markdown with wiktionary table rows).

Usage:
  python3 scripts/extract-wiktionary.py /tmp/learn_a.json 菜脯 臭柿 赤肉

If no keywords given, outputs all entries.
Each keyword filters by substring match on the character field.
"""
import json, base64, re, sys

filename = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
keywords = sys.argv[2:]

with open(filename) as f:
    data = json.load(f)

content = base64.b64decode(data['content']).decode('utf-8')

# Pattern: | | [汉字](URL) | peng'im | ipa |
# Catches the character-row (second row of each two-row entry)
matches = re.findall(
    r'\[\s*([^\]]+?)\s*\]\([^\)]+\)\s*\|\s*([^|\n]+?)\s*\|',
    content
)

for char, pengim in matches:
    if not keywords or any(kw in char for kw in keywords):
        pengim_clean = pengim.strip().split('/')[0].strip()
        print(f"{char} | {pengim_clean}")

# Also extract one-line entries (single-row pattern variant)
# | char | peng'im | ipa | (no wiki link)
matches_flat = re.findall(
    r'^\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|\s*[^|\n]*\|\s*$',
    content,
    re.MULTILINE
)
for char, pengim in matches_flat:
    char = char.strip()
    pengim = pengim.strip().split('/')[0].strip()
    # Skip headers and table separators
    if char and not char.startswith('-') and not char.startswith('Peng'):
        if not keywords or any(kw in char for kw in keywords):
            print(f"{char} | {pengim}")
