"""One-off manual sanity check for the real Gemini API integration.

Confirms structured JSON output actually parses into our pydantic models --
run this once after setting a real GEMINI_API_KEY in .env, before trusting
the AI-backed pool refill in a live bot. Not part of the automated test
suite (tests/integration/test_vocabulary_generation_service.py covers the
business logic against a FakeAIProvider instead, with no network calls).

    python -m scripts.manual_gemini_smoke
"""

import asyncio

from bot.ai.gemini_provider import GeminiAIProvider
from bot.ai.provider import GenerateWordsRequest
from bot.ai.router import AIRouter
from bot.config import settings
from bot.database.models.enums import CEFRLevel


async def main() -> None:
    router = AIRouter(
        default_model=settings.gemini_default_model, advanced_model=settings.gemini_advanced_model
    )
    provider = GeminiAIProvider(settings.gemini_api_key, router)

    print(f"Default model: {settings.gemini_default_model}")
    print(f"Advanced model: {settings.gemini_advanced_model}\n")

    print("=== generate_words ===")
    words = await provider.generate_words(
        GenerateWordsRequest(
            level=CEFRLevel.B1,
            count=3,
            known_words=["buy - купувати", "purchase - купувати, придбавати"],
            exclude_lemmas={"buy", "purchase"},
            topics_hint=["shopping", "money"],
        )
    )
    for word in words:
        print(f"- {word.lemma} ({word.level.value}, {word.part_of_speech.value})")
        print(f"    translation: {word.translation}")
        print(f'    "{word.example_en}" -> "{word.example_uk}"')
    assert words, "expected at least one generated word"

    print("\n=== generate_quiz_sentence ===")
    sentence_en, sentence_uk = await provider.generate_quiz_sentence(
        lemma="affordable",
        translation="доступний за ціною",
        level=CEFRLevel.B1,
        known_words=["buy", "expensive"],
    )
    print(f'EN: "{sentence_en}"')
    print(f'UK: "{sentence_uk}"')
    assert sentence_en and sentence_uk

    print("\n=== evaluate_translation ===")
    is_correct = await provider.evaluate_translation(
        sentence_en="This restaurant is affordable for students.",
        reference_uk="Цей ресторан доступний за ціною для студентів.",
        user_answer_uk="Цей ресторан недорогий для студентів.",
    )
    print(f"Loosely-worded correct translation judged correct: {is_correct}")

    is_incorrect = await provider.evaluate_translation(
        sentence_en="This restaurant is affordable for students.",
        reference_uk="Цей ресторан доступний за ціною для студентів.",
        user_answer_uk="Цей ресторан дуже дорогий.",
    )
    print(f"Wrong-meaning translation judged correct (should be False): {is_incorrect}")

    print("\n=== rank_next_word_candidates (advanced model) ===")
    ranked = await provider.rank_next_word_candidates(
        user_level=CEFRLevel.B1,
        known_words_sample=["hotel", "room", "book", "cheap", "expensive"],
        candidate_lemmas=["available", "reservation", "luggage", "departure"],
    )
    for candidate in sorted(ranked, key=lambda c: c.score, reverse=True):
        print(f"- {candidate.lemma}: score={candidate.score:.2f} -- {candidate.reason}")
    assert ranked, "expected at least one ranked candidate"

    print("\nAll smoke checks completed.")


if __name__ == "__main__":
    asyncio.run(main())
