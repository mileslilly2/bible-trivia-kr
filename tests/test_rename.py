from extractors.bible_rule_engine import extract_facts

def test_rename():
    ref = "Genesis 21:3"
    text = "Abraham called his son's name Isaac."

    facts, drops = extract_facts(ref, text)

    assert len(facts) == 1
    fact = facts[0]
    assert fact["type"] == "rename"
    assert fact["name"] == "Isaac"
