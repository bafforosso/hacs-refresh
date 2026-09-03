"""Constants for HACS Refresh."""

DOMAIN = "hacs_refresh"

SERVICE_REFRESH = "refresh"

CONF_AUTOMATIC_REFRESH = "automatic_refresh"
CONF_DAYS = "days"
CONF_TIMES = "times"

WEEKDAYS = (
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
)

DEFAULT_AUTOMATIC_REFRESH = False
DEFAULT_DAYS = list(WEEKDAYS)
DEFAULT_TIMES = ["03:00"]

MAX_TIMES = 10
