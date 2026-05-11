from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REQUIRED_FIELDS = ("id", "category", "difficulty", "question", "choices", "answer_index", "explanation", "ref", "meta")
WEAK_EXPLANATION_MIN_CHARS = 12
EXAMPLE_LIMIT = 8

AWKWARD_QUESTION_PATTERNS = (
    "who could be reached through the conversation graph",
    "could be reached through the conversation graph",
    "through the souffle conversation graph",
    "through the conversation graph rules",
)

SUSPICIOUS_DEMONYMS = {
    "ammonite",
    "ammonites",
    "edomite",
    "edomites",
    "egyptian",
    "egyptians",
    "gentile",
    "gentiles",
    "hebrew",
    "hebrews",
    "israelite",
    "israelites",
    "judean",
    "judeans",
    "moabite",
    "moabites",
    "moabitess",
    "philistine",
    "philistines",
}
DIALOGUE_GROUP_NAMES = {"israel", "judah"}
DIALOGUE_CATEGORIES = {"Bible • Dialogue", "Bible • Inferred Dialogue"}

DIVINE_NAME_RE = re.compile(r"\b(?:Lord|LORD|Yahweh)\b")
CAPITALIZED_RE = re.compile(r"\b[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*)*")
LEADING_QUESTION_WORDS = {"Who", "What", "Where", "When", "Which", "How", "Whose", "To"}


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", _clean_text(value)).casefold()


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _issue(code: str, severity: str, message: str) -> Dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _question_text(question: Dict[str, Any]) -> str:
    return _clean_text(question.get("question") or question.get("prompt"))


def _choices(question: Dict[str, Any]) -> List[Any]:
    choices = question.get("choices")
    return choices if isinstance(choices, list) else []


def _answer_index(question: Dict[str, Any]) -> Optional[int]:
    try:
        return int(question.get("answer_index"))
    except (TypeError, ValueError):
        return None


def _correct_answer(question: Dict[str, Any]) -> str:
    choices = _choices(question)
    answer_index = _answer_index(question)
    if answer_index is None or answer_index < 0 or answer_index >= len(choices):
        return ""
    return _clean_text(choices[answer_index])


