"""Unit tests for decision cutoff time calculation and timezone handling."""

from datetime import date, datetime, timezone

import pytest

from app.core.errors import ValidationAppError
from app.domain.decision_time import cutoff_for, parse_cutoff_time


def test_parse_cutoff_valid() -> None:
    """Verify parsing valid HH:MM strings."""
    t = parse_cutoff_time("09:00")
    assert t.hour == 9
    assert t.minute == 0

    t2 = parse_cutoff_time("23:59")
    assert t2.hour == 23
    assert t2.minute == 59


def test_parse_cutoff_invalid() -> None:
    """Verify error on invalid time formats."""
    with pytest.raises(ValidationAppError):
        parse_cutoff_time("25:00")

    with pytest.raises(ValidationAppError):
        parse_cutoff_time("09:65")

    with pytest.raises(ValidationAppError):
        parse_cutoff_time("9:00")

    with pytest.raises(ValidationAppError):
        parse_cutoff_time("invalid")


def test_cutoff_for_winter_date() -> None:
    """Verify cutoff on D-1 converted to UTC for January (GMT = UTC)."""
    delivery_date = date(2026, 1, 15)
    cutoff_utc = cutoff_for(delivery_date, "09:00", tz_name="Europe/London")

    # Day before is 2026-01-14
    # In January, London is UTC+0
    expected = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
    assert cutoff_utc == expected
    assert cutoff_utc.tzinfo == timezone.utc
