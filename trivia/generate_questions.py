import json, hashlib, random, os, sys

VEHICLE_PROPERTIES = {
    "rock": {"allowed": ["protection", "stability"], "blocked": ["material", "inanimate", "geological_age"]},
    "whirlwind": {"allowed": ["power", "awe", "uncontrollable"], "blocked": ["meteorological_identity", "material"]},
    "flame of fire": {"allowed": ["presence", "holiness", "purification"], "blocked": ["combustion_identity", "material"]}
}

HUMAN = {
    "protection":"To emphasize protection","stability":"To emphasize stability",
    "power":"To emphasize overwhelming power","awe":"To emphasize awe and majesty",
    "uncontrollable":"To emphasize uncontrollable force",
    "presence":"To emphasize divine presence","holiness":"To emphasize holiness","purification":"To emphasize purification",
    "material":"To claim God is made of matter","inanimate":"To claim God is inanimate",
    "geological_age":"To claim God is geologically ancient","meteorological_identity":"To claim God is literally a storm",
    "combustion_identity":"To claim God is literally fire"
}

def stable_id(*parts: str) -> str:
    return hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:10]

def to_instruction_jsonl(q):
    ctx = ""
    if q["type"] in ("multiple_choice","select_all") and q.get("options"):
        ctx = "Options: " + " | ".join(q["options"])
    return {"instruction": q["question"], "context": ctx, "response": q["correctAnswer"]}

def _ref_slug(ref: str) -> str:
    return ref.lower().replace(" ", "-").replace(":", "-")

def _log(msg: str) -> None:
    print(msg, file=sys.stderr)

def make_tf_non_identity(ref, source, vehicle):
    # vehicle may be None; bail early
    if not vehicle:
        return None
    return {
        "id": f"{_ref_slug(ref)}-tf-{stable_id(ref, vehicle, 'tf')}",
        "type":"true_false",
        "question": f"In {ref}, '{vehicle}' means God is literally identical to {vehicle}.",
        "options":["True","False"],
        "correctAnswer":"False",
        "source":{"ref":ref,"text":source},
        "difficulty":"easy",
        "tags":["non_identity","metaphor",vehicle.replace(" ","_")]
    }

def make_mc_from_vehicle(ref, source, vehicle):
    if not vehicle:
        return None
    props = VEHICLE_PROPERTIES.get(vehicle)
    if not props:
        return None

    correct_key = random.choice(props["allowed"])
    distract_keys = random.sample(props["blocked"], k=min(3, len(props["blocked"])))

    correct = HUMAN.get(correct_key, correct_key)
    distract = [HUMAN.get(k, k) for k in distract_keys]

    q = {
        "id": f"{_ref_slug(ref)}-mc-{stable_id(ref, vehicle, 'mc')}",
        "type":"multiple_choice",
        "question": f"In {ref}, when the text uses '{vehicle}', what is being emphasized?",
        "options":[correct] + distract,
        "correctAnswer":correct,
        "source":{"ref":ref,"text":source},
        "difficulty":"medium",
        "tags":["metaphor",vehicle.replace(" ","_")]
    }

    random.shuffle(q["options"])
    return q

def make_parent_mc(ref, source, parent, child, role="parent"):
    """
    Works for father OR mother.
    role: 'father' | 'mother' | 'parent'
    """
    if not parent or not child:
        return None

    # small demo pool; you can grow this later with real entity lists
    pool = ["Noah","Enoch","Abraham","Isaac","Jacob","Seth","Cain","Eve","Sarah","Rebekah","Rachel","Leah"]
    random.shuffle(pool)

    opts = [parent]
    for n in pool:
        if n != parent and len(opts) < 4:
            opts.append(n)
    random.shuffle(opts)

    if role == "father":
        qtext = f"In {ref}, who is said to have begotten {child}?"
        tag = "father_of"
    elif role == "mother":
        qtext = f"In {ref}, who is said to have borne {child}?"
        tag = "mother_of"
    else:
        qtext = f"In {ref}, who is named as a parent of {child}?"
        tag = "parent_of"

    return {
        "id": f"{_ref_slug(ref)}-gen-{stable_id(ref, parent, child, role)}",
        "type":"multiple_choice",
        "question": qtext,
        "options": opts,
        "correctAnswer": parent,
        "source":{"ref":ref,"text":source},
        "difficulty":"easy",
        "tags":["genealogy", tag]
    }

