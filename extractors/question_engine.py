from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
import hashlib
import json
import random
import re
from datetime import datetime, timezone


# -----------------------------
# Basic normalization + guards
# -----------------------------

def normalize(text: str) -> str:
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


_BAD_NAMES = {
    "He", "She", "They", "His", "Her", "Their", "Him", "Them", "It", "This", "That",
    "One", "Someone", "Anyone", "Noone", "None",
}

NOISY_PREFIXES = {
    "Moreover", "Then", "Now", "And", "But", "After", "Before", "Behold",
}

TITLE_PREFIXES = {
    "King", "Queen", "Prophet", "Priest",
}

BAD_SINGLE_TOKENS = {
    "Ethiopian", "Bethlehemite", "Hushathite", "Moabite", "Moabitess",
}

SUSPICIOUS_ENTITY_NAMES = {
    "ammonite",
    "ammonites",
    "edomite",
    "edomites",
    "egyptian",
    "egyptians",
    "gentile",
    "gentiles",
    "hebrew",
    "hebrews",
    "israelite",
    "israelites",
    "judean",
    "judeans",
    "moabite",
    "moabites",
    "moabitess",
    "philistine",
    "philistines",
}

DIALOGUE_GROUP_NAMES = {
    "Israel", "Judah",
}

DIALOGUE_BAD_SUFFIXES = ("ites", "ite", "ess")
DIALOGUE_PLURAL_SUFFIXES = ("ians", "eans", "ites", "im")

DIVINE_CANON = {
    "Yahweh": "God",
    "God": "God",
    "LORD": "God",
    "Lord": "God",
    "In Gibeon Yahweh": "God",
    "angel of the LORD": "angel of God",
    "angel of Yahweh": "angel of God",
    "angel of God": "angel of God",
}


def normalize_choice_name(s: Optional[str]) -> Optional[str]:
    if not s:
        return None

    s = s.strip()
    if not s:
        return None

    parts = s.split()
    while parts and parts[0] in NOISY_PREFIXES:
        parts = parts[1:]

    if parts and parts[0] in TITLE_PREFIXES and len(parts) >= 2:
        parts = parts[1:]

    s = " ".join(parts).strip(" ,;:")
    if not s:
        return None

    if s in DIVINE_CANON:
        return DIVINE_CANON[s]

    if s in BAD_SINGLE_TOKENS:
        return None

    return s


def is_good_name(s: Optional[str]) -> bool:
    s = normalize_choice_name(s)
    if not s:
        return False
    if s in _BAD_NAMES:
        return False
    if s.casefold() in SUSPICIOUS_ENTITY_NAMES:
        return False
    if len(s) < 2:
        return False
    return True


