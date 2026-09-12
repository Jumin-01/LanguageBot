from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.exceptions import AIGenerationError
from bot.ai.provider import GenerateWordsRequest
from bot.ai.schemas import GeneratedWord
from bot.database.models.enums import CEFRLevel, PartOfSpeech
from bot.database.models.user import User
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.database.repositories.word_repository import WordRepository
from bot.services.vocabulary_generation_service import VocabularyGenerationService
from tests.conftest import FakeAIProvider


async def _create_user(session: AsyncSession, level: CEFRLevel = CEFRLevel.B1) -> User:
    user = User(telegram_id=1, current_level=level)
    session.add(user)
    await session.flush()
    return user


def _word(
    lemma: str,
    level: CEFRLevel = CEFRLevel.B1,
    part_of_speech: PartOfSpeech = PartOfSpeech.VERB,
    transcription_uk: str | None = None,
    transcription_us: str | None = None,
) -> GeneratedWord:
    return GeneratedWord(
        lemma=lemma,
        translation=f"{lemma}-translation",
        example_en=f"An example with {lemma}.",
        example_uk=f"Приклад з {lemma}.",
        level=level,
        part_of_speech=part_of_speech,
        topic="general",
        transcription_uk=transcription_uk,
        transcription_us=transcription_us,
    )


async def test_filters_out_words_the_user_already_knows(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)

    known = await words.create(
        lemma="buy",
        translation="купувати",
        example_en="I buy milk.",
        example_uk="Я купую молоко.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )
    await user_words.create(user.id, known.id)

    fake_ai_provider.words_to_return = [[_word("buy"), _word("achieve")]]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].lemma == "achieve"


async def test_rejects_words_more_than_one_cefr_step_above_user_level(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session, level=CEFRLevel.A1)

    fake_ai_provider.words_to_return = [
        [_word("sophisticated", level=CEFRLevel.C1), _word("house", level=CEFRLevel.A1)]
    ]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].lemma == "house"


async def test_reuses_existing_catalog_word_without_calling_ai(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    """The catalog is checked before the AI, so a level-appropriate word
    already sitting unlinked in the shared catalog is reused for free --
    this is the main lever for not blowing through a small daily AI quota."""

    user = await _create_user(db_session)
    words = WordRepository(db_session)

    existing = await words.create(
        lemma="affordable",
        translation="доступний",
        example_en="It is affordable.",
        example_uk="Це доступно.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
    )

    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].id == existing.id
    assert fake_ai_provider.requests == []


async def test_ai_loop_still_dedupes_against_catalog_word_outside_reusable_band(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    """If the existing catalog row is tagged at a level too far above the
    user's own (so catalog-reuse won't offer it), but the AI proposes the
    same lemma at an in-band level, we still reuse the existing row instead
    of creating a duplicate."""

    user = await _create_user(db_session)  # B1
    words = WordRepository(db_session)

    existing = await words.create(
        lemma="affordable",
        translation="доступний",
        example_en="It is affordable.",
        example_uk="Це доступно.",
        level=CEFRLevel.C1,  # outside the B1 user's reusable band
        part_of_speech=PartOfSpeech.ADJECTIVE,
    )

    fake_ai_provider.words_to_return = [
        [_word("affordable", level=CEFRLevel.B1, part_of_speech=PartOfSpeech.ADJECTIVE)]
    ]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].id == existing.id
    assert len(fake_ai_provider.requests) == 1

    # No duplicate row was created for the same lemma + part of speech.
    matches = await words.get_by_lemma("affordable", PartOfSpeech.ADJECTIVE)
    assert matches is not None
    assert matches.id == existing.id


async def test_persists_genuinely_new_words(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)

    fake_ai_provider.words_to_return = [
        [_word("worthwhile", part_of_speech=PartOfSpeech.ADJECTIVE)]
    ]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    persisted = await words.get_by_lemma("worthwhile", PartOfSpeech.ADJECTIVE)
    assert persisted is not None
    assert persisted.id == result[0].id


async def test_valid_transcription_is_persisted(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)

    fake_ai_provider.words_to_return = [
        [
            _word(
                "reliable",
                part_of_speech=PartOfSpeech.ADJECTIVE,
                transcription_uk="/rɪˈlaɪəbl/",
                transcription_us="/rɪˈlaɪəbl/",
            )
        ]
    ]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert result[0].transcription_uk == "/rɪˈlaɪəbl/"
    assert result[0].transcription_us == "/rɪˈlaɪəbl/"


async def test_implausible_transcription_is_dropped_not_the_whole_word(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)

    fake_ai_provider.words_to_return = [
        [
            _word(
                "reliable",
                part_of_speech=PartOfSpeech.ADJECTIVE,
                transcription_uk="not-ipa-at-all",
                transcription_us=None,
            )
        ]
    ]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].lemma == "reliable"
    assert result[0].transcription_uk is None
    assert result[0].transcription_us is None


