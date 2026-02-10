import re
from typing import List, Dict, Any, Optional

from ingest.stopwords import is_valid_entity


# -----------------------------
# Normalization
# -----------------------------

def _norm(s: str) -> str:
    """
    Normalize verse text to improve regex robustness:
    - unify quotes/dashes
    - collapse whitespace
    """
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _title(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"\s+", " ", s.strip()).title()


def _clean(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"\s+", " ", s.strip()).lower()


def _valid_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = _title(s)
    return s if is_valid_entity(s) else None


# -----------------------------
# Token patterns
# -----------------------------

NAME = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
PLACE = r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*"

DIVINE_RE = re.compile(r"\b(yahweh|lord|yhwh|god)\b", re.IGNORECASE)


# -----------------------------
# Core patterns (Genesis-focused)
# -----------------------------

RE_SAID_TO = re.compile(
    rf"\b(?P<speaker>{NAME}|Yahweh|God|LORD)\b\s+(?:said|spoke|called|cried)\s+to\s+(?P<recipient>{NAME})\b",
    re.IGNORECASE,
)

RE_QUOTE = re.compile(r'"(?P<quote>[^"]{1,200})"')

RE_COMMANDED = re.compile(
    rf"\b(?P<speaker>{NAME}|Yahweh|God|LORD)\b\s+commanded\s+(?P<recipient>{NAME})\b",
    re.IGNORECASE,
)

RE_WENT_TO = re.compile(
    rf"\b(?P<who>{NAME})\b\s+(?:went|journeyed|traveled)\s+to\s+(?P<where>{PLACE})\b",
    re.IGNORECASE,
)

RE_CAME_TO = re.compile(
    rf"\b(?P<who>{NAME})\b\s+came\s+to\s+(?P<where>{PLACE})\b",
    re.IGNORECASE,
)

RE_LEFT = re.compile(
    rf"\b(?P<who>{NAME})\b\s+left\s+(?P<where>{PLACE})\b",
    re.IGNORECASE,
)

RE_BEGAT = re.compile(
    rf"\b(?P<father>{NAME})\b.*?\bbegat\b.*?\b(?P<child>{NAME})\b",
    re.IGNORECASE,
)

RE_FATHER_OF = re.compile(
    rf"\b(?P<father>{NAME})\b\s+became\s+the\s+father\s+of\s+(?P<child>{NAME})\b",
    re.IGNORECASE,
)

RE_BORE = re.compile(
    rf"\b(?P<mother>{NAME})\b\s+(?:bore|gave\s+birth\s+to)\s+(?P<child>{NAME})\b",
    re.IGNORECASE,
)

RE_TOOK_WIFE = re.compile(
    rf"\b(?P<husband>{NAME})\b\s+took\s+(?P<wife>{NAME})\b\s+(?:to\s+be\s+)?his\s+wife\b",
    re.IGNORECASE,
)

RE_CALLED_NAME = re.compile(
    rf"\bcalled\s+(?:his|her|their)\s+name\s+(?P<name>{NAME})\b",
    re.IGNORECASE,
)

RE_NAMED = re.compile(
    rf"\bnamed\s+(?:him|her|it)\s+(?P<name>{NAME})\b",
    re.IGNORECASE,
)

RE_COVENANT_WITH = re.compile(
    rf"\bcovenant\s+with\s+(?P<partner>{NAME})\b",
    re.IGNORECASE,
)

RE_CREATED = re.compile(
    r"\b(God|Yahweh|LORD)\b\s+(?P<verb>created|made|formed)\s+(?P<object>[^.]{1,150})\.",
    re.IGNORECASE,
)

RE_LIKE = re.compile(
    r"\blike\s+(?:a|an)\s+(?P<vehicle>[a-z][a-z\s]{1,60})(?:,|\.|;|$)",
    re.IGNORECASE,
)

RE_AS_AS = re.compile(
    r"\bas\s+(?P<property>[a-z\s]{1,40})\s+as\s+(?P<vehicle>[a-z][a-z\s]{1,60})(?:,|\.|;|$)",
    re.IGNORECASE,
)

RE_IS_MY = re.compile(
    r"\bis\s+my\s+(?P<vehicle>[a-z\s]+?)(?:,| and|\.|$)",
    re.IGNORECASE,
)


# -----------------------------
# Extractor
# -----------------------------

