from pathlib import Path
import sys
import os
import json
import re
from collections import Counter
from typing import Any, Dict, Iterator, Optional, Tuple, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DIVINE_IDS = {"God", "Yahweh", "LORD"}


# -----------------------------
# Robot helpers
# -----------------------------

def j(s: Any) -> str:
    """
    JSON-escape any scalar into a Cypher/Datalog-safe quoted string.
    Always returns a JSON string literal (including quotes).
    """
    if s is None:
        return json.dumps("", ensure_ascii=False)
    return json.dumps(str(s), ensure_ascii=False)


def safe_loads(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except Exception:
        return None


def ref_key(ref: str) -> str:
    return ref.replace(" ", "_").replace(":", "_")


def iter_jsonl(path: str) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            rec = safe_loads(raw)
            if rec is None:
                continue
            if isinstance(rec, dict):
                yield i, rec


def ensure_dir_for(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def stage_log(stage: str, msg: str) -> None:
    log(f"[{stage}] {msg}")


def stage_gap() -> None:
    log("")


def sample_text(value: str, limit: int = 96) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _sorted_count_items(counts: Dict[str, int]) -> List[Tuple[str, int]]:
    items = [(name, count) for name, count in counts.items() if count]
    items.sort(key=lambda item: (-item[1], item[0]))
    return items


def summarize_counts(counts: Dict[str, int]) -> str:
    items = _sorted_count_items(counts)
    if not items:
        return "none"
    return " ".join(f"{name}={count}" for name, count in items)


def take_samples(records: List[Dict[str, Any]], limit: int = 3) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []
    return [dict(rec) for rec in records[:limit]]


def pick_varied_samples(records: List[Dict[str, Any]], key: str = "type", limit: int = 3) -> List[Dict[str, Any]]:
    if limit <= 0:
        return []

    samples: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for rec in records:
        label = str(rec.get(key, ""))
        if label in seen:
            continue
        samples.append(dict(rec))
        if label:
            seen.add(label)
        if len(samples) >= limit:
            return samples

    for rec in records:
        if len(samples) >= limit:
            break
        if any(sample == rec for sample in samples):
            continue
        samples.append(dict(rec))

    return samples


def format_count_lines(
    counts: Dict[str, int],
    *,
    preferred: Optional[Tuple[str, ...]] = None,
    deemphasized: Optional[Tuple[str, ...]] = None,
    include_all: bool = False,
    max_lines: int = 2,
    max_width: int = 88,
) -> List[str]:
    items = _sorted_count_items(counts)
    if not items:
        return ["none"]

    preferred = preferred or ()
    deemphasized = set(deemphasized or ())

    preferred_items = [item for item in items if item[0] in preferred and item[0] not in deemphasized]
    other_items = [item for item in items if item[0] not in preferred and item[0] not in deemphasized]
    low_signal_items = [item for item in items if item[0] in deemphasized]

    ordered = preferred_items + other_items
    if include_all:
        ordered += low_signal_items

    if not ordered:
        ordered = low_signal_items

    lines: List[str] = []
    current = ""
    for name, count in ordered:
        chunk = f"{name}={count}"
        candidate = chunk if not current else f"{current} {chunk}"
        if current and len(candidate) > max_width and len(lines) + 1 < max_lines:
            lines.append(current)
            current = chunk
            continue
        if current and len(candidate) > max_width:
            break
        current = candidate

    if current and len(lines) < max_lines:
        lines.append(current)

    return lines or ["none"]


def count_csv_rows(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8", newline="") as f:
        return sum(1 for line in f if line.strip())


def collect_csv_row_counts(out_dir: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    if not os.path.isdir(out_dir):
        return counts
    for name in sorted(os.listdir(out_dir)):
        if not name.endswith(".csv"):
            continue
        path = os.path.join(out_dir, name)
        if os.path.isfile(path):
            counts[name[:-4]] = count_csv_rows(path)
    return counts


def format_fact_sample(rec: Dict[str, Any]) -> str:
    parts = [f"type={rec.get('type', '?')}"]
    preferred_fields = (
        "speaker",
        "listener",
        "parent",
        "child",
        "killer",
        "victim",
        "traveler",
        "destination",
        "person",
        "role",
        "entity",
        "recipient",
    )
    for key in preferred_fields:
        value = rec.get(key)
        if value:
            parts.append(f"{key}={value}")
    if rec.get("ref"):
        parts.append(f"ref={rec['ref']}")
    return sample_text(" ".join(parts), limit=88)


def format_souffle_row_sample(relation: str, rec: Dict[str, Any]) -> str:
    if relation == "ancestor_of":
        return sample_text(f"ancestor_of {rec.get('ancestor', '')} -> {rec.get('descendant', '')}", limit=88)
    if relation in {"begat", "father"}:
        return sample_text(f"{relation} {rec.get('father', '')} -> {rec.get('child', '')}", limit=88)
    if relation == "event_type":
        return sample_text(f"event_type {rec.get('eid', '')} = {rec.get('event_type', '')}", limit=88)
    if relation == "agent":
        return sample_text(f"agent {rec.get('eid', '')} -> {rec.get('agent', '')}", limit=88)
    if relation == "recipient":
        return sample_text(f"recipient {rec.get('eid', '')} -> {rec.get('recipient', '')}", limit=88)
    if relation == "said":
        return sample_text(f"said {rec.get('speaker', '')} -> {rec.get('listener', '')}", limit=88)
    values = [str(value) for key, value in rec.items() if key != "type" and value not in (None, "")]
    if len(values) >= 2:
        return sample_text(f"{relation} {values[0]} -> {values[1]}", limit=88)
    if len(values) == 1:
        return sample_text(f"{relation} {values[0]}", limit=88)
    return sample_text(json.dumps(rec, ensure_ascii=False), limit=88)


def load_generic_csv_sample(path: str, relation: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", newline="") as f:
        for raw in f:
            row = raw.strip()
            if not row:
                continue
            parts = [part.strip() for part in row.split("\t")]
            if len(parts) >= 2:
                return sample_text(f"{relation} {parts[0]} -> {parts[1]}")
            return sample_text(f"{relation} {parts[0]}")
    return None


def load_souffle_samples(out_dir: str, limit: int = 3) -> List[str]:
    samples: List[str] = []
    csv_counts = collect_csv_row_counts(out_dir)
    for relation, _ in sorted(csv_counts.items(), key=lambda item: (-item[1], item[0])):
        path = os.path.join(out_dir, f"{relation}.csv")
        rows = load_souffle_relation(path, relation)
        if rows:
            samples.append(format_souffle_row_sample(relation, rows[0]))
            if len(samples) >= limit:
                return samples
            continue
        sample_row = load_generic_csv_sample(path, relation)
        if sample_row:
            samples.append(sample_row)
            if len(samples) >= limit:
                return samples
    return samples


def format_trivia_sample(pack: Dict[str, Any]) -> Optional[str]:
    questions = pack.get("questions")
    if not isinstance(questions, list) or not questions:
        return None
    first = questions[0]
    if not isinstance(first, dict):
        return sample_text(str(first))
    prompt = first.get("question") or first.get("prompt") or first.get("text")
    if prompt:
        return sample_text(str(prompt), limit=88)
    return sample_text(json.dumps(first, ensure_ascii=False), limit=88)


def write_jsonl(path: str, records: Iterator[Dict[str, Any]]) -> int:
    ensure_dir_for(path)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


SOUFFLE_RELATION_FIELDS: Dict[str, Tuple[str, ...]] = {
    "ancestor_of": ("ancestor", "descendant"),
    "descendant_of": ("descendant", "ancestor"),
    "sibling": ("person", "sibling"),
    "interacted_with": ("person", "other"),
    "indirect_dialogue": ("person", "other"),
    "conversation_reach": ("person", "reachable"),
    "begat": ("father", "child"),
    "father": ("father", "child"),
    "event": ("eid",),
    "event_type": ("eid", "event_type"),
    "said": ("speaker", "listener", "message"),
}

SOUFFLE_INFERRED_TRIVIA_RELATIONS = (
    "ancestor_of",
    "descendant_of",
    "sibling",
    "interacted_with",
    "indirect_dialogue",
    "conversation_reach",
)
SOUFFLE_RAW_COMPAT_RELATIONS = ("begat", "father", "said")
SOUFFLE_TRIVIA_RELATIONS = SOUFFLE_INFERRED_TRIVIA_RELATIONS + SOUFFLE_RAW_COMPAT_RELATIONS
SOUFFLE_TRIVIA_CAPS = {
    "ancestor_of": 300,
    "descendant_of": 300,
    "sibling": 200,
}
SOUFFLE_DIALOGUE_TRIVIA_CAP = 300
SOUFFLE_CALL_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\((.*)\)\s*$")


def _split_souffle_args(args_src: str) -> List[str]:
    args: List[str] = []
    current: List[str] = []
    in_quotes = False
    escape = False

    for ch in args_src:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if ch == '"':
            current.append(ch)
            in_quotes = not in_quotes
            continue
        if ch == "," and not in_quotes:
            args.append("".join(current).strip())
            current = []
            continue
        current.append(ch)

    args.append("".join(current).strip())
    return args


def _parse_souffle_value(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        try:
            return json.loads(raw)
        except Exception:
            return raw[1:-1]
    return raw


def _parse_souffle_relation_line(line: str, relation: str) -> Optional[List[str]]:
    stripped = line.strip()
    if not stripped:
        return None

    match = SOUFFLE_CALL_RE.match(stripped.rstrip("."))
    if match:
        found_relation, args_src = match.groups()
        if found_relation != relation:
            return None
        return [_parse_souffle_value(part) for part in _split_souffle_args(args_src)]

    if "\t" in stripped:
        return [part.strip() for part in stripped.split("\t")]

    return [stripped]


def load_souffle_relation(path: str, relation: str) -> List[Dict[str, Any]]:
    fields = SOUFFLE_RELATION_FIELDS.get(relation)
    if not fields or not os.path.exists(path):
        return []

    records: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        for raw in f:
            values = _parse_souffle_relation_line(raw, relation)
            if values is None:
                continue
            if len(values) < len(fields):
                values += [""] * (len(fields) - len(values))
            elif len(values) > len(fields):
                values = values[: len(fields)]
            rec: Dict[str, Any] = {"type": relation}
            for field, value in zip(fields, values):
                rec[field] = value
            records.append(rec)
    return records


def _souffle_trivia_fact(rec: Dict[str, Any], relation: str) -> Dict[str, Any]:
    fact = dict(rec)
    fact.update({
        "type": relation,
        "ref": "",
        "text": "",
        "norm": "",
        "source": "souffle",
    })
    return fact


def load_souffle_trivia_facts(out_dir: str) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    facts: List[Dict[str, Any]] = []
    counts: Counter[str] = Counter()
    dialogue_loaded = 0

    for relation in SOUFFLE_INFERRED_TRIVIA_RELATIONS:
        csv_path = os.path.join(out_dir, f"{relation}.csv")
        rows = load_souffle_relation(csv_path, relation)
        if not rows:
            continue

        cap = SOUFFLE_TRIVIA_CAPS.get(relation)
        if relation in {"interacted_with", "indirect_dialogue", "conversation_reach"}:
            remaining = max(SOUFFLE_DIALOGUE_TRIVIA_CAP - dialogue_loaded, 0)
            cap = remaining if cap is None else min(cap, remaining)
        selected = rows[:cap] if cap is not None else rows

        for rec in selected:
            facts.append(_souffle_trivia_fact(rec, relation))
            counts[relation] += 1

        if relation in {"interacted_with", "indirect_dialogue", "conversation_reach"}:
            dialogue_loaded += len(selected)

    for relation in SOUFFLE_RAW_COMPAT_RELATIONS:
        csv_path = os.path.join(out_dir, f"{relation}.csv")
        for rec in load_souffle_relation(csv_path, relation):
            # Translate supported inferred relations into the existing
            # extracted-fact schema expected by question_engine.
            if relation in {"father", "begat"}:
                father = rec.get("father")
                child = rec.get("child")
                if father and child:
                    facts.append({
                        "type": "parent_of",
                        "parent": father,
                        "child": child,
                        "parent_gender": "male",
                        "ref": "",
                        "text": "",
                        "norm": "",
                        "source": "souffle",
                    })
                    counts[relation] += 1
            elif relation == "said":
                speaker = rec.get("speaker")
                listener = rec.get("listener")
                if speaker and listener:
                    facts.append({
                        "type": "spoke_to",
                        "speaker": speaker,
                        "listener": listener,
                        "ref": "",
                        "text": "",
                        "norm": "",
                        "source": "souffle",
                    })
                    counts[relation] += 1

    return facts, dict(counts)


def count_graph_edges_in_cypher(path: str) -> int:
    if not os.path.exists(path):
        return 0
    total = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            total += line.count("[:")
    return total


# -----------------------------
# Logic (Soufflé-style facts)
# -----------------------------

def gen_logic(parsed_path: str, out_facts: str, rules_src: str, rules_dst: str) -> Dict[str, Any]:
    """
    Convert normalized extracted facts into a Soufflé-style fact file.
    Supports:
      - parent_of
      - rename
      - killed
      - spoke_to
      - traveled
      - role
      - appeared_to
      - manifestation
    """

    lines: List[str] = [
        "// Generated facts\n",
    ]

    counts = {
        "parent_of": 0,
        "rename": 0,
        "killed": 0,
        "spoke_to": 0,
        "traveled": 0,
        "role": 0,
        "appeared_to": 0,
        "manifestation": 0,
        "other": 0,
    }

    for _, rec in iter_jsonl(parsed_path):
        ftype = rec.get("type")
        ref = rec.get("ref", "UNKNOWN")

        if ftype == "parent_of":
            counts["parent_of"] += 1
            parent = rec.get("parent")
            child = rec.get("child")
            gender = rec.get("parent_gender")
            if parent and child:
                lines.append(f"parent_of({j(parent)}, {j(child)}).\n")
                lines.append(f"fact_ref({j('parent_of')}, {j(parent)}, {j(child)}, {j(ref)}).\n")
            if parent and gender:
                lines.append(f"parent_gender({j(parent)}, {j(gender)}).\n")
            continue

        if ftype == "rename":
            counts["rename"] += 1
            name = rec.get("name")
            if name:
                lines.append(f"renamed_to({j(ref)}, {j(name)}).\n")
                lines.append(f"fact_ref({j('rename')}, {j(ref)}, {j(name)}, {j(ref)}).\n")
            continue

        if ftype == "killed":
            counts["killed"] += 1
            killer = rec.get("killer")
            victim = rec.get("victim")
            if killer and victim:
                lines.append(f"killed({j(killer)}, {j(victim)}).\n")
                lines.append(f"fact_ref({j('killed')}, {j(killer)}, {j(victim)}, {j(ref)}).\n")
            continue

        if ftype == "spoke_to":
            counts["spoke_to"] += 1
            speaker = rec.get("speaker")
            listener = rec.get("listener")
            if speaker and listener:
                lines.append(f"spoke_to({j(speaker)}, {j(listener)}).\n")
                lines.append(f"fact_ref({j('spoke_to')}, {j(speaker)}, {j(listener)}, {j(ref)}).\n")
            continue

        if ftype == "traveled":
            counts["traveled"] += 1
            traveler = rec.get("traveler")
            source = rec.get("source")
            destination = rec.get("destination")
            if traveler and destination:
                lines.append(f"traveled_to({j(traveler)}, {j(destination)}).\n")
                lines.append(f"fact_ref({j('traveled_to')}, {j(traveler)}, {j(destination)}, {j(ref)}).\n")
            if traveler and source and destination:
                lines.append(f"traveled_from_to({j(traveler)}, {j(source)}, {j(destination)}).\n")
            continue

        if ftype == "role":
            counts["role"] += 1
            person = rec.get("person")
            role_name = rec.get("role")
            realm = rec.get("realm")
            if person and role_name:
                lines.append(f"role({j(person)}, {j(role_name)}).\n")
                lines.append(f"fact_ref({j('role')}, {j(person)}, {j(role_name)}, {j(ref)}).\n")
            if person and realm:
                lines.append(f"reign_realm({j(person)}, {j(realm)}).\n")
            continue

        if ftype == "appeared_to":
            counts["appeared_to"] += 1
            entity = rec.get("entity")
            recipient = rec.get("recipient")
            if entity and recipient:
                lines.append(f"appeared_to({j(entity)}, {j(recipient)}).\n")
                lines.append(f"fact_ref({j('appeared_to')}, {j(entity)}, {j(recipient)}, {j(ref)}).\n")
            continue

        if ftype == "manifestation":
            counts["manifestation"] += 1
            entity = rec.get("entity")
            form = rec.get("form")
            if entity and form:
                lines.append(f"manifestation({j(entity)}, {j(form)}).\n")
                lines.append(f"fact_ref({j('manifestation')}, {j(entity)}, {j(form)}, {j(ref)}).\n")
            continue

        counts["other"] += 1

    ensure_dir_for(out_facts)
    with open(out_facts, "w", encoding="utf-8") as f:
        f.writelines(lines)

   # Skip copying rules since the project now uses modular logic files
    if rules_src and rules_dst:
        ensure_dir_for(rules_dst)
        with open(rules_src, "r", encoding="utf-8") as f_in, open(rules_dst, "w", encoding="utf-8") as f_out:
            f_out.write(f_in.read())

    return {
        "facts_path": out_facts,
        "rules_path": rules_dst if rules_src and rules_dst else None,
        "counts": counts,
    }


# -----------------------------
# Graph (Neo4j Cypher)
# -----------------------------

def gen_graph_cypher(parsed_path: str, verses_path: str, out_cypher: str) -> Dict[str, Any]:
    """
    Convert normalized extracted facts into a Neo4j load.cypher file.

    Supported fact types:
      - parent_of
      - rename
      - killed
      - spoke_to
      - traveled
      - role
      - appeared_to
      - manifestation
    """

    verse_text: Dict[str, str] = {}
    for _, r in iter_jsonl(verses_path):
        ref = r.get("ref")
        txt = r.get("text")
        if ref and txt:
            verse_text[ref] = txt

    stmts: List[str] = [
        "// Generated load.cypher (robot)\n",
        "MERGE (:DivineEntity {id:'God'});\n",
        "MERGE (:DivineEntity {id:'Yahweh'});\n",
        "MERGE (:DivineEntity {id:'LORD'});\n",
    ]

    humans = set()
    places = set()
    roles = set()
    names = set()
    forms = set()

    parent_edges: List[Tuple[str, str, str, str]] = []
    kill_edges: List[Tuple[str, str, str]] = []
    speech_edges: List[Tuple[str, str, str]] = []
    travel_edges: List[Tuple[str, Optional[str], str, str]] = []
    role_edges: List[Tuple[str, str, Optional[str], str]] = []
    rename_facts: List[Tuple[str, str]] = []
    appearance_edges: List[Tuple[str, str, str]] = []
    manifestation_edges: List[Tuple[str, str, str]] = []

    for _, rec in iter_jsonl(parsed_path):
        ftype = rec.get("type")
        ref = rec.get("ref", "UNKNOWN")

        if ftype == "parent_of":
            parent = rec.get("parent")
            child = rec.get("child")
            gender = rec.get("parent_gender")
            if parent and child:
                humans.add(parent)
                humans.add(child)
                parent_edges.append((parent, child, gender or "", ref))
            continue

        if ftype == "rename":
            name = rec.get("name")
            if name:
                names.add(name)
                rename_facts.append((ref, name))
            continue

        if ftype == "killed":
            killer = rec.get("killer")
            victim = rec.get("victim")
            if killer and victim:
                if killer not in DIVINE_IDS:
                    humans.add(killer)
                if victim not in DIVINE_IDS:
                    humans.add(victim)
                kill_edges.append((killer, victim, ref))
            continue

        if ftype == "spoke_to":
            speaker = rec.get("speaker")
            listener = rec.get("listener")
            if speaker and listener:
                if speaker not in DIVINE_IDS:
                    humans.add(speaker)
                if listener not in DIVINE_IDS:
                    humans.add(listener)
                speech_edges.append((speaker, listener, ref))
            continue

        if ftype == "traveled":
            traveler = rec.get("traveler")
            source = rec.get("source")
            destination = rec.get("destination")
            if traveler:
                if traveler not in DIVINE_IDS:
                    humans.add(traveler)
            if source:
                places.add(source)
            if destination:
                places.add(destination)
            if traveler and destination:
                travel_edges.append((traveler, source, destination, ref))
            continue

        if ftype == "role":
            person = rec.get("person")
            role_name = rec.get("role")
            realm = rec.get("realm")
            if person and person not in DIVINE_IDS:
                humans.add(person)
            if role_name:
                roles.add(role_name)
            if realm:
                places.add(realm)
            if person and role_name:
                role_edges.append((person, role_name, realm, ref))
            continue

        if ftype == "appeared_to":
            entity = rec.get("entity")
            recipient = rec.get("recipient")
            if entity and recipient:
                if entity not in DIVINE_IDS:
                    humans.add(entity)
                if recipient not in DIVINE_IDS:
                    humans.add(recipient)
                appearance_edges.append((entity, recipient, ref))
            continue

        if ftype == "manifestation":
            entity = rec.get("entity")
            form = rec.get("form")
            if entity and form:
                if entity not in DIVINE_IDS:
                    humans.add(entity)
                forms.add(form)
                manifestation_edges.append((entity, form, ref))
            continue

    for h in sorted(humans):
        stmts.append(f"MERGE (:Human {{id:{j(h)}}});\n")
    for p in sorted(places):
        stmts.append(f"MERGE (:Place {{id:{j(p)}}});\n")
    for r in sorted(roles):
        stmts.append(f"MERGE (:Role {{id:{j(r)}}});\n")
    for n in sorted(names):
        stmts.append(f"MERGE (:Name {{id:{j(n)}}});\n")
    for form in sorted(forms):
        stmts.append(f"MERGE (:ManifestationForm {{id:{j(form)}}});\n")

    all_refs = set()
    for _, _, _, ref in parent_edges:
        all_refs.add(ref)
    for ref, _ in rename_facts:
        all_refs.add(ref)
    for _, _, ref in kill_edges:
        all_refs.add(ref)
    for _, _, ref in speech_edges:
        all_refs.add(ref)
    for _, _, _, ref in travel_edges:
        all_refs.add(ref)
    for _, _, _, ref in role_edges:
        all_refs.add(ref)
    for _, _, ref in appearance_edges:
        all_refs.add(ref)
    for _, _, ref in manifestation_edges:
        all_refs.add(ref)

    for ref in sorted(all_refs):
        stmts.append(
            f"MERGE (v:Verse {{id:{j(ref)}}}) "
            f"SET v.text={j(verse_text.get(ref, ''))};\n"
        )

    for parent, child, gender, ref in parent_edges:
        props = f"ref:{j(ref)}"
        if gender:
            props += f", parent_gender:{j(gender)}"
        stmts.append(
            f"MATCH (p:Human {{id:{j(parent)}}}),(c:Human {{id:{j(child)}}}),(v:Verse {{id:{j(ref)}}}) "
            f"MERGE (p)-[:PARENT_OF {{{props}}}]->(c) "
            f"MERGE (p)-[:MENTIONED_IN]->(v) "
            f"MERGE (c)-[:MENTIONED_IN]->(v);\n"
        )

    for ref, name in rename_facts:
        stmts.append(
            f"MATCH (n:Name {{id:{j(name)}}}),(v:Verse {{id:{j(ref)}}}) "
            f"MERGE (v)-[:ASSIGNS_NAME]->(n);\n"
        )

    for killer, victim, ref in kill_edges:
        killer_match = f"(g:DivineEntity {{id:{j(killer)}}})" if killer in DIVINE_IDS else f"(k:Human {{id:{j(killer)}}})"
        victim_match = f"(g2:DivineEntity {{id:{j(victim)}}})" if victim in DIVINE_IDS else f"(vct:Human {{id:{j(victim)}}})"
        killer_var = "g" if killer in DIVINE_IDS else "k"
        victim_var = "g2" if victim in DIVINE_IDS else "vct"

        stmts.append(
            f"MATCH {killer_match},{victim_match},(v:Verse {{id:{j(ref)}}}) "
            f"MERGE ({killer_var})-[:KILLED {{ref:{j(ref)}}}]->({victim_var}) "
            f"MERGE ({killer_var})-[:MENTIONED_IN]->(v) "
            f"MERGE ({victim_var})-[:MENTIONED_IN]->(v);\n"
        )

    for speaker, listener, ref in speech_edges:
        speaker_match = f"(g:DivineEntity {{id:{j(speaker)}}})" if speaker in DIVINE_IDS else f"(s:Human {{id:{j(speaker)}}})"
        listener_match = f"(g2:DivineEntity {{id:{j(listener)}}})" if listener in DIVINE_IDS else f"(l:Human {{id:{j(listener)}}})"
        speaker_var = "g" if speaker in DIVINE_IDS else "s"
        listener_var = "g2" if listener in DIVINE_IDS else "l"

        stmts.append(
            f"MATCH {speaker_match},{listener_match},(v:Verse {{id:{j(ref)}}}) "
            f"MERGE ({speaker_var})-[:SPOKE_TO {{ref:{j(ref)}}}]->({listener_var}) "
            f"MERGE ({speaker_var})-[:MENTIONED_IN]->(v) "
            f"MERGE ({listener_var})-[:MENTIONED_IN]->(v);\n"
        )

    for traveler, source, destination, ref in travel_edges:
        traveler_match = f"(g:DivineEntity {{id:{j(traveler)}}})" if traveler in DIVINE_IDS else f"(t:Human {{id:{j(traveler)}}})"
        traveler_var = "g" if traveler in DIVINE_IDS else "t"

        if source:
            stmts.append(
                f"MATCH {traveler_match},(src:Place {{id:{j(source)}}}),(dst:Place {{id:{j(destination)}}}),(v:Verse {{id:{j(ref)}}}) "
                f"MERGE ({traveler_var})-[:TRAVELED_FROM {{ref:{j(ref)}}}]->(src) "
                f"MERGE ({traveler_var})-[:TRAVELED_TO {{ref:{j(ref)}}}]->(dst) "
                f"MERGE ({traveler_var})-[:MENTIONED_IN]->(v);\n"
            )
        else:
            stmts.append(
                f"MATCH {traveler_match},(dst:Place {{id:{j(destination)}}}),(v:Verse {{id:{j(ref)}}}) "
                f"MERGE ({traveler_var})-[:TRAVELED_TO {{ref:{j(ref)}}}]->(dst) "
                f"MERGE ({traveler_var})-[:MENTIONED_IN]->(v);\n"
            )

    for person, role_name, realm, ref in role_edges:
        person_match = f"(g:DivineEntity {{id:{j(person)}}})" if person in DIVINE_IDS else f"(p:Human {{id:{j(person)}}})"
        person_var = "g" if person in DIVINE_IDS else "p"

        if realm:
            stmts.append(
                f"MATCH {person_match},(r:Role {{id:{j(role_name)}}}),(pl:Place {{id:{j(realm)}}}),(v:Verse {{id:{j(ref)}}}) "
                f"MERGE ({person_var})-[:HAS_ROLE {{ref:{j(ref)}}}]->(r) "
                f"MERGE ({person_var})-[:REIGNED_OVER {{ref:{j(ref)}}}]->(pl) "
                f"MERGE ({person_var})-[:MENTIONED_IN]->(v);\n"
            )
        else:
            stmts.append(
                f"MATCH {person_match},(r:Role {{id:{j(role_name)}}}),(v:Verse {{id:{j(ref)}}}) "
                f"MERGE ({person_var})-[:HAS_ROLE {{ref:{j(ref)}}}]->(r) "
                f"MERGE ({person_var})-[:MENTIONED_IN]->(v);\n"
            )

    for entity, recipient, ref in appearance_edges:
        entity_match = f"(g:DivineEntity {{id:{j(entity)}}})" if entity in DIVINE_IDS else f"(e:Human {{id:{j(entity)}}})"
        rec_match = f"(g2:DivineEntity {{id:{j(recipient)}}})" if recipient in DIVINE_IDS else f"(r:Human {{id:{j(recipient)}}})"
        entity_var = "g" if entity in DIVINE_IDS else "e"
        rec_var = "g2" if recipient in DIVINE_IDS else "r"

        stmts.append(
            f"MATCH {entity_match},{rec_match},(v:Verse {{id:{j(ref)}}}) "
            f"MERGE ({entity_var})-[:APPEARED_TO {{ref:{j(ref)}}}]->({rec_var}) "
            f"MERGE ({entity_var})-[:MENTIONED_IN]->(v) "
            f"MERGE ({rec_var})-[:MENTIONED_IN]->(v);\n"
        )

    for entity, form, ref in manifestation_edges:
        entity_match = f"(g:DivineEntity {{id:{j(entity)}}})" if entity in DIVINE_IDS else f"(e:Human {{id:{j(entity)}}})"
        entity_var = "g" if entity in DIVINE_IDS else "e"

        stmts.append(
            f"MATCH {entity_match},(mf:ManifestationForm {{id:{j(form)}}}),(v:Verse {{id:{j(ref)}}}) "
            f"MERGE ({entity_var})-[:MANIFESTED_AS {{ref:{j(ref)}}}]->(mf) "
            f"MERGE ({entity_var})-[:MENTIONED_IN]->(v);\n"
        )

    ensure_dir_for(out_cypher)
    with open(out_cypher, "w", encoding="utf-8") as f:
        f.writelines(stmts)

    return {
        "cypher_path": out_cypher,
        "edge_count": count_graph_edges_in_cypher(out_cypher),
    }


# -----------------------------
# Trivia adapter (robust wrapper around brittle generator)
# -----------------------------

def _trivia_schema_v0_ok(rec: Dict[str, Any]) -> bool:
    """
    Conservative filter for the existing trivia generator.
    This avoids KeyErrors in trivia/generate_questions.py by only passing
    records that match its historical assumptions.
    """
    kind = rec.get("kind")
    args = rec.get("args") or {}

    if kind == "genealogy":
        return bool(args.get("father") and args.get("child"))

    if kind == "metaphor":
        return bool(args.get("source") and args.get("vehicle"))

    if kind == "event":
        return True

    return False


def run_trivia_robust(
    parsed_path: str,
    verses_path: str,
    out_dir: str,
    strict: bool = False,
    translation: str = "WEB",
) -> Dict[str, Any]:
    """
    Generate trivia directly from the normalized extracted facts using the new
    extractors/question_engine.py path.
    """
    from extractors.question_engine import load_json_or_jsonl, facts_to_trivia_pack

    os.makedirs(out_dir, exist_ok=True)

    try:
        pipeline_out_dir = str(Path(out_dir).resolve().parent)
        parsed_facts = load_json_or_jsonl(parsed_path)
        souffle_facts, souffle_counts = load_souffle_trivia_facts(pipeline_out_dir)
        facts = parsed_facts + souffle_facts

        pack = facts_to_trivia_pack(
            facts=facts,
            pack_id=f"bible-{translation.lower()}-pack",
            title=f"Bible Trivia Pack ({translation.upper()})",
            translation=translation,
            n=None,
            seed=42,
        )

        inferred_question_count = 0
        for question in pack.get("questions", []):
            meta = question.get("meta") if isinstance(question, dict) else None
            fact = meta.get("fact") if isinstance(meta, dict) else None
            if isinstance(fact, dict) and fact.get("source") == "souffle":
                inferred_question_count += 1

        out_path = os.path.join(out_dir, "trivia_pack.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)

        return {
            "out_path": out_path,
            "question_count": pack.get("question_count", 0),
            "inferred_question_count": inferred_question_count,
            "inferred_fact_counts": souffle_counts,
            "pack": pack,
            "used_souffle": bool(souffle_facts),
            "source_dir": pipeline_out_dir if souffle_facts else parsed_path,
        }

    except Exception as e:
        stage_log("trivia", f"failed {type(e).__name__}: {e}")
        if strict:
            raise
    from extractors.question_engine import load_json_or_jsonl, facts_to_trivia_pack

    os.makedirs(out_dir, exist_ok=True)

    facts = load_json_or_jsonl(parsed_path)

    pack = facts_to_trivia_pack(
        facts=facts,
        pack_id="bible-pack",
        title="Bible Trivia Pack",
        translation="WEB",
        n=None,
        seed=42,
    )

    out_path = os.path.join(out_dir, "trivia_pack.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2)

    return {
        "out_path": out_path,
        "question_count": pack.get("question_count", 0),
        "pack": pack,
        "used_souffle": False,
        "source_dir": parsed_path,
    }
# -----------------------------
# Pipeline
# -----------------------------

def run_pipeline(
    in_path: str,
    out_dir: str,
    strict: bool = False,
    no_trivia: bool = False,
    translation: str = "WEB",
    verbose: bool = False,
) -> None:
    from extractors.bible_rule_engine import extract_facts

    os.makedirs(out_dir, exist_ok=True)

    translation = translation.upper()
    stage_log("pipeline", f"input={in_path} out={out_dir} translation={translation}")
    stage_gap()

    parsed = os.path.join(out_dir, "parsed.jsonl")
    drops = os.path.join(out_dir, "drops.jsonl")

    all_facts: List[Dict[str, Any]] = []
    all_drops: List[Dict[str, Any]] = []
    fact_counts: Counter[str] = Counter()
    for _, row in iter_jsonl(in_path):
        ref = row.get("ref")
        text = row.get("text", "")
        if not ref or not text:
            continue

        facts, drop_rows = extract_facts(ref, text, translation=translation)

        norm = " ".join(str(text).split())

        for fact in facts:
            fact["text"] = text
            fact["norm"] = norm
            fact["translation"] = translation
            all_facts.append(fact)
            fact_counts[str(fact.get("type", "unknown"))] += 1

        for drop in drop_rows:
            drop["text"] = text
            drop["norm"] = norm
            drop["translation"] = translation
            all_drops.append(drop)

    ensure_dir_for(parsed)
    with open(parsed, "w", encoding="utf-8") as f:
        for rec in all_facts:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    ensure_dir_for(drops)
    with open(drops, "w", encoding="utf-8") as f:
        for rec in all_drops:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    stage_log("extract", f"wrote {parsed} facts={len(all_facts)} drops={len(all_drops)}")
    stage_log("extract", f"drops={drops}")
    for line in format_count_lines(dict(fact_counts), include_all=verbose):
        stage_log("extract", line)
    if verbose:
        for sample_fact in pick_varied_samples(all_facts, key="type", limit=3):
            stage_log("extract", f"sample fact: {format_fact_sample(sample_fact)}")

    stage_gap()
    logic_meta = gen_logic(
        parsed,
        os.path.join(out_dir, "logic", "facts.dl"),
        None,
        None,
    )
    stage_log("logic", f"wrote {logic_meta['facts_path']}")
    for line in format_count_lines(logic_meta["counts"], deemphasized=("other",), include_all=verbose):
        stage_log("logic", line)

    stage_gap()
    graph_meta = gen_graph_cypher(parsed, in_path, os.path.join(out_dir, "graph", "load.cypher"))
    stage_log("graph", f"wrote {graph_meta['cypher_path']} edges={graph_meta['edge_count']}")

    csv_counts = collect_csv_row_counts(out_dir)
    inferred_edges = sum(csv_counts.values())
    if csv_counts:
        stage_gap()
        stage_log("souffle", f"using inferred outputs from {out_dir}/")
        for line in format_count_lines(
            csv_counts,
            preferred=(
                "ancestor_of",
                "descendant_of",
                "indirect_dialogue",
                "interacted_with",
                "sibling",
                "father",
                "begat",
                "participant",
            ),
            deemphasized=("fact_ref",),
            include_all=verbose,
        ):
            stage_log("souffle", line)
        if verbose and csv_counts.get("fact_ref"):
            stage_log("souffle", f"debug fact_ref={csv_counts['fact_ref']}")
        if verbose:
            for sample_row in load_souffle_samples(out_dir, limit=3):
                stage_log("souffle", f"sample row: {sample_row}")
    else:
        stage_gap()
        stage_log("souffle", "inferred outputs not found, falling back to parsed facts")

    trivia_count = 0
    if not no_trivia:
        stage_gap()
        trivia_meta = run_trivia_robust(
            parsed,
            in_path,
            os.path.join(out_dir, "trivia"),
            strict=strict,
            translation=translation,
        )
        trivia_count = trivia_meta["question_count"]
        source_label = "parsed facts + souffle" if trivia_meta["used_souffle"] else "parsed facts"
        inferred_counts = trivia_meta.get("inferred_fact_counts", {})
        if inferred_counts:
            stage_log("trivia", f"inferred facts loaded {summarize_counts(inferred_counts)}")
        if trivia_meta.get("inferred_question_count"):
            stage_log("trivia", f"inferred questions added={trivia_meta['inferred_question_count']}")
        stage_log("trivia", f"source={source_label} path={trivia_meta['source_dir']}")
        stage_log("trivia", f"wrote {trivia_meta['out_path']} questions={trivia_count}")
        if verbose:
            trivia_sample = format_trivia_sample(trivia_meta["pack"])
            if trivia_sample:
                stage_log("trivia", f"sample question: {trivia_sample}")
    else:
        stage_gap()
        stage_log("trivia", "skipped (--no-trivia)")

    stage_gap()
    stage_log(
        "summary",
        f"Bible text -> {len(all_facts)} facts -> {inferred_edges} symbolic relations -> {trivia_count} trivia questions",
    )


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--strict", action="store_true", help="Raise if trivia fails (default: keep going)")
    ap.add_argument("--no-trivia", action="store_true", help="Skip trivia generation entirely")
    ap.add_argument("--translation", default="WEB", choices=["WEB", "KJV"])
    ap.add_argument("--verbose", action="store_true", help="Show sample facts and sample generated rows")
    args = ap.parse_args()

    run_pipeline(
        args.inp,
        args.out,
        strict=args.strict,
        no_trivia=args.no_trivia,
        translation=args.translation,
        verbose=args.verbose,
    )
