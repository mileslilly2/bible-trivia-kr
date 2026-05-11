# AGENTS.md

## Project Overview

`bible-trivia-kr-min` is a lightweight Bible knowledge-engineering pipeline.
It extracts structured facts from verse text, exports those facts into Soufflé-style logic facts and Neo4j Cypher, runs or consumes Datalog inference outputs, and generates trivia packs from extracted or inferred knowledge.

This is not just a trivia app. Trivia is one downstream product of a broader knowledge-extraction, knowledge-representation, inference, graph export, and trivia generation pipeline.

The current runtime center of gravity is the Python extraction and export pipeline. The Soufflé logic layer in `logic/` is real and modular, but `scripts/batch_generate.py` stages facts and consumes inferred CSVs when present rather than fully orchestrating a fresh Soufflé run itself.

## Repository Architecture

Core areas:

- `extractors/`
  - Translation-specific regex extraction lives in `extractors/patterns_web.py` and `extractors/patterns_kjv.py`.
  - `extractors/bible_rule_engine.py` selects extractors by translation and de-duplicates facts.
  - `extractors/question_engine.py` generates downstream trivia from parsed facts or supported inferred facts.

- `scripts/`
  - `scripts/run_extraction.py` runs extraction only.
  - `scripts/batch_generate.py` is the main all-in-one pipeline for extraction, logic export, graph export, and trivia export.
  - `scripts/export_trivia_pack.py` writes a trivia pack JSON.
  - `scripts/build_facts_db.py` writes a SQLite trivia pack database.

- `logic/`
  - `logic/schema.dl` holds the Soufflé relation declarations and outputs.
  - `logic/main.dl` is the modular entrypoint that includes `facts.dl`, `schema.dl`, and each rule module.
  - `logic/rules_*.dl` contains domain-specific inference rules only.

- `graph/`
  - `graph/schema.cypher` contains optional Neo4j schema support.

- `data/`
  - Input verses are primarily under `data/`, especially `data/verses.jsonl`.

- `tests/`
  - Current tests cover extraction behavior, not Soufflé execution.

- `trivia/`
  - Older or auxiliary trivia generation utilities. Do not treat this as the core runtime unless the task specifically targets it.

Do not assume older prototype directories such as `metaphor/`, `patterns/`, `src/`, or the vendored `souffle/` tree are part of the active happy-path pipeline unless the task clearly requires them.

## Current Pipeline Flow

The working pipeline shape is:

```text
data/verses.jsonl -> out/parsed.jsonl -> out/logic/facts.dl -> Soufflé -> CSV relations -> graph + trivia
```

Current behavior:

- `scripts/batch_generate.py` reads `data/verses.jsonl` and writes `out/parsed.jsonl`.
- The same script exports facts-only Soufflé input to `out/logic/facts.dl`.
- Soufflé can be run manually with `logic/main.dl` to produce CSV relations under `out/`.
- The batch script reads inferred CSV outputs if present; otherwise trivia generation falls back to parsed facts.
- Graph export currently comes from normalized extracted facts and is written to `out/graph/load.cypher`.

Do not describe the repository as if trivia generation is the primary architecture. The primary architecture is extraction -> representation -> inference -> exports.

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

`logic/schema.dl` currently declares base extracted relations and derived inference relations, including:

- base/extracted relations: `parent_of`, `spoke_to`, `parent_gender`, `renamed_to`, `killed`, `traveled_to`, `traveled_from_to`, `role`, `reign_realm`, `appeared_to`, `manifestation`, `fact_ref`
- genealogy relations: `begat`, `father`, `ancestor_of`, `descendant_of`, `sibling`
- event relations: `event`, `event_type`, `agent`, `recipient`, `participant`, `travel_path`
- dialogue relations: `said`, `interacted_with`, `indirect_dialogue`

`logic/schema.dl` also owns the shared `.output` declarations.

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

- `scripts/batch_generate.py` exports `out/logic/facts.dl`, but it does not run Soufflé itself.
- The actual modular Soufflé entrypoint is `logic/main.dl`.
- There is no monolithic `logic/rules.dl` in the active logic layout.
- Do not assume the batch pipeline currently executes the modular Soufflé program.

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

