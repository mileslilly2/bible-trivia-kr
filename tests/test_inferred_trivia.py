from extractors.question_engine import facts_to_trivia_pack
from scripts.batch_generate import load_souffle_trivia_facts


def _base_people():
    return [
        {"type": "parent_of", "parent": "Adam", "child": "Seth", "ref": "Genesis 5:3", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Noah", "child": "Shem", "ref": "Genesis 5:32", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Moses", "listener": "Aaron", "ref": "Exodus 4:28", "text": "", "norm": ""},
        {"type": "killed", "killer": "Cain", "victim": "Abel", "ref": "Genesis 4:8", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Abraham", "child": "Isaac", "ref": "Genesis 21:3", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Isaac", "child": "Jacob", "ref": "Genesis 25:26", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Moses", "listener": "Pharaoh", "ref": "Exodus 5:1", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Moses", "listener": "Joshua", "ref": "Exodus 17:9", "text": "", "norm": ""},
    ]


def test_inferred_facts_generate_valid_pack_schema():
    facts = _base_people() + [
        {
            "type": "ancestor_of",
            "ancestor": "Abraham",
            "descendant": "Jacob",
            "ref": "Genesis 21:3; Genesis 25:26",
            "text": "",
            "norm": "",
            "source": "souffle",
            "provenance_refs": ["Genesis 21:3", "Genesis 25:26"],
            "genealogy_chain": ["Abraham", "Isaac", "Jacob"],
            "genealogy_depth": 2,
        },
        {
            "type": "descendant_of",
            "descendant": "Jacob",
            "ancestor": "Abraham",
            "ref": "Genesis 21:3; Genesis 25:26",
            "text": "",
            "norm": "",
            "source": "souffle",
            "provenance_refs": ["Genesis 21:3", "Genesis 25:26"],
            "genealogy_chain": ["Abraham", "Isaac", "Jacob"],
            "genealogy_depth": 2,
        },
        {"type": "sibling", "person": "Moses", "sibling": "Aaron", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "interacted_with", "person": "Moses", "other": "Pharaoh", "ref": "Exodus 4:28", "text": "", "norm": "", "source": "souffle", "provenance_refs": ["Exodus 4:28"]},
        {"type": "indirect_dialogue", "person": "Abraham", "other": "Joseph", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "conversation_reach", "person": "Moses", "reachable": "Joshua", "ref": "", "text": "", "norm": "", "source": "souffle"},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=7)

    assert pack["question_count"] == len(pack["questions"])
    inferred_questions = [q for q in pack["questions"] if q["meta"].get("fact", {}).get("source") == "souffle"]
    assert inferred_questions

    required_keys = {"id", "category", "difficulty", "question", "choices", "answer_index", "explanation", "ref", "meta"}
    for question in pack["questions"]:
        assert required_keys <= set(question)
        assert len(question["choices"]) == 4
        assert len(set(question["choices"])) == 4
        assert 0 <= question["answer_index"] < len(question["choices"])
        assert question["choices"][question["answer_index"]] not in [
            choice for i, choice in enumerate(question["choices"]) if i != question["answer_index"]
        ]
        assert question["explanation"].strip()
        assert question["explanation"].strip() != ":"

    inferred_explanations = {q["meta"]["fact"]["type"]: q["explanation"] for q in inferred_questions}
    assert "genealogy chain: Abraham -> Isaac -> Jacob" in inferred_explanations["ancestor_of"]
    assert "genealogy chain: Abraham -> Isaac -> Jacob" in inferred_explanations["descendant_of"]
    assert "share a parent" in inferred_explanations["sibling"]
    assert "recorded speech" in inferred_explanations["interacted_with"]
    for question in pack["questions"]:
        assert "interacted with" not in question["question"].lower()
        assert "indirectly connected in dialogue" not in question["question"].lower()
    assert "indirect_dialogue" not in inferred_explanations
    assert "conversation_reach" not in inferred_explanations


