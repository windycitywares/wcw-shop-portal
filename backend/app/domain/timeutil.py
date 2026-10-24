"""Store-local time. Reports bucket by the store's calendar day, not UTC. The zone is the owner's choice
(Admin → Settings → General); `set_store_tz` is called whenever settings are loaded."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo

from app.domain.timezones import DEFAULT_TIMEZONE, TIMEZONE_IDS

_name = DEFAULT_TIMEZONE


def set_store_tz(name: str | None) -> None:
    """Use this IANA zone from now on; anything not on the list falls back to the default."""
    global _name
    _name = name if name in TIMEZONE_IDS else DEFAULT_TIMEZONE


def store_tz_name() -> str:
    return _name


class _UsCentral(tzinfo):
    """Fallback for hosts without a time zone database: US Central, with the rules in force since 2007."""

    def _dst_range(self, year: int) -> tuple[datetime, datetime]:
        march = date(year, 3, 8)  # second Sunday in March
        march += timedelta(days=(6 - march.weekday()) % 7)
        november = date(year, 11, 1)  # first Sunday in November
        november += timedelta(days=(6 - november.weekday()) % 7)
        return datetime(march.year, march.month, march.day, 2), datetime(november.year, november.month, november.day, 2)

    def utcoffset(self, dt):
        if dt is None:
            return timedelta(hours=-6)
        start, end = self._dst_range(dt.year)
        naive = dt.replace(tzinfo=None)
        return timedelta(hours=-5) if start <= naive < end else timedelta(hours=-6)

    def dst(self, dt):
        return timedelta(hours=1) if self.utcoffset(dt) == timedelta(hours=-5) else timedelta(0)

    def tzname(self, dt):
        return "CDT" if self.dst(dt) else "CST"


def store_tz() -> tzinfo:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(_name)
    except Exception:  # missing tz database
        return _UsCentral() if _name == "America/Chicago" else timezone.utc


def to_store_time(moment: datetime) -> datetime:
    return moment.astimezone(store_tz())


def store_today(now: datetime | None = None) -> date:
    return to_store_time(now or datetime.now(timezone.utc)).date()


def day_start_utc(day: date) -> datetime:
    """Midnight at the start of `day` in store time, as an aware UTC datetime."""
    local = datetime(day.year, day.month, day.day, tzinfo=store_tz())
    return local.astimezone(timezone.utc)


@dataclass(frozen=True)
class DateRange:
    """Inclusive local dates [start, end]; `start_utc`/`end_utc` are the half-open UTC bounds for SQL."""

    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def start_utc(self) -> datetime:
        return day_start_utc(self.start)

    @property
    def end_utc(self) -> datetime:
        return day_start_utc(self.end + timedelta(days=1))

    def previous(self) -> DateRange:
        return DateRange(self.start - timedelta(days=self.days), self.start - timedelta(days=1))

    def granularity(self) -> str:
        if self.days <= 62:
            return "day"
        return "week" if self.days <= 270 else "month"

    def each_day(self) -> list[date]:
        return [self.start + timedelta(days=i) for i in range(self.days)]


MAX_RANGE_DAYS = 800


def resolve_range(start: date | None, end: date | None, default_days: int = 30, today: date | None = None) -> DateRange:
    """Default: the last `default_days` days up to and including today. Swapped or oversized ranges are fixed."""
    today = today or store_today()
    end = min(end or today, today + timedelta(days=1))
    start = start or end - timedelta(days=default_days - 1)
    if start > end:
        start, end = end, start
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        start = end - timedelta(days=MAX_RANGE_DAYS - 1)
    return DateRange(start, end)
