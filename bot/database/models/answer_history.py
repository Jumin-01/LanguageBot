from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.base import Base
from bot.database.enum_types import pg_enum
from bot.database.models.enums import QuestionType


class AnswerHistory(Base):
    __tablename__ = "answer_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), nullable=False)
    user_word_id: Mapped[int] = mapped_column(
        ForeignKey("user_words.id", ondelete="CASCADE"), nullable=False
    )
    question_type: Mapped[QuestionType] = mapped_column(
        pg_enum(QuestionType, "question_type"), nullable=False
    )
    question_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    session_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("learning_session_runs.id", ondelete="SET NULL")
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_answer_history_user_answered_at", "user_id", "answered_at"),
        Index("ix_answer_history_word_id", "word_id"),
    )
