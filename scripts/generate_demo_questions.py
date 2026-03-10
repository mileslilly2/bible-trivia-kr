# scripts/generate_demo_questions.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


import argparse
import json
from pathlib import Path

from extractors.question_engine import load_json_or_jsonl, generate_questions


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a small demo set of MC trivia questions from parsed facts.")
    ap.add_argument("--input", default="out/parsed.jsonl", help="Facts file (JSON array or JSONL).")
    ap.add_argument("--output", default="out/demo_questions.json", help="Output JSON file.")
    ap.add_argument("--n", type=int, default=30, help="Number of questions to generate.")
    ap.add_argument("--seed", type=int, default=1337, help="Random seed.")
    args = ap.parse_args()

    facts = load_json_or_jsonl(args.input)
    questions = generate_questions(facts, n=args.n, seed=args.seed)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(questions, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Loaded facts: {len(facts)}")
    print(f"Wrote questions: {len(questions)} -> {out_path}")

    # Quick peek
    for q in questions[:5]:
        print("\n---")
        print(q["prompt"])
        for i, c in enumerate(q["choices"]):
            mark = "✅" if i == q["answer_index"] else "  "
            print(f"{mark} {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
