from scripts.audit_trivia_pack import audit_pack, score_question


def _question(**overrides):
    base = {
        "id": "q1",
        "category": "Bible",
        "difficulty": "easy",
        "question": "Who spoke to Moses?",
        "choices": ["Yahweh", "Aaron", "Joshua", "Miriam"],
        "answer_index": 0,
        "explanation": "Exodus 3:4 gives the source for this answer.",
        "ref": "Exodus 3:4",
        "meta": {"fact": {"type": "spoke_to", "speaker": "Yahweh", "listener": "Moses"}},
    }
    base.update(overrides)
    return base


def _codes(result):
    return {issue["code"] for issue in result["issues"]}


def test_score_question_fails_structural_choice_defects():
    no_choices = score_question(_question(choices=[]))
    assert no_choices["quality"] == "fail"
    assert "no_choices" in _codes(no_choices)

    bad_answer_index = score_question(_question(answer_index=9))
    assert bad_answer_index["quality"] == "fail"
    assert "invalid_answer_index" in _codes(bad_answer_index)

    duplicate_choices = score_question(_question(choices=["Yahweh", "Aaron", "Yahweh", "Miriam"], answer_index=0))
    assert duplicate_choices["quality"] == "fail"
    assert {"duplicate_choices", "correct_answer_as_distractor"} <= _codes(duplicate_choices)


def test_score_question_warns_for_quality_concerns():
    weak_ref_and_explanation = score_question(_question(ref="", explanation=":"))
    assert weak_ref_and_explanation["quality"] == "warn"
    assert {"missing_ref", "weak_explanation"} <= _codes(weak_ref_and_explanation)

    awkward = score_question(_question(question="Who could be reached through the conversation graph from Moses?"))
    assert awkward["quality"] == "warn"
    assert "awkward_question" in _codes(awkward)

    suspicious = score_question(_question(choices=["Moabitess", "Aaron", "Joshua", "Miriam"], answer_index=0))
    assert suspicious["quality"] == "warn"
    assert "suspicious_entity_name" in _codes(suspicious)


def test_audit_pack_reports_distributions_and_detectable_sources():
    pack = {
        "questions": [
            _question(id="q1", meta={"fact": {"type": "spoke_to", "source": "souffle"}}),
            _question(id="q2", question="Who spoke to Moses?", choices=["Aaron", "Yahweh", "Joshua", "Miriam"], answer_index=1),
            _question(id="q3", category="Bible • Travel", difficulty="medium", question="Where did Moses travel?", meta={}),
        ]
    }

    report = audit_pack(pack, input_path="pack.json")

    assert report["total_questions"] == 3
    assert report["source_counts"]["inferred"] == 1
    assert report["source_counts"]["extracted"] == 1
    assert report["source_counts"]["unknown"] == 1
    assert report["fact_type_counts"]["spoke_to"] == 2
    assert report["category_distribution"]["Bible"] == 2
    assert report["difficulty_distribution"]["easy"] == 2
    assert report["issue_counts"]["duplicate_questions"] == 2
    assert report["top_repeated_question_templates"][0]["template"] == "who spoke to {entity}?"
