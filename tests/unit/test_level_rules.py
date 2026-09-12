from bot.database.models.enums import CEFRLevel
from bot.learning.level_rules import is_within_level_band


def test_same_level_is_always_allowed() -> None:
    assert is_within_level_band(CEFRLevel.B1, CEFRLevel.B1) is True


def test_lower_level_is_always_allowed() -> None:
    assert is_within_level_band(CEFRLevel.A1, CEFRLevel.C1) is True


def test_one_step_above_is_allowed() -> None:
    assert is_within_level_band(CEFRLevel.B2, CEFRLevel.B1) is True


def test_two_steps_above_is_rejected_by_default() -> None:
    assert is_within_level_band(CEFRLevel.C1, CEFRLevel.A2) is False


def test_a1_user_never_gets_c1_or_c2() -> None:
    assert is_within_level_band(CEFRLevel.C1, CEFRLevel.A1) is False
    assert is_within_level_band(CEFRLevel.C2, CEFRLevel.A1) is False


def test_custom_max_steps_above() -> None:
    assert is_within_level_band(CEFRLevel.B1, CEFRLevel.A1, max_steps_above=2) is True
    assert is_within_level_band(CEFRLevel.B2, CEFRLevel.A1, max_steps_above=2) is False
