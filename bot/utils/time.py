"""Timezone helpers built around a fixed UTC offset (in minutes) rather than
an IANA zone name.

The bot asks the user to type their current local time instead of picking a
timezone name off a list; the offset is derived by comparing that typed time
against the actual UTC time at the moment they send it, rounded to the
nearest 15 minutes. This has no DST awareness -- if a user's offset drifts
(e.g. after a DST change), they just re-answer "what time is it for you?" in
settings again. Simpler for a Telegram bot audience than IANA zone names.
"""

import re
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

_LOCAL_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_ROUND_TO_MINUTES = 15
_MINUTES_PER_DAY = 24 * 60


def offset_timezone(utc_offset_minutes: int) -> dt_timezone:
    return dt_timezone(timedelta(minutes=utc_offset_minutes))


def utc_to_local(dt_utc: datetime, utc_offset_minutes: int) -> datetime:
    return dt_utc.astimezone(offset_timezone(utc_offset_minutes))


def format_offset(utc_offset_minutes: int) -> str:
    sign = "+" if utc_offset_minutes >= 0 else "-"
    hours, minutes = divmod(abs(utc_offset_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def parse_local_time_to_offset(local_time_text: str, now_utc: datetime) -> int | None:
    """Given a user-typed local time like "14:30" and the current UTC
    datetime, returns the implied UTC offset in minutes (rounded to the
    nearest 15 minutes), or None if the text isn't a valid HH:MM time."""

    match = _LOCAL_TIME_RE.match(local_time_text.strip())
    if match is None:
        return None

    local_minutes = int(match.group(1)) * 60 + int(match.group(2))
    utc_minutes = now_utc.hour * 60 + now_utc.minute

    diff = local_minutes - utc_minutes
    # Normalize into (-720, 720] so e.g. 23:45 local vs 00:15 UTC resolves to
    # -30 minutes, not +1410.
    diff = ((diff + _MINUTES_PER_DAY // 2) % _MINUTES_PER_DAY) - _MINUTES_PER_DAY // 2

    return round(diff / _ROUND_TO_MINUTES) * _ROUND_TO_MINUTES
