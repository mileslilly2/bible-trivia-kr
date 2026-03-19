# bible-trivia-kr-min

This repository implements a lightweight knowledge-engineering pipeline that converts Bible text into reusable structured knowledge using pattern extraction, Datalog inference (Soufflé), and graph projection.

It is best understood as a small Bible knowledge-representation workbench: verse text is parsed into normalized facts, those facts can be projected into symbolic logic and graph formats, and downstream consumers such as trivia generation can reuse the same extracted knowledge.

## Project Overview

The repository combines several related layers:

- text-level extraction from Bible verses
- normalized fact generation
- symbolic inference via modular Soufflé Datalog rules
- graph projection for Neo4j-style workflows
- trivia pack generation as one downstream application

The current runtime center of gravity is the Python extraction and export pipeline. The Soufflé layer is real and organized under `logic/`, but the wiring between extracted facts, modular rule files, and a fully automated Soufflé execution step is still evolving.

## Purpose

The goal of the project is not just to generate quiz questions. The broader purpose is to turn verse text into reusable symbolic knowledge that can support multiple consumers:

- fact-oriented analytics and inspection
- Datalog inference over normalized relations
- graph loading and query workflows
- trivia pack and question generation

Conceptually, the repository follows:

`Text -> Facts -> Inference -> Applications`

Or, in concrete file terms:

`data/verses.jsonl -> out/parsed.jsonl -> out/logic/facts.dl + logic/main.dl -> inferred relations / graph export / trivia pack`

## High-Level Architecture

### 1. Pattern extraction

Translation-specific regex extractors read verse text and emit normalized fact records. The active extraction logic lives in:

- `extractors/patterns_web.py`
- `extractors/patterns_kjv.py`
- `extractors/bible_rule_engine.py`

The rule engine selects extractors by translation and de-duplicates overlapping matches. Current normalized fact types include:

- `parent_of`
- `rename`
- `spoke_to`
- `killed`
- `traveled`
- `role`
- `appeared_to`
- `manifestation`

### 2. Knowledge representation

Extracted facts are persisted as JSON/JSONL and also exported into Soufflé-style fact declarations. The canonical logical schema and rule composition live in:

- `logic/schema.dl`
- `logic/main.dl`
- `logic/rules_*.dl`

### 3. Graph projection

The batch pipeline projects extracted facts into Cypher for Neo4j-style graph loading. This makes the same extracted knowledge usable as a property graph, not just as flat JSON.

### 4. Applications

The repository currently has at least two concrete downstream knowledge consumers:

- graph export under `out/graph/load.cypher`
- trivia generation via `extractors/question_engine.py` and `scripts/export_trivia_pack.py`

## End-to-End Flow

The intended pipeline is:

`verses.jsonl -> extracted facts -> Soufflé facts/rules -> inferred relations -> graph/trivia exports`

More concretely:

1. Input verses are read from `data/verses.jsonl`.
2. `extractors/bible_rule_engine.py` applies translation-specific pattern extractors.
3. The pipeline writes normalized extracted facts to `out/parsed.jsonl`.
4. `scripts/batch_generate.py` exports Soufflé-style facts to `out/logic/facts.dl`.
5. `logic/main.dl` composes `logic/schema.dl`, generated facts, and modular rule files.
6. Inferred relations can be consumed from Soufflé CSV outputs when present.
7. The same extracted or inferred knowledge can be projected to:
   - graph export in `out/graph/load.cypher`
   - trivia pack output in `out/trivia/trivia_pack.json`

At a high level, the pipeline is a small neuro-symbolic style stack: regex extraction grounds symbolic facts in text, and Datalog rules add a second inference layer over those facts.

## Soufflé / Inference Layer

The Soufflé program is modular rather than monolithic.

`logic/main.dl` is the composition root. It includes:

