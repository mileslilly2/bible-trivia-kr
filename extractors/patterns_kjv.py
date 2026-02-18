from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple, Optional
import re


# -----------------------------
# Data models (same shape)
# -----------------------------

@dataclass(frozen=True)
class Fact:
    type: str
    ref: str
    fields: Dict[str, Any]

    def to_dict(self):
        d = {"type": self.type, "ref": self.ref}
        d.update(self.fields)
        return d


@dataclass(frozen=True)
class Drop:
    ref: str
    rule: str
    text: str
    details: Dict[str, Any]


# -----------------------------
# Helpers
# -----------------------------

def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def clean_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    if s.lower() in {"and", "then", "after", "when", "that"}:
        return None
    return s


def add_drop(drops, ref, rule, text, **details):
    drops.append(asdict(Drop(ref, rule, text, details)))


# -----------------------------
# Genealogy (KJV syntax)
# -----------------------------

NAME = r"[A-Z][a-z]+(?:-[A-Za-z]+)?"

RE_BEGAT = re.compile(
    rf"\b(?P<father>{NAME})\s+begat\s+(?P<child>{NAME})\b"
)

RE_BORE = re.compile(
    rf"\b(?P<mother>{NAME})\s+(?:also\s+)?(?:bare|bore)\s+(?P<child>{NAME})(?:\b|[,;.])"
)


def extract_genealogy(ref: str, text: str):
    text = normalize(text)
    facts, drops = [], []

    m = RE_BEGAT.search(text)
    if m:
        facts.append({
            "type": "genealogy",
            "ref": ref,
            "father": clean_name(m.group("father")),
            "child": clean_name(m.group("child")),
        })

    m = RE_BORE.search(text)
    if m:
        facts.append({
            "type": "genealogy",
            "ref": ref,
            "mother": clean_name(m.group("mother")),
            "child": clean_name(m.group("child")),
        })

    return facts, drops


# -----------------------------
# Rename (KJV)
# -----------------------------

RE_CALLED_NAME = re.compile(
    r"\bcalled\s+(?:his|her|their)(?:\s+[A-Za-z']+)?\s+name\s+(?P<name>[A-Z][a-z]+)\b"
)


def extract_rename(ref: str, text: str):
    text = normalize(text)
    facts, drops = [], []

    m = RE_CALLED_NAME.search(text)
    if m:
        facts.append({
            "type": "rename",
            "ref": ref,
            "name": clean_name(m.group("name")),
        })

    return facts, drops


# -----------------------------
# Violence (KJV)
# -----------------------------

RE_KILLED = re.compile(
    r"\b(?P<who>[A-Z][a-z]+)\s+(?:slew|killed)\s+(?P<target>[A-Z][a-z]+)\b"
)


def extract_violence(ref: str, text: str):
    text = normalize(text)
    facts, drops = [], []

    m = RE_KILLED.search(text)
    if m:
        facts.append({
            "type": "violence",
            "ref": ref,
            "who": clean_name(m.group("who")),
            "target": clean_name(m.group("target")),
        })

    return facts, drops


# -----------------------------
# Registry
# -----------------------------

def get_extractors():
    return [
        extract_genealogy,
        extract_rename,
        extract_violence,
    ]
