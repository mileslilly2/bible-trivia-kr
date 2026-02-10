# ingest/patterns/web.py
import re

GENEALOGY_PATTERNS = [
    re.compile(
        r"\b(?P<father>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+became\s+the\s+father\s+of\s+(?P<child>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
    re.compile(
        r"\b(?P<mother>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+gave\s+birth\s+to\s+(?P<child>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
]

VIOLENCE_PATTERNS = [
    re.compile(
        r"\b(?P<who>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+killed\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
    re.compile(
        r"\b(?P<who>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+put\s+to\s+death\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
]
