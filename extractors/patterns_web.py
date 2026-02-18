from typing import List, Tuple, Dict, Any
import re


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


# ---- Name handling (WEB) ----
# Token like "Tubal-cain"
NAME_TOKEN = r"[A-Z][a-z]+(?:-[A-Za-z]+)?"
# 1–3 tokens like "Merib Baal", "Beth Rapha"
NAME = rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,2}}"


_BAD_NAME_TOKENS = {
    # pronouns / determiners
    "he", "she", "they", "it", "his", "her", "their", "him", "them",
    "this", "that", "these", "those", "who", "whom", "which", "what",
    # sentence-initial discourse junk that often capitalizes
    "and", "but", "for", "so", "then", "there", "now", "after", "before",
    "because", "therefore", "thus", "also",
    # articles (won’t match NAME_TOKEN usually, but safe)
    "the", "a", "an",
}


def clean_name(s: str) -> str | None:
    if not s:
        return None

    s = s.strip()

    # trim surrounding punctuation
    s = s.strip(" \t\n\r\"'“”‘’[](){}.,;:!?")

    if not s:
        return None

    # collapse spaces
    s = re.sub(r"\s+", " ", s)

    tokens = s.split()
    if not tokens:
        return None

    # reject if any token is junk/pronoun/etc.
    for tok in tokens:
        if tok.lower() in _BAD_NAME_TOKENS:
            return None

    return s


def _drop(ref: str, rule: str, text: str, **details) -> Dict[str, Any]:
    return {
        "ref": ref,
        "rule": rule,
        "details": {"text": text, **details},
    }


# ---- Patterns (WEB) ----
RE_GAVE_BIRTH = re.compile(
    rf"\b(?P<mother>{NAME})\s+gave\s+birth\s+to\s+(?P<child>{NAME})\b"
)

RE_BECAME_FATHER = re.compile(
    rf"\b(?P<father>{NAME})\s+became\s+the\s+father\s+of\s+(?P<child>{NAME})\b"
)

RE_NAMED = re.compile(
    rf"\bnamed\s+(?:him|her|them)\s+(?P<name>{NAME_TOKEN})\b"
)


def extract_genealogy(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    # "Adah gave birth to Jabal"
    for m in RE_GAVE_BIRTH.finditer(text_n):
        mother = clean_name(m.group("mother"))
        child = clean_name(m.group("child"))
        if mother and child:
            facts.append({
                "type": "genealogy",
                "ref": ref,
                "mother": mother,
                "child": child,
            })
        else:
            drops.append(_drop(ref, "web_genealogy_gave_birth_invalid", text_n, extracted=m.groupdict()))

    # "Cush became the father of Nimrod"
    for m in RE_BECAME_FATHER.finditer(text_n):
        father = clean_name(m.group("father"))
        child = clean_name(m.group("child"))
        if father and child:
            facts.append({
                "type": "genealogy",
                "ref": ref,
                "father": father,
                "child": child,
            })
        else:
            drops.append(_drop(ref, "web_genealogy_became_father_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_rename(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    # multiple "named him X" can occur in one verse (Benoni / Benjamin)
    for m in RE_NAMED.finditer(text_n):
        name = clean_name(m.group("name"))
        if name:
            facts.append({
                "type": "rename",
                "ref": ref,
                "name": name,
            })
        else:
            drops.append(_drop(ref, "web_rename_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_violence(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    return [], []  # add WEB-specific later if needed


def get_extractors():
    return [
        extract_genealogy,
        extract_rename,
        extract_violence,
    ]
