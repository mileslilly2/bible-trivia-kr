from typing import List, Tuple, Dict, Any, Optional
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
    # articles
    "the", "a", "an",
}


def clean_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None

    s = s.strip()
    s = s.strip(" \t\n\r\"'“”‘’[](){}.,;:!?")

    if not s:
        return None

    s = re.sub(r"\s+", " ", s)
    tokens = s.split()
    if not tokens:
        return None

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


def _fact(type_: str, ref: str, **fields) -> Dict[str, Any]:
    return {
        "type": type_,
        "ref": ref,
        **fields,
    }


# -----------------------------
# Patterns (WEB)
# -----------------------------

# Genealogy
RE_GAVE_BIRTH = re.compile(
    rf"\b(?P<parent>{NAME})\s+gave\s+birth\s+to\s+(?P<child>{NAME})\b"
)

RE_BECAME_FATHER = re.compile(
    rf"\b(?P<parent>{NAME})\s+became\s+the\s+father\s+of\s+(?P<child>{NAME})\b"
)

# Rename
RE_NAMED = re.compile(
    rf"\bnamed\s+(?:him|her|them)\s+(?P<name>{NAME_TOKEN})\b"
)

# Speech
RE_SAID_TO = re.compile(
    rf"\b(?P<speaker>{NAME})\s+(?:said|spoke)\s+to\s+(?P<listener>{NAME})\b"
)

# Violence
RE_KILLED = re.compile(
    rf"\b(?P<killer>{NAME})\s+killed\s+(?P<victim>{NAME})\b"
)

# Travel
RE_WENT_TO = re.compile(
    rf"\b(?P<traveler>{NAME})\s+went\s+to\s+(?P<destination>{NAME})\b"
)

RE_TRAVELED_FROM_TO = re.compile(
    rf"\b(?P<traveler>{NAME})\s+traveled\s+from\s+(?P<source>{NAME})\s+to\s+(?P<destination>{NAME})\b"
)

RE_JOURNEYED_TO = re.compile(
    rf"\b(?P<traveler>{NAME})\s+journeyed\s+to\s+(?P<destination>{NAME})\b"
)

# Roles
RE_WAS_KING = re.compile(
    rf"\b(?P<person>{NAME})\s+was\s+king\b"
)

RE_WAS_PROPHET = re.compile(
    rf"\b(?P<person>{NAME})\s+was\s+(?:a\s+)?prophet\b"
)

RE_WAS_PRIEST = re.compile(
    rf"\b(?P<person>{NAME})\s+was\s+(?:a\s+)?priest\b"
)

RE_REIGNED_OVER = re.compile(
    rf"\b(?P<person>{NAME})\s+reigned\s+over\s+(?P<realm>{NAME})\b"
)


def extract_genealogy(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_GAVE_BIRTH.finditer(text_n):
        parent = clean_name(m.group("parent"))
        child = clean_name(m.group("child"))
        if parent and child:
            facts.append(_fact(
                "parent_of",
                ref,
                parent=parent,
                child=child,
                parent_gender="female",
                source_pattern="gave_birth_to",
            ))
        else:
            drops.append(_drop(ref, "web_parent_of_gave_birth_invalid", text_n, extracted=m.groupdict()))

    for m in RE_BECAME_FATHER.finditer(text_n):
        parent = clean_name(m.group("parent"))
        child = clean_name(m.group("child"))
        if parent and child:
            facts.append(_fact(
                "parent_of",
                ref,
                parent=parent,
                child=child,
                parent_gender="male",
                source_pattern="became_father_of",
            ))
        else:
            drops.append(_drop(ref, "web_parent_of_became_father_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_rename(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_NAMED.finditer(text_n):
        name = clean_name(m.group("name"))
        if name:
            facts.append(_fact(
                "rename",
                ref,
                name=name,
                source_pattern="named_him_her_them",
            ))
        else:
            drops.append(_drop(ref, "web_rename_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_speech(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_SAID_TO.finditer(text_n):
        speaker = clean_name(m.group("speaker"))
        listener = clean_name(m.group("listener"))
        if speaker and listener:
            facts.append(_fact(
                "spoke_to",
                ref,
                speaker=speaker,
                listener=listener,
                source_pattern="said_or_spoke_to",
            ))
        else:
            drops.append(_drop(ref, "web_spoke_to_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_killing(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_KILLED.finditer(text_n):
        killer = clean_name(m.group("killer"))
        victim = clean_name(m.group("victim"))
        if killer and victim:
            facts.append(_fact(
                "killed",
                ref,
                killer=killer,
                victim=victim,
                source_pattern="killed",
            ))
        else:
            drops.append(_drop(ref, "web_killed_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_travel(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_TRAVELED_FROM_TO.finditer(text_n):
        traveler = clean_name(m.group("traveler"))
        source = clean_name(m.group("source"))
        destination = clean_name(m.group("destination"))
        if traveler and source and destination:
            facts.append(_fact(
                "traveled",
                ref,
                traveler=traveler,
                source=source,
                destination=destination,
                source_pattern="traveled_from_to",
            ))
        else:
            drops.append(_drop(ref, "web_traveled_from_to_invalid", text_n, extracted=m.groupdict()))

    for m in RE_WENT_TO.finditer(text_n):
        traveler = clean_name(m.group("traveler"))
        destination = clean_name(m.group("destination"))
        if traveler and destination:
            facts.append(_fact(
                "traveled",
                ref,
                traveler=traveler,
                source=None,
                destination=destination,
                source_pattern="went_to",
            ))
        else:
            drops.append(_drop(ref, "web_went_to_invalid", text_n, extracted=m.groupdict()))

    for m in RE_JOURNEYED_TO.finditer(text_n):
        traveler = clean_name(m.group("traveler"))
        destination = clean_name(m.group("destination"))
        if traveler and destination:
            facts.append(_fact(
                "traveled",
                ref,
                traveler=traveler,
                source=None,
                destination=destination,
                source_pattern="journeyed_to",
            ))
        else:
            drops.append(_drop(ref, "web_journeyed_to_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def extract_roles(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for pattern, role_name, rule_name in [
        (RE_WAS_KING, "king", "web_role_king_invalid"),
        (RE_WAS_PROPHET, "prophet", "web_role_prophet_invalid"),
        (RE_WAS_PRIEST, "priest", "web_role_priest_invalid"),
    ]:
        for m in pattern.finditer(text_n):
            person = clean_name(m.group("person"))
            if person:
                facts.append(_fact(
                    "role",
                    ref,
                    person=person,
                    role=role_name,
                    source_pattern=f"was_{role_name}",
                ))
            else:
                drops.append(_drop(ref, rule_name, text_n, extracted=m.groupdict()))

    for m in RE_REIGNED_OVER.finditer(text_n):
        person = clean_name(m.group("person"))
        realm = clean_name(m.group("realm"))
        if person:
            facts.append(_fact(
                "role",
                ref,
                person=person,
                role="king",
                realm=realm,
                source_pattern="reigned_over",
            ))
        else:
            drops.append(_drop(ref, "web_role_reigned_over_invalid", text_n, extracted=m.groupdict()))

    return facts, drops


def get_extractors():
    return [
        extract_genealogy,
        extract_rename,
        extract_speech,
        extract_killing,
        extract_travel,
        extract_roles,
    ]