def extract_relations(ref: str, text: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    t = _norm(text)

    # --- Speech ---
    m = RE_SAID_TO.search(t)
    if m:
        speaker = _valid_name(m.group("speaker"))
        recipient = _valid_name(m.group("recipient"))
        if speaker and recipient:
            q = RE_QUOTE.search(t)
            out.append({
                "kind": "event",
                "ref": ref,
                "args": {
                    "event_type": "Speech",
                    "speaker": speaker,
                    "recipient": recipient,
                    "content": q.group("quote").strip() if q else None,
                },
                "evidence": text,
            })

    m = RE_COMMANDED.search(t)
    if m:
        speaker = _valid_name(m.group("speaker"))
        recipient = _valid_name(m.group("recipient"))
        if speaker and recipient:
            out.append({
                "kind": "event",
                "ref": ref,
                "args": {
                    "event_type": "Command",
                    "agent": speaker,
                    "recipient": recipient,
                },
                "evidence": text,
            })

    # --- Movement ---
    for rex, etype in [
        (RE_WENT_TO, "MoveTo"),
        (RE_CAME_TO, "ArriveAt"),
        (RE_LEFT, "DepartFrom"),
    ]:
        m = rex.search(t)
        if m:
            who = _valid_name(m.group("who"))
            where = _valid_name(m.group("where"))
            if who and where:
                out.append({
                    "kind": "event",
                    "ref": ref,
                    "args": {
                        "event_type": etype,
                        "who": who,
                        "where": where,
                    },
                    "evidence": text,
                })

    # --- Genealogy (normalized) ---
    m = RE_BEGAT.search(t)
    if m:
        father = _valid_name(m.group("father"))
        child = _valid_name(m.group("child"))
        if father and child:
            out.append({
                "kind": "genealogy",
                "ref": ref,
                "args": {
                    "parent": father,
                    "child": child,
                    "role": "father",
                },
                "evidence": text,
            })

    m = RE_FATHER_OF.search(t)
    if m:
        father = _valid_name(m.group("father"))
        child = _valid_name(m.group("child"))
        if father and child:
            out.append({
                "kind": "genealogy",
                "ref": ref,
                "args": {
                    "parent": father,
                    "child": child,
                    "role": "father",
                },
                "evidence": text,
            })

    m = RE_BORE.search(t)
    if m:
        mother = _valid_name(m.group("mother"))
        child = _valid_name(m.group("child"))
        if mother and child:
            out.append({
                "kind": "genealogy",
                "ref": ref,
                "args": {
                    "parent": mother,
                    "child": child,
                    "role": "mother",
                },
                "evidence": text,
            })

    # --- Marriage ---
    m = RE_TOOK_WIFE.search(t)
    if m:
        husband = _valid_name(m.group("husband"))
        wife = _valid_name(m.group("wife"))
        if husband and wife:
            out.append({
                "kind": "event",
                "ref": ref,
                "args": {
                    "event_type": "Marriage",
                    "husband": husband,
                    "wife": wife,
                },
                "evidence": text,
            })

    # --- Naming ---
    for rex in (RE_CALLED_NAME, RE_NAMED):
        m = rex.search(t)
        if m:
            name = _valid_name(m.group("name"))
            if name:
                out.append({
                    "kind": "event",
                    "ref": ref,
                    "args": {
                        "event_type": "Naming",
                        "name": name,
                    },
                    "evidence": text,
                })

    # --- Covenant ---
    m = RE_COVENANT_WITH.search(t)
    if m and DIVINE_RE.search(t):
        partner = _valid_name(m.group("partner"))
        if partner:
            out.append({
                "kind": "event",
                "ref": ref,
                "args": {
                    "event_type": "Covenant",
                    "agent": "God",
                    "partner": partner,
                },
                "evidence": text,
            })

    # --- Creation ---
    m = RE_CREATED.search(t)
    if m:
        out.append({
            "kind": "event",
            "ref": ref,
            "args": {
                "event_type": "Create",
                "agent": "God",
                "verb": m.group("verb").lower(),
                "object": _clean(m.group("object")),
            },
            "evidence": text,
        })

    # --- Metaphor / Simile ---
    m = RE_LIKE.search(t)
    if m:
        out.append({
            "kind": "metaphor",
            "ref": ref,
            "args": {
                "metaphor_type": "Like",
                "vehicle": _clean(m.group("vehicle")),
            },
            "evidence": text,
        })

    m = RE_AS_AS.search(t)
    if m:
        out.append({
            "kind": "metaphor",
            "ref": ref,
            "args": {
                "metaphor_type": "AsAs",
                "property": _clean(m.group("property")),
                "vehicle": _clean(m.group("vehicle")),
            },
            "evidence": text,
        })

    m = RE_IS_MY.search(t)
    if m:
        out.append({
            "kind": "metaphor",
            "ref": ref,
            "args": {
                "metaphor_type": "IsMy",
                "source": "God",
                "vehicle": _clean(m.group("vehicle")),
            },
            "evidence": text,
        })

    return out