async def test_makes_only_one_ai_call_even_if_the_batch_is_all_duplicates(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    """MAX_GENERATION_ATTEMPTS=1 by design (see module docstring): a free
    LLM quota is spent per *call*, not per word, so we over-request within
    one call (OVER_REQUEST_FACTOR) rather than retrying with a second call
    when the first comes back short."""

    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)

    known = await words.create(
        lemma="buy",
        translation="купувати",
        example_en="I buy milk.",
        example_uk="Я купую молоко.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )
    await user_words.create(user.id, known.id)

    fake_ai_provider.words_to_return = [[_word("buy")], [_word("achieve")]]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert result == []
    assert len(fake_ai_provider.requests) == 1


async def test_catalog_reuse_and_ai_generation_combine_to_fill_the_request(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)

    catalog_word = await words.create(
        lemma="cheap",
        translation="дешевий",
        example_en="It is cheap.",
        example_uk="Це дешево.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
    )
    fake_ai_provider.words_to_return = [[_word("achieve")]]
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=2)

    lemmas = {w.lemma for w in result}
    assert lemmas == {"cheap", "achieve"}
    assert len(fake_ai_provider.requests) == 1
    # The AI was only asked for what the catalog couldn't already cover.
    assert fake_ai_provider.requests[0].count >= 1
    assert catalog_word.id in {w.id for w in result}


async def test_graph_adjacent_word_is_preferred_over_unrelated_catalog_word(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)

    known = await words.create(
        lemma="buy",
        translation="купувати",
        example_en="I buy milk.",
        example_uk="Я купую молоко.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
        synonyms=["purchase"],
    )
    await user_words.create(user.id, known.id)

    related = await words.create(
        lemma="purchase",
        translation="придбати",
        example_en="I purchase groceries.",
        example_uk="Я купую продукти.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )
    await words.create(
        lemma="random",
        translation="випадковий",
        example_en="A random example.",
        example_uk="Випадковий приклад.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
    )

    service = VocabularyGenerationService(db_session, fake_ai_provider)
    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].id == related.id
    # Only one graph-adjacent candidate existed, so there was no ranking
    # decision to make -- the advanced model was never called.
    assert fake_ai_provider.rank_calls == []


async def test_ai_ranks_graph_candidates_when_there_are_more_than_needed(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)

    known = await words.create(
        lemma="buy",
        translation="купувати",
        example_en="I buy milk.",
        example_uk="Я купую молоко.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
        synonyms=["purchase", "acquire"],
    )
    await user_words.create(user.id, known.id)

    await words.create(
        lemma="purchase",
        translation="придбати",
        example_en="I purchase groceries.",
        example_uk="Я купую продукти.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )
    acquire = await words.create(
        lemma="acquire",
        translation="набувати",
        example_en="They acquire new skills.",
        example_uk="Вони набувають нових навичок.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )

    fake_ai_provider.ranking_scores = {"acquire": 0.9, "purchase": 0.1}
    service = VocabularyGenerationService(db_session, fake_ai_provider)

    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1
    assert result[0].id == acquire.id  # higher-ranked candidate wins the one slot
    assert len(fake_ai_provider.rank_calls) == 1
    assert set(fake_ai_provider.rank_calls[0]) == {"purchase", "acquire"}


async def test_ranking_failure_falls_back_to_unranked_candidates(
    db_session: AsyncSession,
) -> None:
    class RankingFailsProvider:
        async def generate_words(self, request: GenerateWordsRequest) -> list[GeneratedWord]:
            return []

        async def rank_next_word_candidates(self, user_level, known_words_sample, candidate_lemmas):
            raise AIGenerationError("ranking unavailable")

    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)

    known = await words.create(
        lemma="buy",
        translation="купувати",
        example_en="I buy milk.",
        example_uk="Я купую молоко.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
        synonyms=["purchase", "acquire"],
    )
    await user_words.create(user.id, known.id)
    await words.create(
        lemma="purchase",
        translation="придбати",
        example_en="I purchase groceries.",
        example_uk="Я купую продукти.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )
    await words.create(
        lemma="acquire",
        translation="набувати",
        example_en="They acquire new skills.",
        example_uk="Вони набувають нових навичок.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )

    service = VocabularyGenerationService(db_session, RankingFailsProvider())
    result = await service.generate_candidate_words(user.id, count=1)

    assert len(result) == 1  # still got a word despite the ranking call failing


async def test_ai_failure_returns_gracefully_without_raising(db_session: AsyncSession) -> None:
    class FailingProvider:
        async def generate_words(self, request: GenerateWordsRequest) -> list[GeneratedWord]:
            raise AIGenerationError("boom")

    user = await _create_user(db_session)
    service = VocabularyGenerationService(db_session, FailingProvider())

    result = await service.generate_candidate_words(user.id, count=5)

    assert result == []
