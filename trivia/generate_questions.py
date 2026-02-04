import json, hashlib, random, os

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
    ctx=""
    if q["type"] in ("multiple_choice","select_all") and q.get("options"):
        ctx="Options: " + " | ".join(q["options"])
    return {"instruction": q["question"], "context": ctx, "response": q["correctAnswer"]}
def make_tf_non_identity(ref, source, vehicle):
    return {"id": f"{ref.lower().replace(' ','-').replace(':','-')}-tf-{stable_id(ref,vehicle,'tf')}",
            "type":"true_false",
            "question": f"In {ref}, '{vehicle}' means God is literally identical to {vehicle}.",
            "options":["True","False"],
            "correctAnswer":"False",
            "source":{"ref":ref,"text":source},
            "difficulty":"easy",
            "tags":["non_identity","metaphor",vehicle.replace(" ","_")]}
def make_mc_from_vehicle(ref, source, vehicle):
    props=VEHICLE_PROPERTIES.get(vehicle)
    if not props: return None
    correct_key=random.choice(props["allowed"])
    distract_keys=random.sample(props["blocked"], k=min(3,len(props["blocked"])))
    correct=HUMAN.get(correct_key, correct_key)
    distract=[HUMAN.get(k,k) for k in distract_keys]
    q={"id": f"{ref.lower().replace(' ','-').replace(':','-')}-mc-{stable_id(ref,vehicle,'mc')}",
       "type":"multiple_choice",
       "question": f"In {ref}, when the text uses '{vehicle}', what is being emphasized?",
       "options":[correct]+distract,
       "correctAnswer":correct,
       "source":{"ref":ref,"text":source},
       "difficulty":"medium",
       "tags":["metaphor",vehicle.replace(" ","_")]}
    random.shuffle(q["options"])
    return q
def make_genealogy_mc(ref, source, father, child):
    pool=["Noah","Enoch","Abraham","Isaac","Jacob","Seth","Cain","Eve"]
    random.shuffle(pool)
    opts=[father]
    for n in pool:
        if n!=father and len(opts)<4: opts.append(n)
    random.shuffle(opts)
    return {"id": f"{ref.lower().replace(' ','-').replace(':','-')}-gen-{stable_id(ref,father,child)}",
            "type":"multiple_choice",
            "question": f"In {ref}, who is said to have begotten {child}?",
            "options":opts,
            "correctAnswer":father,
            "source":{"ref":ref,"text":source},
            "difficulty":"easy",
            "tags":["genealogy"]}
def generate(parsed_path: str, verses_path: str, out_dir: str):
    verse_text={}
    with open(verses_path,"r",encoding="utf-8") as f:
        for line in f:
            r=json.loads(line); verse_text[r["ref"]]=r["text"]
    qs=[]
    with open(parsed_path,"r",encoding="utf-8") as f:
        for line in f:
            rec=json.loads(line)
            ref=rec["ref"]; source=verse_text.get(ref, rec.get("evidence",""))
            if rec["kind"]=="metaphor":
                v=rec["args"]["vehicle"]; mc=make_mc_from_vehicle(ref, source, v)
                if mc: qs += [mc, make_tf_non_identity(ref, source, v)]
            if rec["kind"]=="event" and rec.get("event_type")=="DivineSpeech":
                m=rec["args"].get("medium"); mc=make_mc_from_vehicle(ref, source, m)
                if mc: qs += [mc, make_tf_non_identity(ref, source, m)]
            if rec["kind"]=="genealogy":
                qs.append(make_genealogy_mc(ref, source, rec["args"]["father"], rec["args"]["child"]))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir,"questions.game.json"),"w",encoding="utf-8") as f:
        json.dump(qs,f,ensure_ascii=False,indent=2)
    with open(os.path.join(out_dir,"questions.instruction.jsonl"),"w",encoding="utf-8") as f:
        for q in qs:
            f.write(json.dumps(to_instruction_jsonl(q),ensure_ascii=False)+"\n")
