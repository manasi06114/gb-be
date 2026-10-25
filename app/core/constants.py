"""Core domain constants and definitions for the API."""

METRIC_DEFINITIONS: dict[str, str] = {
    "error": (
        "Signed difference between forecast and actual generation: "
        "error = forecast - actual (MW). Positive indicates over-forecasting."
    ),
    "mae": "Mean Absolute Error: average magnitude of forecast errors in MW.",
    "rmse": (
        "Root Mean Squared Error: square root of average squared errors, "
        "penalising larger errors more heavily (MW)."
    ),
    "bias": (
        "Mean signed forecast error (MW). Positive value indicates systematic over-forecasting; "
        "negative indicates under-forecasting."
    ),
    "nmae": (
        "Normalised MAE expressed as a percentage of mean actual generation: "
        "(MAE / mean(actual)) * 100."
    ),
    "coverage": (
        "Percentage of target half-hour periods that have an available forecast "
        "at the decision cutoff."
    ),
    "uncertainty_band": (
        "Symmetric uncertainty interval around forecast calculated as +/- historical RMSE."
    ),
}

# Standard resolution constants
SETTLEMENT_PERIODS_PER_DAY = 48
PERIOD_DURATION_MINUTES = 30
