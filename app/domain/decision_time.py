"""Decision cutoff time calculation and timezone conversion (Europe/London to UTC)."""

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.errors import ValidationAppError

CUTOFF_REGEX = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_cutoff_time(cutoff_str: str) -> time:
    """Validate and parse a HH:MM string into a time object.

    Args:
        cutoff_str: String formatted as 'HH:MM'.

    Returns:
        datetime.time object.

    Raises:
        ValidationAppError: If cutoff_str format is invalid.
    """
    match = CUTOFF_REGEX.match(cutoff_str.strip())
    if not match:
        raise ValidationAppError(
            f"Invalid cutoff time format '{cutoff_str}'. Expected format is 'HH:MM' (24-hour)."
        )
    hour, minute = int(match.group(1)), int(match.group(2))
    return time(hour=hour, minute=minute)


def cutoff_for(
    delivery_date: date,
    cutoff_local_time: str,
    tz_name: str = "Europe/London",
) -> datetime:
    """Calculate the UTC decision cutoff timestamp for a given delivery date and local cutoff time.

    The decision cutoff occurs on D-1 (the day before delivery day D).

    Args:
        delivery_date: The delivery date (D).
        cutoff_local_time: Cutoff time on D-1 formatted as 'HH:MM'.
        tz_name: Local timezone name (default: 'Europe/London').

    Returns:
        A tz-aware datetime in UTC representing the cutoff instant.
    """
    parsed_time = parse_cutoff_time(cutoff_local_time)
    decision_date = delivery_date - timedelta(days=1)

    tz = ZoneInfo(tz_name)
    local_dt = datetime.combine(decision_date, parsed_time, tzinfo=tz)
    return local_dt.astimezone(timezone.utc)
