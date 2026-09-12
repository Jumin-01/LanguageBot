from datetime import datetime, time

from bot.scheduling.quiet_hours import is_within_quiet_hours, next_allowed_time

# 22:00 -> 08:00 (wraps midnight) is the spec's example quiet window.
QUIET_START = time(22, 0)
QUIET_END = time(8, 0)


def test_daytime_is_not_quiet() -> None:
    assert is_within_quiet_hours(time(14, 0), QUIET_START, QUIET_END) is False


def test_late_evening_is_quiet() -> None:
    assert is_within_quiet_hours(time(23, 30), QUIET_START, QUIET_END) is True


def test_early_morning_is_quiet() -> None:
    assert is_within_quiet_hours(time(3, 0), QUIET_START, QUIET_END) is True


def test_exact_start_boundary_is_quiet() -> None:
    assert is_within_quiet_hours(QUIET_START, QUIET_START, QUIET_END) is True


def test_exact_end_boundary_is_not_quiet() -> None:
    assert is_within_quiet_hours(QUIET_END, QUIET_START, QUIET_END) is False


def test_same_day_window_no_wrap() -> None:
    start, end = time(13, 0), time(14, 0)
    assert is_within_quiet_hours(time(13, 30), start, end) is True
    assert is_within_quiet_hours(time(12, 59), start, end) is False
    assert is_within_quiet_hours(time(14, 0), start, end) is False


def test_zero_length_window_is_never_quiet() -> None:
    assert is_within_quiet_hours(time(22, 0), time(22, 0), time(22, 0)) is False


def test_next_allowed_time_unchanged_when_not_quiet() -> None:
    candidate = datetime(2026, 1, 1, 14, 0)
    assert next_allowed_time(candidate, QUIET_START, QUIET_END) == candidate


def test_next_allowed_time_late_evening_defers_to_tomorrow_morning() -> None:
    candidate = datetime(2026, 1, 1, 23, 0)
    result = next_allowed_time(candidate, QUIET_START, QUIET_END)
    assert result == datetime(2026, 1, 2, 8, 0)


def test_next_allowed_time_early_morning_defers_to_same_morning() -> None:
    candidate = datetime(2026, 1, 1, 3, 0)
    result = next_allowed_time(candidate, QUIET_START, QUIET_END)
    assert result == datetime(2026, 1, 1, 8, 0)


def test_next_allowed_time_same_day_window() -> None:
    start, end = time(13, 0), time(14, 0)
    candidate = datetime(2026, 1, 1, 13, 30)
    result = next_allowed_time(candidate, start, end)
    assert result == datetime(2026, 1, 1, 14, 0)
