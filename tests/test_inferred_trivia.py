from extractors.question_engine import facts_to_trivia_pack
from scripts.batch_generate import load_souffle_trivia_facts


def _base_people():
    return [
        {"type": "parent_of", "parent": "Adam", "child": "Seth", "ref": "Genesis 5:3", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Noah", "child": "Shem", "ref": "Genesis 5:32", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Moses", "listener": "Aaron", "ref": "Exodus 4:28", "text": "", "norm": ""},
        {"type": "killed", "killer": "Cain", "victim": "Abel", "ref": "Genesis 4:8", "text": "", "norm": ""},
    ]


def test_inferred_facts_generate_valid_pack_schema():
    facts = _base_people() + [
        {"type": "ancestor_of", "ancestor": "Abraham", "descendant": "Jacob", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "descendant_of", "descendant": "Jacob", "ancestor": "Abraham", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "sibling", "person": "Moses", "sibling": "Aaron", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "interacted_with", "person": "Moses", "other": "Pharaoh", "ref": "", "text": "", "norm": "", "source": "souffle"},
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
    assert "inferred as an ancestor" in inferred_explanations["ancestor_of"]
    assert "inferred as a descendant" in inferred_explanations["descendant_of"]
    assert "share a parent" in inferred_explanations["sibling"]
    assert "through a dialogue relation" in inferred_explanations["interacted_with"]
    assert "through the dialogue graph" in inferred_explanations["indirect_dialogue"]


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
        {"type": "interacted_with", "person": "Moses", "other": "Pharaoh", "ref": "", "text": "", "norm": "", "source": "souffle"},
        {"type": "interacted_with", "person": "Aaron", "other": "Joshua", "ref": "", "text": "", "norm": "", "source": "souffle"},
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
