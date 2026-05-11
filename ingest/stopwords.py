"""
Lexical stopwords and lightweight entity filters.

Purpose:
- Prevent parser from treating conjunctions, pronouns, or discourse words
  as entities (e.g. "And", "She", "He").
- This is NOT semantics or theology — it is lexical hygiene.

Design rule:
- Conservative: block obvious junk
- Never block real proper nouns (Eve, Cain, God, etc.)
"""

from typing import Set

# -----------------------------
# Core stopwords (lowercase)
# -----------------------------

STOPWORDS: Set[str] = {
    # conjunctions / discourse markers
    "and", "but", "or", "so", "then", "now", "for", "yet",

    # pronouns
    "he", "she", "they", "them", "him", "her", "his", "their", "theirs",

    # determiners
    "the", "a", "an", "this", "that", "these", "those",

    # auxiliaries / copulas
    "is", "was", "were", "be", "been", "being",

    # common verbs that appear capitalized in KJV-style text
    "said", "says", "answered", "spoke", "called", "knew",

    # fillers often capitalized at sentence start
    "there", "here", "when", "where", "which", "who", "whom", "whose",
}

# -----------------------------
# Public helpers
# -----------------------------

def normalize(token: str) -> str:
    """Normalize a token for comparison."""
    return token.strip().lower()


def is_stopword(token: str) -> bool:
    """
    Returns True if token should NEVER be treated as an entity.
    """
    if not token:
        return True
    return normalize(token) in STOPWORDS


def is_valid_entity(token: str) -> bool:
    """
    Returns True if token is allowed to be an entity candidate.

    This does NOT guarantee correctness — only that it is not garbage.
    """
    if not token:
        return False

    t = normalize(token)

    # block stopwords
    if t in STOPWORDS:
        return False

    # block pure punctuation / numbers
    if not any(c.isalpha() for c in t):
        return False

    # allow everything else
    return True
