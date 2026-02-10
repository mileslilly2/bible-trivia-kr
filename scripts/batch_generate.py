import os
import json
import sys
from typing import Any, Dict, Iterator, Optional, Tuple, List

from ingest.parse_verse import main as parse_main


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

def write_jsonl(path: str, records: Iterator[Dict[str, Any]]) -> int:
    ensure_dir_for(path)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


# -----------------------------
# Logic (Soufflé-style facts)
# -----------------------------

def gen_logic(parsed_path: str, out_facts: str, rules_src: str, rules_dst: str) -> None:
    """
    Convert parsed KR records into a fact file. This function is schema-defensive:
    - genealogy supports father/mother/parent roles
    - events emit generic event_arg(e,k,v) so adding keys won't break logic
    - metaphors tolerate missing source/vehicle and still emit metaphor_arg(...)
    """

    lines: List[str] = [
        "// Generated facts (robot)\n",
        # Legacy demo predicates (kept for compatibility)
        ".decl begat(father:symbol, child:symbol)\n",
        ".decl bore(mother:symbol, child:symbol)\n",
        # Normalized parent model (recommended)
        ".decl parent_of(parent:symbol, child:symbol)\n",
        ".decl parent_role(parent:symbol, role:symbol)\n",
        # Events
        ".decl event(eid:symbol)\n",
        ".decl event_type(eid:symbol, t:symbol)\n",
        ".decl agent(eid:symbol, a:symbol)\n",
        ".decl recipient(eid:symbol, r:symbol)\n",
        ".decl medium(eid:symbol, m:symbol)\n",
        ".decl event_arg(eid:symbol, k:symbol, v:symbol)\n",
        # Metaphors
        ".decl metaphor(mid:symbol, source:symbol, vehicle:symbol)\n",
        ".decl metaphor_arg(mid:symbol, k:symbol, v:symbol)\n\n",
    ]

    eid = 0
    mid = 0
    counts = {"genealogy": 0, "event": 0, "metaphor": 0, "other": 0}

    for _, rec in iter_jsonl(parsed_path):
        kind = rec.get("kind")
        ref = rec.get("ref", "UNKNOWN")
        kref = ref_key(ref)
        args = rec.get("args") or {}

        if kind == "genealogy":
            counts["genealogy"] += 1
            child = args.get("child")
            father = args.get("father")
            mother = args.get("mother")
            parent = args.get("parent")
            role = args.get("role")

            if father and child:
                lines.append(f"begat({j(father)}, {j(child)}).\n")
                lines.append(f"parent_of({j(father)}, {j(child)}).\n")
                lines.append(f"parent_role({j(father)}, {j('father')}).\n")

            if mother and child:
                lines.append(f"bore({j(mother)}, {j(child)}).\n")
                lines.append(f"parent_of({j(mother)}, {j(child)}).\n")
                lines.append(f"parent_role({j(mother)}, {j('mother')}).\n")

            if parent and child:
                lines.append(f"parent_of({j(parent)}, {j(child)}).\n")
                if role:
                    lines.append(f"parent_role({j(parent)}, {j(role)}).\n")

            continue

        if kind == "event":
            counts["event"] += 1
            eid += 1
            e = f"e{eid}_{kref}"
            et = rec.get("event_type") or "Event"

            lines.append(f"event({j(e)}).\n")
            lines.append(f"event_type({j(e)}, {j(et)}).\n")

            # Prefer explicit agent; fall back to speaker/who
            a = args.get("agent") or args.get("speaker") or args.get("who")
            r = args.get("recipient")
            m = args.get("medium") or args.get("form")

            if a:
                lines.append(f"agent({j(e)}, {j(a)}).\n")
            if r:
                lines.append(f"recipient({j(e)}, {j(r)}).\n")
            if m:
                lines.append(f"medium({j(e)}, {j(m)}).\n")

            # Generic args: adding new fields won't break the logic stage
            for k, v in args.items():
                if v is None:
                    continue
                lines.append(f"event_arg({j(e)}, {j(k)}, {j(v)}).\n")

            continue

        if kind == "metaphor":
            counts["metaphor"] += 1
            mid += 1
            m_id = f"m{mid}_{kref}"

            source = args.get("source")
            vehicle = args.get("vehicle")

            # Only emit the core triple when vehicle exists; tolerate missing source.
            if vehicle:
                lines.append(f"metaphor({j(m_id)}, {j(source or 'UNKNOWN')}, {j(vehicle)}).\n")

            # Always emit metadata/args
            mtype = rec.get("metaphor_type")
            if mtype:
                lines.append(f"metaphor_arg({j(m_id)}, {j('metaphor_type')}, {j(mtype)}).\n")

            for k, v in args.items():
                if v is None:
                    continue
                lines.append(f"metaphor_arg({j(m_id)}, {j(k)}, {j(v)}).\n")

            continue

        counts["other"] += 1

    ensure_dir_for(out_facts)
    with open(out_facts, "w", encoding="utf-8") as f:
        f.writelines(lines)

    ensure_dir_for(rules_dst)
    with open(rules_src, "r", encoding="utf-8") as f_in, open(rules_dst, "w", encoding="utf-8") as f_out:
        f_out.write(f_in.read())

    log(f"[gen_logic] wrote {out_facts} counts={counts}")