- `logic/schema.dl`
- generated `facts.dl`
- rule modules such as:
  - `logic/rules_family.dl`
  - `logic/rules_events.dl`
  - `logic/rules_dialogue.dl`
  - `logic/rules_roles.dl`
  - `logic/rules_theophany.dl`
  - `logic/rules_travel.dl`
  - `logic/rules_locations.dl`
  - `logic/rules_prophets.dl`
  - `logic/rules_kings.dl`

`logic/schema.dl` declares both extracted/base relations and derived relations. At the time of writing, it includes declarations for relations such as:

- extracted/base-style relations:
  - `parent_of`
  - `spoke_to`
  - `parent_gender`
  - `renamed_to`
  - `killed`
  - `traveled_to`
  - `traveled_from_to`
  - `role`
  - `reign_realm`
  - `appeared_to`
  - `manifestation`
  - `fact_ref`
- derived/inference-oriented relations:
  - `begat`
  - `father`
  - `ancestor_of`
  - `descendant_of`
  - `sibling`
  - `event`
  - `event_type`
  - `agent`
  - `recipient`
  - `participant`
  - `travel_path`
  - `said`
  - `interacted_with`
  - `indirect_dialogue`

The rule modules do real inference work, for example:

- genealogy expansion from `parent_of` to `begat`, `father`, `ancestor_of`, and `descendant_of`
- dialogue/event lifting from `spoke_to` into `said`, `event`, `agent`, and `recipient`
- secondary categorization such as `theophany`, `divine_speech`, `royal_action`, `prophetic_speech`, and `visitation`

Important practical note: the repository contains a real inference layer, but the default batch script currently stages logic facts rather than fully orchestrating a fresh Soufflé run itself. `scripts/batch_generate.py` will read inferred CSV outputs from the output directory if they already exist, and otherwise it falls back to parsed facts.

## Graph Export

`scripts/batch_generate.py` also emits `out/graph/load.cypher`.

The generated graph projection currently creates or links entities such as:

- `Human`
- `Place`
- `Role`
- `Name`
- `Verse`
- `DivineEntity`
- `ManifestationForm`

It also materializes typed edges such as:

- `PARENT_OF`
- `SPOKE_TO`
- `KILLED`
- `TRAVELED_FROM`
- `TRAVELED_TO`
- `HAS_ROLE`
- `REIGNED_OVER`
- `APPEARED_TO`
- `MANIFESTED_AS`
- `MENTIONED_IN`

`graph/schema.cypher` contains optional Neo4j constraints for entity and event identifiers.

## Trivia Generation

Trivia generation is a downstream consumer of the extracted knowledge, not the architectural definition of the repository.

The active question path is:

- `extractors/question_engine.py`
- `scripts/export_trivia_pack.py`
- `scripts/build_facts_db.py`
- `scripts/generate_demo_questions.py`

The question engine reads normalized parsed facts and generates multiple-choice questions with distractors, explanations, references, categories, and difficulty labels. It supports question families around:

- genealogy
- dialogue
- violence/events
- travel
- roles and kingdoms
- theophany / appearance
- manifestation form

`scripts/batch_generate.py` can also use Soufflé-derived outputs for a subset of trivia generation when those inferred relation CSVs are present, translating supported relations such as `father`, `begat`, and `said` back into the current trivia fact schema.

The repository also contains an older `trivia/generate_questions.py` path, which reflects an earlier schema and appears to be a legacy generation layer rather than the primary current runtime.

## Repository Layout

- `extractors/`
  - Active extraction logic and the current trivia question engine.
- `logic/`
  - Soufflé schema, modular rule files, and Datalog entrypoint.
- `graph/`
  - Optional Cypher schema support for Neo4j.
- `scripts/`
  - Main pipeline scripts for extraction, export, and trivia packaging.
- `trivia/`
  - Older question-generation utilities.
- `data/`
  - Source verse text and example Bible data.
- `tests/`
  - Tests for extraction behavior.
- `out/`
  - Generated pipeline outputs.
- `out_example/`
  - Example generated artifacts.
- `patterns/`, `ingest/`, `metaphor/`, `src/`, `souffle/`
  - Older or auxiliary layers that exist in the repository but are not the primary happy-path pipeline described above.

