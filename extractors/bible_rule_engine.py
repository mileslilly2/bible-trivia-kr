"""
bible_rule_engine.py

Orchestrator for Bible fact extraction.
Loads translation-specific pattern modules.
"""

from typing import List, Dict, Any, Tuple, Callable

_Extractor = Callable[[str, str], Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]

_EXTRACTOR_CACHE: dict[str, List[_Extractor]] = {}


def _load_extractors(translation: str) -> List[_Extractor]:
    t = (translation or "").upper().strip()
    if not t:
        raise ValueError("translation is required (e.g. 'WEB' or 'KJV')")

    if t in _EXTRACTOR_CACHE:
        return _EXTRACTOR_CACHE[t]

    if t == "KJV":
        from .patterns_kjv import get_extractors
        extractors = get_extractors()
    elif t == "WEB":
        from .patterns_web import get_extractors
        extractors = get_extractors()
    else:
        raise ValueError(f"Unsupported translation: {translation}")

    _EXTRACTOR_CACHE[t] = extractors
    return extractors


def _fact_key(f: Dict[str, Any]) -> tuple:
    # ignore any attached evidence fields if you add them later
    ignore = {"text", "norm", "evidence"}
    items = tuple(sorted((k, v) for k, v in f.items() if k not in ignore))
    return items


def extract_facts(
    ref: str,
    text: str,
    translation: str = "WEB",
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:

    extractors = _load_extractors(translation)

    all_facts: List[Dict[str, Any]] = []
    all_drops: List[Dict[str, Any]] = []

    seen = set()

    for extractor in extractors:
        facts, drops = extractor(ref, text)
        for f in facts:
            k = _fact_key(f)
            if k not in seen:
                seen.add(k)
                all_facts.append(f)
        all_drops.extend(drops)

    return all_facts, all_drops
