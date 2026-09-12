from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.enum_types import pg_enum
from bot.database.models.enums import WordStatus

if TYPE_CHECKING:
    from bot.database.models.user import User
    from bot.database.models.word import Word


class UserWord(Base):
    __tablename__ = "user_words"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), nullable=False)
    status: Mapped[WordStatus] = mapped_column(
        pg_enum(WordStatus, "word_status"), nullable=False, default=WordStatus.NEW
    )
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wrong_answers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    repetitions: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    consecutive_correct: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    ease_factor: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, default=Decimal("2.50")
    )
    current_interval_days: Mapped[Decimal] = mapped_column(
        Numeric(6, 2), nullable=False, default=Decimal("0.00")
    )
    last_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    learned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="words")
    word: Mapped["Word"] = relationship(back_populates="user_links", lazy="joined")

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_words_user_word"),
        CheckConstraint("ease_factor >= 1.3", name="ease_factor_min"),
        Index("ix_user_words_user_status", "user_id", "status"),
        Index(
            "ix_user_words_due",
            "user_id",
            "next_review_at",
            postgresql_where=text("status IN ('learning', 'review')"),
        ),
    )