def test_ungrounded_long_inferred_genealogy_is_filtered_out():
    facts = _base_people() + [
        {"type": "ancestor_of", "ancestor": "Jacob", "descendant": "Ram", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "descendant_of", "descendant": "Ram", "ancestor": "Jacob", "ref": "", "text": "", "norm": "", "source": "souffle"},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=13)

    inferred_types = {q["meta"].get("fact", {}).get("type") for q in pack["questions"] if q["meta"].get("fact", {}).get("source") == "souffle"}
    assert "ancestor_of" not in inferred_types
    assert "descendant_of" not in inferred_types


def test_no_graph_like_inferred_dialogue_questions_are_generated():
    facts = _base_people() + [
        {"type": "interacted_with", "person": "Moses", "other": "Pharaoh", "ref": "Exodus 4:28", "text": "", "norm": "", "source": "souffle", "provenance_refs": ["Exodus 4:28"]},
        {"type": "indirect_dialogue", "person": "Abraham", "other": "Joseph", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "conversation_reach", "person": "Moses", "reachable": "Joshua", "ref": "", "text": "", "norm": "", "source": "souffle"},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=19)

    questions = [q["question"].lower() for q in pack["questions"]]
    assert all("interacted with" not in question for question in questions)
    assert all("indirectly connected in dialogue" not in question for question in questions)
    inferred_types = [q["meta"].get("fact", {}).get("type") for q in pack["questions"] if q["meta"].get("fact", {}).get("source") == "souffle"]
    assert "interacted_with" in inferred_types
    assert "indirect_dialogue" not in inferred_types
    assert "conversation_reach" not in inferred_types


