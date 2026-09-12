from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database.models.enums import OnboardingStatus, QuestionType
from bot.di import Services
from bot.keyboards.main_menu import BTN_LEARN
from bot.keyboards.quiz import (
    FAST_TRACK_CALLBACK_PREFIX,
    QUIZ_CALLBACK_PREFIX,
    parse_fast_track_callback_data,
    parse_quiz_callback_data,
    quiz_options_keyboard,
)
from bot.rendering.quiz_cards import (
    end_card_fetch,
    format_card_message,
    format_result_message,
    pop_pending_question,
    register_pending_question,
    try_begin_card_fetch,
)
from bot.services.dto import UserWordDTO
from bot.states.quiz_states import QuizFlow

router = Router(name="learning")

_LEARNED_MESSAGE = "🎉 Ти вивчив(-ла) це слово! У пул додано нове слово замість нього."
_FAST_TRACK_LEARNED_MESSAGE = (
    "⚡ Підтверджено! Слово одразу позначено вивченим, у пул додано нове слово замість нього."
)
_FETCH_IN_PROGRESS_MESSAGE = "⏳ Слово вже шукається, зачекай трохи..."
_FETCHING_MESSAGE = "⏳ Шукаю слово..."


async def send_card_message(
    message: Message, services: Services, state: FSMContext, card: UserWordDTO
) -> None:
    """Generates a question for `card` and sends it -- shared by the manual
    "📚 Вчити слова" handler below and "🔄 Повторення" (bot/handlers/review.py),
    which only differ in *which* card they fetch."""

    if message.from_user is None:
        return

    question = await services.quiz.generate_question(card)
    register_pending_question(message.from_user.id, card, question)

    if question.question_type == QuestionType.TRANSLATE_SENTENCE:
        await state.set_state(QuizFlow.awaiting_translation)
        await state.update_data(pending_user_word_id=card.id)
    else:
        await state.clear()

    await message.answer(
        format_card_message(card, question),
        reply_markup=quiz_options_keyboard(question, show_fast_track=True),
    )


@router.message(F.text == BTN_LEARN)
async def on_learn_pressed(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    if not try_begin_card_fetch(telegram_id):
        await message.answer(_FETCH_IN_PROGRESS_MESSAGE)
        return

    try:
        user = await services.user.get_or_create_user(
            telegram_id, message.from_user.username, message.from_user.first_name
        )
        if user.onboarding_status == OnboardingStatus.PENDING_LEVEL:
            await message.answer("Спочатку обери свій рівень командою /start.")
            return

        status_message = await message.answer(_FETCHING_MESSAGE)
        card = await services.pool.get_next_card(user.id)
        if card is None:
            await status_message.edit_text("Наразі немає слів для вивчення. Спробуй пізніше.")
            return

        await status_message.delete()
        await send_card_message(message, services, state, card)
    finally:
        end_card_fetch(telegram_id)


@router.callback_query(F.data.startswith(f"{QUIZ_CALLBACK_PREFIX}:"))
async def on_quiz_answer(callback: CallbackQuery, services: Services) -> None:
    if (
        callback.from_user is None
        or callback.data is None
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    parsed = parse_quiz_callback_data(callback.data)
    if parsed is None:
        await callback.answer()
        return
    user_word_id, option_index = parsed

    pending = pop_pending_question(callback.from_user.id, user_word_id)
    if pending is None:
        await callback.answer(
            'Питання застаріло. Натисни "📚 Вчити слова" ще раз.', show_alert=True
        )
        return
    card, question, fast_track = pending

    user = await services.user.get_or_create_user(
        callback.from_user.id, callback.from_user.username, callback.from_user.first_name
    )
    outcome = await services.quiz.submit_answer(
        user.id, user_word_id, question, str(option_index), fast_track=fast_track
    )

    await callback.message.edit_text(format_result_message(card, outcome))

    if outcome.became_learned:
        await callback.message.answer(
            _FAST_TRACK_LEARNED_MESSAGE if fast_track else _LEARNED_MESSAGE
        )

    await callback.answer()


@router.callback_query(F.data.startswith(f"{FAST_TRACK_CALLBACK_PREFIX}:"))
async def on_fast_track_requested(
    callback: CallbackQuery, services: Services, state: FSMContext
) -> None:
    """"✅ Я вже знаю це слово" -- swaps the current card's question for the
    hardest available one. A correct answer marks the word learned right
    away instead of forcing it through the full repetition ladder; a wrong
    answer sends it into the normal learning cycle, same as any other miss.
    """

    if (
        callback.from_user is None
        or callback.data is None
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    user_word_id = parse_fast_track_callback_data(callback.data)
    if user_word_id is None:
        await callback.answer()
        return

    pending = pop_pending_question(callback.from_user.id, user_word_id)
    if pending is None:
        await callback.answer(
            'Питання застаріло. Натисни "📚 Вчити слова" ще раз.', show_alert=True
        )
        return
    card, _old_question, _ = pending

    question = await services.quiz.generate_fast_track_question(card)
    register_pending_question(callback.from_user.id, card, question, fast_track=True)

    if question.question_type == QuestionType.TRANSLATE_SENTENCE:
        await state.set_state(QuizFlow.awaiting_translation)
        await state.update_data(pending_user_word_id=user_word_id)
    else:
        await state.clear()

    await callback.message.edit_text(
        format_card_message(card, question, fast_track=True),
        reply_markup=quiz_options_keyboard(question, show_fast_track=False),
    )
    await callback.answer("Перевіримо складнішим питанням 💪")


@router.message(QuizFlow.awaiting_translation)
async def on_translation_answer(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return

    data = await state.get_data()
    user_word_id = data.get("pending_user_word_id")
    await state.clear()

    if user_word_id is None:
        await message.answer("Питання застаріло. Спробуй ще раз.")
        return

    pending = pop_pending_question(message.from_user.id, user_word_id)
    if pending is None:
        await message.answer('Питання застаріло. Натисни "📚 Вчити слова" ще раз.')
        return
    card, question, fast_track = pending

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    outcome = await services.quiz.submit_answer(
        user.id, user_word_id, question, message.text, fast_track=fast_track
    )

    await message.answer(format_result_message(card, outcome))

    if outcome.became_learned:
        await message.answer(_FAST_TRACK_LEARNED_MESSAGE if fast_track else _LEARNED_MESSAGE)
