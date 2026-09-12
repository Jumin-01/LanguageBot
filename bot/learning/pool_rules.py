"""Pure rules governing the size of a user's active learning pool.

MAX_ACTIVE_WORDS is a hard business rule (spec section 6): at most this many
new/learning/review words per user at once. This module is the single
source of truth for that number and the arithmetic around it; PoolService
is the only place that acts on it against the database.
"""

from typing import Final

MAX_ACTIVE_WORDS: Final[int] = 50


def slots_free(active_count: int) -> int:
    return max(0, MAX_ACTIVE_WORDS - active_count)


def needs_replacement(active_count: int) -> bool:
    return active_count < MAX_ACTIVE_WORDS
