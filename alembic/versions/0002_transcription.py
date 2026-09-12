"""add IPA transcription fields to words

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("words", sa.Column("transcription_uk", sa.String(length=255), nullable=True))
    op.add_column("words", sa.Column("transcription_us", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("words", "transcription_us")
    op.drop_column("words", "transcription_uk")
