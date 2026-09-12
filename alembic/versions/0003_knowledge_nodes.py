"""add knowledge_nodes table (Obsidian vault cross-reference)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

knowledge_node_type = postgresql.ENUM(
    "word", "phrase", "topic", "grammar", name="knowledge_node_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    knowledge_node_type.create(bind, checkfirst=True)

    op.create_table(
        "knowledge_nodes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_knowledge_nodes_user_id_users"),
            nullable=False,
        ),
        sa.Column(
            "word_id",
            sa.BigInteger(),
            sa.ForeignKey("words.id", ondelete="CASCADE", name="fk_knowledge_nodes_word_id_words"),
            nullable=True,
        ),
        sa.Column("node_type", knowledge_node_type, nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("obsidian_id", sa.String(length=512), nullable=False),
        sa.Column("obsidian_path", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "obsidian_id", name="uq_knowledge_nodes_user_obsidian_id"),
        sa.UniqueConstraint("user_id", "node_type", "slug", name="uq_knowledge_nodes_user_type_slug"),
    )
    op.create_index("ix_knowledge_nodes_user_id", "knowledge_nodes", ["user_id"])
    op.create_index("ix_knowledge_nodes_word_id", "knowledge_nodes", ["word_id"])


def downgrade() -> None:
    op.drop_table("knowledge_nodes")
    bind = op.get_bind()
    knowledge_node_type.drop(bind, checkfirst=True)
