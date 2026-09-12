"""Plain DTOs returned by the service layer.

Handlers (and any future web/mobile client) depend only on these, never on
SQLAlchemy model instances -- so the ORM can change shape without touching
callers, and services stay testable without a live session in the caller.
"""

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal

from bot.database.models.enums import (
    CEFRLevel,
    OnboardingStatus,
    PartOfSpeech,
    WordSource,
    WordStatus,
)


@dataclass(frozen=True)
class WordDTO:
    id: int
    lemma: str
    translation: str
    example_en: str
    example_uk: str
    level: CEFRLevel
    part_of_speech: PartOfSpeech
    topic: str | None
    transcription_uk: str | None
    transcription_us: str | None
    synonyms: list[str]
    antonyms: list[str]
    collocations: list[str]
    source: WordSource


@dataclass(frozen=True)
class UserWordDTO:
    id: int
    user_id: int
    word: WordDTO
    status: WordStatus
    correct_answers: int
    wrong_answers: int
    repetitions: int
    consecutive_correct: int
    ease_factor: Decimal
    current_interval_days: Decimal
    last_review_at: datetime | None
    next_review_at: datetime | None
    learned_at: datetime | None


@dataclass(frozen=True)
class UserDTO:
    id: int
    telegram_id: int
    username: str | None
    first_name: str | None
    current_level: CEFRLevel
    onboarding_status: OnboardingStatus


@dataclass(frozen=True)
class UserSettingsDTO:
    user_id: int
    utc_offset_minutes: int
    daily_new_words_goal: int
    sessions_per_day: int
    quiet_hours_start: time
    quiet_hours_end: time


@dataclass(frozen=True)
class SessionTimeDTO:
    time_of_day: time
    enabled: bool


@dataclass(frozen=True)
class StatisticsSummaryDTO:
    total_learned: int
    new_this_week: int
    total_repetitions: int
    correct_percentage: float | None
    avg_words_per_day: float
    current_level: CEFRLevel
    learned_this_week: int
    learned_this_month: int
