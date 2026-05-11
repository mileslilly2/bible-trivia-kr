from typing import List, Tuple, Dict, Any, Optional
import re


def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


# ---- Name handling (WEB) ----
NAME_TOKEN = r"[A-Z][a-z]+(?:-[A-Za-z]+)?"
NAME = rf"{NAME_TOKEN}(?:\s+{NAME_TOKEN}){{0,2}}"
NAME_LIST = rf"{NAME}(?:,\s*{NAME})*(?:\s*,?\s+and\s+{NAME})?"

_BAD_NAME_TOKENS = {
    "he", "she", "they", "it", "his", "her", "their", "him", "them",
    "this", "that", "these", "those", "who", "whom", "which", "what",
    "and", "but", "for", "so", "then", "there", "now", "after", "before",
    "because", "therefore", "thus", "also",
    "the", "a", "an",
}

KNOWN_PLACES = {
    "Egypt", "Gerar", "Canaan", "Jerusalem", "Bethel", "Hebron", "Shechem",
    "Moab", "Jordan", "Bethlehem", "Nazareth", "Samaria", "Jericho",
    "Damascus", "Gaza", "Sinai", "Haran", "Ur", "Beersheba", "Edom",
    "Philistia", "Judea", "Galilee", "Babylon", "Assyria", "Israel", "Judah",
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


def normalize_person_name(s: Optional[str]) -> Optional[str]:
    s = clean_name(s)
    if not s:
        return None

    # Strip leading titles
    s = re.sub(r"^(King|Prophet|Priest)\s+", "", s).strip()

    # Strip trailing descriptive ethnics / appositives if present
    s = re.sub(r"\s+the\s+[A-Z][a-z]+(?:ite|ian|athite|ite)$", "", s).strip()

    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None


def normalize_place_name(s: Optional[str]) -> Optional[str]:
    s = clean_name(s)
    if not s:
        return None
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    return s or None


def is_known_place(s: Optional[str]) -> bool:
    if not s:
        return False
    return s in KNOWN_PLACES


def split_name_list(chunk: Optional[str]) -> List[str]:
    if not chunk:
        return []
    parts = re.split(r",\s*|\s+and\s+", chunk)
    out: List[str] = []
    for p in parts:
        c = clean_name(p)
        if c:
            out.append(c)
    return out


def _guess_divine_entity(text_n: str) -> Optional[str]:
    if "angel of Yahweh" in text_n:
        return "angel of Yahweh"
    if "angel of God" in text_n:
        return "angel of God"
    if "Yahweh" in text_n:
        return "Yahweh"
    if "God" in text_n:
        return "God"
    return None


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
    rf"\b(?P<parent>{NAME})\s+became\s+the\s+father\s+of\s+(?P<children>{NAME_LIST})\b"
)

# Rename
RE_NAMED = re.compile(
    rf"\bnamed\s+(?:him|her|them)\s+(?P<name>{NAME_TOKEN})\b"
)

# Speech
RE_SAID_TO = re.compile(
    rf"\b(?P<speaker>{NAME})\s+(?:said|spoke)\s+to\s+(?P<listener>{NAME})\b"
)

RE_SAID_TO_TWO = re.compile(
    rf"\b(?P<speaker>{NAME})\s+(?:said|spoke)\s+to\s+(?P<listener1>{NAME})\s+and\s+to\s+(?P<listener2>{NAME})\b"
)

