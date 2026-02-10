"""
bible_rule_engine.py

Minimal, working rule engine for Bible fact extraction.

CURRENTLY SUPPORTED (on purpose):
- genealogy (father_of / mother_of)
- rename (called / named)
- violence (killed / slew)

Design rules:
- High precision only
- If a rule is uncertain, drop it
- Every rule must produce real output in Genesis
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple, Optional
import re


# -----------------------------
# Data models
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
    drops.append(Drop(ref, rule, text, details))


# -----------------------------
# Genealogy
# -----------------------------


#NAME = r"[A-Z][a-z]+(?:-[A-Z][a-z]+)?"
#NAME = r"[A-Z][a-z]+(?:-[A-Z][a-z]+)?"
NAME = r"[A-Z][a-z]+(?:-[A-Za-z]+)?"






RE_BEGAT = re.compile(
    rf"\b(?P<father>{NAME})\s+begat\s+(?P<child>{NAME})"
)


RE_BORE = re.compile(
    rf"\b(?P<mother>{NAME})\s+(?:also\s+)?(?:bare|bore|gave birth to)\s+(?P<child>{NAME})(?:\b|[,;.])"
)




def extract_genealogy(ref: str, text: str) -> Tuple[List[Fact], List[Drop]]:
    facts, drops = [], []

    # Father lineage: "X begat Y"
    m = RE_BEGAT.search(text)
    if m:
        father = clean_name(m.group("father"))
        child = clean_name(m.group("child"))
        if father and child:
            facts.append(Fact(
                "genealogy",
                ref,
                {"father": father, "child": child}
            ))
        else:
            add_drop(drops, ref, "genealogy_invalid_begat", text, extracted=m.groupdict())

    # Mother lineage: "X bare/bore Y"
    m = RE_BORE.search(text)
    if m:
        mother = clean_name(m.group("mother"))
        child = clean_name(m.group("child"))
        if mother and child:
            facts.append(Fact(
                "genealogy",
                ref,
                {"mother": mother, "child": child}
            ))
        else:
            add_drop(drops, ref, "genealogy_invalid_bore", text, extracted=m.groupdict())

    return facts, drops

# -----------------------------
# Rename
# -----------------------------

RE_CALLED_NAME = re.compile(
    r"\bcalled\s+(?:his|her|their)\s+name\s+(?P<name>[A-Z][a-z]+)\b"
)

RE_NAMED = re.compile(
    r"\bnamed\s+(?:him|her|them)\s+(?P<name>[A-Z][a-z]+)\b"
)


def extract_rename(ref: str, text: str) -> Tuple[List[Fact], List[Drop]]:
    facts, drops = [], []

    for pat in (RE_CALLED_NAME, RE_NAMED):
        m = pat.search(text)
        if m:
            name = clean_name(m.group("name"))
            if name:
                facts.append(Fact(
                    "rename",
                    ref,
                    {"name": name}
                ))
            else:
                add_drop(drops, ref, "rename_invalid", text, extracted=m.groupdict())

    return facts, drops


# -----------------------------
# Violence
# -----------------------------

RE_KILLED = re.compile(
    r"\b(?P<who>[A-Z][a-z]+)\s+(?:killed|slew)\s+(?P<target>[A-Z][a-z]+)\b"
)


def extract_violence(ref: str, text: str) -> Tuple[List[Fact], List[Drop]]:
    facts, drops = [], []

    m = RE_KILLED.search(text)
    if m:
        who = clean_name(m.group("who"))
        target = clean_name(m.group("target"))
        if who and target:
            facts.append(Fact(
                "violence",
                ref,
                {"who": who, "target": target}
            ))
        else:
            add_drop(drops, ref, "violence_invalid", text, extracted=m.groupdict())

    return facts, drops


# -----------------------------
# Orchestrator
# -----------------------------

def extract_facts(ref: str, text: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    raw = normalize(text)

    facts: List[Fact] = []
    drops: List[Drop] = []

    # 1. Genealogy first
    genealogy_facts, genealogy_drops = extract_genealogy(ref, raw)
    facts.extend(genealogy_facts)
    drops.extend(genealogy_drops)

    # 2. Rename only if no genealogy found
    if not genealogy_facts:
        rename_facts, rename_drops = extract_rename(ref, raw)
        facts.extend(rename_facts)
        drops.extend(rename_drops)

    # 3. Violence always allowed
    violence_facts, violence_drops = extract_violence(ref, raw)
    facts.extend(violence_facts)
    drops.extend(violence_drops)


    return [f.to_dict() for f in facts], [asdict(d) for d in drops]


# -----------------------------
# Smoke test
# -----------------------------

if __name__ == "__main__":
    tests = [
        ("Genesis 4:22", "And Zillah also bare Tubal-cain, an instructor of every artificer in brass and iron."),
        ("Genesis 27:41", "Then will I slay my brother Jacob."),
        ("Genesis 21:3", "Abraham called his son's name Isaac."),
    ]

    for ref, text in tests:
        facts, drops = extract_facts(ref, text)
        print("\n", ref)
        print("TEXT:", text)
        print("FACTS:", facts)
        print("DROPS:", drops)
