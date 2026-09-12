from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Computed,
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.enum_types import pg_enum
from bot.database.models.enums import CEFRLevel, PartOfSpeech, WordSource

if TYPE_CHECKING:
    from bot.database.models.user_word import UserWord


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lemma: Mapped[str] = mapped_column(String(255), nullable=False)
    lemma_normalized: Mapped[str] = mapped_column(
        String(255), Computed("lower(trim(lemma))", persisted=True)
    )
    translation: Mapped[str] = mapped_column(Text, nullable=False)
    example_en: Mapped[str] = mapped_column(Text, nullable=False)
    example_uk: Mapped[str] = mapped_column(Text, nullable=False)
    # NOTE: here "_uk"/"_us" mean British/American PRONUNCIATION (IPA), unlike
    # the "_uk" above which means the Ukrainian TRANSLATION -- unfortunate
    # naming collision, kept as specified. IPA strings, e.g. "/əˈfɔːdəbl/".
    transcription_uk: Mapped[str | None] = mapped_column(String(255))
    transcription_us: Mapped[str | None] = mapped_column(String(255))
    level: Mapped[CEFRLevel] = mapped_column(pg_enum(CEFRLevel, "cefr_level"), nullable=False)
    topic: Mapped[str | None] = mapped_column(String(100))
    part_of_speech: Mapped[PartOfSpeech] = mapped_column(
        pg_enum(PartOfSpeech, "part_of_speech"), nullable=False
    )
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    antonyms: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    collocations: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[WordSource] = mapped_column(
        pg_enum(WordSource, "word_source"), nullable=False, default=WordSource.AI_GENERATED
    )
    generation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user_links: Mapped[list["UserWord"]] = relationship(back_populates="word")

    __table_args__ = (
        UniqueConstraint("lemma_normalized", "part_of_speech", name="uq_words_lemma_pos"),
        Index("ix_words_level", "level"),
        Index("ix_words_topic", "topic"),
    )
