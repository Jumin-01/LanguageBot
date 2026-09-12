from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.enum_types import pg_enum
from bot.database.models.enums import CEFRLevel, OnboardingStatus

if TYPE_CHECKING:
    from bot.database.models.learning_session import LearningSession
    from bot.database.models.user_settings import UserSettings
    from bot.database.models.user_word import UserWord


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    current_level: Mapped[CEFRLevel] = mapped_column(
        pg_enum(CEFRLevel, "cefr_level"), nullable=False, default=CEFRLevel.A1
    )
    onboarding_status: Mapped[OnboardingStatus] = mapped_column(
        pg_enum(OnboardingStatus, "onboarding_status"),
        nullable=False,
        default=OnboardingStatus.PENDING_LEVEL,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    words: Mapped[list["UserWord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["LearningSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
