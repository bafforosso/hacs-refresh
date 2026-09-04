"""Constants for HACS Refresh."""

from datetime import timedelta

DOMAIN = "hacs_refresh"
SERVICE_REFRESH = "refresh"

CONF_AUTOMATIC_REFRESH = "automatic_refresh"
CONF_DAYS = "days"
CONF_TIMES = "times"

MIN_REFRESH_INTERVAL = timedelta(minutes=10)

STORAGE_VERSION = 1

WEEKDAYS = (
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
)

DEFAULT_AUTOMATIC_REFRESH = True
DEFAULT_DAYS = list(WEEKDAYS)
DEFAULT_TIMES = ["02:30"]

MAX_TIMES = 10