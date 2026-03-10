# scripts/build_facts_db.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from extractors.question_engine import load_json_or_jsonl, generate_questions


SCHEMA = """
CREATE TABLE IF NOT EXISTS pack_manifest (
  pack_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  version TEXT NOT NULL,
  description TEXT,
  author TEXT,
  license TEXT,
  modes_supported TEXT,
  schema_version TEXT,
  created_at TEXT
);

CREATE TABLE IF NOT EXISTS facts (
  id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  context TEXT,
  answer_type TEXT NOT NULL,
  answer_mode TEXT NOT NULL,
  answer_values TEXT,
  answer_boolean INTEGER,
  answer_number REAL,
  explanation TEXT,
  answer_references TEXT,
  difficulty INTEGER,
  tags TEXT,
  language TEXT,
  FOREIGN KEY(pack_id) REFERENCES pack_manifest(pack_id)
);

CREATE TABLE IF NOT EXISTS items (
  id TEXT PRIMARY KEY,
  pack_id TEXT NOT NULL,
  fact_id TEXT NOT NULL,
  type TEXT NOT NULL,
  prompt TEXT NOT NULL,
  options TEXT,
  correct_index INTEGER,
  accepted TEXT,
  difficulty INTEGER,
  tags TEXT,
  mode_rules TEXT,
  FOREIGN KEY(pack_id) REFERENCES pack_manifest(pack_id),
  FOREIGN KEY(fact_id) REFERENCES facts(id)
);

CREATE TABLE IF NOT EXISTS wheels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  segments TEXT NOT NULL
);
"""


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _difficulty_to_int(s: str) -> int:
    s = (s or "").lower().strip()
    if s == "easy":
        return 1
    if s == "medium":
        return 2
    if s == "hard":
        return 3
    return 1


def _tags_from_question(q: Dict[str, Any], translation: str) -> List[str]:
    tags: List[str] = []

    # category like: "Bible • Genealogy"
    cat = (q.get("category") or "").strip()
    if cat:
        parts = [p.strip() for p in cat.split("•")]
        for p in parts:
            if p and p.lower() != "bible":
                tags.append(p.replace(" ", ""))  # "Genealogy", "Names", etc.

    # always tag translation
    tags.append(translation.upper())

    # keep any existing tags if present
    extra = q.get("meta", {}).get("tags")
    if isinstance(extra, list):
        tags.extend([str(x) for x in extra if x])

    # de-dupe preserving order
    seen = set()
    out = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _init_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA)
    return conn


def _upsert_manifest(
    conn: sqlite3.Connection,
    pack_id: str,
    title: str,
    version: str,
    description: Optional[str],
    author: Optional[str],
    license_str: str,
    modes_supported: List[str],
) -> None:
    conn.execute(
        """
        INSERT INTO pack_manifest
          (pack_id, title, version, description, author, license, modes_supported, schema_version, created_at)
        VALUES
          (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(pack_id) DO UPDATE SET
          title=excluded.title,
          version=excluded.version,
          description=excluded.description,
          author=excluded.author,
          license=excluded.license,
          modes_supported=excluded.modes_supported,
          schema_version=excluded.schema_version
        """,
        (
            pack_id,
            title,
            version,
            description,
            author,
            license_str,
            json.dumps(modes_supported, ensure_ascii=False),
            "trivia-bank/1.0",
            _now_utc_iso(),
        ),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a Trivia Royale SQLite pack DB from parsed facts.")
    ap.add_argument("--input", default="out/parsed.jsonl", help="Facts file (JSON array or JSONL).")
    ap.add_argument("--output", default="out/trivia_pack.sqlite", help="Output SQLite DB file.")
    ap.add_argument("--pack-id", default="bible-web-v1", help="Pack id.")
    ap.add_argument("--title", default="Bible Genealogy (WEB)", help="Pack title.")
    ap.add_argument("--translation", default="WEB", help="Translation tag (WEB/KJV).")
    ap.add_argument("--version", default="1.0.0", help="Pack version string.")
    ap.add_argument("--description", default=None, help="Optional description.")
    ap.add_argument("--author", default=None, help="Optional author.")
    ap.add_argument("--license", dest="license_str", default="commercial", help="License tag.")
    ap.add_argument("--limit", type=int, default=None, help="Optional max questions.")
    ap.add_argument("--seed", type=int, default=1337, help="Random seed.")
    args = ap.parse_args()

    facts = load_json_or_jsonl(args.input)
    questions = generate_questions(facts, n=args.limit, seed=args.seed)

    out_db = Path(args.output)
    conn = _init_db(out_db)

    _upsert_manifest(
        conn=conn,
        pack_id=args.pack_id,
        title=args.title,
        version=args.version,
        description=args.description,
        author=args.author,
        license_str=args.license_str,
        modes_supported=["mcq"],
    )

    # Clear any prior content for this pack_id (keeps it deterministic for rebuilds)
    conn.execute("DELETE FROM items WHERE pack_id = ?", (args.pack_id,))
    conn.execute("DELETE FROM facts WHERE pack_id = ?", (args.pack_id,))

    fact_rows = []
    item_rows = []

    for q in questions:
        qid = q["id"]
        prompt = q["prompt"]
        choices = q["choices"]
        answer_index = int(q["answer_index"])
        correct = choices[answer_index]

        # Use a distinct fact_id (your existing DB separates fact vs item)
        fact_id = f"f_{qid}"

        difficulty = _difficulty_to_int(q.get("difficulty") or "easy")
        tags = _tags_from_question(q, args.translation)
        explanation = q.get("explanation") or ""

        # facts row (canonical truth)
        fact_rows.append(
            (
                fact_id,
                args.pack_id,
                prompt,
                None,                 # context (optional)
                "text",               # answer_type
                "single",             # answer_mode
                json.dumps([correct], ensure_ascii=False),
                None,                 # answer_boolean
                None,                 # answer_number
                explanation,
                json.dumps([q.get("ref", "")], ensure_ascii=False),
                difficulty,
                json.dumps(tags, ensure_ascii=False),
                "en",
            )
        )

        # items row (the MCQ rendering of that fact)
        item_rows.append(
            (
                qid,
                args.pack_id,
                fact_id,
                "mcq",
                prompt,
                json.dumps(choices, ensure_ascii=False),
                answer_index,
                None,                 # accepted (for short_answer)
                difficulty,
                json.dumps(tags, ensure_ascii=False),
                None,                 # mode_rules
            )
        )

    conn.executemany(
        """
        INSERT INTO facts
          (id, pack_id, prompt, context, answer_type, answer_mode, answer_values,
           answer_boolean, answer_number, explanation, answer_references, difficulty, tags, language)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        fact_rows,
    )

    conn.executemany(
        """
        INSERT INTO items
          (id, pack_id, fact_id, type, prompt, options, correct_index, accepted, difficulty, tags, mode_rules)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        item_rows,
    )

    conn.commit()
    conn.close()

    print(f"Loaded facts: {len(facts)}")
    print(f"Generated questions: {len(questions)}")
    print(f"Wrote SQLite pack -> {out_db}")
    print(f"Pack id: {args.pack_id} | title: {args.title} | translation: {args.translation.upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())