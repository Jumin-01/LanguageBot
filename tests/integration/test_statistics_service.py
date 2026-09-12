from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, PartOfSpeech, QuestionType, WordStatus
from bot.database.models.user import User
from bot.database.models.user_word import UserWord
from bot.database.repositories.answer_history_repository import AnswerHistoryRepository
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.database.repositories.word_repository import WordRepository
from bot.services.statistics_service import StatisticsService


async def _create_user(session: AsyncSession, level: CEFRLevel = CEFRLevel.B1) -> User:
    user = User(telegram_id=1, current_level=level)
    session.add(user)
    await session.flush()
    return user


async def _create_word(words: WordRepository, lemma: str) -> int:
    word = await words.create(
        lemma=lemma,
        translation=f"{lemma}-переклад",
        example_en=f"An example with {lemma}.",
        example_uk=f"Приклад з {lemma}.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.NOUN,
    )
    return word.id


async def test_get_summary_for_fresh_user_is_all_zero(db_session: AsyncSession) -> None:
    user = await _create_user(db_session, level=CEFRLevel.A2)
    service = StatisticsService(db_session)

    summary = await service.get_summary(user.id)

    assert summary.total_learned == 0
    assert summary.new_this_week == 0
    assert summary.total_repetitions == 0
    assert summary.correct_percentage is None
    assert summary.avg_words_per_day == 0.0
    assert summary.learned_this_week == 0
    assert summary.learned_this_month == 0
    assert summary.current_level == CEFRLevel.A2


async def test_get_summary_counts_learned_and_recent_words(db_session: AsyncSession) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    now = datetime.now(UTC)

    # Learned 2 days ago -> counts toward total, this week, and this month.
    recent_id = await _create_word(words, "recent")
    db_session.add(
        UserWord(
            user_id=user.id,
            word_id=recent_id,
            status=WordStatus.LEARNED,
            added_at=now - timedelta(days=10),
            learned_at=now - timedelta(days=2),
        )
    )

    # Learned 40 days ago -> counts toward total only (outside week/month windows).
    old_id = await _create_word(words, "old")
    db_session.add(
        UserWord(
            user_id=user.id,
            word_id=old_id,
            status=WordStatus.LEARNED,
            added_at=now - timedelta(days=50),
            learned_at=now - timedelta(days=40),
        )
    )

    # Added 3 days ago, still learning -> counts toward "new this week" only.
    new_id = await _create_word(words, "newish")
    db_session.add(
        UserWord(
            user_id=user.id,
            word_id=new_id,
            status=WordStatus.LEARNING,
            added_at=now - timedelta(days=3),
        )
    )
    await db_session.flush()

    service = StatisticsService(db_session)
    summary = await service.get_summary(user.id)

    assert summary.total_learned == 2
    assert summary.learned_this_week == 1
    # "old" was learned 40 days ago, outside the 30-day window.
    assert summary.learned_this_month == 1
    assert summary.new_this_week == 1


async def test_get_summary_computes_correct_percentage(db_session: AsyncSession) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)
    history = AnswerHistoryRepository(db_session)

    word_id = await _create_word(words, "practice")
    user_word = await user_words.create(user.id, word_id)

    for is_correct in (True, False, True):
        await history.create(
            user_id=user.id,
            word_id=word_id,
            user_word_id=user_word.id,
            question_type=QuestionType.EN_TO_UA_CHOICE,
            question_payload={"prompt": "?"},
            user_answer="a",
            correct_answer="a",
            is_correct=is_correct,
        )

    service = StatisticsService(db_session)
    summary = await service.get_summary(user.id)

    assert summary.total_repetitions == 3
    assert summary.correct_percentage == 66.7
