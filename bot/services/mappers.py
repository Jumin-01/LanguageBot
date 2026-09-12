"""ORM -> DTO conversion, kept in one place so services don't hand-roll it."""

from bot.database.models.user import User
from bot.database.models.user_settings import UserSettings
from bot.database.models.user_word import UserWord
from bot.database.models.word import Word
from bot.services.dto import UserDTO, UserSettingsDTO, UserWordDTO, WordDTO


def word_to_dto(word: Word) -> WordDTO:
    return WordDTO(
        id=word.id,
        lemma=word.lemma,
        translation=word.translation,
        example_en=word.example_en,
        example_uk=word.example_uk,
        level=word.level,
        part_of_speech=word.part_of_speech,
        topic=word.topic,
        transcription_uk=word.transcription_uk,
        transcription_us=word.transcription_us,
        synonyms=list(word.synonyms),
        antonyms=list(word.antonyms),
        collocations=list(word.collocations),
        source=word.source,
    )


def user_word_to_dto(user_word: UserWord) -> UserWordDTO:
    return UserWordDTO(
        id=user_word.id,
        user_id=user_word.user_id,
        word=word_to_dto(user_word.word),
        status=user_word.status,
        correct_answers=user_word.correct_answers,
        wrong_answers=user_word.wrong_answers,
        repetitions=user_word.repetitions,
        consecutive_correct=user_word.consecutive_correct,
        ease_factor=user_word.ease_factor,
        current_interval_days=user_word.current_interval_days,
        last_review_at=user_word.last_review_at,
        next_review_at=user_word.next_review_at,
        learned_at=user_word.learned_at,
    )


def user_to_dto(user: User) -> UserDTO:
    return UserDTO(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        current_level=user.current_level,
        onboarding_status=user.onboarding_status,
    )


def user_settings_to_dto(settings: UserSettings) -> UserSettingsDTO:
    return UserSettingsDTO(
        user_id=settings.user_id,
        utc_offset_minutes=settings.utc_offset_minutes,
        daily_new_words_goal=settings.daily_new_words_goal,
        sessions_per_day=settings.sessions_per_day,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
    )
