from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    """Normalize database datetimes, including SQLite values without timezone metadata."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
