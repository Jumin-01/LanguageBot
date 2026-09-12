from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.schemas import GeneratedWord
from bot.database.models.enums import CEFRLevel, PartOfSpeech
from bot.database.repositories.word_repository import WordRepository
from bot.scheduling.catalog_topup import MIN_CATALOG_SIZE_PER_LEVEL, CatalogTopUpJob
from tests.conftest import FakeAIProvider


@asynccontextmanager
async def _reuse_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield session


def _word(lemma: str, level: CEFRLevel) -> GeneratedWord:
    return GeneratedWord(
        lemma=lemma,
        translation=f"{lemma}-переклад",
        example_en=f"An example with {lemma}.",
        example_uk=f"Приклад з {lemma}.",
        level=level,
        part_of_speech=PartOfSpeech.NOUN,
    )


async def test_tops_up_a_thin_level_and_skips_a_well_stocked_one(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    words = WordRepository(db_session)

    # B1 is already well-stocked -- should not trigger any AI call.
    for i in range(MIN_CATALOG_SIZE_PER_LEVEL):
        await words.create(
            lemma=f"b1-word-{i}",
            translation="переклад",
            example_en=f"Example {i}.",
            example_uk=f"Приклад {i}.",
            level=CEFRLevel.B1,
            part_of_speech=PartOfSpeech.NOUN,
        )

    fake_ai_provider.words_to_return = [[_word("newword", CEFRLevel.A1)]]
    job = CatalogTopUpJob(fake_ai_provider, session_factory=lambda: _reuse_session(db_session))

    await job.run()

    # One request per thin level (all except B1, which was already full).
    requested_levels = {r.level for r in fake_ai_provider.requests}
    assert CEFRLevel.B1 not in requested_levels
    assert CEFRLevel.A1 in requested_levels

    persisted = await words.get_by_lemma("newword", PartOfSpeech.NOUN)
    assert persisted is not None


async def test_skips_duplicate_and_invalid_candidates(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    words = WordRepository(db_session)
    existing = await words.create(
        lemma="existing",
        translation="існуюче",
        example_en="This already exists.",
        example_uk="Це вже існує.",
        level=CEFRLevel.A1,
        part_of_speech=PartOfSpeech.NOUN,
    )

    bad = GeneratedWord(
        lemma="badword",
        translation="",  # fails validation: empty translation
        example_en="No mention here.",
        example_uk="Тут немає згадки.",
        level=CEFRLevel.A1,
        part_of_speech=PartOfSpeech.NOUN,
    )
    fake_ai_provider.words_to_return = [[_word("existing", CEFRLevel.A1), bad]]

    job = CatalogTopUpJob(fake_ai_provider, session_factory=lambda: _reuse_session(db_session))
    await job.run()

    assert await words.get_by_lemma("badword", PartOfSpeech.NOUN) is None
    # The existing row wasn't duplicated.
    matches = await words.get_by_lemma("existing", PartOfSpeech.NOUN)
    assert matches is not None
    assert matches.id == existing.id
