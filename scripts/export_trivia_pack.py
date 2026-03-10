# scripts/export_trivia_pack.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from extractors.question_engine import load_json_or_jsonl, facts_to_trivia_pack


def main() -> int:
    ap = argparse.ArgumentParser(description="Export a Trivia Royale pack JSON from parsed facts.")
    ap.add_argument("--input", default="out/parsed.jsonl", help="Facts file (JSON array or JSONL).")
    ap.add_argument("--output", default="out/trivia_pack.json", help="Output pack JSON file.")
    ap.add_argument("--pack-id", default="bible-web-v1", help="Pack id.")
    ap.add_argument("--title", default="Bible Genealogy (WEB)", help="Pack title.")
    ap.add_argument("--translation", default="WEB", help="Translation tag (WEB/KJV).")
    ap.add_argument("--limit", type=int, default=None, help="Optional max questions.")
    ap.add_argument("--seed", type=int, default=1337, help="Random seed.")
    args = ap.parse_args()

    facts = load_json_or_jsonl(args.input)
    pack = facts_to_trivia_pack(
        facts=facts,
        pack_id=args.pack_id,
        title=args.title,
        translation=args.translation,
        n=args.limit,
        seed=args.seed,
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(pack, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Loaded facts: {len(facts)}")
    print(f"Wrote pack: {pack['question_count']} questions -> {out_path}")
    print(f"Pack id: {pack['pack_id']} | title: {pack['title']} | translation: {pack['translation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
