from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    SmallInteger,
    Time,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base

if TYPE_CHECKING:
    from bot.database.models.user import User


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # Fixed UTC offset in minutes, derived from a user-typed local time
    # compared against the current UTC time (see bot/utils/time.py) rather
    # than an IANA zone name -- simpler for users, no DST awareness needed
    # since the offset is just re-asked if it ever drifts.
    utc_offset_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=120)
    daily_new_words_goal: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=5)
    sessions_per_day: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    quiet_hours_start: Mapped[time] = mapped_column(Time, nullable=False, default=time(22, 0))
    quiet_hours_end: Mapped[time] = mapped_column(Time, nullable=False, default=time(8, 0))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="settings")

    __table_args__ = (
        CheckConstraint("daily_new_words_goal BETWEEN 1 AND 20", name="daily_new_words_goal_range"),
        CheckConstraint("sessions_per_day BETWEEN 1 AND 5", name="sessions_per_day_range"),
        CheckConstraint(
            "utc_offset_minutes BETWEEN -720 AND 840", name="utc_offset_minutes_range"
        ),
    )
