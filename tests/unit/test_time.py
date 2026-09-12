from datetime import UTC, datetime

from bot.utils.time import format_offset, offset_timezone, parse_local_time_to_offset, utc_to_local


def test_format_offset_positive() -> None:
    assert format_offset(120) == "UTC+02:00"


def test_format_offset_negative() -> None:
    assert format_offset(-300) == "UTC-05:00"


def test_format_offset_zero() -> None:
    assert format_offset(0) == "UTC+00:00"


def test_format_offset_half_hour() -> None:
    assert format_offset(330) == "UTC+05:30"


def test_offset_timezone_matches_utc_to_local() -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    local = utc_to_local(now_utc, 120)
    assert local.hour == 14
    assert local.tzinfo == offset_timezone(120)


def test_parse_local_time_exact_match_gives_zero_offset() -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert parse_local_time_to_offset("12:00", now_utc) == 0


def test_parse_local_time_two_hours_ahead() -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert parse_local_time_to_offset("14:00", now_utc) == 120


def test_parse_local_time_behind_utc() -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert parse_local_time_to_offset("07:00", now_utc) == -300


def test_parse_local_time_rounds_to_nearest_15_minutes() -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    # 12:07 is 7 minutes ahead -- rounds to the nearest 15 (0).
    assert parse_local_time_to_offset("12:07", now_utc) == 0
    # 12:08 is 8 minutes ahead -- rounds up to 15.
    assert parse_local_time_to_offset("12:08", now_utc) == 15


def test_parse_local_time_wraps_around_midnight() -> None:
    # Local is 23:45, UTC is 00:15 the same instant -- offset should be -30,
    # not +1410.
    now_utc = datetime(2026, 1, 1, 0, 15, tzinfo=UTC)
    assert parse_local_time_to_offset("23:45", now_utc) == -30


def test_parse_local_time_rejects_invalid_format() -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert parse_local_time_to_offset("not a time", now_utc) is None
    assert parse_local_time_to_offset("25:00", now_utc) is None
    assert parse_local_time_to_offset("12:60", now_utc) is None
