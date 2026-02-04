import json
import re
from pathlib import Path

# Matches: Genesis 1:1 In the beginning...
VERSE_RE = re.compile(
    r"""
    ^(?P<book>[1-3]?\s?[A-Za-z]+)?   # Optional book (some files repeat it)
    \s*
    (?P<chapter>\d+)
    :
    (?P<verse>\d+)
    \s+
    (?P<text>.+)
    $
    """,
    re.VERBOSE,
)

# Matches: Book 01 Genesis
BOOK_RE = re.compile(
    r"^Book\s+\d+\s+(?P<book>.+)$",
    re.IGNORECASE,
)

def normalize_web(input_path: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    bible_out = output_dir / "bible.web.jsonl"
    per_book = {}

    current_book = None
    total = 0

    with input_path.open("r", encoding="utf-8") as f_in, bible_out.open(
        "w", encoding="utf-8"
    ) as f_all:

        for line_no, raw in enumerate(f_in, start=1):
            line = raw.strip()
            if not line:
                continue

            # Handle "Book XX Genesis"
            m_book = BOOK_RE.match(line)
            if m_book:
                current_book = m_book.group("book").strip()
                continue

            # Try verse line
            m = VERSE_RE.match(line)
            if not m:
                # Skip non-verse metadata safely
                continue

            book = m.group("book")
            if book:
                book = book.strip()
                current_book = book
            elif not current_book:
                raise ValueError(
                    f"Verse before book context at line {line_no}:\n{line}"
                )

            chapter = int(m.group("chapter"))
            verse = int(m.group("verse"))
            text = m.group("text").strip()

            ref = f"{current_book} {chapter}:{verse}"

            record = {
                "book": current_book,
                "chapter": chapter,
                "verse": verse,
                "ref": ref,
                "text": text,
            }

            f_all.write(json.dumps(record, ensure_ascii=False) + "\n")
            per_book.setdefault(current_book, []).append(record)
            total += 1

    # Write per-book files
    for book, verses in per_book.items():
        safe_book = book.replace(" ", "_")
        out_path = output_dir / f"{safe_book}.jsonl"
        with out_path.open("w", encoding="utf-8") as f:
            for rec in verses:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"✔ Normalized {total} verses")
    print(f"✔ Wrote full Bible: {bible_out}")
    print(f"✔ Wrote {len(per_book)} book files")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Normalize WEB Bible text")
    parser.add_argument("--in", dest="inp", required=True)
    parser.add_argument("--out", dest="out", default="data/bible/web")

    args = parser.parse_args()
    normalize_web(Path(args.inp), Path(args.out))
