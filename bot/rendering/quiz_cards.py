"""Renders a QuizQuestion as Telegram HTML text (pure, no I/O), and tracks
the pending question awaiting an answer for each (telegram_id, user_word_id)
pair.

Kept deliberately compact (no blank-line padding, no section labels) so the
whole card plus its answer buttons fits on one mobile screen without
scrolling -- the word and its meaning should be visible without any user
action.

Shared between the manual "📚 Вчити слова" handler (bot/handlers/learning.py)
and the scheduled push job (bot/scheduling/jobs.py) so a card looks and
behaves identically regardless of how it was triggered. The in-memory
pending-question store is process-local -- fine for a single-instance MVP
bot; a multi-instance deployment would move this into shared storage (e.g.
Redis or a DB table) instead.
"""

import html

from bot.database.models.enums import WordStatus
from bot.learning.models import AnswerOutcome, QuizQuestion
from bot.services.dto import UserWordDTO, WordDTO

_pending_questions: dict[tuple[int, int], tuple[UserWordDTO, QuizQuestion, bool]] = {}


def register_pending_question(
    telegram_id: int, card: UserWordDTO, question: QuizQuestion, *, fast_track: bool = False
) -> None:
    _pending_questions[(telegram_id, card.id)] = (card, question, fast_track)


def pop_pending_question(
    telegram_id: int, user_word_id: int
) -> tuple[UserWordDTO, QuizQuestion, bool] | None:
    return _pending_questions.pop((telegram_id, user_word_id), None)


# Guards against a user spamming "📚 Вчити слова" / "🔄 Повторення" while a
# card is still being fetched (which can involve a live AI call) -- a second
# tap while one is in flight would otherwise kick off a duplicate fetch.
_fetching_users: set[int] = set()


def try_begin_card_fetch(telegram_id: int) -> bool:
    """True and marks the user busy if no fetch was already in flight for
    them; False (and no state change) if one was -- the caller should then
    just tell the user to wait instead of starting a second fetch."""

    if telegram_id in _fetching_users:
        return False
    _fetching_users.add(telegram_id)
    return True


def end_card_fetch(telegram_id: int) -> None:
    _fetching_users.discard(telegram_id)


def _format_transcription_line(word: WordDTO) -> str | None:
    parts = []
    if word.transcription_uk:
        parts.append(f"UK {html.escape(word.transcription_uk)}")
    if word.transcription_us:
        parts.append(f"US {html.escape(word.transcription_us)}")
    if not parts:
        return None
    return "🔊 " + " · ".join(parts)


def _word_heading(word: WordDTO) -> str:
    heading = f"<b>{html.escape(word.lemma)}</b>"
    transcription_line = _format_transcription_line(word)
    if transcription_line:
        heading += f"  {transcription_line}"
    return heading


def format_card_message(
    card: UserWordDTO, question: QuizQuestion, *, fast_track: bool = False
) -> str:
    word = card.word
    if fast_track:
        header = "⚡ ПЕРЕВІРКА"
    else:
        header = "📚 NEW WORD" if card.status == WordStatus.NEW else "🔄 REVIEW"

    lines = [
        header,
        _word_heading(word),
        f"🇺🇦 <tg-spoiler>{html.escape(word.translation)}</tg-spoiler>",
        "",
        f'"{html.escape(word.example_en)}"',
        f"🇺🇦 <tg-spoiler>{html.escape(word.example_uk)}</tg-spoiler>",
        "",
        f"❓ {html.escape(question.prompt)}",
    ]
    return "\n".join(lines)


def format_outcome_line(outcome: AnswerOutcome) -> str:
    if outcome.is_correct:
        return "✅ Correct!"
    return f"❌ Incorrect.\nПравильна відповідь: «{html.escape(outcome.correct_answer_text)}»."


def format_result_message(card: UserWordDTO, outcome: AnswerOutcome) -> str:
    """Post-answer view: translation and example are revealed (no spoiler --
    the point of hiding them was only to not give the answer away before the
    quiz question)."""

    word = card.word
    lines = [
        _word_heading(word),
        f"🇺🇦 {html.escape(word.translation)}",
        "",
        f'"{html.escape(word.example_en)}"',
        f"🇺🇦 {html.escape(word.example_uk)}",
        "",
        format_outcome_line(outcome),
    ]
    return "\n".join(lines)
