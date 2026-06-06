#!/usr/bin/env python3
"""
Extract Teochew character + Peng'im pairs from learn-teochew source files.
Handles THREE input types:
  1. GitHub Content API JSON (base64-encoded markdown)
  2. Raw markdown files (downloaded from raw.githubusercontent.com)
  3. Address/grammar page markdown (Jekyll tables with | Def | IPA | Peng'im | Char |)

Usage:
  # From GitHub API JSON:
  python3 scripts/extract-wiktionary.py /tmp/learn_a.json [关键词...]

  # From raw markdown:
  python3 scripts/extract-wiktionary.py /tmp/wiktionary_c.md [关键词...]

  # From address/grammar page (table format):
  python3 scripts/extract-wiktionary.py /tmp/learn_address.md --address [关键词...]
"""
import json, base64, re, sys

filename = sys.argv[1] if len(sys.argv) > 1 else "/dev/stdin"
is_address_mode = "--address" in sys.argv
keywords = [k for k in sys.argv[2:] if not k.startswith('--')]

# Read file
with open(filename, 'rb') as f:
    raw = f.read()

content = raw.decode('utf-8', errors='replace')

# Detect JSON (GitHub Content API)
if content.strip().startswith('{'):
    try:
        data = json.loads(content)
        if 'content' in data:
            content = base64.b64decode(data['content']).decode('utf-8')
        elif 'download_url' in data:
            import urllib.request
            content = urllib.request.urlopen(data['download_url']).read().decode('utf-8')
    except:
        pass

# === Strategy selection based on mode ===

if is_address_mode or 'Definition' in content[:500] and 'Peng' in content[:500]:
    # Mode: Address/grammar page table (| Def | IPA | Peng'im | Char |)
    entries = []
    lines = content.split('\n')
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.count('|') >= 4:
            if re.match(r'^[\|\-\s:]+$', stripped):
                continue  # separator line
            cols = [c.strip() for c in stripped.split('|')]
            cols = [c for c in cols if c]  # remove empty from leading/trailing
            if len(cols) >= 4:
                definition = cols[0].strip('" ')
                pengim = cols[2].strip()
                characters = cols[3].strip()
                # Remove tone sandhi annotations like tai3(2)tai3 -> tai3tai3
                pengim_clean = re.sub(r'\([^)]*\)', '', pengim).strip()
                if characters and pengim_clean and re.search(r'[\u4e00-\u9fff\U00020000-\U0002a6df\u3400-\u4dbf]', characters):
                    if not keywords or any(kw in characters for kw in keywords):
                        entries.append((characters, definition, pengim_clean))

    for chars, defn, pengim in entries:
        print(f"{chars}\t{pengim}\t{defn}")
    sys.exit(0)

# === Wiktionary mode: extract [汉字](url) | peng'im pairs ===

seen_chars = set()
entries = []

# Strategy 1: [汉字](url) | peng'im | IPA (standard wiktionary format)
for m in re.finditer(r'\[([^\]]+)\]\([^\)]+\)\s*\|\s*([a-zA-Z0-9]+)\s*\|', content):
    char = m.group(1).strip()
    pengim = m.group(2).strip()
    if char not in seen_chars and len(char) <= 4:
        clean_char = re.sub(r'[^\u4e00-\u9fff\U00020000-\U0002a6df\u3400-\u4dbf]', '', char)
        if clean_char and clean_char not in seen_chars:
            seen_chars.add(clean_char)
            entries.append((clean_char, pengim))

# Strategy 2: || [汉字](url) | peng'im | IPA (two-row format)
for m in re.finditer(r'\|\s*\|\s*\[([^\]]+)\]\([^\)]+\)\s*\|\s*([a-zA-Z0-9]+)\s*\|', content):
    char = m.group(1).strip()
    pengim = m.group(2).strip()
    clean_char = re.sub(r'[^\u4e00-\u9fff\U00020000-\U0002a6df\u3400-\u4dbf]', '', char)
    if clean_char and clean_char not in seen_chars and len(clean_char) <= 4:
        seen_chars.add(clean_char)
        entries.append((clean_char, pengim))

# Filter by keywords
if keywords:
    entries = [(c, p) for c, p in entries if any(kw in c for kw in keywords)]

# Sort by character
for char, pengim in sorted(entries):
    print(f"{char}\t{pengim}")
