from bot.learning.pool_rules import MAX_ACTIVE_WORDS, needs_replacement, slots_free


def test_max_active_words_is_50() -> None:
    assert MAX_ACTIVE_WORDS == 50


def test_slots_free_below_cap() -> None:
    assert slots_free(12) == 38


def test_slots_free_at_cap() -> None:
    assert slots_free(50) == 0


def test_slots_free_never_negative() -> None:
    assert slots_free(55) == 0


def test_needs_replacement_true_below_cap() -> None:
    assert needs_replacement(49) is True


def test_needs_replacement_false_at_cap() -> None:
    assert needs_replacement(50) is False
