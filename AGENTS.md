# AGENTS.md

## Project Overview

`bible-trivia-kr-min` is a lightweight Bible knowledge-engineering pipeline.
It extracts structured facts from verse text, exports those facts into Soufflé-style logic facts and Neo4j Cypher, and generates trivia packs from the extracted facts.

The current runtime center of gravity is the Python extraction and trivia pipeline. The Soufflé logic layer exists in `logic/`, but the default batch script does not fully wire the modular logic layout into a runnable Soufflé invocation.

## Repository Architecture

Core areas:

- `extractors/`
  - Translation-specific regex extraction lives in `extractors/patterns_web.py` and `extractors/patterns_kjv.py`.
  - `extractors/bible_rule_engine.py` selects extractors by translation and de-duplicates facts.
  - `extractors/question_engine.py` generates trivia from extracted facts.

- `scripts/`
  - `scripts/run_extraction.py` runs extraction only.
  - `scripts/batch_generate.py` is the main all-in-one pipeline for extraction, logic export, graph export, and trivia export.
  - `scripts/export_trivia_pack.py` writes a trivia pack JSON.
  - `scripts/build_facts_db.py` writes a SQLite trivia pack database.

- `logic/`
  - `logic/schema.dl` holds the Soufflé relation declarations and outputs.
  - `logic/main.dl` is the modular entrypoint that includes `facts.dl`, `schema.dl`, and each rule module.
  - `logic/rules_*.dl` contains domain-specific inference rules.

- `graph/`
  - `graph/schema.cypher` contains optional Neo4j schema support.

- `data/`
  - Input verses are primarily under `data/`, especially `data/verses.jsonl`.

- `tests/`
  - Current tests cover extraction behavior, not Soufflé execution.

Do not assume older prototype directories such as `metaphor/`, `patterns/`, `src/`, or the vendored `souffle/` tree are part of the active happy-path pipeline unless the task clearly requires them.

## Soufflé Logic Structure

`logic/main.dl` is the composition root:

- includes `facts.dl`
- includes `schema.dl`
- includes each rule module:
  - `rules_family.dl`
  - `rules_events.dl`
  - `rules_dialogue.dl`
  - `rules_roles.dl`
  - `rules_theophany.dl`
  - `rules_travel.dl`
  - `rules_locations.dl`
  - `rules_prophets.dl`
  - `rules_kings.dl`

`logic/schema.dl` currently declares the logical core:

- genealogy relations: `begat`, `father`, `ancestor_of`
- event relations: `event`, `event_type`, `agent`, `recipient`
- dialogue relation: `said`

`logic/schema.dl` also owns the current `.output` declarations:

- `father`
- `ancestor_of`
- `event_type`
- `agent`
- `recipient`

Rule-module responsibilities:

- `rules_family.dl`: derives `father` and `ancestor_of` from `begat`
- `rules_dialogue.dl`: derives event records from `said`
- `rules_events.dl`: derives generic event typing from `event_type`, `agent`, `recipient`
- `rules_roles.dl`: derives role-oriented event categories
- `rules_theophany.dl`: tags divine appearances and divine speech
- `rules_travel.dl`: maps movement verbs into `travel` and `visitation`
- `rules_locations.dl`: derives `arrival`, `presence`, and `gathering`
- `rules_prophets.dl`: derives prophetic speech and encounter categories
- `rules_kings.dl`: derives royal rule and succession categories

Important limitation:

- `scripts/batch_generate.py` exports `out/logic/facts.dl`, but it currently tries to copy `logic/rules.dl` into the output tree.
- There is no `logic/rules.dl` in the repository.
- The actual modular Soufflé entrypoint is `logic/main.dl`.
- Do not assume the batch pipeline currently executes or correctly stages the modular Soufflé program.

## Pipeline Commands

Environment setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Main pipeline:

```bash
python scripts/batch_generate.py --in data/verses.jsonl --out out --translation WEB
```

Extraction only:

```bash
python scripts/run_extraction.py --in data/verses.jsonl --facts-out out/parsed.jsonl --drops-out out/drops.jsonl --translation WEB
```

Trivia pack JSON:

```bash
python scripts/export_trivia_pack.py --input out/parsed.jsonl --output out/trivia_pack.json --pack-id bible-web-v1 --title "Bible Trivia Pack (WEB)" --translation WEB
```

Trivia pack SQLite:

```bash
python scripts/build_facts_db.py --input out/parsed.jsonl --output out/trivia_pack.sqlite --pack-id bible-web-v1 --title "Bible Trivia Pack (WEB)" --translation WEB
```

Tests:

```bash
pytest
```

Be careful with output-format assumptions:

- `scripts/batch_generate.py` writes newline-delimited JSON records to `out/parsed.jsonl`.
- `scripts/run_extraction.py` writes JSON arrays even though its default filenames also end in `.jsonl`.
- `extractors/question_engine.py` reads line-by-line JSON records.

## Constraints on Modifying Rule Modules

When editing `logic/rules_*.dl`:

- Keep rule modules focused on derivation only.
- Do not add base fact declarations to rule modules.
- Do not add `.output` declarations to rule modules unless the schema strategy is intentionally being changed across the repo.
- Prefer adding a new `rules_*.dl` file plus one include in `logic/main.dl` over overloading unrelated modules.
- Build new rules only on relations that already exist in `schema.dl`, `facts.dl`, or earlier derivations.
- Preserve the current modular include pattern in `logic/main.dl`.

Before changing relation names or semantics in a rule module, check all downstream consumers:

- `logic/schema.dl`
- `logic/main.dl`
- `scripts/batch_generate.py`
- any generated fact names in `out/logic/facts.dl`
- trivia generation paths in `extractors/question_engine.py`

Do not silently replace the current modular entrypoint with a different architecture. If a task requires making Soufflé execution actually work, wire it around `logic/main.dl` rather than inventing a separate rule layout.

## Rules for `schema.dl` Declarations

`logic/schema.dl` is the canonical place for logical declarations.

Rules:

- Put shared `.decl` definitions in `logic/schema.dl`.
- Put shared `.output` definitions in `logic/schema.dl`.
- Keep declaration names and arities stable unless the corresponding facts exporter and rule modules are updated together.
- If you introduce a new base or shared derived relation, declare it in `logic/schema.dl` first, then use it from rule modules.
- If a relation is only meaningful because a generator exports it, update the generator and schema in the same change.

Current reality to preserve:

- `logic/schema.dl` declares `begat`, `father`, `ancestor_of`, `event`, `event_type`, `agent`, `recipient`, and `said`.
- The batch exporter currently emits a separate generated `facts.dl` file with declarations such as `parent_of`, `killed`, `spoke_to`, `traveled_to`, `role`, `appeared_to`, and `manifestation`.
- Those generated fact names do not currently match the relations used by `logic/schema.dl` and `logic/main.dl`.

If you are asked to fix or extend the Soufflé pipeline, treat that mismatch as a real integration issue and resolve it explicitly instead of papering over it in docs or comments.

## Working Style for This Repo

- Prefer small, local fixes over broad redesigns.
- Keep documentation aligned with the code, especially around the logic pipeline.
- Call out mismatches between extraction facts, logic schema, and tests instead of assuming they are already reconciled.
