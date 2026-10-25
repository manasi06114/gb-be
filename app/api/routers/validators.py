"""Query parameter validation helpers shared across routers."""

from datetime import date

from app.core.errors import ValidationAppError


def validate_date_range(date_from: date, date_to: date) -> None:
    """Raise ValidationAppError if date_from is after date_to."""
    if date_from > date_to:
        raise ValidationAppError(
            f"date_from ({date_from}) must be on or before date_to ({date_to})."
        )


def validate_delivery_window(
    date_from: date,
    date_to: date,
    window_start: date,
    window_end: date,
) -> None:
    """Raise ValidationAppError if queried range is outside the configured delivery window."""
    if date_from < window_start or date_to > window_end:
        raise ValidationAppError(
            f"Requested date range [{date_from}, {date_to}] is outside the configured "
            f"delivery window [{window_start}, {window_end}]."
        )


def validate_single_date(d: date, window_start: date, window_end: date) -> None:
    """Raise ValidationAppError if a single delivery_date is outside the configured window."""
    if d < window_start or d > window_end:
        raise ValidationAppError(
            f"delivery_date {d} is outside the configured delivery window "
            f"[{window_start}, {window_end}]."
        )


def resolve_delivery_window(
    repo: object, default_start: date, default_end: date
) -> tuple[date, date]:
    """Resolve active delivery window from repository data or fallback to defaults."""
    if hasattr(repo, "get_delivery_bounds"):
        min_d, max_d = repo.get_delivery_bounds()
        return min_d or default_start, max_d or default_end
    return default_start, default_end
