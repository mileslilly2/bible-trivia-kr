import re
import sys
from pathlib import Path
import json

# --- FORCE project root onto PYTHONPATH (must be before importing extractors) ---
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extractors.bible_rule_engine import extract_facts

INPUT_FILE = "data/verses.jsonl"
FACTS_OUT = "out/parsed.jsonl"
DROPS_OUT = "out/drops.jsonl"


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def load_jsonl(path: str):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Bad JSON on line {lineno}: {e}")
    return rows


def main():
    verses = load_jsonl(INPUT_FILE)
    print("TOTAL VERSES LOADED:", len(verses))

    all_facts = []
    all_drops = []

    for row in verses:
        ref = row.get("ref")
        text = row.get("text", "")

        if not ref or not text:
            continue

        norm = normalize(text)

        # NOTE: extract_facts returns (facts, drops)
        facts, drops = extract_facts(ref, text, translation="WEB")

        for fact in facts:
            fact["text"] = text
            fact["norm"] = norm
            all_facts.append(fact)

        for drop in drops:
            drop["text"] = text
            drop["norm"] = norm
            all_drops.append(drop)

    print(f"Extracted {len(all_facts)} facts")
    print(f"Dropped {len(all_drops)} candidates")

    Path(FACTS_OUT).parent.mkdir(parents=True, exist_ok=True)
    Path(DROPS_OUT).parent.mkdir(parents=True, exist_ok=True)

    with open(FACTS_OUT, "w", encoding="utf-8") as f:
        json.dump(all_facts, f, indent=2, ensure_ascii=False)

    with open(DROPS_OUT, "w", encoding="utf-8") as f:
        json.dump(all_drops, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
