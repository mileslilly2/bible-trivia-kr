

# bible-trivia-kr-min

This repository implements a lightweight knowledge-engineering pipeline
that converts Bible text into reusable structured knowledge using
pattern extraction, Datalog inference (Soufflé), and graph projection.

The system extracts normalized facts from verse text, derives additional
relations through logic rules, and exports the resulting knowledge to
graph databases and dataset formats.

## Purpose

The project exists to turn unstructured Bible verses into reusable structured knowledge:

- entity and relation facts such as parentage, speech, travel, killing, roles, and divine appearances
- logic-friendly relations for Souffle Datalog inference
- graph-friendly edges for Neo4j import
- question-ready records for trivia pack export

In practice, the system is trying to answer a larger question: how do you extract durable Bible knowledge from verse text once, then reuse it across logic, graph, and quiz applications?

## High-Level Architecture

The repository has four main layers:

1. Text ingestion and extraction
   - Translation-specific regex extractors read verse text and emit normalized fact records.
   - Current extraction coverage lives mainly in [`extractors/patterns_web.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/patterns_web.py) and [`extractors/patterns_kjv.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/patterns_kjv.py).

2. Knowledge representation
   - Extracted facts are serialized as JSON/JSONL and also converted into Souffle-style `.dl` fact files.
   - The canonical Souffle schema is in [`logic/schema.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/schema.dl).
   - Rule modules in [`logic/`](/home/miles/Documents/bible-trivia-kr-min/logic) add inference over genealogy, dialogue, events, travel, kingship, prophets, theophanies, and locations.

3. Graph projection
   - The same extracted facts are rendered as a Neo4j `load.cypher` script.
   - This produces graph nodes such as `Human`, `Place`, `Role`, `Verse`, `DivineEntity`, and `ManifestationForm`, plus typed edges like `PARENT_OF`, `SPOKE_TO`, `TRAVELED_TO`, `HAS_ROLE`, and `APPEARED_TO`.

4. Trivia generation
   - Structured facts are turned into multiple-choice questions.
   - The project can export a JSON trivia pack and a SQLite pack database suitable for downstream game or content systems.

## End-to-End Flow

The intended flow is:

`verses.jsonl -> extracted facts -> Souffle facts/rules -> inferred relations -> graph/trivia exports`

Concretely:

1. Verse input
   - Input verses are JSONL records with at least `ref` and `text`.
   - Example source: [`data/verses.jsonl`](/home/miles/Documents/bible-trivia-kr-min/data/verses.jsonl).

2. Fact extraction
   - [`scripts/run_extraction.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/run_extraction.py) and [`scripts/batch_generate.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/batch_generate.py) call [`extractors/bible_rule_engine.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/bible_rule_engine.py).
   - The rule engine loads a translation-specific extractor set and de-duplicates facts.
   - Output facts include types like:
     - `parent_of`
     - `rename`
     - `spoke_to`
     - `killed`
     - `traveled`
     - `role`
     - `appeared_to`
     - `manifestation`

3. Normalized fact output
   - The pipeline writes extracted facts to `out/parsed.jsonl` and rejected candidates to `out/drops.jsonl`.
   - Each fact carries provenance such as verse reference, source pattern, original text, and normalized text.

4. Souffle-style export
   - [`scripts/batch_generate.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/batch_generate.py) converts parsed facts into Datalog facts like `parent_of(...)`, `spoke_to(...)`, `traveled_to(...)`, `role(...)`, and `appeared_to(...)`.
   - Rule modules in [`logic/`](/home/miles/Documents/bible-trivia-kr-min/logic) define inference on top of the base schema in [`logic/schema.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/schema.dl).
   - The module entrypoint is [`logic/main.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/main.dl), which includes the schema and the rule modules.

5. Graph export
   - [`scripts/batch_generate.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/batch_generate.py) also emits `out/graph/load.cypher`.
   - This makes the extracted knowledge queryable in Neo4j or any process that can consume Cypher.

6. Trivia export
   - [`extractors/question_engine.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/question_engine.py) turns facts into MCQs with distractors, explanations, references, categories, and difficulties.
   - [`scripts/export_trivia_pack.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/export_trivia_pack.py) writes a JSON pack.
   - [`scripts/build_facts_db.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/build_facts_db.py) writes a SQLite database with `pack_manifest`, `facts`, and `items` tables.

## Souffle in This Repository

Souffle is used here as the inference layer, not the extraction layer.

- [`logic/schema.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/schema.dl) declares a compact logical core:
  - genealogy: `begat`, `father`, `ancestor_of`
  - events: `event`, `event_type`, `agent`, `recipient`
  - dialogue: `said`
