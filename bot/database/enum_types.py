"""SQLAlchemy Enum column type factory.

SQLAlchemy's Enum type stores the Python enum MEMBER NAME by default (e.g.
"VERB"), not its .value ("verb"). Our Postgres enum types (created in the
Alembic migration) use the lowercase .value strings, matching how the rest of
the codebase compares/serializes these enums -- so every enum column must be
built through this helper to store .value instead.
"""

from typing import TypeVar

from sqlalchemy import Enum as SAEnum

E = TypeVar("E")


def pg_enum(enum_cls: type[E], name: str) -> SAEnum:
    return SAEnum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [member.value for member in cls],
    )
