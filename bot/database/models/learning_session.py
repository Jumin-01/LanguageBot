from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.enum_types import pg_enum
from bot.database.models.enums import SessionRunStatus

if TYPE_CHECKING:
    from bot.database.models.user import User


class LearningSession(Base):
    """A configured daily push time (schedule), per the spec's 'schedules' entity."""

    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    time_of_day: Mapped[time] = mapped_column(Time, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="sessions")

    __table_args__ = (
        UniqueConstraint("user_id", "time_of_day", name="uq_learning_sessions_user_time"),
    )


class LearningSessionRun(Base):
    """A concrete firing of a scheduled job, used for scheduler idempotency and stats."""

    __tablename__ = "learning_session_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SessionRunStatus] = mapped_column(
        pg_enum(SessionRunStatus, "session_run_status"),
        nullable=False,
        default=SessionRunStatus.PENDING,
    )
    deferred_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
