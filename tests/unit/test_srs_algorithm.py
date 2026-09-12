from datetime import UTC, datetime, timedelta
from decimal import Decimal

from bot.database.models.enums import WordStatus
from bot.learning.models import WordProgress
from bot.learning.srs_algorithm import (
    MASTERY_INTERVAL_DAYS,
    MIN_EASE_FACTOR,
    MIN_INTERVAL_DAYS,
    MIN_STREAK_FOR_MASTERY,
    compute_fast_mastery_state,
    compute_next_state,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _progress(**overrides) -> WordProgress:
    defaults = dict(
        user_word_id=1,
        status=WordStatus.NEW,
        correct_answers=0,
        wrong_answers=0,
        repetitions=0,
        consecutive_correct=0,
        ease_factor=Decimal("2.50"),
        current_interval_days=Decimal("0"),
        last_review_at=None,
        next_review_at=None,
    )
    defaults.update(overrides)
    return WordProgress(**defaults)


def test_first_correct_answer_schedules_one_day_and_stays_learning() -> None:
    result = compute_next_state(_progress(), is_correct=True, now=NOW)

    assert result.new_repetitions == 1
    assert result.new_consecutive_correct == 1
    assert result.new_interval_days == Decimal("1")
    assert result.new_status == WordStatus.LEARNING
    assert result.became_learned is False
    assert result.new_next_review_at == NOW + timedelta(days=1)


def test_baseline_progression_matches_spec_1_3_7_14() -> None:
    progress = _progress()
    intervals = []
    for _ in range(4):
        result = compute_next_state(progress, is_correct=True, now=NOW)
        intervals.append(result.new_interval_days)
        progress = _progress(
            repetitions=result.new_repetitions,
            consecutive_correct=result.new_consecutive_correct,
            ease_factor=result.new_ease_factor,
            current_interval_days=result.new_interval_days,
        )

    assert intervals == [Decimal("1"), Decimal("3"), Decimal("7"), Decimal("14")]


def test_third_correct_answer_moves_to_review_but_not_learned() -> None:
    progress = _progress(repetitions=2, consecutive_correct=2, current_interval_days=Decimal("3"))
    result = compute_next_state(progress, is_correct=True, now=NOW)

    assert result.new_repetitions == 3
    assert result.new_interval_days == Decimal("7")
    assert result.new_status == WordStatus.REVIEW
    assert result.became_learned is False


def test_fourth_correct_answer_with_full_streak_becomes_learned() -> None:
    progress = _progress(repetitions=3, consecutive_correct=3, current_interval_days=Decimal("7"))
    result = compute_next_state(progress, is_correct=True, now=NOW)

    assert result.new_repetitions == 4
    assert result.new_interval_days == Decimal("14")
    assert result.became_learned is True
    assert result.new_status == WordStatus.LEARNED


def test_cannot_reach_mastery_by_guessing_after_a_miss_breaks_the_streak() -> None:
    # A user who has a full baseline streak going (3 correct) but then misses
    # must restart the 1/3/7/14 climb -- they cannot recover mastery on the
    # very next correct answer.
    progress = _progress(repetitions=3, consecutive_correct=3, current_interval_days=Decimal("7"))
    missed = compute_next_state(progress, is_correct=False, now=NOW)
    assert missed.became_learned is False
    assert missed.new_consecutive_correct == 0

    recovered_progress = _progress(
        repetitions=missed.new_repetitions,
        consecutive_correct=missed.new_consecutive_correct,
        ease_factor=missed.new_ease_factor,
        current_interval_days=missed.new_interval_days,
    )
    next_correct = compute_next_state(recovered_progress, is_correct=True, now=NOW)
    assert next_correct.became_learned is False
    assert next_correct.new_repetitions < 4


def test_wrong_answer_steps_back_one_stage_not_a_full_reset() -> None:
    progress = _progress(repetitions=2, consecutive_correct=2, current_interval_days=Decimal("3"))
    result = compute_next_state(progress, is_correct=False, now=NOW)

    assert result.new_repetitions == 1
    assert result.new_consecutive_correct == 0
    assert result.new_status == WordStatus.LEARNING
    assert result.became_learned is False


def test_wrong_answer_shrinks_interval_by_half() -> None:
    progress = _progress(current_interval_days=Decimal("14"))
    result = compute_next_state(progress, is_correct=False, now=NOW)
    assert result.new_interval_days == Decimal("7.00")


def test_wrong_answer_interval_never_below_floor() -> None:
    progress = _progress(current_interval_days=Decimal("0.5"))
    result = compute_next_state(progress, is_correct=False, now=NOW)
    assert result.new_interval_days == MIN_INTERVAL_DAYS


def test_wrong_answer_never_regresses_status_to_new() -> None:
    progress = _progress(
        status=WordStatus.LEARNING, repetitions=0, current_interval_days=Decimal("1")
    )
    result = compute_next_state(progress, is_correct=False, now=NOW)
    assert result.new_status == WordStatus.LEARNING
    assert result.new_status != WordStatus.NEW


def test_repetitions_never_go_negative() -> None:
    progress = _progress(repetitions=0)
    result = compute_next_state(progress, is_correct=False, now=NOW)
    assert result.new_repetitions == 0


def test_ease_factor_never_drops_below_minimum() -> None:
    progress = _progress(ease_factor=MIN_EASE_FACTOR)
    for _ in range(20):
        result = compute_next_state(progress, is_correct=False, now=NOW)
        progress = _progress(
            ease_factor=result.new_ease_factor,
            repetitions=result.new_repetitions,
            current_interval_days=result.new_interval_days,
        )
    assert progress.ease_factor >= MIN_EASE_FACTOR


def test_ease_factor_unchanged_by_a_correct_answer() -> None:
    # SM-2's quality=4 (our "correct" signal) yields a zero EF delta -- EF only
    # ever moves down (on a miss), never up, matching the classic algorithm.
    progress = _progress(ease_factor=Decimal("2.50"))
    result = compute_next_state(progress, is_correct=True, now=NOW)
    assert result.new_ease_factor == Decimal("2.50")


def test_ease_factor_decreases_on_wrong_answer() -> None:
    progress = _progress(ease_factor=Decimal("2.50"))
    result = compute_next_state(progress, is_correct=False, now=NOW)
    assert result.new_ease_factor < Decimal("2.50")


def test_growth_past_baseline_table_uses_ease_factor() -> None:
    progress = _progress(repetitions=4, consecutive_correct=4, current_interval_days=Decimal("14"))
    result = compute_next_state(progress, is_correct=True, now=NOW)
    # repetitions=5 is past the 4-entry baseline table, so interval grows via ease factor.
    assert result.new_interval_days == Decimal("14") * result.new_ease_factor


def test_fast_mastery_marks_learned_immediately_from_a_brand_new_word() -> None:
    # "I already know this word" on a word never answered before: one correct
    # verification answer is enough -- no 1/3/7/14-day climb required.
    progress = _progress()
    result = compute_fast_mastery_state(progress, now=NOW)

    assert result.new_status == WordStatus.LEARNED
    assert result.became_learned is True
    assert result.new_repetitions >= MIN_STREAK_FOR_MASTERY
    assert result.new_consecutive_correct == MIN_STREAK_FOR_MASTERY
    assert result.new_interval_days == MASTERY_INTERVAL_DAYS
    assert result.new_next_review_at == NOW + timedelta(days=float(MASTERY_INTERVAL_DAYS))


def test_fast_mastery_does_not_shrink_existing_repetitions() -> None:
    progress = _progress(repetitions=6, consecutive_correct=1, current_interval_days=Decimal("2"))
    result = compute_fast_mastery_state(progress, now=NOW)
    assert result.new_repetitions == 6


def test_fast_mastery_ease_factor_unchanged_like_any_correct_answer() -> None:
    progress = _progress(ease_factor=Decimal("2.50"))
    result = compute_fast_mastery_state(progress, now=NOW)
    assert result.new_ease_factor == Decimal("2.50")