def _iter_text_fields(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _iter_text_fields(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_text_fields(child)


def _visible_text(question: Dict[str, Any]) -> str:
    return " ".join([_question_text(question), *[_clean_text(choice) for choice in _choices(question)]])


def _find_suspicious_names(question: Dict[str, Any]) -> List[str]:
    haystack = _visible_text(question)
    tokens = {token.group(0) for token in re.finditer(r"\b[A-Za-z]+\b", haystack)}
    category = _clean_text(question.get("category"))
    suspicious = []
    for token in tokens:
        folded = token.casefold()
        if folded in SUSPICIOUS_DEMONYMS:
            suspicious.append(token)
        elif category in DIALOGUE_CATEGORIES and folded in DIALOGUE_GROUP_NAMES:
            suspicious.append(token)
    return sorted(suspicious)


def _divine_name_variants(question: Dict[str, Any]) -> List[str]:
    return sorted(set(DIVINE_NAME_RE.findall(_visible_text(question))))


def _question_template(question_text: str) -> str:
    text = re.sub(r"\s+", " ", question_text.strip())

    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        first = value.split()[0]
        if match.start() == 0 and first in LEADING_QUESTION_WORDS:
            return value
        return "{entity}"

    return CAPITALIZED_RE.sub(replace, text).casefold()


def score_question(question: Dict[str, Any], index: int = 0) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    qid = _clean_text(question.get("id")) or f"#{index}"
    question_text = _question_text(question)
    choices = _choices(question)
    answer_index = _answer_index(question)

    for field in REQUIRED_FIELDS:
        if field not in question:
            issues.append(_issue("missing_field", "warn", f"Missing field: {field}."))
        elif field in {"id", "category", "difficulty", "question", "meta"} and _is_blank(question.get(field)):
            issues.append(_issue("empty_field", "warn", f"Empty field: {field}."))

    if not question_text:
        issues.append(_issue("empty_question", "fail", "Question text is empty."))

    if not isinstance(question.get("choices"), list):
        issues.append(_issue("choices_not_list", "fail", "Choices must be a list."))
    elif not choices:
        issues.append(_issue("no_choices", "fail", "Question has no answer choices."))
    else:
        empty_choice_positions = [str(i) for i, choice in enumerate(choices) if _is_blank(choice)]
        if empty_choice_positions:
            issues.append(_issue("empty_choice", "fail", f"Empty choice at index(es): {', '.join(empty_choice_positions)}."))

    if answer_index is None or answer_index < 0 or answer_index >= len(choices):
        issues.append(_issue("invalid_answer_index", "fail", "answer_index does not point to a choice."))

    normalized_choices = [_normalized(choice) for choice in choices]
    nonempty_normalized = [choice for choice in normalized_choices if choice]
    if len(nonempty_normalized) != len(set(nonempty_normalized)):
        issues.append(_issue("duplicate_choices", "fail", "Question has duplicate answer choices."))

    if answer_index is not None and 0 <= answer_index < len(choices):
        correct = normalized_choices[answer_index]
        if correct and any(i != answer_index and choice == correct for i, choice in enumerate(normalized_choices)):
            issues.append(_issue("correct_answer_as_distractor", "fail", "Correct answer also appears as a distractor."))

    ref = _clean_text(question.get("ref"))
    if not ref:
        issues.append(_issue("missing_ref", "warn", "Reference is empty."))

    explanation = _clean_text(question.get("explanation"))
    if not explanation or explanation == ":" or len(explanation) < WEAK_EXPLANATION_MIN_CHARS:
        issues.append(_issue("weak_explanation", "warn", "Explanation is empty or too short."))

    lower_question = question_text.casefold()
    if any(pattern in lower_question for pattern in AWKWARD_QUESTION_PATTERNS):
        issues.append(_issue("awkward_question", "warn", "Question contains awkward or overly mechanical phrasing."))

    suspicious_names = _find_suspicious_names(question)
    if suspicious_names:
        issues.append(
            _issue(
                "suspicious_entity_name",
                "warn",
                f"Suspicious generic entity name(s): {', '.join(suspicious_names)}.",
            )
        )

    divine_variants = _divine_name_variants(question)
    if len(divine_variants) > 1:
        issues.append(
            _issue(
                "divine_name_inconsistency",
                "warn",
                f"Mixed divine-name variants: {', '.join(divine_variants)}.",
            )
        )

    quality = "pass"
    if any(issue["severity"] == "fail" for issue in issues):
        quality = "fail"
    elif issues:
        quality = "warn"

    return {
        "id": qid,
        "index": index,
        "quality": quality,
        "question": question_text,
        "ref": ref,
        "answer": _correct_answer(question),
        "issues": issues,
    }


def audit_pack(pack: Dict[str, Any], input_path: str = "") -> Dict[str, Any]:
    raw_questions = pack.get("questions", [])
    questions = raw_questions if isinstance(raw_questions, list) else []
    scored = [score_question(question if isinstance(question, dict) else {}, index) for index, question in enumerate(questions)]

    issue_counts: Counter[str] = Counter()
    for result in scored:
        issue_counts.update(issue["code"] for issue in result["issues"])

    question_counts = Counter(_normalized(_question_text(question)) for question in questions if isinstance(question, dict))
    duplicate_questions = sum(count for key, count in question_counts.items() if key and count > 1)
    if duplicate_questions:
        issue_counts["duplicate_questions"] = duplicate_questions

    category_distribution = Counter(
        _clean_text(question.get("category")) or "<empty>" for question in questions if isinstance(question, dict)
    )
    difficulty_distribution = Counter(
        _clean_text(question.get("difficulty")) or "<empty>" for question in questions if isinstance(question, dict)
    )

    source_counts: Counter[str] = Counter()
    fact_type_counts: Counter[str] = Counter()
    answer_counts: Counter[str] = Counter()
    template_counts: Counter[str] = Counter()
    divine_name_counts: Counter[str] = Counter()

    for question in questions:
        if not isinstance(question, dict):
            continue

        fact = question.get("meta", {}).get("fact", {}) if isinstance(question.get("meta"), dict) else {}
        fact_type = _clean_text(fact.get("type")) if isinstance(fact, dict) else ""
        source = _clean_text(fact.get("source")) if isinstance(fact, dict) else ""
        if source == "souffle":
            source_counts["inferred"] += 1
        elif fact_type:
            source_counts["extracted"] += 1
        else:
            source_counts["unknown"] += 1
        if fact_type:
            fact_type_counts[fact_type] += 1

        answer = _correct_answer(question)
        if answer:
            answer_counts[answer] += 1

        template = _question_template(_question_text(question))
        if template:
            template_counts[template] += 1

        divine_name_counts.update(_divine_name_variants(question))

    quality_counts = Counter(result["quality"] for result in scored)
    duplicate_question_examples = [
        {"question": key, "count": count} for key, count in question_counts.most_common() if key and count > 1
    ][:EXAMPLE_LIMIT]

    examples_by_code: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for result in scored:
        for issue in result["issues"]:
            bucket = examples_by_code[issue["code"]]
            if len(bucket) < 3:
                bucket.append(
                    {
                        "id": result["id"],
                        "index": result["index"],
                        "question": result["question"],
                        "message": issue["message"],
                    }
                )

    return {
        "input": input_path,
        "total_questions": len(questions),
        "quality_counts": dict(sorted(quality_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "category_distribution": dict(category_distribution.most_common()),
        "difficulty_distribution": dict(difficulty_distribution.most_common()),
        "source_counts": dict(source_counts.most_common()),
        "fact_type_counts": dict(fact_type_counts.most_common()),
        "divine_name_distribution": dict(divine_name_counts.most_common()),
        "top_repeated_answers": [
            {"answer": answer, "count": count} for answer, count in answer_counts.most_common(15) if count > 1
        ],
        "top_repeated_question_templates": [
            {"template": template, "count": count} for template, count in template_counts.most_common(15) if count > 1
        ],
        "duplicate_question_examples": duplicate_question_examples,
        "examples_by_issue": dict(examples_by_code),
        "questions": scored,
    }


def _print_counter(title: str, values: Dict[str, int], limit: int = 8) -> None:
    print(title)
    if not values:
        print("  none")
        return
    for key, count in list(values.items())[:limit]:
        print(f"  {key}: {count}")


def print_summary(report: Dict[str, Any], output_path: Path) -> None:
    print(f"[audit] questions={report['total_questions']} report={output_path}")
    print(
        "[quality] "
        f"pass={report['quality_counts'].get('pass', 0)} "
        f"warn={report['quality_counts'].get('warn', 0)} "
        f"fail={report['quality_counts'].get('fail', 0)}"
    )

    issue_counts = report["issue_counts"]
    print(
        "[warnings] "
        f"missing_refs={issue_counts.get('missing_ref', 0)} "
        f"weak_explanations={issue_counts.get('weak_explanation', 0)} "
        f"duplicate_questions={issue_counts.get('duplicate_questions', 0)} "
        f"duplicate_choices={issue_counts.get('duplicate_choices', 0)} "
        f"empty_fields={issue_counts.get('empty_field', 0)} "
        f"vague={issue_counts.get('awkward_question', 0)} "
        f"suspicious_entities={issue_counts.get('suspicious_entity_name', 0)}"
    )

    _print_counter("[audit] category distribution", report["category_distribution"])
    _print_counter("[audit] difficulty distribution", report["difficulty_distribution"])
    _print_counter("[audit] source counts", report["source_counts"])
    _print_counter("[audit] fact type counts", report["fact_type_counts"])

    print("[audit] top repeated answers")
    for item in report["top_repeated_answers"][:8]:
        print(f"  {item['answer']}: {item['count']}")
    if not report["top_repeated_answers"]:
        print("  none")

    print("[audit] top repeated question templates")
    for item in report["top_repeated_question_templates"][:8]:
        print(f"  {item['template']}: {item['count']}")
    if not report["top_repeated_question_templates"]:
        print("  none")

    print("[examples]")
    shown = 0
    for result in report["questions"]:
        if result["quality"] == "pass":
            continue
        codes = ", ".join(issue["code"] for issue in result["issues"])
        print(f"  {result['quality']} q{result['index']} {result['id']}: {codes} | {result['question']}")
        shown += 1
        if shown >= EXAMPLE_LIMIT:
            break
    if shown == 0:
        print("  none")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a generated trivia pack for obvious quality defects.")
    parser.add_argument("--input", default="out/trivia/trivia_pack.json", help="Input trivia pack JSON.")
    parser.add_argument("--output", default="out/trivia/trivia_audit.json", help="Output audit report JSON.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    pack = json.loads(input_path.read_text(encoding="utf-8"))
    report = audit_pack(pack, input_path=str(input_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print_summary(report, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
