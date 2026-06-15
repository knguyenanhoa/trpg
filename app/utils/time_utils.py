"""Timezone-aware timestamp utilities."""

from datetime import datetime, timezone, timedelta

from app.config import TIMEZONE_OFFSET


def get_tz():
    """Get the configured timezone."""
    return timezone(timedelta(hours=TIMEZONE_OFFSET))


def now() -> datetime:
    """Get current time in configured timezone."""
    return datetime.now(get_tz())


def now_iso() -> str:
    """Get current time as ISO8601 string."""
    return now().isoformat()


def parse_iso(iso_str: str) -> datetime:
    """Parse an ISO8601 string to datetime."""
    return datetime.fromisoformat(iso_str)


def start_of_day(dt: datetime) -> datetime:
    """Get start of day for a given datetime."""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime) -> datetime:
    """Get end of day for a given datetime."""
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_month(dt: datetime) -> datetime:
    """Get start of current month."""
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def end_of_month(dt: datetime) -> datetime:
    """Get end of current month."""
    if dt.month == 12:
        next_month = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        next_month = dt.replace(month=dt.month + 1, day=1)
    return next_month - timedelta(microseconds=1)


def duration_seconds(start: datetime, end: datetime) -> int:
    """Calculate duration in seconds between two datetimes."""
    return max(0, int((end - start).total_seconds()))
