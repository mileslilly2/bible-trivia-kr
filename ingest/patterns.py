import re

# -----------------------------
# Genealogy
# -----------------------------

RE_BEGAT = re.compile(
    r"""
    (?P<father>[A-Z][a-z]+)
    .*?
    begat
    .*?
    (?P<child>[A-Z][a-z]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

RE_FATHER_OF = re.compile(
    r"""
    (?P<father>[A-Z][a-z]+)
    \s+
    became
    \s+
    the
    \s+
    father
    \s+
    of
    \s+
    (?P<child>[A-Z][a-z]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# -----------------------------
# Divine speech / events
# -----------------------------

RE_DIVINE_SPEECH = re.compile(
    r"""
    (answered|said)
    \s+
    (?:to\s+)?               # optional "to"
    (?P<recipient>[A-Z][a-z]+)
    .*?
    (?:out\s+of\s+the\s+(?P<medium>[a-z\s]+))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# -----------------------------
# Appearances
# -----------------------------

RE_APPEARED_IN = re.compile(
    r"""
    appeared
    .*?
    in
    \s+
    (?P<form>[^.]+?)
    \s+
    out
    \s+
    of
    \s+
    the
    \s+
    midst
    \s+
    of
    \s+
    a
    \s+
    (?P<container>[a-z\s]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# -----------------------------
# Metaphor: "is my X"
# -----------------------------

RE_IS_MY = re.compile(
    r"""
    \bis
    \s+
    my
    \s+
    (?P<vehicle>[a-z\s]+?)
    (?:,| and|\.|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)

# -----------------------------
# Extractor
# -----------------------------

def extract_relations(ref: str, text: str):
    out = []

    # --- Divine mention (useful signal, not theology) ---
    if re.search(r"\b(yahweh|lord|yhwh)\b", text, re.IGNORECASE):
        out.append({
            "kind": "divine_mention",
            "ref": ref,
            "args": {"name": "Yahweh"},
            "evidence": text,
        })

    # --- Genealogy ---
    m = RE_BEGAT.search(text)
    if m:
        out.append({
            "kind": "genealogy",
            "ref": ref,
            "relation": "Begat",
            "args": {
                "father": m.group("father").title(),
                "child": m.group("child").title(),
            },
            "evidence": text,
        })

    m = RE_FATHER_OF.search(text)
    if m:
        out.append({
            "kind": "genealogy",
            "ref": ref,
            "relation": "FatherOf",
            "args": {
                "father": m.group("father").title(),
                "child": m.group("child").title(),
            },
            "evidence": text,
        })

    # --- Divine speech ---
    m = RE_DIVINE_SPEECH.search(text)
    if m:
        out.append({
            "kind": "event",
            "ref": ref,
            "event_type": "DivineSpeech",
            "args": {
                "agent": "God",
                "recipient": m.group("recipient").title(),
                "medium": (m.group("medium") or "").strip().lower() or None,
            },
            "evidence": text,
        })

    # --- Appearance ---
    m = RE_APPEARED_IN.search(text)
    if m:
        out.append({
            "kind": "event",
            "ref": ref,
            "event_type": "Appearance",
            "args": {
                "agent": "AngelOfTheLORD",
                "form": m.group("form").strip().lower(),
                "container": m.group("container").strip().lower(),
            },
            "evidence": text,
        })

    # --- Metaphor ---
    m = RE_IS_MY.search(text)
    if m:
        out.append({
            "kind": "metaphor",
            "ref": ref,
            "metaphor_type": "IsMy",
            "args": {
                "source": "God",
                "vehicle": m.group("vehicle").strip().lower(),
            },
            "evidence": text,
        })

    return out
