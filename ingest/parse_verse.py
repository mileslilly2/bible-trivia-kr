import json
from ingest.patterns import extract_relations

def main(in_path: str, out_path: str):
    with open(in_path, "r", encoding="utf-8") as f_in, open(out_path, "w", encoding="utf-8") as f_out:
        for i, line in enumerate(f_in):
            #print("READ LINE", i)
            if not line.strip():
                continue
            rec = json.loads(line)
            rels = extract_relations(rec["ref"], rec["text"])
            if rels:
                print("MATCH:", rec["ref"], rels)
            for rel in rels:
                f_out.write(json.dumps(rel, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import sys
    main(sys.argv[1], sys.argv[2])

