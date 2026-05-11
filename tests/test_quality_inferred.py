from extractors.question_engine import facts_to_trivia_pack
import random

def _base_people():
    return [
        {"type": "parent_of", "parent": "Adam", "child": "Seth", "ref": "Genesis 5:3", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Noah", "child": "Shem", "ref": "Genesis 5:32", "text": "", "norm": ""},
        {"type": "spoke_to", "speaker": "Moses", "listener": "Aaron", "ref": "Exodus 4:28", "text": "", "norm": ""},
        {"type": "killed", "killer": "Cain", "victim": "Abel", "ref": "Genesis 4:8", "text": "", "norm": ""},
        {"type": "parent_of", "parent": "Abraham", "child": "Isaac", "ref": "Genesis 21:3"},
        {"type": "parent_of", "parent": "Isaac", "child": "Jacob", "ref": "Genesis 25:26"},
    ]

def test_genealogy_depth_filtering():
    # Depth 3, no provenance -> should be filtered
    facts = _base_people() + [
        {
            "type": "ancestor_of",
            "ancestor": "Abraham",
            "descendant": "Jacob",
            "ref": "",
            "text": "",
            "norm": "",
            "source": "souffle",
            "genealogy_chain": ["Abraham", "Isaac", "Esau", "Jacob"], # depth 3
            "genealogy_depth": 3,
        }
    ]
    
    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=42)
    inferred = [q for q in pack["questions"] if q["meta"]["fact"]["type"] == "ancestor_of"]
    assert len(inferred) == 0

    # Depth 2, no provenance -> should be kept
    facts2 = _base_people() + [
        {
            "type": "ancestor_of",
            "ancestor": "Abraham",
            "descendant": "Jacob",
            "ref": "",
            "text": "",
            "norm": "",
            "source": "souffle",
            "genealogy_chain": ["Abraham", "Isaac", "Jacob"], # depth 2
            "genealogy_depth": 2,
        }
    ]
    pack2 = facts_to_trivia_pack(facts2, "test-pack", "Test Pack", "WEB", seed=42)
    inferred2 = [q for q in pack2["questions"] if q["meta"]["fact"]["type"] == "ancestor_of"]
    assert len(inferred2) == 1

def test_obscure_name_filtering():
    # "ObscureName" never appears in extracted facts -> should be filtered
    facts = _base_people() + [
        {
            "type": "interacted_with",
            "person": "Moses",
            "other": "ObscureName",
            "ref": "Exodus 1:1",
            "text": "",
            "norm": "",
            "source": "souffle",
            "provenance_refs": ["Exodus 1:1"]
        }
    ]
    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=42)
    inferred = [q for q in pack["questions"] if q["meta"]["fact"]["type"] == "interacted_with"]
    assert len(inferred) == 0

    # "Pharaoh" appears in extracted facts (implicitly through _base_people if we add it)
    facts2 = _base_people() + [
        {"type": "spoke_to", "speaker": "Moses", "listener": "Pharaoh", "ref": "Exodus 5:1", "text": "", "norm": ""},
        {
            "type": "interacted_with",
            "person": "Aaron",
            "other": "Pharaoh",
            "ref": "Exodus 5:1",
            "text": "",
            "norm": "",
            "source": "souffle",
            "provenance_refs": ["Exodus 5:1"]
        }
    ]
    pack2 = facts_to_trivia_pack(facts2, "test-pack", "Test Pack", "WEB", seed=42)
    inferred2 = [q for q in pack2["questions"] if q["meta"]["fact"]["type"] == "interacted_with"]
    assert len(inferred2) == 1

def test_improved_explanation_phrasing():
    facts = _base_people() + [
        {"type": "spoke_to", "speaker": "Moses", "listener": "Pharaoh", "ref": "Exodus 5:1"},
        {
            "type": "interacted_with",
            "person": "Moses",
            "other": "Pharaoh",
            "ref": "Exodus 5:1",
            "text": "",
            "norm": "",
            "source": "souffle",
            "provenance_refs": ["Exodus 5:1"]
        }
    ]
    pack = facts_to_trivia_pack(facts, "test-pack", "Test Pack", "WEB", seed=42)
    q = next(q for q in pack["questions"] if q["meta"]["fact"]["type"] == "interacted_with")
    assert "linked through a chain of recorded speech interactions" in q["explanation"]