- [`logic/main.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/main.dl) composes the rule system from smaller domain modules.
- Rule files such as [`logic/rules_family.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_family.dl), [`logic/rules_dialogue.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_dialogue.dl), and [`logic/rules_theophany.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_theophany.dl) add derived knowledge.

Examples of the kind of inference the rules target:

- ancestry closure from direct parentage
- event classification from agents and recipients
- speech events derived from `said(...)`
- divine appearance and divine speech tagging
- travel, visitation, arrival, and presence classification
- role-derived groupings for kings, prophets, priests, and other offices

Important architectural note:

- The repo currently exports Souffle-style fact files, but the default Python pipeline does not invoke the Souffle engine itself.
- [`scripts/batch_generate.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/batch_generate.py) writes `out/logic/facts.dl` and attempts to copy `logic/rules.dl`, but the source tree now uses modular logic rooted at [`logic/main.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/main.dl).
- In other words, the inference model is present, but the execution wiring between the current modular `logic/` layout and the generated `out/logic/` directory is still incomplete.

## How Derived Relations Become Trivia Questions

Trivia generation is fact-centric today.

The current question generator reads normalized extracted facts directly rather than reading Souffle output relations. The path is:

`parsed fact -> question template -> distractor selection -> trivia pack`

[`extractors/question_engine.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/question_engine.py) does the following:

- builds answer pools from all extracted facts
- normalizes names and forms for cleaner distractors
- converts each fact type into one or more MCQ templates
- deduplicates prompts and limits template overuse
- returns a pack JSON structure with metadata

Current question families include:

- genealogy
  - `Who was the father/mother of X?`
- dialogue
  - `Who spoke to X?`
- events
  - `Who killed X?`
  - `Who was killed?`
- travel
  - `Where did X travel to?`
  - `From where did X travel to Y?`
- roles and kingdoms
  - `What role did X have?`
  - `Over what realm did X reign?`
- theophany and manifestation
  - `To whom did God/Yahweh/LORD appear?`
  - `Who appeared to X?`
  - `In what form did X manifest?`

Architecturally, this means the project already has two different but compatible knowledge consumers:

- graph export for knowledge graph use
- trivia export for gameplay/content use

The natural next step is to let Souffle-derived relations feed the same question engine so the system can ask questions from inferred knowledge, not only directly extracted facts.

## Repository Layout

### Core logic

- [`logic/schema.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/schema.dl)
  - Base Souffle relation declarations and outputs.
- [`logic/main.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/main.dl)
  - Rule composition entrypoint.
- [`logic/rules_family.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_family.dl)
  - Genealogy and ancestry inference.
- [`logic/rules_events.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_events.dl)
  - Generic event typing.
- [`logic/rules_dialogue.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_dialogue.dl)
  - Speech to event/participant inference.
- [`logic/rules_roles.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_roles.dl)
  - Role-based event groupings.
- [`logic/rules_theophany.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_theophany.dl)
  - Divine appearance and divine speech typing.
- [`logic/rules_travel.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_travel.dl)
  - Travel and visitation typing.
- [`logic/rules_locations.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_locations.dl)
  - Arrival, presence, and gathering typing.
- [`logic/rules_prophets.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_prophets.dl)
  - Prophetic event typing.
- [`logic/rules_kings.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/rules_kings.dl)
  - Royal rule and succession typing.

### Extraction

- [`extractors/bible_rule_engine.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/bible_rule_engine.py)
  - Translation switchboard and de-duplication.
- [`extractors/patterns_web.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/patterns_web.py)
  - WEB-specific regex extractors.
- [`extractors/patterns_kjv.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/patterns_kjv.py)
  - KJV-specific regex extractors.

### Trivia

- [`extractors/question_engine.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/question_engine.py)
  - Current trivia generation engine.
- [`trivia/generate_questions.py`](/home/miles/Documents/bible-trivia-kr-min/trivia/generate_questions.py)
  - Older generation path with metaphor-focused logic.
- [`scripts/export_trivia_pack.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/export_trivia_pack.py)
  - Export parsed facts to a JSON trivia pack.
- [`scripts/build_facts_db.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/build_facts_db.py)
  - Export questions into SQLite tables for pack distribution.

### Pipeline scripts

- [`scripts/run_extraction.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/run_extraction.py)
  - Extract facts and drop candidates from verse input.
- [`scripts/batch_generate.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/batch_generate.py)
  - Main all-in-one pipeline: extraction, logic export, graph export, trivia export.
