"""Shared pieces for the report builders: running queries, KPI cards, date buckets."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timeutil import STORE_TZ_NAME, DateRange

Row = dict[str, Any]


def num(value: Any, digits: int = 2) -> float:
    """Decimal/int/None -> float for JSON, rounded."""
    if value is None:
        return 0.0
    return round(float(value), digits)


def ratio(part: float | int | Decimal | None, whole: float | int | Decimal | None) -> float | None:
    """part / whole, or None when there is nothing to divide by (so the screen can show a dash, not 0%)."""
    if not whole:
        return None
    return round(float(part or 0) / float(whole), 6)


def avg(part: float | int | Decimal | None, whole: float | int | Decimal | None, digits: int = 2) -> float | None:
    """An average to a few decimals (money: cents), or None when there is nothing to divide by."""
    if not whole:
        return None
    return round(float(part or 0) / float(whole), digits)


def params(rng: DateRange, **extra: Any) -> dict[str, Any]:
    return {"start": rng.start_utc, "end": rng.end_utc, "tz": STORE_TZ_NAME, "gran": rng.granularity(), **extra}


async def rows(session: AsyncSession, sql: str, p: Mapping[str, Any] | None = None) -> list[Row]:
    result = await session.execute(text(sql), dict(p or {}))
    return [dict(r) for r in result.mappings().all()]


async def one(session: AsyncSession, sql: str, p: Mapping[str, Any] | None = None) -> Row:
    found = await rows(session, sql, p)
    return found[0] if found else {}


async def scalar(session: AsyncSession, sql: str, p: Mapping[str, Any] | None = None) -> Any:
    return (await session.execute(text(sql), dict(p or {}))).scalar_one_or_none()


# ---- KPI cards -----------------------------------------------------------------------------------


def kpi(key: str, label: str, value: float | None, previous: float | None = None, fmt: str = "number", help: str = "", better: str = "up") -> Row:
    """One number with its comparison. `better` says which direction is good news ("up", "down" or "none")."""
    change = None
    delta = None
    if value is not None and previous is not None:
        delta = round(value - previous, 6)
        if previous:
            change = round((value - previous) / abs(previous), 6)
    return {"key": key, "label": label, "value": value, "previous": previous, "delta": delta, "change": change, "format": fmt, "help": help, "better": better}


# ---- time buckets ------------------------------------------------------------------------------------


def bucket_starts(rng: DateRange) -> list[date]:
    """The first day of every day/week/month bucket that overlaps the range, matching date_trunc in SQL."""
    gran = rng.granularity()
    if gran == "day":
        return rng.each_day()
    out: list[date] = []
    cursor = rng.start - timedelta(days=rng.start.weekday()) if gran == "week" else rng.start.replace(day=1)
    while cursor <= rng.end:
        out.append(cursor)
        if gran == "week":
            cursor += timedelta(days=7)
        else:
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def bucket_label(day: date, gran: str) -> str:
    if gran == "month":
        return day.strftime("%b %Y")
    return f"{day.strftime('%b')} {day.day}"


def fill_series(rng: DateRange, found: Iterable[Row], fields: Mapping[str, Any]) -> list[Row]:
    """One entry per bucket (zeros where nothing happened). `fields` maps output name -> default value."""
    by_bucket = {r["bucket"]: r for r in found}
    gran = rng.granularity()
    series = []
    for day in bucket_starts(rng):
        source = by_bucket.get(day, {})
        entry: Row = {"bucket": day.isoformat(), "label": bucket_label(day, gran)}
        for name, default in fields.items():
            value = source.get(name, default)
            entry[name] = num(value) if isinstance(value, Decimal) else value
        series.append(entry)
    return series


def range_info(rng: DateRange) -> Row:
    prev = rng.previous()
    return {
        "start": rng.start.isoformat(), "end": rng.end.isoformat(), "days": rng.days, "granularity": rng.granularity(),
        "previous_start": prev.start.isoformat(), "previous_end": prev.end.isoformat(),
    }


def clean(row: Row) -> Row:
    """Make a database row JSON-friendly: Decimals become floats, datetimes become ISO strings."""
    out: Row = {}
    for key, value in row.items():
        if isinstance(value, Decimal):
            out[key] = num(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def clean_all(found: Iterable[Row]) -> list[Row]:
    return [clean(r) for r in found]
