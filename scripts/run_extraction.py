import sys
from pathlib import Path
import json
import re

verses = []

# --- FORCE project root onto PYTHONPATH ---
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


import json
from extractors.bible_rule_engine import extract_facts

# Example input format:
# [
#   {"ref": "Genesis 4:22", "text": "And Zillah also bare Tubal-cain..."},
#   ...
# ]

INPUT_FILE = "data/verses.jsonl"
FACTS_OUT = "out/parsed.jsonl"
DROPS_OUT = "out/drops.jsonl"


all_facts = []
all_drops = []

import json
import re

verses = []

buffer = ""
brace_depth = 0

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for lineno, raw_line in enumerate(f, start=1):
        line = raw_line.strip()
        if not line:
            continue

        # strip inline editorial notes { ... }
        line = re.sub(r"\{[^}]*\}", "", line)

        # accumulate
        buffer += line

        # track braces
        brace_depth += line.count("{")
        brace_depth -= line.count("}")

        # when braces balance, we have a full JSON object
        if brace_depth == 0 and buffer:
            try:
                verses.append(json.loads(buffer))
            except json.JSONDecodeError as e:
                print(f"[WARN] Dropping malformed JSON ending on line {lineno}: {e}")
            buffer = ""

# optional: warn if file ended mid-object
if buffer.strip():
    print("[WARN] File ended with incomplete JSON object")



for row in verses:
    ref = row["ref"]
    text = row["text"]

    facts, drops = extract_facts(ref, text)

    all_facts.extend(facts)
    all_drops.extend(drops)

print(f"Extracted {len(all_facts)} facts")
print(f"Dropped {len(all_drops)} candidates")

with open(FACTS_OUT, "w", encoding="utf-8") as f:
    json.dump(all_facts, f, indent=2)

with open(DROPS_OUT, "w", encoding="utf-8") as f:
    json.dump(all_drops, f, indent=2)