def normalize_form(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip().lower()
    if not s:
        return None
    return s


def normalize_dialogue_name(s: Optional[str]) -> Optional[str]:
    s = normalize_choice_name(s)
    if not s:
        return None
    return s


def is_good_dialogue_person(s: Optional[str]) -> bool:
    s = normalize_dialogue_name(s)
    if not is_good_name(s):
        return False
    if s in DIALOGUE_GROUP_NAMES:
        return False
    lower = s.lower()
    if " " not in s and lower.endswith(DIALOGUE_BAD_SUFFIXES):
        return False
    if " " not in s and lower.endswith(DIALOGUE_PLURAL_SUFFIXES):
        return False
    return True


def _verse_or_fallback(ref: str, src_text: str, fallback: str) -> str:
    ref = (ref or "").strip()
    src_text = (src_text or "").strip()
    if ref and src_text:
        return f"{ref}: {src_text}"
    if src_text:
        return src_text
    return fallback


def _parent_explanation(parent: str, child: str, parent_gender: Optional[str], ref: str, src_text: str) -> str:
    relation = "mother" if parent_gender == "female" else "father" if parent_gender == "male" else "parent"
    return _verse_or_fallback(ref, src_text, f"{parent} is recorded as the {relation} of {child}.")


def _inferred_explanation(base: str, fact: Dict[str, Any]) -> str:
    refs = fact.get("provenance_refs") or []
    if refs:
        return f"{base} from source facts including {refs[0]}."
    return base + "."


def _chain_text(chain: List[str]) -> str:
    return " -> ".join(chain)


def _genealogy_explanation(relation: str, answer: str, target: str, fact: Dict[str, Any]) -> str:
    chain = fact.get("genealogy_chain") or []
    if chain:
        if relation == "ancestor_of":
            return f"{answer} is inferred as an ancestor of {target} through the genealogy chain: {_chain_text(chain)}."
        return f"{answer} is inferred as a descendant of {target} through the genealogy chain: {_chain_text(chain)}."
    return _inferred_explanation(f"{answer} is inferred in the genealogy relation for {target}", fact)


def _sibling_explanation(person: str, sibling: str, fact: Dict[str, Any]) -> str:
    shared_parent = fact.get("shared_parent")
    if shared_parent:
        return _inferred_explanation(f"{person} and {sibling} are inferred as siblings because they share {shared_parent} as a parent", fact)
    return _inferred_explanation(f"{person} and {sibling} are inferred as siblings because they share a parent", fact)


def _has_grounded_genealogy(fact: Dict[str, Any]) -> bool:
    depth = fact.get("genealogy_depth") or (len(fact.get("genealogy_chain", [])) - 1)
    has_refs = bool(fact.get("provenance_refs"))

    # If it's a long hop (> 2) and we don't have direct verse refs for it, filter it.
    if depth > 2 and not has_refs:
        return False

    # Needs at least some grounding (either a short hop or a verse ref)
    if not has_refs and depth <= 0:
        return False

    return True


def _fact_explanation(ftype: str, ref: str, src_text: str, **parts: str) -> str:
    if ftype == "rename":
        return _verse_or_fallback(ref, src_text, f"{parts['name']} is the recorded name in this extracted naming fact.")
    if ftype == "killed_killer":
        return _verse_or_fallback(ref, src_text, f"{parts['killer']} is recorded as killing {parts['victim']}.")
    if ftype == "killed_victim":
        return _verse_or_fallback(ref, src_text, f"{parts['victim']} is recorded as being killed by {parts['killer']}.")
    if ftype == "spoke_to":
        return _verse_or_fallback(ref, src_text, f"{parts['speaker']} spoke to {parts['listener']}.")
    if ftype == "traveled_destination":
        return _verse_or_fallback(ref, src_text, f"{parts['traveler']} traveled to {parts['destination']}.")
    if ftype == "traveled_source":
        return _verse_or_fallback(ref, src_text, f"{parts['traveler']} traveled from {parts['source']} to {parts['destination']}.")
    if ftype == "role_name":
        return _verse_or_fallback(ref, src_text, f"{parts['person']} is recorded with the role {parts['role']}.")
    if ftype == "role_realm":
        return _verse_or_fallback(ref, src_text, f"{parts['person']} reigned over {parts['realm']}.")
    if ftype in {"appeared_to_recipient", "appeared_to_entity"}:
        return _verse_or_fallback(ref, src_text, f"{parts['entity']} appeared to {parts['recipient']}.")
    if ftype == "manifestation_form":
        return _verse_or_fallback(ref, src_text, f"{parts['entity']} manifested in the form of {parts['form']}.")
    return _verse_or_fallback(ref, src_text, "This question is based on an extracted fact.")


def _choose_template(rng: random.Random, templates: List[str], **parts: str) -> str:
    return rng.choice(templates).format(**parts)


def _direct_genealogy_prompt(ref: str, relation: str, child: str) -> str:
    if ref:
        return f"According to the genealogy in {ref}, who was the {relation} of {child}?"
    return f"According to the biblical genealogy, who was the {relation} of {child}?"


def _rename_prompt(ref: str) -> str:
    if ref:
        return f"In {ref}, what name was given?"
    return "According to the naming record, what name was given?"


def _short_quote(text: str, max_words: int = 10) -> Optional[str]:
    text = normalize(text).strip(" \"'")
    if not text:
        return None
    words = text.split()
    if not words:
        return None
    clipped = " ".join(words[:max_words]).strip(" ,;:")
    if not clipped:
        return None
    if len(words) > max_words:
        clipped = clipped.rstrip(".!?") + "..."
    return clipped


def _quoted_speech_snippet(src_text: str, speaker: str, listener: str) -> Optional[str]:
    text = normalize(src_text)
    if not text or '"' not in text:
        return None

    escaped_speaker = re.escape(speaker)
    escaped_listener = re.escape(listener)
    speech_cues = [
        rf"\b{escaped_speaker}\s+(?:said|spoke)\s+to\s+{escaped_listener}\b",
        rf"\b{escaped_speaker}\s+(?:said|spoke)\s+to\s+(?:him|her|them)\b",
        rf"\b(?:said|spoke)\s+to\s+{escaped_listener}\b",
        rf"\b(?:said|spoke)\s+to\s+(?:him|her|them)\b",
        rf"\b{escaped_speaker}\s+(?:said|spoke)\b",
    ]

    start_at = -1
    for cue in speech_cues:
        match = re.search(cue, text, flags=re.IGNORECASE)
        if match:
            start_at = match.end()
            break
    if start_at < 0:
        return None

    quote_match = re.search(r'"([^"]+)"', text[start_at:])
    if not quote_match:
        return None
    return _short_quote(quote_match.group(1))


def _dialogue_prompt(rng: random.Random, ref: str, speaker: str, listener: str, src_text: str) -> str:
    quote = _quoted_speech_snippet(src_text, speaker, listener)
    if quote and ref:
        return f"In {ref}, who said to {listener}, '{quote}'?"
    if quote:
        return f"According to the recorded speech, who said to {listener}, '{quote}'?"
    if ref:
        return _choose_template(
            rng,
            [
                "In {ref}, who spoke with {listener}?",
                "According to {ref}, who addressed {listener}?",
                "Who spoke to {listener} in {ref}?",
            ],
            ref=ref,
            listener=listener,
        )
    return _choose_template(
        rng,
        [
            "According to recorded speech events, who spoke with {listener}?",
            "In the recorded dialogue, who addressed {listener}?",
        ],
        listener=listener,
    )


def _travel_destination_prompt(rng: random.Random, ref: str, traveler: str) -> str:
    if ref:
        return _choose_template(
            rng,
            [
                "In {ref}, where did {traveler} travel?",
                "According to {ref}, where did {traveler} go?",
                "Where did {traveler} travel in {ref}?",
            ],
            ref=ref,
            traveler=traveler,
        )
    return f"According to the travel record, where did {traveler} travel?"


def _travel_source_prompt(rng: random.Random, ref: str, traveler: str, destination: str) -> str:
    if ref:
        return _choose_template(
            rng,
            [
                "In {ref}, from where did {traveler} travel to {destination}?",
                "According to {ref}, where did {traveler}'s journey to {destination} begin?",
            ],
            ref=ref,
            traveler=traveler,
            destination=destination,
        )
    return f"According to the travel record, from where did {traveler} travel to {destination}?"


def _appearance_recipient_prompt(rng: random.Random, ref: str, entity: str) -> str:
    if ref:
        return _choose_template(
            rng,
            [
                "To whom did {entity} appear in {ref}?",
                "In {ref}, to whom did {entity} appear?",
            ],
            ref=ref,
            entity=entity,
        )
    return f"According to the appearance account, to whom did {entity} appear?"


def _appearance_entity_prompt(rng: random.Random, ref: str, recipient: str) -> str:
    if ref:
        return _choose_template(
            rng,
            [
                "Who appeared to {recipient} in {ref}?",
                "In {ref}, who appeared to {recipient}?",
            ],
            ref=ref,
            recipient=recipient,
        )
    return f"According to the appearance account, who appeared to {recipient}?"


def _manifestation_prompt(ref: str, entity: str) -> str:
    if ref:
        return f"In {ref}, in what form did {entity} appear?"
    return f"According to the manifestation account, in what form did {entity} appear?"


def _genealogy_anchor(fact: Dict[str, Any]) -> Optional[str]:
    chain = fact.get("genealogy_chain") or []
    if len(chain) >= 2 and chain[0]:
        return normalize_choice_name(chain[0])
    return None


def _ancestor_prompt(rng: random.Random, fact: Dict[str, Any], descendant: str) -> str:
    anchor = _genealogy_anchor(fact)
    if anchor and anchor != descendant:
        return _choose_template(
            rng,
            [
                "Through the genealogy of {anchor}, who was an ancestor of {descendant}?",
                "According to the genealogy running from {anchor}, who was an ancestor of {descendant}?",
            ],
            anchor=anchor,
            descendant=descendant,
        )
    return _choose_template(
        rng,
        [
            "According to biblical genealogies, who was an ancestor of {descendant}?",
            "In the biblical genealogies, who was counted among the ancestors of {descendant}?",
        ],
        descendant=descendant,
    )


def _descendant_prompt(rng: random.Random, fact: Dict[str, Any], ancestor: str) -> str:
    anchor = _genealogy_anchor(fact)
    if anchor:
        return _choose_template(
            rng,
            [
                "Through the genealogy of {anchor}, who was a descendant of {ancestor}?",
                "According to the genealogy running from {anchor}, who descended from {ancestor}?",
            ],
            anchor=anchor,
            ancestor=ancestor,
        )
    return _choose_template(
        rng,
        [
            "According to biblical genealogies, who was a descendant of {ancestor}?",
            "In the biblical genealogies, who was counted among the descendants of {ancestor}?",
        ],
        ancestor=ancestor,
    )


def _sibling_prompt(person: str) -> str:
    return f"According to biblical genealogies, who was a sibling of {person}?"


def _inferred_dialogue_prompt(rng: random.Random, fact: Dict[str, Any], person: str) -> str:
    ref = fact.get("ref", "")
    if ref:
        return _choose_template(
            rng,
            [
                "In the cited passage {ref}, who is recorded as speaking with {person}?",
                "According to {ref}, who is linked with {person} through recorded speech?",
                "Who is connected with {person} through recorded speech in {ref}?",
            ],
            ref=ref,
            person=person,
        )
    return f"According to recorded speech events, who is connected with {person}?"


# -----------------------------
# Question model
# -----------------------------

@dataclass(frozen=True)
class MCQuestion:
    id: str
    prompt: str
    choices: List[str]
    answer_index: int
    explanation: str
    ref: str
    category: str = "Bible"
    difficulty: str = "easy"
    meta: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["meta"] is None:
            d["meta"] = {}
        return d


def _stable_id(*parts: str) -> str:
    raw = "||".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


# -----------------------------
# Loading helpers (JSONL)
# -----------------------------

def load_json_or_jsonl(path: str | Path):
    p = Path(path)
    rows = []

    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    return rows


# -----------------------------
# Pools and importance
# -----------------------------

def build_pools(facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    from collections import Counter
    name_counts: Counter[str] = Counter()
    people = set()
    parent_male = set()
    parent_female = set()
    names = set()
    destinations = set()
    roles = set()
    realms = set()
    entities = set()
    forms = set()
    speakers = set()
    listeners = set()
    killers = set()
    victims = set()
    travelers = set()
    appearance_recipients = set()
    dialogue_people = set()

    for f in facts:
        ftype = f.get("type")

        if ftype == "parent_of":
            parent = normalize_choice_name(f.get("parent"))
            child = normalize_choice_name(f.get("child"))
            gender = f.get("parent_gender")

            if is_good_name(parent):
                people.add(parent)
                if gender == "male":
                    parent_male.add(parent)
                elif gender == "female":
                    parent_female.add(parent)

            if is_good_name(child):
                people.add(child)

        elif ftype == "rename":
            name = normalize_choice_name(f.get("name"))
            if is_good_name(name):
                names.add(name)

        elif ftype == "killed":
            killer = normalize_choice_name(f.get("killer"))
            victim = normalize_choice_name(f.get("victim"))
            if is_good_name(killer):
                people.add(killer)
                killers.add(killer)
            if is_good_name(victim):
                people.add(victim)
                victims.add(victim)

        elif ftype == "spoke_to":
            speaker = normalize_dialogue_name(f.get("speaker"))
            listener = normalize_dialogue_name(f.get("listener"))
            if is_good_dialogue_person(speaker):
                people.add(speaker)
                speakers.add(speaker)
                dialogue_people.add(speaker)
            if is_good_dialogue_person(listener):
                people.add(listener)
                listeners.add(listener)
                dialogue_people.add(listener)

        elif ftype == "traveled":
            traveler = normalize_choice_name(f.get("traveler"))
            source = normalize_choice_name(f.get("source"))
            destination = normalize_choice_name(f.get("destination"))
            if is_good_name(traveler):
                people.add(traveler)
                travelers.add(traveler)
            if is_good_name(source):
                destinations.add(source)
            if is_good_name(destination):
                destinations.add(destination)

        elif ftype == "role":
            person = normalize_choice_name(f.get("person"))
            role_name = normalize_choice_name(f.get("role"))
            realm = normalize_choice_name(f.get("realm"))
            if is_good_name(person):
                people.add(person)
            if is_good_name(role_name):
                roles.add(role_name)
            if is_good_name(realm):
                realms.add(realm)

        elif ftype == "appeared_to":
            entity = normalize_choice_name(f.get("entity"))
            recipient = normalize_choice_name(f.get("recipient"))
            if is_good_name(entity):
                entities.add(entity)
                people.add(entity)
            if is_good_name(recipient):
                appearance_recipients.add(recipient)
                people.add(recipient)

        elif ftype == "manifestation":
            entity = normalize_choice_name(f.get("entity"))
            form = normalize_form(f.get("form"))
            if is_good_name(entity):
                entities.add(entity)
                people.add(entity)
            if form:
                forms.add(form)

        elif ftype == "ancestor_of":
            ancestor = normalize_choice_name(f.get("ancestor"))
            descendant = normalize_choice_name(f.get("descendant"))
            if is_good_name(ancestor):
                people.add(ancestor)
            if is_good_name(descendant):
                people.add(descendant)

        elif ftype == "descendant_of":
            descendant = normalize_choice_name(f.get("descendant"))
            ancestor = normalize_choice_name(f.get("ancestor"))
            if is_good_name(descendant):
                people.add(descendant)
            if is_good_name(ancestor):
                people.add(ancestor)

        elif ftype == "sibling":
            person = normalize_choice_name(f.get("person") or f.get("person1"))
            sibling = normalize_choice_name(f.get("sibling") or f.get("person2"))
            if is_good_name(person):
                people.add(person)
            if is_good_name(sibling):
                people.add(sibling)

        elif ftype in {"interacted_with", "indirect_dialogue", "conversation_reach"}:
            person = normalize_dialogue_name(f.get("person") or f.get("a"))
            other = normalize_dialogue_name(f.get("other") or f.get("b") or f.get("reachable"))
            if is_good_dialogue_person(person):
                people.add(person)
                speakers.add(person)
                dialogue_people.add(person)
            if is_good_dialogue_person(other):
                people.add(other)
                listeners.add(other)
                dialogue_people.add(other)

    # Count narrative presence from extracted/grounded facts
    for f in facts:
        if f.get("source") == "souffle" or f.get("inferred"):
            continue
        for key in ("parent", "child", "speaker", "listener", "killer", "victim", "traveler", "person", "entity", "recipient"):
            val = normalize_choice_name(f.get(key))
            if is_good_name(val):
                name_counts[val] += 1

    return {
        "people": sorted(people),
        "parent_male": sorted(parent_male),
        "parent_female": sorted(parent_female),
        "names": sorted(names),
        "destinations": sorted(destinations),
        "roles": sorted(roles),
        "realms": sorted(realms),
        "entities": sorted(entities),
        "forms": sorted(forms),
        "speakers": sorted(speakers),
        "listeners": sorted(listeners),
        "dialogue_people": sorted(dialogue_people),
        "killers": sorted(killers),
        "victims": sorted(victims),
        "travelers": sorted(travelers),
        "appearance_recipients": sorted(appearance_recipients),
        "name_counts": name_counts,
    }


def _pick_distractors(rng: random.Random, pool: List[str], correct: str, k: int) -> Optional[List[str]]:
    correct = normalize_choice_name(correct) or correct
    pool2 = []
    for x in pool:
        nx = normalize_choice_name(x) if isinstance(x, str) else x
        if nx and nx != correct:
            pool2.append(nx)
    pool2 = sorted(set(pool2))
    if len(pool2) < k:
        return None
    return rng.sample(pool2, k)


def choices_look_clean(choices: List[str]) -> bool:
    for c in choices:
        c2 = normalize_choice_name(c)
        if not is_good_name(c2):
            return False
        if c2.startswith(("Moreover ", "Then ", "Now ")):
            return False
    return True


# -----------------------------
# Fact → MC questions
# -----------------------------


INFERRED_TEMPLATE_LIMITS = {
    "ancestor_of": 300,
    "descendant_of": 300,
    "sibling": 200,
    "interacted_with": 300,
    "indirect_dialogue": 300,
    "conversation_reach": 300,
}


def _append_inferred_question(
    out: List[MCQuestion],
    *,
    rng: random.Random,
    pools: Dict[str, List[str]],
    fact: Dict[str, Any],
    qtype: str,
    prompt: str,
    correct: str,
    explanation: str,
    category: str,
    difficulty: str = "medium",
    pool_key: str = "people",
) -> None:
    if not is_good_name(correct):
        return

    # Filter obscure names for inferred questions. 
    # Must have appeared at least once in extracted facts.
    name_counts = pools.get("name_counts")
    if name_counts and name_counts.get(correct, 0) < 1:
        return

    pool = pools[pool_key]
    distractors = _pick_distractors(rng, pool, correct, 3)
    if not distractors and pool_key != "people":
        distractors = _pick_distractors(rng, pools["people"], correct, 3)
    if not distractors:
        return

    choices = distractors + [correct]
    rng.shuffle(choices)
    if not choices_look_clean(choices):
        return

    meta = {"fact": fact, "norm": fact.get("norm", "")}
    provenance_refs = fact.get("provenance_refs")
    if provenance_refs:
        meta["provenance_refs"] = provenance_refs
        meta["inferred"] = True
    for key in ("genealogy_chain", "genealogy_depth", "shared_parent"):
        if key in fact:
            meta[key] = fact[key]

    out.append(MCQuestion(
        id=_stable_id(qtype, correct, prompt),
        prompt=prompt,
        choices=choices,
        answer_index=choices.index(correct),
        explanation=explanation,
        ref=fact.get("ref", ""),
        category=category,
        difficulty=difficulty,
        meta=meta,
    ))

def fact_to_questions(
    fact: Dict[str, Any],
    pools: Dict[str, List[str]],
    rng: random.Random,
) -> List[MCQuestion]:
    out: List[MCQuestion] = []

    ftype = fact.get("type")
    ref = fact.get("ref", "")
    src_text = fact.get("text") or ""
    norm_text = fact.get("norm") or normalize(src_text)

    # ---------- parent_of ----------
    if ftype == "parent_of":
        parent = normalize_choice_name(fact.get("parent"))
        child = normalize_choice_name(fact.get("child"))
        parent_gender = fact.get("parent_gender")

        if is_good_name(child) and is_good_name(parent):
            if parent_gender == "female":
                prompt = _direct_genealogy_prompt(ref, "mother", child)
                distractor_pool = pools["parent_female"] or pools["people"]
            elif parent_gender == "male":
                prompt = _direct_genealogy_prompt(ref, "father", child)
                distractor_pool = pools["parent_male"] or pools["people"]
            else:
                prompt = _direct_genealogy_prompt(ref, "parent", child)
                distractor_pool = pools["people"]

            correct = parent
            distractors = _pick_distractors(rng, distractor_pool, correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("parent_of", ref, child, correct, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_parent_explanation(parent, child, parent_gender, ref, src_text),
                        ref=ref,
                        category="Bible • Genealogy",
                        difficulty="easy",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- rename ----------
    if ftype == "rename":
        name = normalize_choice_name(fact.get("name"))
        if is_good_name(name):
            prompt = _rename_prompt(ref)
            correct = name
            distractors = _pick_distractors(rng, pools["names"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("rename_name", ref, correct, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("rename", ref, src_text, name=name),
                        ref=ref,
                        category="Bible • Names",
                        difficulty="easy",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- killed ----------
    if ftype == "killed":
        killer = normalize_choice_name(fact.get("killer"))
        victim = normalize_choice_name(fact.get("victim"))

        if is_good_name(victim) and is_good_name(killer):
            prompt = f"Who killed {victim}?"
            correct = killer
            distractors = _pick_distractors(rng, pools["killers"] or pools["people"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("killed_killer", ref, killer, victim, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("killed_killer", ref, src_text, killer=killer, victim=victim),
                        ref=ref,
                        category="Bible • Events",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))

            prompt2 = f"According to {ref}, who was killed?"
            correct2 = victim
            distractors2 = _pick_distractors(rng, pools["victims"] or pools["people"], correct2, 3)
            if distractors2:
                choices2 = distractors2 + [correct2]
                rng.shuffle(choices2)
                if choices_look_clean(choices2):
                    answer_index2 = choices2.index(correct2)
                    qid2 = _stable_id("killed_victim", ref, killer, victim, prompt2)
                    out.append(MCQuestion(
                        id=qid2,
                        prompt=prompt2,
                        choices=choices2,
                        answer_index=answer_index2,
                        explanation=_fact_explanation("killed_victim", ref, src_text, killer=killer, victim=victim),
                        ref=ref,
                        category="Bible • Events",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- spoke_to ----------
    if ftype == "spoke_to":
        speaker = normalize_dialogue_name(fact.get("speaker"))
        listener = normalize_dialogue_name(fact.get("listener"))

        if is_good_dialogue_person(listener) and is_good_dialogue_person(speaker):
            prompt = _dialogue_prompt(rng, ref, speaker, listener, src_text)
            correct = speaker
            distractors = _pick_distractors(rng, pools["speakers"] or pools["people"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("spoke_to_speaker", ref, speaker, listener, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("spoke_to", ref, src_text, speaker=speaker, listener=listener),
                        ref=ref,
                        category="Bible • Dialogue",
                        difficulty="easy",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- traveled ----------
    if ftype == "traveled":
        traveler = normalize_choice_name(fact.get("traveler"))
        source = normalize_choice_name(fact.get("source"))
        destination = normalize_choice_name(fact.get("destination"))

        if is_good_name(traveler) and is_good_name(destination):
            prompt = _travel_destination_prompt(rng, ref, traveler)
            correct = destination
            distractors = _pick_distractors(rng, pools["destinations"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("traveled_destination", ref, traveler, destination, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("traveled_destination", ref, src_text, traveler=traveler, destination=destination),
                        ref=ref,
                        category="Bible • Travel",
                        difficulty="easy",
                        meta={"fact": fact, "norm": norm_text},
                    ))

        if is_good_name(traveler) and is_good_name(source) and is_good_name(destination):
            prompt2 = _travel_source_prompt(rng, ref, traveler, destination)
            correct2 = source
            distractors2 = _pick_distractors(rng, pools["destinations"], correct2, 3)
            if distractors2:
                choices2 = distractors2 + [correct2]
                rng.shuffle(choices2)
                if choices_look_clean(choices2):
                    answer_index2 = choices2.index(correct2)
                    qid2 = _stable_id("traveled_source", ref, traveler, source, destination, prompt2)
                    out.append(MCQuestion(
                        id=qid2,
                        prompt=prompt2,
                        choices=choices2,
                        answer_index=answer_index2,
                        explanation=_fact_explanation("traveled_source", ref, src_text, traveler=traveler, source=source, destination=destination),
                        ref=ref,
                        category="Bible • Travel",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- role ----------
    if ftype == "role":
        person = normalize_choice_name(fact.get("person"))
        role_name = normalize_choice_name(fact.get("role"))
        realm = normalize_choice_name(fact.get("realm"))

        if is_good_name(person) and is_good_name(role_name):
            prompt = f"What role did {person} have?"
            correct = role_name
            distractors = _pick_distractors(rng, pools["roles"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("role_name", ref, person, role_name, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("role_name", ref, src_text, person=person, role=role_name),
                        ref=ref,
                        category="Bible • Roles",
                        difficulty="easy",
                        meta={"fact": fact, "norm": norm_text},
                    ))

        if is_good_name(person) and role_name == "king" and is_good_name(realm):
            prompt2 = f"Over what realm did {person} reign?"
            correct2 = realm
            distractors2 = _pick_distractors(rng, pools["realms"], correct2, 3)
            if distractors2:
                choices2 = distractors2 + [correct2]
                rng.shuffle(choices2)
                if choices_look_clean(choices2):
                    answer_index2 = choices2.index(correct2)
                    qid2 = _stable_id("role_realm", ref, person, realm, prompt2)
                    out.append(MCQuestion(
                        id=qid2,
                        prompt=prompt2,
                        choices=choices2,
                        answer_index=answer_index2,
                        explanation=_fact_explanation("role_realm", ref, src_text, person=person, realm=realm),
                        ref=ref,
                        category="Bible • Kingdoms",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- appeared_to ----------
    if ftype == "appeared_to":
        entity = normalize_choice_name(fact.get("entity"))
        recipient = normalize_choice_name(fact.get("recipient"))

        if is_good_name(entity) and is_good_name(recipient):
            prompt = _appearance_recipient_prompt(rng, ref, entity)
            correct = recipient
            distractors = _pick_distractors(rng, pools["appearance_recipients"] or pools["people"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("appeared_to_recipient", ref, entity, recipient, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("appeared_to_recipient", ref, src_text, entity=entity, recipient=recipient),
                        ref=ref,
                        category="Bible • Theophany",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))

            prompt2 = _appearance_entity_prompt(rng, ref, recipient)
            correct2 = entity
            distractors2 = _pick_distractors(rng, pools["entities"] or pools["people"], correct2, 3)
            if distractors2:
                choices2 = distractors2 + [correct2]
                rng.shuffle(choices2)
                if choices_look_clean(choices2):
                    answer_index2 = choices2.index(correct2)
                    qid2 = _stable_id("appeared_to_entity", ref, entity, recipient, prompt2)
                    out.append(MCQuestion(
                        id=qid2,
                        prompt=prompt2,
                        choices=choices2,
                        answer_index=answer_index2,
                        explanation=_fact_explanation("appeared_to_entity", ref, src_text, entity=entity, recipient=recipient),
                        ref=ref,
                        category="Bible • Theophany",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- manifestation ----------
    if ftype == "manifestation":
        entity = normalize_choice_name(fact.get("entity"))
        form = normalize_form(fact.get("form"))

        if is_good_name(entity) and form:
            prompt = _manifestation_prompt(ref, entity)
            correct = form
            distractors = _pick_distractors(rng, pools["forms"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                if choices_look_clean(choices):
                    answer_index = choices.index(correct)
                    qid = _stable_id("manifestation_form", ref, entity, form, prompt)
                    out.append(MCQuestion(
                        id=qid,
                        prompt=prompt,
                        choices=choices,
                        answer_index=answer_index,
                        explanation=_fact_explanation("manifestation_form", ref, src_text, entity=entity, form=form),
                        ref=ref,
                        category="Bible • Manifestation",
                        difficulty="medium",
                        meta={"fact": fact, "norm": norm_text},
                    ))
        return out

    # ---------- inferred genealogy ----------
    if ftype == "ancestor_of":
        ancestor = normalize_choice_name(fact.get("ancestor"))
        descendant = normalize_choice_name(fact.get("descendant"))
        if is_good_name(ancestor) and is_good_name(descendant) and _has_grounded_genealogy(fact):
            _append_inferred_question(
                out,
                rng=rng,
                pools=pools,
                fact=fact,
                qtype="ancestor_of",
                prompt=_ancestor_prompt(rng, fact, descendant),
                correct=ancestor,
                explanation=_genealogy_explanation("ancestor_of", ancestor, descendant, fact),
                category="Bible • Inferred Genealogy",
            )
        return out

    if ftype == "descendant_of":
        descendant = normalize_choice_name(fact.get("descendant"))
        ancestor = normalize_choice_name(fact.get("ancestor"))
        if is_good_name(descendant) and is_good_name(ancestor) and _has_grounded_genealogy(fact):
            _append_inferred_question(
                out,
                rng=rng,
                pools=pools,
                fact=fact,
                qtype="descendant_of",
                prompt=_descendant_prompt(rng, fact, ancestor),
                correct=descendant,
                explanation=_genealogy_explanation("descendant_of", descendant, ancestor, fact),
                category="Bible • Inferred Genealogy",
            )
        return out

    if ftype == "sibling":
        person = normalize_choice_name(fact.get("person") or fact.get("person1"))
        sibling = normalize_choice_name(fact.get("sibling") or fact.get("person2"))
        if is_good_name(person) and is_good_name(sibling):
            _append_inferred_question(
                out,
                rng=rng,
                pools=pools,
                fact=fact,
                qtype="sibling",
                prompt=_sibling_prompt(person),
                correct=sibling,
                explanation=_sibling_explanation(person, sibling, fact),
                category="Bible • Inferred Genealogy",
            )
        return out

    # ---------- inferred dialogue graph ----------
    if ftype == "interacted_with":
        person = normalize_dialogue_name(fact.get("person") or fact.get("a"))
        other = normalize_dialogue_name(fact.get("other") or fact.get("b"))
        if is_good_dialogue_person(person) and is_good_dialogue_person(other) and fact.get("ref"):
            _append_inferred_question(
                out,
                rng=rng,
                pools=pools,
                fact=fact,
                qtype="interacted_with",
                pool_key="dialogue_people",
                prompt=_inferred_dialogue_prompt(rng, fact, person),
                correct=other,
                explanation=_inferred_explanation(f"{other} and {person} are linked through a chain of recorded speech interactions in the cited passages", fact),
                category="Bible • Inferred Dialogue",
            )
        return out

    if ftype in {"indirect_dialogue", "conversation_reach"}:
        return out

    return out


# -----------------------------
# Generate questions from many facts
# -----------------------------

def generate_questions(
    facts: List[Dict[str, Any]],
    n: Optional[int] = None,
    seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    pools = build_pools(facts)

    idxs = list(range(len(facts)))
    rng.shuffle(idxs)

    seen_ids = set()
    seen_prompt_texts = set()
    template_counts: Dict[tuple, int] = {}
    questions: List[MCQuestion] = []

    for i in idxs:
        qs = fact_to_questions(facts[i], pools, rng)
        for q in qs:
            if q.id in seen_ids:
                continue

            prompt_key = q.prompt.strip().lower()
            if prompt_key in seen_prompt_texts:
                continue

            meta_fact = q.meta.get("fact", {}) if q.meta else {}
            ftype = meta_fact.get("type", "unknown")

            if ftype == "spoke_to":
                template_key = ("spoke_to", "who_spoke_to")
            elif ftype == "parent_of":
                template_key = ("parent_of", q.prompt.split("?")[0].lower())
            else:
                template_key = (ftype, q.prompt.split("?")[0].lower())

            template_counts[template_key] = template_counts.get(template_key, 0) + 1
            template_limit = INFERRED_TEMPLATE_LIMITS.get(ftype, 25)
            if template_counts[template_key] > template_limit:
                continue

            if not choices_look_clean(q.choices):
                continue

            seen_ids.add(q.id)
            seen_prompt_texts.add(prompt_key)
            questions.append(q)

    if n is not None:
        rng.shuffle(questions)
        questions = questions[:n]

    return [q.to_dict() for q in questions]


# -----------------------------
# Trivia Royale pack export
# -----------------------------

def facts_to_trivia_pack(
    facts: List[Dict[str, Any]],
    pack_id: str,
    title: str,
    translation: str,
    n: Optional[int] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    questions = generate_questions(facts, n=n, seed=seed)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "pack_id": pack_id,
        "title": title,
        "version": 1,
        "translation": translation.upper(),
        "generated_at": now,
        "question_count": len(questions),
        "questions": [
            {
                "id": q["id"],
                "category": q.get("category", "Bible"),
                "difficulty": q.get("difficulty", "easy"),
                "question": q["prompt"],
                "choices": q["choices"],
                "answer_index": q["answer_index"],
                "explanation": q.get("explanation", ""),
                "ref": q.get("ref", ""),
                "meta": q.get("meta", {}),
            }
            for q in questions
        ],
    }
