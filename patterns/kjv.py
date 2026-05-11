# ingest/patterns/kjv.py
import re

GENEALOGY_PATTERNS = [
    re.compile(
        r"\b(?P<father>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+begat\s+(?P<child>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
    re.compile(
        r"\b(?P<mother>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+bare\s+(?P<child>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
]

VIOLENCE_PATTERNS = [
    re.compile(
        r"\b(?P<who>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+slew\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
    re.compile(
        r"\b(?P<who>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+smote\s+(?P<target>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    ),
]
