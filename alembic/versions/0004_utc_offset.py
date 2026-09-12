"""replace user_settings.timezone (IANA name) with utc_offset_minutes

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column("utc_offset_minutes", sa.SmallInteger(), nullable=False, server_default="120"),
    )
    op.create_check_constraint(
        "utc_offset_minutes_range",
        "user_settings",
        "utc_offset_minutes BETWEEN -720 AND 840",
    )
    op.drop_column("user_settings", "timezone")


def downgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "timezone", sa.String(length=64), nullable=False, server_default="Europe/Kyiv"
        ),
    )
    op.drop_constraint("utc_offset_minutes_range", "user_settings", type_="check")
    op.drop_column("user_settings", "utc_offset_minutes")
