# bible-trivia-kr-min

Minimal KR pipeline: verse → relations/events/metaphor → graph (Cypher) → trivia JSON.

Run:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/batch_generate.py --in data/verses.jsonl --out out
```

Outputs:
- out/parsed.jsonl
- out/logic/facts.dl + out/logic/rules.dl
- out/graph/load.cypher
- out/trivia/questions.game.json
- out/trivia/questions.instruction.jsonl