def generate(parsed_path: str, verses_path: str, out_dir: str):
    # Load verse text
    verse_text = {}
    with open(verses_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if isinstance(r, dict) and "ref" in r and "text" in r:
                verse_text[r["ref"]] = r["text"]

    qs = []
    stats = {
        "seen": 0,
        "metaphor": 0,
        "event_divine_speech": 0,
        "genealogy": 0,
        "added": 0,
        "skipped_bad_json": 0,
        "skipped_missing_args": 0,
        "skipped_unknown_vehicle": 0,
        "skipped_missing_parent": 0,
    }

    with open(parsed_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                stats["skipped_bad_json"] += 1
                continue

            if not isinstance(rec, dict):
                stats["skipped_bad_json"] += 1
                continue

            stats["seen"] += 1
            kind = rec.get("kind")
            ref = rec.get("ref", "UNKNOWN")
            args = rec.get("args") or {}
            if not isinstance(args, dict):
                stats["skipped_missing_args"] += 1
                continue

            source = verse_text.get(ref, rec.get("evidence", ""))

            # --- Metaphor ---
            if kind == "metaphor":
                stats["metaphor"] += 1
                v = args.get("vehicle")  # may be missing -> safe
                mc = make_mc_from_vehicle(ref, source, v)
                tf = make_tf_non_identity(ref, source, v)
                if mc:
                    qs.append(mc); stats["added"] += 1
                else:
                    if v and v not in VEHICLE_PROPERTIES:
                        stats["skipped_unknown_vehicle"] += 1
                if tf:
                    qs.append(tf); stats["added"] += 1
                continue

            # --- Event: DivineSpeech -> treat medium/form like a vehicle prompt ---
            if kind == "event" and rec.get("event_type") == "DivineSpeech":
                stats["event_divine_speech"] += 1
                med = args.get("medium") or args.get("form")
                mc = make_mc_from_vehicle(ref, source, med)
                tf = make_tf_non_identity(ref, source, med)
                if mc:
                    qs.append(mc); stats["added"] += 1
                else:
                    if med and med not in VEHICLE_PROPERTIES:
                        stats["skipped_unknown_vehicle"] += 1
                if tf:
                    qs.append(tf); stats["added"] += 1
                continue

            # --- Genealogy: father OR mother ---
            if kind == "genealogy":
                stats["genealogy"] += 1
                child = args.get("child")
                father = args.get("father")
                mother = args.get("mother")
                parent = args.get("parent")

                # prefer explicit roles if present; else fall back
                if father and child:
                    q = make_parent_mc(ref, source, father, child, role="father")
                    if q:
                        qs.append(q); stats["added"] += 1
                    continue

                if mother and child:
                    q = make_parent_mc(ref, source, mother, child, role="mother")
                    if q:
                        qs.append(q); stats["added"] += 1
                    continue

                if parent and child:
                    q = make_parent_mc(ref, source, parent, child, role=args.get("role", "parent"))
                    if q:
                        qs.append(q); stats["added"] += 1
                    continue

                stats["skipped_missing_parent"] += 1
                continue

            # other kinds ignored safely

    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "questions.game.json"), "w", encoding="utf-8") as f:
        json.dump(qs, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "questions.instruction.jsonl"), "w", encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(to_instruction_jsonl(q), ensure_ascii=False) + "\n")

    _log(f"[trivia.generate] wrote {len(qs)} questions -> {out_dir}")
    _log(f"[trivia.generate] stats: {stats}")
