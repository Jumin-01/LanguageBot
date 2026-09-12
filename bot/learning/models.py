"""Pure domain dataclasses for the learning engine.

Deliberately free of any ORM/Telegram imports (only stdlib + the plain enum
definitions in bot.database.models.enums, which have no SQLAlchemy dependency
of their own) so this module -- and everything built on top of it in
bot/learning/ -- stays 100% unit-testable without a database or Telegram.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from bot.database.models.enums import QuestionType, WordStatus


@dataclass(frozen=True)
class WordProgress:
    """Snapshot of a user_words row's SRS-relevant fields."""

    user_word_id: int
    status: WordStatus
    correct_answers: int
    wrong_answers: int
    repetitions: int
    consecutive_correct: int
    ease_factor: Decimal
    current_interval_days: Decimal
    last_review_at: datetime | None
    next_review_at: datetime | None


@dataclass(frozen=True)
class SRSUpdateResult:
    """Result of applying one answer to a WordProgress via the SRS algorithm."""

    new_status: WordStatus
    new_repetitions: int
    new_consecutive_correct: int
    new_ease_factor: Decimal
    new_interval_days: Decimal
    new_next_review_at: datetime
    became_learned: bool


@dataclass(frozen=True)
class QuizQuestion:
    """A fully-formed question ready to render, independent of Telegram."""

    user_word_id: int
    word_id: int
    question_type: QuestionType
    prompt: str
    options: list[str] | None  # None for free-text question types
    correct_option_index: int | None
    correct_answer_text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerOutcome:
    """Result of submitting an answer to a QuizQuestion."""

    is_correct: bool
    correct_answer_text: str
    srs_result: SRSUpdateResult
    became_learned: bool
