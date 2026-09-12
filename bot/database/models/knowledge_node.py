"""Cross-reference between PostgreSQL (source of truth for learning state)
and a note file in the user's Obsidian vault (source of truth for how that
knowledge relates to everything else the user knows). See bot/obsidian/ and
bot/services/knowledge_graph_service.py.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.base import Base
from bot.database.enum_types import pg_enum
from bot.database.models.enums import KnowledgeNodeType

if TYPE_CHECKING:
    from bot.database.models.word import Word


class KnowledgeNode(Base):
    __tablename__ = "knowledge_nodes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    word_id: Mapped[int | None] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))
    node_type: Mapped[KnowledgeNodeType] = mapped_column(
        pg_enum(KnowledgeNodeType, "knowledge_node_type"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    obsidian_id: Mapped[str] = mapped_column(String(512), nullable=False)
    obsidian_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    word: Mapped["Word | None"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "obsidian_id", name="uq_knowledge_nodes_user_obsidian_id"),
        UniqueConstraint("user_id", "node_type", "slug", name="uq_knowledge_nodes_user_type_slug"),
    )
