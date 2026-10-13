"""Small helpers (port of the non-component exports in src/components/ui.jsx)."""
import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None


def today() -> str:
    """Today's date as YYYY-MM-DD (UTC, like the original toISOString().slice(0, 10))."""
    return datetime.now(timezone.utc).date().isoformat()


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string, accepting a trailing 'Z'."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def hours(entry: dict) -> float:
    """Hours between clock_in and clock_out; 0 while the entry is still open."""
    if not entry.get("clock_out"):
        return 0.0
    return (parse_iso(entry["clock_out"]) - parse_iso(entry["clock_in"])).total_seconds() / 3600


def num(value, default=0):
    """Form value -> number (int when whole), like JavaScript's unary plus."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if n != n or n in (float("inf"), float("-inf")):
        return default
    return int(n) if n.is_integer() else n


def _local(value):
    """ISO string -> datetime in APP_TZ (default: the server's local timezone)."""
    if not value:
        return None
    tz = ZoneInfo(os.environ["APP_TZ"]) if os.environ.get("APP_TZ") and ZoneInfo else None
    return parse_iso(value).astimezone(tz)


def localtime(value) -> str:
    dt = _local(value)
    return dt.strftime("%H:%M:%S") if dt else ""


def localdatetime(value) -> str:
    dt = _local(value)
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else ""
