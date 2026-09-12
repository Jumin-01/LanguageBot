import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, PartOfSpeech, WordSource, WordStatus
from bot.database.models.user import User
from bot.database.models.user_word import UserWord
from bot.database.models.word import Word
from bot.learning.pool_rules import MAX_ACTIVE_WORDS
from bot.services.answer_history_service import AnswerHistoryService
from bot.services.mappers import word_to_dto
from bot.services.pool_service import PoolService
from bot.services.quiz_service import QuizService
from bot.services.spaced_repetition_service import SpacedRepetitionService
from tests.fixtures.seed_words import insert_seed_words


class SeedCatalogProvider:
    """Minimal VocabularyProvider test double: hands out seed words the user
    isn't linked to yet. Stands in for the AI-backed VocabularyGenerationService
    (Phase 4) and the StaticPoolFiller (Phase 3) -- both satisfy the same
    Protocol PoolService depends on. If the hand-authored seed catalog runs
    dry (it's ~40 words; the active pool cap can be larger), synthesizes
    extra filler words on the fly rather than capping supply at the fixture's
    size -- pool-cap tests shouldn't be coupled to how many words happen to
    be hand-written in the dev seed catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def generate_candidate_words(self, user_id: int, count: int) -> list:
        known = select(UserWord.word_id).where(UserWord.user_id == user_id)
        result = await self._session.execute(
            select(Word).where(Word.id.not_in(known)).order_by(Word.id).limit(count)
        )
        words = list(result.scalars().all())
        if len(words) < count:
            words += await self._synthesize_extra(count - len(words))
        return [word_to_dto(w) for w in words]

    async def _synthesize_extra(self, needed: int) -> list[Word]:
        extra: list[Word] = []
        for _ in range(needed):
            suffix = uuid.uuid4().hex[:8]
            word = Word(
                lemma=f"testword-{suffix}",
                translation=f"тестове слово {suffix}",
                example_en=f"This is a test sentence with testword-{suffix}.",
                example_uk=f"Це тестове речення зі словом testword-{suffix}.",
                level=CEFRLevel.B1,
                part_of_speech=PartOfSpeech.NOUN,
                source=WordSource.SEED,
            )
            self._session.add(word)
            extra.append(word)
        await self._session.flush()
        return extra


async def _create_user(session: AsyncSession, telegram_id: int = 1) -> User:
    user = User(telegram_id=telegram_id, current_level=CEFRLevel.B1)
    session.add(user)
    await session.flush()
    return user


async def test_ensure_pool_filled_tops_up_to_max_active_words(db_session: AsyncSession) -> None:
    await insert_seed_words(db_session)
    user = await _create_user(db_session)
    pool = PoolService(db_session, vocabulary_provider=SeedCatalogProvider(db_session))

    added = await pool.ensure_pool_filled(user.id)
    assert len(added) == MAX_ACTIVE_WORDS

    active_pool = await pool.get_active_pool(user.id)
    assert len(active_pool) == MAX_ACTIVE_WORDS
    assert all(item.status == WordStatus.NEW for item in active_pool)


async def test_ensure_pool_filled_never_exceeds_cap_when_called_twice(
    db_session: AsyncSession,
) -> None:
    await insert_seed_words(db_session)
    user = await _create_user(db_session)
    pool = PoolService(db_session, vocabulary_provider=SeedCatalogProvider(db_session))

    await pool.ensure_pool_filled(user.id)
    second_call_additions = await pool.ensure_pool_filled(user.id)

    assert second_call_additions == []
    active_pool = await pool.get_active_pool(user.id)
    assert len(active_pool) == MAX_ACTIVE_WORDS


async def test_add_words_to_pool_skips_words_user_already_knows(db_session: AsyncSession) -> None:
    words = await insert_seed_words(db_session)
    user = await _create_user(db_session)
    pool = PoolService(db_session)

    first_word_dto = word_to_dto(words[0])
    await pool.add_words_to_pool(user.id, [first_word_dto])
    # Attempting to add the same word again must not create a duplicate link.
    added_again = await pool.add_words_to_pool(user.id, [first_word_dto])

    assert added_again == []
    active_pool = await pool.get_active_pool(user.id)
    assert len(active_pool) == 1


async def test_full_learning_loop_get_card_answer_apply_replace(db_session: AsyncSession) -> None:
    await insert_seed_words(db_session)
    user = await _create_user(db_session)
    provider = SeedCatalogProvider(db_session)
    pool = PoolService(db_session, vocabulary_provider=provider)
    srs = SpacedRepetitionService(db_session, pool_service=pool)
    history = AnswerHistoryService(db_session)
    quiz = QuizService(db_session, srs, history)

    await pool.ensure_pool_filled(user.id)
    card = await pool.get_next_card(user.id)
    assert card is not None
    assert card.status == WordStatus.NEW

    question = await quiz.generate_question(card)
    correct_index = question.correct_option_index
    assert correct_index is not None

    outcome = await quiz.submit_answer(user.id, card.id, question, str(correct_index))
    assert outcome.is_correct is True
    assert outcome.became_learned is False  # one correct answer isn't enough for mastery

    updated_pool = await pool.get_active_pool(user.id)
    updated_card = next(item for item in updated_pool if item.id == card.id)
    assert updated_card.status == WordStatus.LEARNING
    assert updated_card.repetitions == 1
    assert len(updated_pool) == MAX_ACTIVE_WORDS  # unchanged: nothing was learned yet


async def test_word_becoming_learned_triggers_pool_auto_replacement(
    db_session: AsyncSession,
) -> None:
    await insert_seed_words(db_session)
    user = await _create_user(db_session)
    provider = SeedCatalogProvider(db_session)
    pool = PoolService(db_session, vocabulary_provider=provider)
    srs = SpacedRepetitionService(db_session, pool_service=pool)

    await pool.ensure_pool_filled(user.id)
    active_pool = await pool.get_active_pool(user.id)
    target = active_pool[0]

    # Fast-forward the target word to the brink of mastery (3 correct answers,
    # 7-day interval) by writing SRS state directly, then apply the 4th
    # correct answer through the real service to trigger mastery + replacement.
    from decimal import Decimal

    user_word = await db_session.get(UserWord, target.id)
    assert user_word is not None
    user_word.repetitions = 3
    user_word.consecutive_correct = 3
    user_word.current_interval_days = Decimal("7")
    user_word.status = WordStatus.REVIEW
    await db_session.flush()

    result = await srs.apply_answer(user.id, target.id, is_correct=True)
    assert result.became_learned is True
    assert result.new_status.value == "learned"

    active_pool_after = await pool.get_active_pool(user.id)
    assert len(active_pool_after) == MAX_ACTIVE_WORDS  # replacement kept the pool topped up
    assert target.id not in {item.id for item in active_pool_after}  # learned word left the pool

    learned_word = await db_session.get(UserWord, target.id)
    assert learned_word is not None
    assert learned_word.status == WordStatus.LEARNED
    assert learned_word.learned_at is not None


async def test_fast_track_correct_answer_learns_word_immediately_and_replaces_it(
    db_session: AsyncSession,
) -> None:
    # A brand-new card ("I already know this word") should not need the
    # 1/3/7/14-day climb: one correct answer on the hardest question, via the
    # fast-track path, is enough to mark it learned and free the pool slot.
    await insert_seed_words(db_session)
    user = await _create_user(db_session)
    provider = SeedCatalogProvider(db_session)
    pool = PoolService(db_session, vocabulary_provider=provider)
    srs = SpacedRepetitionService(db_session, pool_service=pool)
    history = AnswerHistoryService(db_session)
    quiz = QuizService(db_session, srs, history)

    await pool.ensure_pool_filled(user.id)
    card = await pool.get_next_card(user.id)
    assert card is not None
    assert card.status == WordStatus.NEW

    question = await quiz.generate_fast_track_question(card)
    correct_answer = question.correct_answer_text

    outcome = await quiz.submit_answer(
        user.id, card.id, question, correct_answer, fast_track=True
    )
    assert outcome.is_correct is True
    assert outcome.became_learned is True

    learned_word = await db_session.get(UserWord, card.id)
    assert learned_word is not None
    assert learned_word.status == WordStatus.LEARNED
    assert learned_word.learned_at is not None

    active_pool_after = await pool.get_active_pool(user.id)
    assert len(active_pool_after) == MAX_ACTIVE_WORDS  # replacement kept the pool topped up
    assert card.id not in {item.id for item in active_pool_after}


async def test_fast_track_wrong_answer_falls_back_to_normal_learning_cycle(
    db_session: AsyncSession,
) -> None:
    await insert_seed_words(db_session)
    user = await _create_user(db_session)
    provider = SeedCatalogProvider(db_session)
    pool = PoolService(db_session, vocabulary_provider=provider)
    srs = SpacedRepetitionService(db_session, pool_service=pool)
    history = AnswerHistoryService(db_session)
    quiz = QuizService(db_session, srs, history)

    await pool.ensure_pool_filled(user.id)
    card = await pool.get_next_card(user.id)
    assert card is not None

    question = await quiz.generate_fast_track_question(card)

    outcome = await quiz.submit_answer(
        user.id, card.id, question, "definitely the wrong answer", fast_track=True
    )
    assert outcome.is_correct is False
    assert outcome.became_learned is False

    updated_word = await db_session.get(UserWord, card.id)
    assert updated_word is not None
    assert updated_word.status == WordStatus.LEARNING
    assert updated_word.repetitions == 0
