import os, json
from ingest.parse_verse import main as parse_main

def gen_logic(parsed_path: str, out_facts: str, rules_src: str, rules_dst: str):
    lines=["// Generated facts (demo)\n",
           ".decl begat(father:symbol, child:symbol)\n",
           ".decl event(eid:symbol)\n",
           ".decl event_type(eid:symbol, t:symbol)\n",
           ".decl agent(eid:symbol, a:symbol)\n",
           ".decl recipient(eid:symbol, r:symbol)\n",
           ".decl medium(eid:symbol, m:symbol)\n",
           ".decl metaphor(mid:symbol, source:symbol, vehicle:symbol)\n\n"]
    eid=0; mid=0
    with open(parsed_path,"r",encoding="utf-8") as f:
        for line in f:
            rec=json.loads(line)
            ref=rec["ref"].replace(" ","_").replace(":","_")
            if rec["kind"]=="genealogy":
                lines.append(f"begat(\"{rec['args']['father']}\", \"{rec['args']['child']}\").\n")
            elif rec["kind"]=="event":
                eid+=1; e=f"e{eid}_{ref}"
                lines += [f"event(\"{e}\").\n", f"event_type(\"{e}\", \"{rec['event_type']}\").\n"]
                a=rec["args"].get("agent"); r=rec["args"].get("recipient"); m=rec["args"].get("medium") or rec["args"].get("form")
                if a: lines.append(f"agent(\"{e}\", \"{a}\").\n")
                if r: lines.append(f"recipient(\"{e}\", \"{r}\").\n")
                if m: lines.append(f"medium(\"{e}\", \"{m}\").\n")
            elif rec["kind"]=="metaphor":
                mid+=1; m=f"m{mid}_{ref}"
                lines.append(f"metaphor(\"{m}\", \"{rec['args']['source']}\", \"{rec['args']['vehicle']}\").\n")
    os.makedirs(os.path.dirname(out_facts), exist_ok=True)
    with open(out_facts,"w",encoding="utf-8") as f: f.writelines(lines)
    os.makedirs(os.path.dirname(rules_dst), exist_ok=True)
    with open(rules_src,"r",encoding="utf-8") as f_in, open(rules_dst,"w",encoding="utf-8") as f_out:
        f_out.write(f_in.read())

def gen_graph_cypher(parsed_path: str, verses_path: str, out_cypher: str):
    verse_text={}
    with open(verses_path,"r",encoding="utf-8") as f:
        for line in f:
            r=json.loads(line); verse_text[r["ref"]]=r["text"]
    stmts=["// Generated load.cypher (demo)\n","MERGE (:DivineEntity {id:'God'});\n"]
    humans=set(); phenomena=set(); vehicles=set(); events=[]; metaphors=[]
    eid=0; mid=0
    with open(parsed_path,"r",encoding="utf-8") as f:
        for line in f:
            rec=json.loads(line); ref=rec["ref"]
            if rec["kind"]=="event":
                eid+=1; args=rec["args"]
                if "recipient" in args: humans.add(args["recipient"])
                if "medium" in args: phenomena.add(args["medium"])
                if "form" in args: phenomena.add(args["form"])
                events.append({"id":f"E{eid}","type":rec["event_type"],"ref":ref,"text":verse_text.get(ref,rec.get("evidence","")),"args":args})
            if rec["kind"]=="metaphor":
                mid+=1; vehicles.add(rec["args"]["vehicle"])
                metaphors.append({"id":f"M{mid}","ref":ref,"text":verse_text.get(ref,rec.get("evidence","")),"vehicle":rec["args"]["vehicle"]})
            if rec["kind"]=="genealogy":
                humans.add(rec["args"]["father"]); humans.add(rec["args"]["child"])
    for h in sorted(humans): stmts.append(f"MERGE (:Human {{id:{json.dumps(h)}}});\n")
    for p in sorted(phenomena): stmts.append(f"MERGE (:Phenomenon {{id:{json.dumps(p)}}});\n")
    for v in sorted(vehicles): stmts.append(f"MERGE (:Vehicle {{id:{json.dumps(v)}}});\n")
    for ev in events:
        stmts.append(f"MERGE (e:Event {{id:{json.dumps(ev['id'])}}}) SET e.type={json.dumps(ev['type'])}, e.ref={json.dumps(ev['ref'])}, e.text={json.dumps(ev['text'])};\n")
        if ev["args"].get("agent")=="God":
            stmts.append(f"MATCH (g:DivineEntity {{id:'God'}}),(e:Event {{id:{json.dumps(ev['id'])}}}) MERGE (g)-[:AGENT_OF]->(e);\n")
        if "recipient" in ev["args"]:
            stmts.append(f"MATCH (h:Human {{id:{json.dumps(ev['args']['recipient'])}}}),(e:Event {{id:{json.dumps(ev['id'])}}}) MERGE (e)-[:SPOKE_TO]->(h);\n")
        med=ev["args"].get("medium") or ev["args"].get("form")
        if med:
            stmts.append(f"MATCH (p:Phenomenon {{id:{json.dumps(med)}}}),(e:Event {{id:{json.dumps(ev['id'])}}}) MERGE (e)-[:APPEARED_AS]->(p);\n")
    for m in metaphors:
        stmts.append(f"MERGE (mm:Metaphor {{id:{json.dumps(m['id'])}}}) SET mm.ref={json.dumps(m['ref'])}, mm.text={json.dumps(m['text'])};\n")
        stmts.append(f"MATCH (g:DivineEntity {{id:'God'}}),(mm:Metaphor {{id:{json.dumps(m['id'])}}}) MERGE (g)-[:SOURCE_OF]->(mm);\n")
        stmts.append(f"MATCH (v:Vehicle {{id:{json.dumps(m['vehicle'])}}}),(mm:Metaphor {{id:{json.dumps(m['id'])}}}) MERGE (mm)-[:VEHICLE]->(v);\n")
        stmts.append(f"MATCH (g:DivineEntity {{id:'God'}}),(v:Vehicle {{id:{json.dumps(m['vehicle'])}}}) MERGE (g)-[:NOT_IDENTICAL_TO]->(v);\n")
    os.makedirs(os.path.dirname(out_cypher), exist_ok=True)
    with open(out_cypher,"w",encoding="utf-8") as f: f.writelines(stmts)

def run_pipeline(in_path: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    parsed=os.path.join(out_dir,"parsed.jsonl")
    parse_main(in_path, parsed)
    gen_logic(parsed, os.path.join(out_dir,"logic","facts.dl"), os.path.join("logic","rules.dl"), os.path.join(out_dir,"logic","rules.dl"))
    gen_graph_cypher(parsed, in_path, os.path.join(out_dir,"graph","load.cypher"))
    from trivia.generate_questions import generate
    generate(parsed, in_path, os.path.join(out_dir,"trivia"))

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args=ap.parse_args()
    run_pipeline(args.inp, args.out)