def test_empty_extracted_dialogue_explanation_uses_fallback_sentence():
    facts = _base_people() + [
        {"type": "spoke_to", "speaker": "Miriam", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Joshua", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Samuel", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=3)

    dialogue_questions = [q for q in pack["questions"] if q["meta"].get("fact", {}).get("type") == "spoke_to"]
    assert dialogue_questions
    for question in dialogue_questions:
        assert question["explanation"].strip()
        assert question["explanation"].strip() != ":"
        assert " spoke to " in question["explanation"] or ":" in question["explanation"]
        assert len(question["choices"]) == 4
        assert len(set(question["choices"])) == 4
        assert 0 <= question["answer_index"] < len(question["choices"])


def test_inferred_dialogue_filters_group_answers_from_choices():
    facts = _base_people() + [
        {"type": "interacted_with", "person": "Moses", "other": "Israel", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "interacted_with", "person": "Moses", "other": "Judah", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "interacted_with", "person": "Moses", "other": "Pharaoh", "ref": "Exodus 4:28", "text": "", "norm": "", "source": "souffle", "provenance_refs": ["Exodus 4:28"]},
        {"type": "interacted_with", "person": "Aaron", "other": "Joshua", "ref": "Numbers 27:18", "text": "", "norm": "", "source": "souffle", "provenance_refs": ["Numbers 27:18"]},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=11)

    inferred_dialogue = [q for q in pack["questions"] if q["category"] == "Bible • Inferred Dialogue"]
    assert inferred_dialogue
    for question in inferred_dialogue:
        assert "Israel" not in question["choices"]
        assert "Judah" not in question["choices"]
        assert len(question["choices"]) == 4
        assert len(set(question["choices"])) == 4
        assert 0 <= question["answer_index"] < len(question["choices"])


def test_dialogue_filters_demonyms_and_normalizes_divine_names():
    facts = [
        {"type": "parent_of", "parent": "Adam", "child": "Seth", "ref": "Genesis 5:3", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Noah", "child": "Shem", "ref": "Genesis 5:32", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Yahweh", "listener": "Moses", "ref": "Exodus 4:4", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "LORD", "listener": "Aaron", "ref": "Exodus 4:28", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Moabitess", "listener": "Moses", "ref": "", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Israelites", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Miriam", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Joshua", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Samuel", "listener": "Aaron", "ref": "", "text": "", "norm": ""},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=17)
    dialogue_questions = [q for q in pack["questions"] if q["category"] == "Bible • Dialogue"]

    assert dialogue_questions
    for question in dialogue_questions:
        rendered = " ".join([question["question"], *question["choices"]])
        assert "Yahweh" not in rendered
        assert "LORD" not in rendered
        assert "Moabitess" not in rendered
        assert "Israelites" not in rendered
        assert len(question["choices"]) == 4
        assert len(set(question["choices"])) == 4
        assert 0 <= question["answer_index"] < len(question["choices"])


def test_extracted_dialogue_prefers_short_source_quote_when_available():
    facts = [
        {"type": "parent_of", "parent": "Adam", "child": "Seth", "ref": "Genesis 5:3", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Noah", "child": "Shem", "ref": "Genesis 5:32", "text": "", "norm": ""},
        {
            "type": "spoke_to",
            "speaker": "David",
            "listener": "Jonathan",
            "ref": "1 Samuel 20:4",
            "text": 'David said to Jonathan, "Whatever your soul desires, I will even do it for you."',
            "norm": "",
        },
        {"type": "spoke_to", "speaker": "Moses", "listener": "Aaron", "ref": "Exodus 4:28", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Samuel", "listener": "Saul", "ref": "1 Samuel 15:1", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Nathan", "listener": "David", "ref": "2 Samuel 12:7", "text": "", "norm": ""},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=23)
    question = next(q for q in pack["questions"] if q["ref"] == "1 Samuel 20:4")

    assert question["question"] == "In 1 Samuel 20:4, who said to Jonathan, 'Whatever your soul desires, I will even do it for...'?"
    assert question["choices"][question["answer_index"]] == "David"


def test_extracted_questions_use_contextual_ref_aware_templates():
    facts = _base_people() + [
        {"type": "rename", "name": "Seth", "ref": "Genesis 4:25", "text": "", "norm": ""},
        {"type": "rename", "name": "Noah", "ref": "Genesis 5:29", "text": "", "norm": ""},
        {"type": "rename", "name": "Isaac", "ref": "Genesis 21:3", "text": "", "norm": ""},
        {"type": "rename", "name": "Israel", "ref": "Genesis 35:10", "text": "", "norm": ""},
        {"type": "traveled", "traveler": "Abraham", "source": "Haran", "destination": "Canaan", "ref": "Genesis 12:5", "text": "", "norm": ""},
        {"type": "traveled", "traveler": "Jacob", "source": "Beersheba", "destination": "Haran", "ref": "Genesis 28:10", "text": "", "norm": ""},
        {"type": "traveled", "traveler": "Moses", "source": "Midian", "destination": "Egypt", "ref": "Exodus 4:20", "text": "", "norm": ""},
        {"type": "traveled", "traveler": "Jonah", "source": "Joppa", "destination": "Nineveh", "ref": "Jonah 3:3", "text": "", "norm": ""},
        {"type": "appeared_to", "entity": "God", "recipient": "Abram", "ref": "Genesis 17:1", "text": "", "norm": ""},
        {"type": "appeared_to", "entity": "angel of God", "recipient": "Moses", "ref": "Exodus 3:2", "text": "", "norm": ""},
        {"type": "appeared_to", "entity": "Jesus", "recipient": "Paul", "ref": "Acts 26:16", "text": "", "norm": ""},
        {"type": "appeared_to", "entity": "angel of God", "recipient": "Joseph", "ref": "Matthew 1:20", "text": "", "norm": ""},
        {"type": "manifestation", "entity": "God", "form": "burning bush", "ref": "Exodus 3:2", "text": "", "norm": ""},
        {"type": "manifestation", "entity": "God", "form": "pillar of fire", "ref": "Exodus 13:21", "text": "", "norm": ""},
        {"type": "manifestation", "entity": "God", "form": "pillar of cloud", "ref": "Exodus 13:21", "text": "", "norm": ""},
        {"type": "manifestation", "entity": "God", "form": "whirlwind", "ref": "Job 38:1", "text": "", "norm": ""},
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=29)
    by_type = {q["meta"]["fact"]["type"]: [] for q in pack["questions"]}
    for question in pack["questions"]:
        by_type.setdefault(question["meta"]["fact"]["type"], []).append(question["question"])

    assert any(q.startswith("According to the genealogy in Genesis") for q in by_type["parent_of"])
    assert "In Genesis 4:25, what name was given?" in by_type["rename"]
    assert any("Genesis 12:5" in q and "travel" in q.lower() for q in by_type["traveled"])
    assert any("Genesis 17:1" in q and "appear" in q.lower() for q in by_type["appeared_to"])
    assert "In Exodus 3:2, in what form did God appear?" in by_type["manifestation"]


def test_inferred_genealogy_uses_biblical_genealogy_framing_without_refs():
    facts = _base_people() + [
        {
            "type": "ancestor_of",
            "ancestor": "Abraham",
            "descendant": "Jacob",
            "ref": "",
            "text": "",
            "norm": "",
            "source": "souffle",
            "genealogy_chain": ["Abraham", "Isaac", "Jacob"],
            "genealogy_depth": 2,
        }
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=31)
    question = next(q for q in pack["questions"] if q["meta"]["fact"]["type"] == "ancestor_of")

    assert "genealogy" in question["question"].lower()
    assert "Jacob" in question["question"]
    assert question["ref"] == ""
    assert question["choices"][question["answer_index"]] == "Abraham"


def test_load_souffle_trivia_facts_attaches_safe_fact_ref_provenance(tmp_path):
    (tmp_path / "ancestor_of.csv").write_text("Abraham\tIsaac\nAbraham\tJacob\n", encoding="utf-8")
    (tmp_path / "descendant_of.csv").write_text("Isaac\tAbraham\n", encoding="utf-8")
    (tmp_path / "interacted_with.csv").write_text("Moses\tAaron\n", encoding="utf-8")
    (tmp_path / "indirect_dialogue.csv").write_text("Moses\tPharaoh\n", encoding="utf-8")
    (tmp_path / "conversation_reach.csv").write_text("Moses\tJoshua\n", encoding="utf-8")
    (tmp_path / "sibling.csv").write_text("Isaac\tIshmael\n", encoding="utf-8")
    (tmp_path / "fact_ref.csv").write_text(
        "parent_of\tAbraham\tIsaac\tGenesis 21:3\n"
        "parent_of\tAbraham\tIshmael\tGenesis 16:15\n"
        "spoke_to\tMoses\tAaron\tExodus 4:28\n"
        "spoke_to\tMoses\tJoshua\tDeuteronomy 31:7\n",
        encoding="utf-8",
    )

    facts, _ = load_souffle_trivia_facts(str(tmp_path))
    ancestor_direct = next(f for f in facts if f["type"] == "ancestor_of" and f["descendant"] == "Isaac")
    ancestor_indirect = next(f for f in facts if f["type"] == "ancestor_of" and f["descendant"] == "Jacob")
    descendant_direct = next(f for f in facts if f["type"] == "descendant_of")
    interacted = next(f for f in facts if f["type"] == "interacted_with")
    indirect = next(f for f in facts if f["type"] == "indirect_dialogue")
    reach = next(f for f in facts if f["type"] == "conversation_reach")
    sibling = next(f for f in facts if f["type"] == "sibling")

    assert ancestor_direct["ref"] == "Genesis 21:3"
    assert ancestor_direct["provenance_refs"] == ["Genesis 21:3"]
    assert ancestor_indirect["ref"] == ""
    assert "provenance_refs" not in ancestor_indirect
    assert descendant_direct["ref"] == "Genesis 21:3"
    assert interacted["ref"] == "Exodus 4:28"
    assert indirect["ref"] == ""
    assert reach["ref"] == "Deuteronomy 31:7"
    assert sibling["ref"] == "Genesis 21:3; Genesis 16:15"
    assert sibling["provenance_refs"] == ["Genesis 21:3", "Genesis 16:15"]


def test_load_souffle_trivia_facts_attaches_genealogy_chain_context(tmp_path):
    (tmp_path / "ancestor_of.csv").write_text("Jacob\tRam\n", encoding="utf-8")
    (tmp_path / "descendant_of.csv").write_text("Ram\tJacob\n", encoding="utf-8")
    (tmp_path / "fact_ref.csv").write_text(
        "parent_of\tJacob\tJudah\tGenesis 29:35\n"
        "parent_of\tJudah\tPerez\tGenesis 38:29\n"
        "parent_of\tPerez\tHezron\tRuth 4:18\n"
        "parent_of\tHezron\tRam\tRuth 4:19\n",
        encoding="utf-8",
    )

    facts, _ = load_souffle_trivia_facts(str(tmp_path))
    ancestor = next(f for f in facts if f["type"] == "ancestor_of")
    descendant = next(f for f in facts if f["type"] == "descendant_of")

    assert ancestor["genealogy_chain"] == ["Jacob", "Judah", "Perez", "Hezron", "Ram"]
    assert ancestor["genealogy_depth"] == 4
    assert ancestor["ref"] == "Genesis 29:35; Genesis 38:29"
    assert ancestor["provenance_refs"] == ["Genesis 29:35", "Genesis 38:29", "Ruth 4:18", "Ruth 4:19"]
    assert descendant["genealogy_chain"] == ["Jacob", "Judah", "Perez", "Hezron", "Ram"]


def test_inferred_question_meta_includes_provenance_refs_when_available():
    facts = _base_people() + [
        {
            "type": "ancestor_of",
            "ancestor": "Abraham",
            "descendant": "Isaac",
            "ref": "Genesis 21:3",
            "text": "",
            "norm": "",
            "source": "souffle",
            "provenance_refs": ["Genesis 21:3"],
        }
    ]

    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=5)
    question = next(q for q in pack["questions"] if q["meta"].get("fact", {}).get("type") == "ancestor_of")

    assert question["ref"] == "Genesis 21:3"
    assert question["meta"]["provenance_refs"] == ["Genesis 21:3"]
    assert question["meta"]["inferred"] is True
    assert "Genesis 21:3" in question["explanation"]


def test_load_souffle_trivia_facts_loads_inferred_relations_with_caps(tmp_path):
    (tmp_path / "ancestor_of.csv").write_text("".join(f"Ancestor{i}\tDescendant{i}\n" for i in range(305)), encoding="utf-8")
    (tmp_path / "descendant_of.csv").write_text("Jacob\tAbraham\n", encoding="utf-8")
    (tmp_path / "sibling.csv").write_text("Moses\tAaron\n", encoding="utf-8")
    (tmp_path / "interacted_with.csv").write_text("Moses\tPharaoh\n", encoding="utf-8")
    (tmp_path / "indirect_dialogue.csv").write_text("", encoding="utf-8")
    (tmp_path / "conversation_reach.csv").write_text("Moses\tJoshua\n", encoding="utf-8")

    facts, counts = load_souffle_trivia_facts(str(tmp_path))

    assert counts["ancestor_of"] == 300
    assert counts["descendant_of"] == 1
    assert counts["sibling"] == 1
    assert counts["interacted_with"] == 1
    assert counts["conversation_reach"] == 1
    assert all(fact.get("source") == "souffle" for fact in facts)
    assert {fact["type"] for fact in facts} >= {"ancestor_of", "descendant_of", "sibling", "interacted_with", "conversation_reach"}
