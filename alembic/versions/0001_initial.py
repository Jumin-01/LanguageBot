"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False: enum types are created/dropped explicitly in upgrade()/downgrade()
# below, since op.create_table() creates them with checkfirst=False and would otherwise
# collide with our own explicit CREATE TYPE statements within the same migration.
cefr_level = postgresql.ENUM(
    "A1", "A2", "B1", "B2", "C1", "C2", name="cefr_level", create_type=False
)
part_of_speech = postgresql.ENUM(
    "noun", "verb", "adjective", "adverb", "phrase", "phrasal_verb",
    "idiom", "preposition", "conjunction", "other", name="part_of_speech", create_type=False,
)
word_status = postgresql.ENUM(
    "new", "learning", "review", "learned", "suspended", name="word_status", create_type=False
)
question_type = postgresql.ENUM(
    "en_to_ua_choice", "ua_to_en_choice", "fill_blank", "choose_word_for_sentence",
    "translate_sentence", "choose_correct_example", name="question_type", create_type=False,
)
word_source = postgresql.ENUM(
    "ai_generated", "seed", "manual", name="word_source", create_type=False
)
onboarding_status = postgresql.ENUM(
    "pending_level", "active", name="onboarding_status", create_type=False
)
session_run_status = postgresql.ENUM(
    "pending", "sent", "deferred", "skipped", name="session_run_status", create_type=False
)

ALL_ENUMS = [
    cefr_level, part_of_speech, word_status, question_type,
    word_source, onboarding_status, session_run_status,
]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("current_level", cefr_level, nullable=False, server_default="A1"),
        sa.Column(
            "onboarding_status", onboarding_status, nullable=False, server_default="pending_level"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "user_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_settings_user_id_users"),
            nullable=False,
            unique=True,
        ),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Kyiv"),
        sa.Column("daily_new_words_goal", sa.SmallInteger(), nullable=False, server_default="5"),
        sa.Column("sessions_per_day", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("quiet_hours_start", sa.Time(), nullable=False, server_default="22:00:00"),
        sa.Column("quiet_hours_end", sa.Time(), nullable=False, server_default="08:00:00"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "daily_new_words_goal BETWEEN 1 AND 20", name="daily_new_words_goal_range"
        ),
        sa.CheckConstraint("sessions_per_day BETWEEN 1 AND 5", name="sessions_per_day_range"),
    )

    op.create_table(
        "words",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("lemma", sa.String(length=255), nullable=False),
        sa.Column(
            "lemma_normalized",
            sa.String(length=255),
            sa.Computed("lower(trim(lemma))", persisted=True),
        ),
        sa.Column("translation", sa.Text(), nullable=False),
        sa.Column("example_en", sa.Text(), nullable=False),
        sa.Column("example_uk", sa.Text(), nullable=False),
        sa.Column("level", cefr_level, nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=True),
        sa.Column("part_of_speech", part_of_speech, nullable=False),
        sa.Column(
            "synonyms", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "antonyms", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"
        ),
        sa.Column(
            "collocations", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", word_source, nullable=False, server_default="ai_generated"),
        sa.Column("generation_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("lemma_normalized", "part_of_speech", name="uq_words_lemma_pos"),
    )
    op.create_index("ix_words_level", "words", ["level"])
    op.create_index("ix_words_topic", "words", ["topic"])

    op.create_table(
        "user_words",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_words_user_id_users"),
            nullable=False,
        ),
        sa.Column(
            "word_id",
            sa.BigInteger(),
            sa.ForeignKey("words.id", name="fk_user_words_word_id_words"),
            nullable=False,
        ),
        sa.Column("status", word_status, nullable=False, server_default="new"),
        sa.Column("correct_answers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("wrong_answers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("repetitions", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("consecutive_correct", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("ease_factor", sa.Numeric(4, 2), nullable=False, server_default="2.50"),
        sa.Column("current_interval_days", sa.Numeric(6, 2), nullable=False, server_default="0.00"),
        sa.Column("last_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("learned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "word_id", name="uq_user_words_user_word"),
        sa.CheckConstraint("ease_factor >= 1.3", name="ease_factor_min"),
    )
    op.create_index("ix_user_words_user_status", "user_words", ["user_id", "status"])
    op.create_index(
        "ix_user_words_due",
        "user_words",
        ["user_id", "next_review_at"],
        postgresql_where=sa.text("status IN ('learning', 'review')"),
    )

    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_learning_sessions_user_id_users"),
            nullable=False,
        ),
        sa.Column("time_of_day", sa.Time(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "time_of_day", name="uq_learning_sessions_user_time"),
    )

    op.create_table(
        "learning_session_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "users.id", ondelete="CASCADE", name="fk_learning_session_runs_user_id_users"
            ),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", session_run_status, nullable=False, server_default="pending"),
        sa.Column("deferred_reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "answer_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_answer_history_user_id_users"),
            nullable=False,
        ),
        sa.Column(
            "word_id",
            sa.BigInteger(),
            sa.ForeignKey("words.id", name="fk_answer_history_word_id_words"),
            nullable=False,
        ),
        sa.Column(
            "user_word_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "user_words.id", ondelete="CASCADE", name="fk_answer_history_user_word_id_user_words"
            ),
            nullable=False,
        ),
        sa.Column("question_type", question_type, nullable=False),
        sa.Column("question_payload", postgresql.JSONB(), nullable=False),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column(
            "session_run_id",
            sa.BigInteger(),
            sa.ForeignKey(
                "learning_session_runs.id",
                ondelete="SET NULL",
                name="fk_answer_history_session_run_id_learning_session_runs",
            ),
            nullable=True,
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_answer_history_user_answered_at", "answer_history", ["user_id", "answered_at"])
    op.create_index("ix_answer_history_word_id", "answer_history", ["word_id"])


def downgrade() -> None:
    op.drop_table("answer_history")
    op.drop_table("learning_session_runs")
    op.drop_table("learning_sessions")
    op.drop_table("user_words")
    op.drop_table("words")
    op.drop_table("user_settings")
    op.drop_table("users")

    bind = op.get_bind()
    for enum_type in reversed(ALL_ENUMS):
        enum_type.drop(bind, checkfirst=True)