Manual Soufflé run after generating `out/logic/facts.dl`:

```bash
souffle -D out -I out/logic logic/main.dl
```

Verbose pipeline logging:

```bash
python scripts/batch_generate.py --in data/verses.jsonl --out out --translation WEB --verbose
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
- Do not add `.decl` declarations to rule modules.
- Do not add `.output` declarations to rule modules.
- Prefer adding a new `rules_*.dl` file plus one include in `logic/main.dl` over overloading unrelated modules.
- Build new rules only on relations that are declared in `logic/schema.dl`.
- If a new relation is used in a rule, declare it in `logic/schema.dl` first.
- Keep relation arity identical across `logic/schema.dl`, generated `facts.dl`, and every rule use.
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

- All `.decl` statements MUST live in `logic/schema.dl`.
- Put shared `.output` definitions in `logic/schema.dl`.
- `logic/rules_*.dl` files MUST contain rules only.
- Generated `out/logic/facts.dl` MUST contain facts only. Do not emit `.decl` or `.output` into generated facts.
- Keep declaration names and arities stable unless the corresponding facts exporter and rule modules are updated together.
- If you introduce a new base or shared derived relation, declare it in `logic/schema.dl` first, then use it from rule modules.
- If a relation is only meaningful because a generator exports it, update the generator and schema in the same change.
- Arity must match across schema declarations, generated facts, and rule bodies/heads.

Current reality to preserve:

- `logic/schema.dl` declares both exported base fact relations and derived relations.
- `scripts/batch_generate.py` emits generated facts such as `parent_of(...)`, `killed(...)`, `spoke_to(...)`, `traveled_to(...)`, `role(...)`, `appeared_to(...)`, `manifestation(...)`, and `fact_ref(...)`.
- Those generated fact names must match declarations in `logic/schema.dl` and uses in `logic/rules_*.dl`.

If you are asked to fix or extend the Soufflé pipeline, treat schema/rule/fact mismatches as real integration issues and resolve them explicitly instead of papering over them in docs or comments.

## Common Failure Modes

- `Undefined relation`: the relation is used in a rule or facts file but is missing a `.decl` in `logic/schema.dl`.
- `Redefinition of relation`: a `.decl` was duplicated in generated `facts.dl` or a `logic/rules_*.dl` file.
- Arity mismatch: the number of columns differs between `logic/schema.dl`, generated facts, and rule usage.
- Missing facts include: `logic/main.dl` includes `facts.dl`; run Soufflé with `-I out/logic` after generating `out/logic/facts.dl`.
- Wrong output expectation: trivia can fall back to `out/parsed.jsonl` when inferred Soufflé CSV outputs are absent.

## Logging Changes

- Pipeline logging belongs in `scripts/batch_generate.py`.
- Prefer clean stage-based logs: `[extract]`, `[logic]`, `[souffle]`, `[graph]`, `[trivia]`, `[summary]`.
- Keep routine logs concise and stable.
- Put noisy debug output, sample rows, and detailed counts behind `--verbose`.
- Do not add ad hoc print debugging in extractors, rule modules, or trivia code when stage logging would be clearer.

## Trivia Generation Changes

- Trivia is downstream of the knowledge pipeline. Do not reshape the whole repository around trivia.
- Prefer consuming supported Soufflé CSV outputs when they are available.
- Preserve the parsed-fact fallback path for runs without inferred CSVs.
- Maintain question schema consistency in `extractors/question_engine.py`.
- Preserve references and metadata fields such as `ref`, `translation`, `category`, `difficulty`, explanations, and answer options.
- If adding a new inferred relation for trivia, update the Soufflé adapter and question generation path together.

## Safe Edit Rules

- Prefer modifying existing files in place.
- Do not rename files or move core entrypoints unless explicitly requested.
- Do not introduce new architecture layers without instruction.
- Keep changes minimal, local, and testable.
- For pipeline changes, update docs and tests alongside behavior when practical.
- For Soufflé changes, verify schema, facts, rules, and command examples remain aligned.

## Working Style for This Repo

- Prefer small, local fixes over broad redesigns.
- Keep documentation aligned with the code, especially around the logic pipeline.
- Call out mismatches between extraction facts, logic schema, and tests instead of assuming they are already reconciled.