# -----------------------------
# Graph (Neo4j Cypher)
# -----------------------------

def gen_graph_cypher(parsed_path: str, verses_path: str, out_cypher: str) -> None:
    """
    Convert parsed KR to a Neo4j load.cypher file. Schema-defensive:
    - genealogy supports mother/father
    - events can use agent/speaker/who
    - metaphors tolerate missing source
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
    ]

    humans = set()
    places = set()
    phenomena = set()
    vehicles = set()

    events: List[Dict[str, Any]] = []
    metaphors: List[Dict[str, Any]] = []
    parent_edges: List[Tuple[str, str, str]] = []  # (parent, child, role)

    eid = 0
    mid = 0

    for _, rec in iter_jsonl(parsed_path):
        kind = rec.get("kind")
        ref = rec.get("ref", "UNKNOWN")
        args = rec.get("args") or {}

        if kind == "genealogy":
            child = args.get("child")
            father = args.get("father")
            mother = args.get("mother")

            if father and child:
                humans.add(father); humans.add(child)
                parent_edges.append((father, child, "father"))
            if mother and child:
                humans.add(mother); humans.add(child)
                parent_edges.append((mother, child, "mother"))
            continue

        if kind == "event":
            eid += 1
            ev_id = f"E{eid}"
            et = rec.get("event_type") or "Event"

            agent = args.get("agent") or args.get("speaker") or args.get("who")
            recipient = args.get("recipient")

            if recipient and recipient not in DIVINE_IDS:
                humans.add(recipient)

            if agent and agent not in DIVINE_IDS:
                humans.add(agent)

            where = args.get("where")
            if where:
                places.add(where)

            med = args.get("medium") or args.get("form")
            if med:
                phenomena.add(med)

            events.append({
                "id": ev_id,
                "type": et,
                "ref": ref,
                "text": verse_text.get(ref, rec.get("evidence", "")),
                "args": args,
            })
            continue

        if kind == "metaphor":
            mid += 1
            m_id = f"M{mid}"
            vehicle = args.get("vehicle")
            source = args.get("source")
            mtype = rec.get("metaphor_type") or "Metaphor"

            if vehicle:
                vehicles.add(vehicle)
            if source and source not in DIVINE_IDS:
                humans.add(source)

            metaphors.append({
                "id": m_id,
                "ref": ref,
                "text": verse_text.get(ref, rec.get("evidence", "")),
                "vehicle": vehicle,
                "source": source,
                "type": mtype,
                "args": args,
            })
            continue

    # Nodes
    for h in sorted(humans):
        stmts.append(f"MERGE (:Human {{id:{j(h)}}});\n")
    for p in sorted(places):
        stmts.append(f"MERGE (:Place {{id:{j(p)}}});\n")
    for ph in sorted(phenomena):
        stmts.append(f"MERGE (:Phenomenon {{id:{j(ph)}}});\n")
    for v in sorted(vehicles):
        stmts.append(f"MERGE (:Vehicle {{id:{j(v)}}});\n")

    # Parent edges
    for parent, child, role in parent_edges:
        stmts.append(
            f"MATCH (p:Human {{id:{j(parent)}}}),(c:Human {{id:{j(child)}}}) "
            f"MERGE (p)-[:PARENT_OF {{role:{j(role)}}}]->(c);\n"
        )

    # Events
    for ev in events:
        stmts.append(
            f"MERGE (e:Event {{id:{j(ev['id'])}}}) "
            f"SET e.type={j(ev['type'])}, e.ref={j(ev['ref'])}, e.text={j(ev['text'])};\n"
        )

        args = ev["args"]
        agent = args.get("agent") or args.get("speaker") or args.get("who")
        if agent in DIVINE_IDS:
            stmts.append(
                f"MATCH (g:DivineEntity {{id:'God'}}),(e:Event {{id:{j(ev['id'])}}}) "
                f"MERGE (g)-[:AGENT_OF]->(e);\n"
            )
        elif agent:
            stmts.append(
                f"MATCH (h:Human {{id:{j(agent)}}}),(e:Event {{id:{j(ev['id'])}}}) "
                f"MERGE (h)-[:AGENT_OF]->(e);\n"
            )

        recipient = args.get("recipient")
        if recipient:
            stmts.append(
                f"MATCH (h:Human {{id:{j(recipient)}}}),(e:Event {{id:{j(ev['id'])}}}) "
                f"MERGE (e)-[:RECIPIENT]->(h);\n"
            )

        med = args.get("medium") or args.get("form")
        if med:
            stmts.append(
                f"MATCH (p:Phenomenon {{id:{j(med)}}}),(e:Event {{id:{j(ev['id'])}}}) "
                f"MERGE (e)-[:HAS_MEDIUM]->(p);\n"
            )

        where = args.get("where")
        who = args.get("who")
        if where and who:
            stmts.append(
                f"MATCH (h:Human {{id:{j(who)}}}),(pl:Place {{id:{j(where)}}}) "
                f"MERGE (h)-[:MOVED_TO]->(pl);\n"
            )

    # Metaphors
    for m in metaphors:
        stmts.append(
            f"MERGE (mm:Metaphor {{id:{j(m['id'])}}}) "
            f"SET mm.type={j(m['type'])}, mm.ref={j(m['ref'])}, mm.text={j(m['text'])};\n"
        )

        source = m.get("source")
        vehicle = m.get("vehicle")

        if source in DIVINE_IDS:
            stmts.append(
                f"MATCH (g:DivineEntity {{id:'God'}}),(mm:Metaphor {{id:{j(m['id'])}}}) "
                f"MERGE (g)-[:SOURCE_OF]->(mm);\n"
            )
        elif source:
            stmts.append(
                f"MATCH (h:Human {{id:{j(source)}}}),(mm:Metaphor {{id:{j(m['id'])}}}) "
                f"MERGE (h)-[:SOURCE_OF]->(mm);\n"
            )

        if vehicle:
            stmts.append(
                f"MATCH (v:Vehicle {{id:{j(vehicle)}}}),(mm:Metaphor {{id:{j(m['id'])}}}) "
                f"MERGE (mm)-[:VEHICLE]->(v);\n"
            )

        # Add NOT_IDENTICAL_TO only for divine source
        if source in DIVINE_IDS and vehicle:
            stmts.append(
                f"MATCH (g:DivineEntity {{id:'God'}}),(v:Vehicle {{id:{j(vehicle)}}}) "
                f"MERGE (g)-[:NOT_IDENTICAL_TO]->(v);\n"
            )

    ensure_dir_for(out_cypher)
    with open(out_cypher, "w", encoding="utf-8") as f:
        f.writelines(stmts)

    log(f"[gen_graph_cypher] wrote {out_cypher}")


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
        # old trivia expects args['father'] and args['child']
        return bool(args.get("father") and args.get("child"))

    if kind == "metaphor":
        # old trivia often expects args['source'] and args['vehicle']
        return bool(args.get("source") and args.get("vehicle"))

    if kind == "event":
        # keep events; event templates usually tolerate missing fields
        return True

    return False

def run_trivia_robust(parsed_path: str, verses_path: str, out_dir: str, strict: bool = False) -> None:
    """
    Try to generate trivia. If the trivia module crashes due to schema drift,
    retry with a filtered parsed file that matches the module's expectations.
    """
    from trivia.generate_questions import generate

    os.makedirs(out_dir, exist_ok=True)

    # Attempt 1: run on full parsed
    try:
        generate(parsed_path, verses_path, out_dir)
        log(f"[trivia] ok (full parsed) -> {out_dir}")
        return
    except Exception as e:
        log(f"[trivia] failed on full parsed: {type(e).__name__}: {e}")

    # Attempt 2: filter down to v0-safe records and retry
    filtered_path = os.path.join(out_dir, "parsed.trivia.jsonl")
    def filtered_iter() -> Iterator[Dict[str, Any]]:
        for _, rec in iter_jsonl(parsed_path):
            if _trivia_schema_v0_ok(rec):
                yield rec

    kept = write_jsonl(filtered_path, filtered_iter())
    log(f"[trivia] retry with filtered parsed ({kept} records) -> {filtered_path}")

    try:
        generate(filtered_path, verses_path, out_dir)
        log(f"[trivia] ok (filtered) -> {out_dir}")
        return
    except Exception as e:
        log(f"[trivia] failed on filtered parsed: {type(e).__name__}: {e}")
        if strict:
            raise


# -----------------------------
# Pipeline
# -----------------------------

def run_pipeline(in_path: str, out_dir: str, strict: bool = False, no_trivia: bool = False) -> None:
    os.makedirs(out_dir, exist_ok=True)

    parsed = os.path.join(out_dir, "parsed.jsonl")
    parse_main(in_path, parsed)

    gen_logic(
        parsed,
        os.path.join(out_dir, "logic", "facts.dl"),
        os.path.join("logic", "rules.dl"),
        os.path.join(out_dir, "logic", "rules.dl"),
    )

    gen_graph_cypher(parsed, in_path, os.path.join(out_dir, "graph", "load.cypher"))

    if not no_trivia:
        run_trivia_robust(parsed, in_path, os.path.join(out_dir, "trivia"), strict=strict)
    else:
        log("[trivia] skipped (--no-trivia)")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--strict", action="store_true", help="Raise if trivia fails (default: keep going)")
    ap.add_argument("--no-trivia", action="store_true", help="Skip trivia generation entirely")
    args = ap.parse_args()

    run_pipeline(args.inp, args.out, strict=args.strict, no_trivia=args.no_trivia)
