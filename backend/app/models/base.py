from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, MetaData, String, Text, cast, func
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def pg_enum(enum_cls: type[Enum], name: str) -> PGEnum:
    """Postgres ENUM that stores the enum *values* (lowercase strings).

    The types themselves are created by the migration, hence create_type=False.
    """
    return PGEnum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )


class Ltree(UserDefinedType):
    """PostgreSQL `ltree` (materialized path) exposed to Python as a dotted string, e.g. "1.4.9".

    Values travel to and from the driver as text (text2ltree / ::text), so no
    driver-specific codec is required.
    """

    cache_ok = True

    def get_col_spec(self, **kw) -> str:
        return "LTREE"

    def bind_expression(self, bindvalue):
        return func.text2ltree(cast(bindvalue, Text))

    def column_expression(self, col):
        return cast(col, String)
