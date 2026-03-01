"""
checkchunks.py – Search chunks_improved.json for keywords.
Run:  python utils/checkchunks.py
"""

import json

CHUNKS_FILE = "./data/chunks_improved.json"

with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

keywords = ["unemployment allowance", "section 7", "compensation", "wage delay", "0.05%"]

for kw in keywords:
    print(f"\n🔍 Searching for: '{kw}'")
    found = False
    for i, chunk in enumerate(chunks):
        if kw.lower() in chunk.lower():
            found = True
            print(f"  ✅ Chunk {i}: {chunk[:300]}…")
    if not found:
        print(f"  ❌ Not found.")
