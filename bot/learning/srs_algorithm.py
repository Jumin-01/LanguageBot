"""Spaced-repetition scheduling: pure function, no I/O.

Baseline progression (per the product spec): 1 day -> 3 days -> 7 days -> 14 days,
after which a word is considered learned -- but only if the streak of *consecutive*
correct answers actually cleared all four checkpoints. A wrong answer at any point
steps the word back one baseline stage, shrinks the interval, and resets the streak,
so a user cannot "guess" their way to mastery.

Past the fourth baseline checkpoint the interval keeps growing using an SM-2-style
ease factor, so the algorithm keeps adapting for words reviewed beyond the baseline
table instead of repeating a fixed schedule forever.
"""

from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from bot.database.models.enums import WordStatus
from bot.learning.models import SRSUpdateResult, WordProgress

BASELINE_INTERVALS_DAYS: list[Decimal] = [Decimal("1"), Decimal("3"), Decimal("7"), Decimal("14")]
REVIEW_THRESHOLD_DAYS = Decimal("7")
MASTERY_INTERVAL_DAYS = Decimal("14")
MIN_STREAK_FOR_MASTERY = len(BASELINE_INTERVALS_DAYS)  # 4
MIN_EASE_FACTOR = Decimal("1.3")
MIN_INTERVAL_DAYS = Decimal("0.5")
WRONG_ANSWER_SHRINK_FACTOR = Decimal("0.5")

_EF_DELTA_BASE = Decimal("0.1")
_EF_DELTA_LINEAR = Decimal("0.08")
_EF_DELTA_QUADRATIC = Decimal("0.02")


def _next_ease_factor(current: Decimal, is_correct: bool) -> Decimal:
    # SM-2-style quality signal, binary per spec.
    quality = Decimal(4) if is_correct else Decimal(2)
    delta = _EF_DELTA_BASE - (5 - quality) * (
        _EF_DELTA_LINEAR + (5 - quality) * _EF_DELTA_QUADRATIC
    )
    return max(current + delta, MIN_EASE_FACTOR)


def compute_next_state(progress: WordProgress, is_correct: bool, now: datetime) -> SRSUpdateResult:
    ease_factor = _next_ease_factor(progress.ease_factor, is_correct)

    if is_correct:
        repetitions = progress.repetitions + 1
        consecutive_correct = progress.consecutive_correct + 1

        if repetitions <= len(BASELINE_INTERVALS_DAYS):
            interval = BASELINE_INTERVALS_DAYS[repetitions - 1]
        else:
            # Past the baseline table: keep growing using the ease factor, SM-2 style.
            interval = progress.current_interval_days * ease_factor

        became_learned = (
            repetitions >= MIN_STREAK_FOR_MASTERY
            and consecutive_correct >= MIN_STREAK_FOR_MASTERY
            and interval >= MASTERY_INTERVAL_DAYS
        )
        if became_learned:
            new_status = WordStatus.LEARNED
        elif interval >= REVIEW_THRESHOLD_DAYS:
            new_status = WordStatus.REVIEW
        else:
            new_status = WordStatus.LEARNING
    else:
        # Step back one baseline stage rather than a full reset; shrink the interval
        # so a missed word resurfaces sooner; break the consecutive-correct streak.
        repetitions = max(0, progress.repetitions - 1)
        consecutive_correct = 0
        interval = max(
            progress.current_interval_days * WRONG_ANSWER_SHRINK_FACTOR, MIN_INTERVAL_DAYS
        )
        became_learned = False
        # A word that has been attempted at least once never regresses to 'new'.
        new_status = WordStatus.LEARNING

    next_review_at = now + timedelta(days=float(interval))

    return SRSUpdateResult(
        new_status=new_status,
        new_repetitions=repetitions,
        new_consecutive_correct=consecutive_correct,
        new_ease_factor=ease_factor,
        new_interval_days=interval,
        new_next_review_at=next_review_at,
        became_learned=became_learned,
    )


def compute_fast_mastery_state(progress: WordProgress, now: datetime) -> SRSUpdateResult:
    """A user-initiated fast track ("I already know this word") still requires
    a correct answer on the hardest verification question, but skips the
    1/3/7/14-day baseline ladder entirely. For vocabulary the user genuinely
    already knows, forcing weeks of repetition before a pool slot frees up is
    pure friction, not verification -- the hard question is the verification.
    """
    ease_factor = _next_ease_factor(progress.ease_factor, True)
    next_review_at = now + timedelta(days=float(MASTERY_INTERVAL_DAYS))
    return SRSUpdateResult(
        new_status=WordStatus.LEARNED,
        new_repetitions=max(progress.repetitions, MIN_STREAK_FOR_MASTERY),
        new_consecutive_correct=MIN_STREAK_FOR_MASTERY,
        new_ease_factor=ease_factor,
        new_interval_days=MASTERY_INTERVAL_DAYS,
        new_next_review_at=next_review_at,
        became_learned=True,
    )


def apply_answer_counts(progress: WordProgress, is_correct: bool) -> WordProgress:
    """Helper for callers that need updated correct/wrong counters alongside the
    SRS state (kept separate from compute_next_state so that function stays a
    pure function of exactly the fields the algorithm itself needs)."""

    if is_correct:
        return replace(progress, correct_answers=progress.correct_answers + 1)
    return replace(progress, wrong_answers=progress.wrong_answers + 1)