- [`scripts/normalize_web.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/normalize_web.py)
  - Text cleanup support.
- [`scripts/export_prolog.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/export_prolog.py)
  - Additional logic-oriented export path.

### Data and graph assets

- [`data/`](/home/miles/Documents/bible-trivia-kr-min/data)
  - Source verse text and intermediate Bible data.
- [`graph/schema.cypher`](/home/miles/Documents/bible-trivia-kr-min/graph/schema.cypher)
  - Optional Neo4j constraints.
- [`constraints/non_identity.ttl`](/home/miles/Documents/bible-trivia-kr-min/constraints/non_identity.ttl)
  - Constraint asset for metaphor/non-literal reasoning work.
- [`metaphor/metaphor.lp`](/home/miles/Documents/bible-trivia-kr-min/metaphor/metaphor.lp)
  - Experimental logic for metaphor interpretation.

### Tests

- [`tests/test_genealogy.py`](/home/miles/Documents/bible-trivia-kr-min/tests/test_genealogy.py)
- [`tests/test_rename.py`](/home/miles/Documents/bible-trivia-kr-min/tests/test_rename.py)

These tests confirm that extraction works for at least some core fact types.

## What the System Currently Models

At the extractor level, the repository currently has explicit support for:

- genealogy
- naming/renaming
- speech/dialogue
- killing/violence
- travel/movement
- roles and kingdoms
- divine appearances
- manifestation forms

At the logic level, the repository also defines derived categories for:

- ancestry chains
- speech events
- interaction events
- office actions
- theophanies
- divine speech
- visitation, arrival, and presence
- prophetic speech and encounters
- royal rule and succession

## Running the Pipeline

Basic local run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/batch_generate.py --in data/verses.jsonl --out out --translation WEB
```

Typical outputs:

- `out/parsed.jsonl`
- `out/drops.jsonl`
- `out/logic/facts.dl`
- `out/graph/load.cypher`
- `out/trivia/trivia_pack.json`
- `out/trivia_pack.sqlite` if you run the SQLite export step separately

To build a SQLite trivia pack from parsed facts:

```bash
python scripts/build_facts_db.py \
  --input out/parsed.jsonl \
  --output out/trivia_pack.sqlite \
  --pack-id bible-web-v1 \
  --title "Bible Trivia Pack (WEB)" \
  --translation WEB
```

To export a JSON trivia pack directly:

```bash
python scripts/export_trivia_pack.py \
  --input out/parsed.jsonl \
  --output out/trivia_pack.json \
  --pack-id bible-web-v1 \
  --title "Bible Trivia Pack (WEB)" \
  --translation WEB
```

## Extending the Rule System

To extend the Souffle inference layer:

1. Add or update a rule module under [`logic/`](/home/miles/Documents/bible-trivia-kr-min/logic).
2. Keep base relation declarations in [`logic/schema.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/schema.dl), not in the rule modules.
3. Include the new module from [`logic/main.dl`](/home/miles/Documents/bible-trivia-kr-min/logic/main.dl).
4. Build rules only from relations that are actually produced by extraction or by prior inference.
5. If the new inference should affect trivia, add a mapping in [`extractors/question_engine.py`](/home/miles/Documents/bible-trivia-kr-min/extractors/question_engine.py).

Practical extension patterns:

- add new base fact types in the extractor layer
  - Example: covenant, sacrifice, priestly blessing, battle participation.
- export those facts into Souffle facts
  - This happens in [`scripts/batch_generate.py`](/home/miles/Documents/bible-trivia-kr-min/scripts/batch_generate.py).
- write new derived relations in `logic/`
  - Example: `ancestor_of`, `theophany`, `presence`, `royal_succession`.
- consume the derived relations
  - by Neo4j export
  - by trivia generation
  - by new analytics or search layers

## Architectural Observations

The repository currently mixes a few generations of the project:

- a newer extractor-and-trivia pipeline centered on normalized fact records
- a Souffle modular logic layer for knowledge inference
- a graph export path for Neo4j
- older prototype logic around metaphor reasoning and legacy trivia generation

That is not a problem, but it does mean the project is best understood as a small knowledge engineering workbench rather than a single-purpose quiz app.

If you want to evolve it cleanly, the clearest target architecture is:

`Bible text -> extracted facts -> Souffle inference -> canonical derived facts -> graph export + trivia export`

That would make Souffle a first-class runtime component instead of only a serialization target.
