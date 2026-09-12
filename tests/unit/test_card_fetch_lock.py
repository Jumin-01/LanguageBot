"""try_begin_card_fetch/end_card_fetch guard against a user spamming
"📚 Вчити слова" / "🔄 Повторення" while a card fetch (possibly involving a
live AI call) is already in flight for them."""

from bot.rendering.quiz_cards import end_card_fetch, try_begin_card_fetch

# Distinct per test so the shared module-level state can't leak between tests.
_TELEGRAM_ID = 900001


def test_first_fetch_for_a_user_is_allowed() -> None:
    telegram_id = _TELEGRAM_ID
    try:
        assert try_begin_card_fetch(telegram_id) is True
    finally:
        end_card_fetch(telegram_id)


def test_second_fetch_while_first_is_in_flight_is_rejected() -> None:
    telegram_id = _TELEGRAM_ID + 1
    try:
        assert try_begin_card_fetch(telegram_id) is True
        assert try_begin_card_fetch(telegram_id) is False
    finally:
        end_card_fetch(telegram_id)


def test_fetch_allowed_again_after_end_card_fetch() -> None:
    telegram_id = _TELEGRAM_ID + 2
    try:
        assert try_begin_card_fetch(telegram_id) is True
        end_card_fetch(telegram_id)
        assert try_begin_card_fetch(telegram_id) is True
    finally:
        end_card_fetch(telegram_id)


def test_different_users_do_not_block_each_other() -> None:
    a, b = _TELEGRAM_ID + 3, _TELEGRAM_ID + 4
    try:
        assert try_begin_card_fetch(a) is True
        assert try_begin_card_fetch(b) is True
    finally:
        end_card_fetch(a)
        end_card_fetch(b)


def test_end_card_fetch_is_a_no_op_for_a_user_not_in_flight() -> None:
    end_card_fetch(_TELEGRAM_ID + 5)  # must not raise