## Running the Pipeline

### Environment setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Main pipeline

```bash
python scripts/batch_generate.py --in data/verses.jsonl --out out --translation WEB
```

This writes, at minimum:

- `out/parsed.jsonl`
- `out/drops.jsonl`
- `out/logic/facts.dl`
- `out/graph/load.cypher`
- `out/trivia/trivia_pack.json` unless `--no-trivia` is used

Useful options:

```bash
python scripts/batch_generate.py --in data/verses.jsonl --out out --translation WEB --verbose
python scripts/batch_generate.py --in data/verses.jsonl --out out --translation KJV --no-trivia
```

### Extraction only

```bash
python scripts/run_extraction.py --in data/verses.jsonl --facts-out out/parsed.jsonl --drops-out out/drops.jsonl --translation WEB
```

Note: `scripts/run_extraction.py` writes JSON arrays, while `scripts/batch_generate.py` writes newline-delimited JSON to `out/parsed.jsonl`. The filename suffix alone does not guarantee the same serialization format.

### Trivia pack JSON

```bash
python scripts/export_trivia_pack.py --input out/parsed.jsonl --output out/trivia_pack.json --pack-id bible-web-v1 --title "Bible Trivia Pack (WEB)" --translation WEB
```

### Trivia pack SQLite

```bash
python scripts/build_facts_db.py --input out/parsed.jsonl --output out/trivia_pack.sqlite --pack-id bible-web-v1 --title "Bible Trivia Pack (WEB)" --translation WEB
```

### Demo question generation

```bash
python scripts/generate_demo_questions.py --input out/parsed.jsonl --output out/demo_questions.json --n 30
```

### Tests

```bash
pytest
```

## Extending the Rule System

When extending the symbolic layer, the current repository structure favors modular rules over one large logic file.

Recommended approach:

1. Add shared relation declarations to `logic/schema.dl` if the relation is meant to be part of the common schema.
2. Add a focused new `logic/rules_*.dl` module or extend the closest existing module.
3. Include the new rule module from `logic/main.dl`.
4. If the relation depends on extracted base facts, update the Python fact exporter in `scripts/batch_generate.py` in the same change.
5. Check whether downstream consumers also need updates:
   - trivia generation
   - graph projection
   - tests

As a design rule, keep rule modules focused on derivation rather than fact declaration or output staging.

## Current Limitations / Architectural Notes

- The repository contains both older and newer layers. Not every directory participates in the default runtime path.
- The Soufflé layer is real and structured, but default pipeline orchestration is still partial. The batch script exports facts and consumes inferred CSVs if present; it does not fully guarantee end-to-end Soufflé execution on its own.
- Some downstream generation still relies directly on parsed extracted facts rather than only on inferred relations.
- The active normalized extraction schema and some older scripts/tests are not perfectly aligned. For example, some legacy code still assumes older fact shapes.
- `scripts/run_extraction.py` and `scripts/batch_generate.py` do not serialize `parsed.jsonl` in the same way.
- The repository includes a vendored `souffle/` tree, but the active logical program for this project lives under the top-level `logic/` directory.

These are normal signs of an evolving research/engineering codebase, but they are worth understanding before treating every directory as part of one fully unified production pipeline.

## Future Directions

Natural next steps for the repository include:

- fully wiring `logic/main.dl` into an automated Soufflé execution step from the batch pipeline
- expanding extractor coverage beyond the current relation set
- making inferred relations first-class inputs to trivia generation and graph export
- improving schema consistency across extraction, logic, tests, and older utility scripts
- adding tests for Soufflé execution and inference outputs, not only extraction behavior
- broadening graph and database export options for downstream knowledge applications

## Summary

This repository is best viewed as a lightweight Bible knowledge-extraction and knowledge-representation pipeline. Trivia generation is one downstream application, but the core system is the reusable symbolic conversion of Bible verse text into normalized facts, inference-ready relations, and graph-friendly structure.
