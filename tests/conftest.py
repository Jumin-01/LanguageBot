import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Guarantee the project root is importable regardless of how pytest's rootdir
# auto-detection resolves it, so `import bot...` / `import scripts...` always work.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.ai.provider import GenerateWordsRequest  # noqa: E402
from bot.ai.schemas import GeneratedWord, RankedWordCandidate  # noqa: E402
from bot.database.models.enums import CEFRLevel, PartOfSpeech  # noqa: E402

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://languagebot:languagebot@localhost:55432/languagebot_test",
)


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session bound to one connection + one outer transaction that is always
    rolled back at teardown, so integration tests never leave data behind and
    never need a separate test database. Services only ever call session.flush()
    (never commit()), so nothing escapes this rollback."""

    engine = create_async_engine(TEST_DATABASE_URL)
    connection = await engine.connect()
    transaction = await connection.begin()
    session_factory = async_sessionmaker(bind=connection, expire_on_commit=False, autoflush=False)
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


class FakeAIProvider:
    """Deterministic, no-network stand-in for GeminiAIProvider -- satisfies
    the AIProvider Protocol structurally. `words_to_return` is a queue: each
    call to generate_words() pops and returns one batch, so a test can script
    multiple retry rounds (e.g. VocabularyGenerationService's "not enough
    accepted, ask again" path)."""

    def __init__(self) -> None:
        self.words_to_return: list[list[GeneratedWord]] = []
        self.requests: list[GenerateWordsRequest] = []
        # Optional per-lemma score override for rank_next_word_candidates;
        # unset lemmas default to 0.5 so ranking is a deliberate, opt-in test
        # behavior rather than something that silently reorders candidates.
        self.ranking_scores: dict[str, float] = {}
        self.rank_calls: list[list[str]] = []

    async def generate_words(self, request: GenerateWordsRequest) -> list[GeneratedWord]:
        self.requests.append(request)
        if not self.words_to_return:
            return []
        return self.words_to_return.pop(0)

    async def generate_quiz_sentence(
        self, lemma: str, translation: str, level: CEFRLevel, known_words: list[str]
    ) -> tuple[str, str]:
        return f"This sentence uses {lemma}.", f"Це речення використовує «{translation}»."

    async def evaluate_translation(
        self, sentence_en: str, reference_uk: str, user_answer_uk: str
    ) -> bool:
        return user_answer_uk.strip().lower() == reference_uk.strip().lower()

    async def generate_transcription(
        self, lemma: str, part_of_speech: PartOfSpeech
    ) -> tuple[str | None, str | None]:
        return f"/{lemma}-uk/", f"/{lemma}-us/"

    async def rank_next_word_candidates(
        self, user_level: CEFRLevel, known_words_sample: list[str], candidate_lemmas: list[str]
    ) -> list[RankedWordCandidate]:
        self.rank_calls.append(list(candidate_lemmas))
        return [
            RankedWordCandidate(
                lemma=lemma,
                score=self.ranking_scores.get(lemma.strip().lower(), 0.5),
                reason="test",
            )
            for lemma in candidate_lemmas
        ]


@pytest.fixture
def fake_ai_provider() -> FakeAIProvider:
    return FakeAIProvider()
