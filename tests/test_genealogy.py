from extractors.bible_rule_engine import extract_facts

TESTS = [
    (
        "Genesis 4:22",
        "And Zillah also bare Tubal-cain, an instructor of every artificer in brass and iron.",
        {"mother": "Zillah", "child": "Tubal-cain"},
    ),
    (
        "Genesis 5:3",
        "And Adam begat Seth.",
        {"father": "Adam", "child": "Seth"},
    ),
]

def test_genealogy():
    for ref, text, expected in TESTS:
        facts, drops = extract_facts(ref, text)
        assert len(facts) == 1, (ref, facts, drops)

        fact = facts[0]
        assert fact["type"] == "genealogy"

        for k, v in expected.items():
            assert fact[k] == v
