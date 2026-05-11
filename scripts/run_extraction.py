import re
import sys
from pathlib import Path
import json
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extractors.bible_rule_engine import extract_facts

DEFAULT_INPUT_FILE = "data/verses.jsonl"
DEFAULT_FACTS_OUT = "out/parsed.jsonl"
DEFAULT_DROPS_OUT = "out/drops.jsonl"


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=DEFAULT_INPUT_FILE)
    ap.add_argument("--facts-out", dest="facts_out", default=DEFAULT_FACTS_OUT)
    ap.add_argument("--drops-out", dest="drops_out", default=DEFAULT_DROPS_OUT)
    ap.add_argument("--translation", dest="translation", default="WEB", choices=["WEB", "KJV"])
    args = ap.parse_args()

    verses = load_jsonl(args.inp)
    print("TOTAL VERSES LOADED:", len(verses))

    all_facts = []
    all_drops = []

    for row in verses:
        ref = row.get("ref")
        text = row.get("text", "")

        if not ref or not text:
            continue

        norm = normalize(text)
        facts, drops = extract_facts(ref, text, translation=args.translation)

        for fact in facts:
            fact["text"] = text
            fact["norm"] = norm
            fact["translation"] = args.translation
            all_facts.append(fact)

        for drop in drops:
            drop["text"] = text
            drop["norm"] = norm
            drop["translation"] = args.translation
            all_drops.append(drop)

    print(f"Extracted {len(all_facts)} facts")
    print(f"Dropped {len(all_drops)} candidates")

    Path(args.facts_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.drops_out).parent.mkdir(parents=True, exist_ok=True)

    with open(args.facts_out, "w", encoding="utf-8") as f:
        json.dump(all_facts, f, indent=2, ensure_ascii=False)

    with open(args.drops_out, "w", encoding="utf-8") as f:
        json.dump(all_drops, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()