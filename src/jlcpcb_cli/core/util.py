"""Shared utilities."""

from datetime import datetime, timezone


def ms_to_iso(ms: int | None) -> str | None:
    """Convert millisecond timestamp to ISO 8601 string."""
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