# Violence
RE_KILLED = re.compile(
    rf"\b(?P<killer>{NAME})\s+killed\s+(?P<victims>{NAME_LIST})\b"
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

RE_WAS_KING_SON_OF = re.compile(
    rf"\b(?P<person>{NAME})\s+the\s+son\s+of\s+{NAME}\s+was\s+king(?:\s+of|\s+over)?\s+(?P<realm>{NAME})\b"
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

RE_BEGAN_TO_REIGN_OVER = re.compile(
    rf"\b(?P<person>{NAME})(?:\s+the\s+son\s+of\s+{NAME})?\s+began\s+to\s+reign\s+over\s+(?P<realm>{NAME})\b"
)

# Appearance / manifestation
RE_APPEARED_TO = re.compile(
    rf"\b(?P<entity>{NAME})\s+appeared\s+to\s+(?P<recipient>{NAME})\b"
)

RE_OUT_OF_THE_WHIRLWIND = re.compile(
    r"\bout of the (?P<form>whirlwind)\b",
    re.IGNORECASE,
)

RE_IN_A_FLAME_OF_FIRE = re.compile(
    r"\bin a flame of fire\b",
    re.IGNORECASE,
)

RE_PILLAR_FORM = re.compile(
    r"\b(?P<form>pillar of fire|pillar of cloud)\b",
    re.IGNORECASE,
)

RE_BURNING_BUSH = re.compile(
    r"\b(?P<form>burning bush)\b",
    re.IGNORECASE,
)


def extract_genealogy(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_GAVE_BIRTH.finditer(text_n):
        parent = normalize_person_name(m.group("parent"))
        child = normalize_person_name(m.group("child"))
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
        parent = normalize_person_name(m.group("parent"))
        children = [normalize_person_name(x) for x in split_name_list(m.group("children"))]
        children = [x for x in children if x]
        if parent and children:
            for child in children:
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

    for m in RE_SAID_TO_TWO.finditer(text_n):
        speaker = normalize_person_name(m.group("speaker"))
        l1 = normalize_person_name(m.group("listener1"))
        l2 = normalize_person_name(m.group("listener2"))
        if speaker and l1 and l2:
            facts.append(_fact(
                "spoke_to",
                ref,
                speaker=speaker,
                listener=l1,
                source_pattern="said_or_spoke_to_two",
            ))
            facts.append(_fact(
                "spoke_to",
                ref,
                speaker=speaker,
                listener=l2,
                source_pattern="said_or_spoke_to_two",
            ))
        else:
            drops.append(_drop(ref, "web_spoke_to_two_invalid", text_n, extracted=m.groupdict()))

    for m in RE_SAID_TO.finditer(text_n):
        speaker = normalize_person_name(m.group("speaker"))
        listener = normalize_person_name(m.group("listener"))
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
        killer = normalize_person_name(m.group("killer"))
        victims = [normalize_person_name(x) for x in split_name_list(m.group("victims"))]
        victims = [x for x in victims if x]
        if killer and victims:
            for victim in victims:
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
        traveler = normalize_person_name(m.group("traveler"))
        source = normalize_place_name(m.group("source"))
        destination = normalize_place_name(m.group("destination"))
        if traveler and source and destination and is_known_place(source) and is_known_place(destination):
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
        traveler = normalize_person_name(m.group("traveler"))
        destination = normalize_place_name(m.group("destination"))
        if traveler and destination and is_known_place(destination):
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
        traveler = normalize_person_name(m.group("traveler"))
        destination = normalize_place_name(m.group("destination"))
        if traveler and destination and is_known_place(destination):
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
            person = normalize_person_name(m.group("person"))
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

    for m in RE_WAS_KING_SON_OF.finditer(text_n):
        person = normalize_person_name(m.group("person"))
        realm = normalize_place_name(m.group("realm"))
        if person:
            facts.append(_fact(
                "role",
                ref,
                person=person,
                role="king",
                realm=realm,
                source_pattern="was_king_son_of",
            ))
        else:
            drops.append(_drop(ref, "web_role_was_king_son_of_invalid", text_n, extracted=m.groupdict()))

    for m in RE_BEGAN_TO_REIGN_OVER.finditer(text_n):
        person = normalize_person_name(m.group("person"))
        realm = normalize_place_name(m.group("realm"))
        if person:
            facts.append(_fact(
                "role",
                ref,
                person=person,
                role="king",
                realm=realm,
                source_pattern="began_to_reign_over",
            ))
        else:
            drops.append(_drop(ref, "web_role_began_to_reign_invalid", text_n, extracted=m.groupdict()))

    for m in RE_REIGNED_OVER.finditer(text_n):
        person = normalize_person_name(m.group("person"))
        realm = normalize_place_name(m.group("realm"))
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


def extract_appearance(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    text_n = normalize(text)
    facts: List[Dict[str, Any]] = []
    drops: List[Dict[str, Any]] = []

    for m in RE_APPEARED_TO.finditer(text_n):
        entity = normalize_person_name(m.group("entity")) or _guess_divine_entity(text_n)
        recipient = normalize_person_name(m.group("recipient"))
        if entity and recipient:
            facts.append(_fact(
                "appeared_to",
                ref,
                entity=entity,
                recipient=recipient,
                source_pattern="appeared_to",
            ))
        else:
            drops.append(_drop(ref, "web_appeared_to_invalid", text_n, extracted=m.groupdict()))

    guessed_entity = _guess_divine_entity(text_n)

    for m in RE_OUT_OF_THE_WHIRLWIND.finditer(text_n):
        if guessed_entity:
            facts.append(_fact(
                "manifestation",
                ref,
                entity=guessed_entity,
                form=m.group("form").lower(),
                source_pattern="out_of_the_whirlwind",
            ))

    for m in RE_PILLAR_FORM.finditer(text_n):
        if guessed_entity:
            facts.append(_fact(
                "manifestation",
                ref,
                entity=guessed_entity,
                form=m.group("form").lower(),
                source_pattern="pillar_form",
            ))

    if RE_IN_A_FLAME_OF_FIRE.search(text_n) and guessed_entity:
        facts.append(_fact(
            "manifestation",
            ref,
            entity=guessed_entity,
            form="flame of fire",
            source_pattern="in_a_flame_of_fire",
        ))

    if RE_BURNING_BUSH.search(text_n) and guessed_entity:
        facts.append(_fact(
            "manifestation",
            ref,
            entity=guessed_entity,
            form="burning bush",
            source_pattern="burning_bush",
        ))

    return facts, drops


def get_extractors():
    return [
        extract_genealogy,
        extract_rename,
        extract_speech,
        extract_killing,
        extract_travel,
        extract_roles,
        extract_appearance,
    ]