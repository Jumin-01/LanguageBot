import random
from decimal import Decimal

from bot.database.models.enums import QuestionType, WordStatus
from bot.learning.models import WordProgress
from bot.learning.question_selector import choose_question_type


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


def test_brand_new_word_gets_easiest_recognition_question() -> None:
    progress = _progress(repetitions=0)
    assert choose_question_type(progress) == QuestionType.EN_TO_UA_CHOICE


def test_tier_one_is_production_question() -> None:
    progress = _progress(repetitions=1, consecutive_correct=1)
    assert choose_question_type(progress) == QuestionType.UA_TO_EN_CHOICE


def test_tier_two_is_fill_blank_or_choose_word() -> None:
    progress = _progress(repetitions=2, consecutive_correct=2)
    rng = random.Random(42)
    result = choose_question_type(progress, rng)
    assert result in (QuestionType.FILL_BLANK, QuestionType.CHOOSE_WORD_FOR_SENTENCE)


def test_tier_three_is_translate_or_choose_example() -> None:
    progress = _progress(repetitions=3, consecutive_correct=3)
    rng = random.Random(7)
    result = choose_question_type(progress, rng)
    assert result in (QuestionType.TRANSLATE_SENTENCE, QuestionType.CHOOSE_CORRECT_EXAMPLE)


def test_tier_four_and_above_rotates_through_all_types() -> None:
    progress = _progress(repetitions=10, consecutive_correct=10)
    rng = random.Random(1)
    result = choose_question_type(progress, rng)
    assert result in set(QuestionType)


def test_recent_wrong_answer_forces_easiest_question_regardless_of_repetitions() -> None:
    progress = _progress(repetitions=3, consecutive_correct=0, wrong_answers=1)
    assert choose_question_type(progress) == QuestionType.EN_TO_UA_CHOICE
