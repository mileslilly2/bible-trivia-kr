# extractors/question_engine.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
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

def is_good_name(s: Optional[str]) -> bool:
    if not s:
        return False
    s = s.strip()
    if not s:
        return False
    if s in _BAD_NAMES:
        return False
    # Avoid single-letter junk, etc.
    if len(s) < 2:
        return False
    return True


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
# Loading helpers (json OR jsonl)
# -----------------------------

def load_json_or_jsonl(path: str | Path) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(str(p))

    txt = p.read_text(encoding="utf-8").lstrip()
    if not txt:
        return []

    # If it starts like a JSON array/object, treat as json.
    if txt[0] in "[{":
        data = json.loads(txt)
        # Your out/parsed.jsonl is currently a JSON array → handle it.
        if isinstance(data, list):
            return data
        return [data]

    # Otherwise treat as JSONL.
    rows: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"Bad JSONL at {p}:{lineno}: {e}") from e
    return rows


# -----------------------------
# Pools for distractors
# -----------------------------

def build_pools(facts: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    fathers, mothers, children, names = set(), set(), set(), set()

    for f in facts:
        if f.get("type") == "genealogy":
            if is_good_name(f.get("father")):
                fathers.add(f["father"])
            if is_good_name(f.get("mother")):
                mothers.add(f["mother"])
            if is_good_name(f.get("child")):
                children.add(f["child"])

        if f.get("type") == "rename":
            if is_good_name(f.get("name")):
                names.add(f["name"])

    return {
        "fathers": sorted(fathers),
        "mothers": sorted(mothers),
        "children": sorted(children),
        "names": sorted(names),
    }


def _pick_distractors(rng: random.Random, pool: List[str], correct: str, k: int) -> Optional[List[str]]:
    pool2 = [x for x in pool if x != correct]
    if len(pool2) < k:
        return None
    return rng.sample(pool2, k)


# -----------------------------
# Fact → MC questions
# -----------------------------

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

    # ---------- genealogy ----------
    if ftype == "genealogy":
        child = fact.get("child")
        father = fact.get("father")
        mother = fact.get("mother")

        if is_good_name(child) and is_good_name(father):
            # Q: Who became the father of X?
            prompt = f"Who became the father of {child}?"
            correct = father
            distractors = _pick_distractors(rng, pools["fathers"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                answer_index = choices.index(correct)
                qid = _stable_id("genealogy_father_of", ref, child, correct, prompt)
                out.append(MCQuestion(
                    id=qid,
                    prompt=prompt,
                    choices=choices,
                    answer_index=answer_index,
                    explanation=f"{ref}: {src_text}".strip(),
                    ref=ref,
                    category="Bible • Genealogy",
                    difficulty="easy",
                    meta={"fact": fact, "norm": norm_text},
                ))

        if is_good_name(child) and is_good_name(mother):
            # Q: Who gave birth to X? (your WEB pattern uses “gave birth to” a lot)
            prompt = f"Who gave birth to {child}?"
            correct = mother
            distractors = _pick_distractors(rng, pools["mothers"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                answer_index = choices.index(correct)
                qid = _stable_id("genealogy_mother_of", ref, child, correct, prompt)
                out.append(MCQuestion(
                    id=qid,
                    prompt=prompt,
                    choices=choices,
                    answer_index=answer_index,
                    explanation=f"{ref}: {src_text}".strip(),
                    ref=ref,
                    category="Bible • Genealogy",
                    difficulty="easy",
                    meta={"fact": fact, "norm": norm_text},
                ))

        return out

    # ---------- rename ----------
    # Your rename facts currently only have {"name": X}, which is not enough for strong standalone Qs.
    # So we only produce a “reference-anchored” question (high precision, low ambiguity).
    if ftype == "rename":
        name = fact.get("name")
        if is_good_name(name):
            prompt = f"In {ref}, what name is given?"
            correct = name
            distractors = _pick_distractors(rng, pools["names"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                answer_index = choices.index(correct)
                qid = _stable_id("rename_name", ref, correct, prompt)
                out.append(MCQuestion(
                    id=qid,
                    prompt=prompt,
                    choices=choices,
                    answer_index=answer_index,
                    explanation=f"{ref}: {src_text}".strip(),
                    ref=ref,
                    category="Bible • Names",
                    difficulty="easy",
                    meta={"fact": fact, "norm": norm_text},
                ))
        return out

    # ---------- violence ----------
    if ftype == "violence":
        who = fact.get("who")
        target = fact.get("target")
        if is_good_name(who) and is_good_name(target):
            prompt = f"According to {ref}, who was killed?"
            correct = target
            distractors = _pick_distractors(rng, pools["children"], correct, 3) or _pick_distractors(rng, pools["names"], correct, 3)
            if distractors:
                choices = distractors + [correct]
                rng.shuffle(choices)
                answer_index = choices.index(correct)
                qid = _stable_id("violence_target", ref, who, target, prompt)
                out.append(MCQuestion(
                    id=qid,
                    prompt=prompt,
                    choices=choices,
                    answer_index=answer_index,
                    explanation=f"{ref}: {src_text}".strip(),
                    ref=ref,
                    category="Bible • Events",
                    difficulty="medium",
                    meta={"fact": fact, "norm": norm_text},
                ))
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

    # Make deterministic-ish shuffle before expansion
    idxs = list(range(len(facts)))
    rng.shuffle(idxs)

    seen_ids = set()
    questions: List[MCQuestion] = []

    for i in idxs:
        qs = fact_to_questions(facts[i], pools, rng)
        for q in qs:
            if q.id in seen_ids:
                continue
            seen_ids.add(q.id)
            questions.append(q)

    if n is not None:
        rng.shuffle(questions)
        questions = questions[:n]

    return [q.to_dict() for q in questions]


# -----------------------------
# Trivia Royale pack export (B)
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

    # Minimal, coherent pack container (easy to adapt to your in-app schema)
    return {
        "pack_id": pack_id,
        "title": title,
        "version": 1,
        "translation": translation.upper(),
        "generated_at": now,
        "question_count": len(questions),
        "questions": [
            {
                # common Trivia Royale-ish keys:
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
