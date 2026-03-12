import json

with open("out/parsed.jsonl") as f:
    lines = [json.loads(x) for x in f]

with open("logic/facts.pl","w") as out:
    for row in lines:
        rel = row["relation"]
        s = row["subject"].lower().replace(" ", "_")
        o = row["object"].lower().replace(" ", "_")
        out.write(f"{rel}({s},{o}).\n")