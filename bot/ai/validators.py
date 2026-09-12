"""Validation gate between an AI-proposed word and persisting it.

Spec: "якщо відповідь не проходить валідацію -- не записувати її в БД."
Structural validity (right fields, right types, enum membership) is already
guaranteed by pydantic/response_schema; this module checks the *substance*
a schema can't -- e.g. does the example sentence actually use the word
being taught.
"""

from bot.ai.schemas import GeneratedWord
from bot.learning.transcription_rules import is_plausible_ipa


def _normalized_stem(lemma: str) -> str:
    # Loose stem: the first few characters of the first token, lowercased --
    # enough to catch "affordable" appearing as-is, or "buy" appearing as
    # "buys"/"buying", without a full morphological analyzer.
    first_token = lemma.strip().lower().split()[0] if lemma.strip() else ""
    return first_token[:4]


def example_mentions_word(lemma: str, example_en: str) -> bool:
    stem = _normalized_stem(lemma)
    if not stem:
        return False
    return stem in example_en.lower()


def validate_generated_word(item: GeneratedWord) -> list[str]:
    """Returns a list of problems; an empty list means the candidate is safe
    to persist. Never raises -- the caller decides whether to drop it."""

    problems: list[str] = []

    if not item.lemma.strip():
        problems.append("empty lemma")
    if not item.translation.strip():
        problems.append("empty translation")
    if not item.example_en.strip():
        problems.append("empty example_en")
    if not item.example_uk.strip():
        problems.append("empty example_uk")
    if item.example_en.strip() and not example_mentions_word(item.lemma, item.example_en):
        problems.append("example does not appear to use the word")

    return problems


def sanitize_transcriptions(item: GeneratedWord) -> tuple[str | None, str | None]:
    """Drops an implausible transcription rather than rejecting the whole
    word for it -- transcription is a nice-to-have field, not core data."""

    uk = item.transcription_uk if is_plausible_ipa(item.transcription_uk) else None
    us = item.transcription_us if is_plausible_ipa(item.transcription_us) else None
    return uk, us
