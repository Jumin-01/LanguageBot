"""Pure quiet-hours arithmetic, no I/O. Handles a window that wraps midnight
(e.g. 22:00 -> 08:00), which is the common case for "don't message me at
night" -- as well as a same-day window (e.g. 13:00 -> 14:00).
"""

from datetime import datetime, time, timedelta


def is_within_quiet_hours(moment: time, quiet_start: time, quiet_end: time) -> bool:
    if quiet_start == quiet_end:
        return False  # a zero-length window is treated as "never quiet"
    if quiet_start < quiet_end:
        return quiet_start <= moment < quiet_end
    return moment >= quiet_start or moment < quiet_end  # wraps midnight


def next_allowed_time(candidate: datetime, quiet_start: time, quiet_end: time) -> datetime:
    """If `candidate` (a local, tz-aware or naive datetime -- only its wall-clock
    time matters here) falls inside the quiet window, returns the moment the
    window ends; otherwise returns `candidate` unchanged."""

    moment = candidate.time()
    if not is_within_quiet_hours(moment, quiet_start, quiet_end):
        return candidate

    end_today = candidate.replace(
        hour=quiet_end.hour, minute=quiet_end.minute, second=0, microsecond=0
    )

    if quiet_start < quiet_end:
        # Same-day window: `candidate` is within [start, end) today, so the
        # window also ends today.
        return end_today

    # Wraps midnight (e.g. 22:00 -> 08:00): if we're in the late part of the
    # window (>= start, i.e. still "today"), the window ends tomorrow morning;
    # if we're in the early part (< end, i.e. already past midnight), it ends
    # later today.
    if moment >= quiet_start:
        return end_today + timedelta(days=1)
    return end_today
