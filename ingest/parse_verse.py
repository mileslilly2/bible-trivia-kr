import re
from typing import List, Dict


# -----------------------------
# Regex patterns
# -----------------------------

BOOK_RE = re.compile(r'^Book\s+\d+\s+(?P<book>.+)$')
VERSE_START_RE = re.compile(
    r'^(?P<chapter>\d{3}):(?P<verse>\d{3})\s+(?P<text>.+)$'
)

# Inline editorial notes: { ... }
NOTE_RE = re.compile(r'\{.*?\}', re.DOTALL)


# -----------------------------
# Core parser
# -----------------------------

def parse_txt_bible(path: str) -> List[Dict[str, str]]:
    """
    Parse a fixed-width Bible TXT file with:
      - Book headers (e.g. 'Book 01 Genesis')
      - Verse starts like '001:001 ...'
      - Wrapped continuation lines
      - Inline editorial notes in { ... }

    Returns:
      List of dicts: { "ref": "Genesis 1:1", "text": "..." }
    """

    verses: List[Dict[str, str]] = []

    current_book = None
    current_ref = None
    current_text_parts: List[str] = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for lineno, raw_line in enumerate(f, start=1):
            line = raw_line.rstrip()

            # Skip empty lines
            if not line.strip():
                continue

            # -----------------------------
            # Book header
            # -----------------------------
            m = BOOK_RE.match(line)
            if m:
                current_book = m.group("book")
                continue

            # -----------------------------
            # Verse start
            # -----------------------------
            m = VERSE_START_RE.match(line)
            if m:
                # Flush previous verse
                if current_ref and current_text_parts:
                    text = " ".join(current_text_parts)
                    text = NOTE_RE.sub("", text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    verses.append({
                        "ref": current_ref,
                        "text": text
                    })

                chapter = int(m.group("chapter"))
                verse = int(m.group("verse"))

                if not current_book:
                    # Should not happen, but be defensive
                    current_book = "UNKNOWN"

                current_ref = f"{current_book} {chapter}:{verse}"
                current_text_parts = [m.group("text").strip()]
                continue

            # -----------------------------
            # Continuation line (indented)
            # -----------------------------
            if current_ref and line.startswith(" "):
                current_text_parts.append(line.strip())
                continue

            # -----------------------------
            # Anything else is ignored
            # -----------------------------
            # This includes stray headers, page numbers, etc.
            continue

        # Flush last verse
        if current_ref and current_text_parts:
            text = " ".join(current_text_parts)
            text = NOTE_RE.sub("", text)
            text = re.sub(r'\s+', ' ', text).strip()
            verses.append({
                "ref": current_ref,
                "text": text
            })

    return verses


# -----------------------------
# CLI helper (optional)
# -----------------------------

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 3:
        print("Usage: python parse_verse.py <input_txt> <output_jsonl>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    verses = parse_txt_bible(input_path)

    with open(output_path, "w", encoding="utf-8") as out:
        for v in verses:
            out.write(json.dumps(v, ensure_ascii=False) + "\n")

    print(f"Wrote {len(verses)} verses to {output_path}")
