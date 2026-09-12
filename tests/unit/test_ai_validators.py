from bot.ai.schemas import GeneratedWord
from bot.ai.validators import (
    example_mentions_word,
    sanitize_transcriptions,
    validate_generated_word,
)
from bot.database.models.enums import CEFRLevel, PartOfSpeech


def _word(**overrides) -> GeneratedWord:
    defaults = dict(
        lemma="affordable",
        translation="доступний за ціною",
        example_en="This restaurant is affordable for students.",
        example_uk="Цей ресторан доступний за ціною для студентів.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
    )
    defaults.update(overrides)
    return GeneratedWord(**defaults)


def test_example_mentions_word_true_for_exact_match() -> None:
    assert example_mentions_word("affordable", "This is affordable.") is True


def test_example_mentions_word_true_for_inflected_form() -> None:
    assert example_mentions_word("buy", "She buys milk every week.") is True


def test_example_mentions_word_false_when_absent() -> None:
    assert example_mentions_word("affordable", "This is expensive.") is False


def test_validate_generated_word_accepts_well_formed_candidate() -> None:
    assert validate_generated_word(_word()) == []


def test_validate_generated_word_rejects_example_missing_the_word() -> None:
    problems = validate_generated_word(_word(example_en="This is expensive for students."))
    assert any("example" in p for p in problems)


def test_validate_generated_word_rejects_empty_fields() -> None:
    problems = validate_generated_word(_word(translation=""))
    assert any("translation" in p for p in problems)


def test_sanitize_transcriptions_keeps_valid_ipa() -> None:
    word = _word(transcription_uk="/əˈfɔːdəbl/", transcription_us="/əˈfɔːrdəbl/")
    assert sanitize_transcriptions(word) == ("/əˈfɔːdəbl/", "/əˈfɔːrdəbl/")


def test_sanitize_transcriptions_drops_implausible_values() -> None:
    word = _word(transcription_uk="not ipa", transcription_us=None)
    assert sanitize_transcriptions(word) == (None, None)
