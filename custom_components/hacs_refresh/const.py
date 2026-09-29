"""Constants for HACS Refresh."""

from datetime import timedelta

DOMAIN = "hacs_refresh"
INTEGRATION_NAME = "HACS Refresh"

MIN_HA_VERSION = "2024.12.0"

SERVICE_REFRESH = "refresh"

AUTOMATIC_REFRESH_SWITCH_UNIQUE_ID = "hacs_refresh_automatic_refresh"
BUTTON_ENTITY_UNIQUE_ID = "hacs_refresh_manual_refresh"
EVENT_ENTITY_UNIQUE_ID = "hacs_refresh_refresh_completed"
PROGRESS_SENSOR_UNIQUE_ID = "hacs_refresh_progress"
STATUS_SENSOR_UNIQUE_ID = "hacs_refresh_status"

STORAGE_KEY = f"{DOMAIN}.last_refresh"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 2

EVENT_TYPE_SUCCESS = "success"
EVENT_TYPE_PARTIAL = "partial"
EVENT_TYPE_FAILED = "failed"

REFRESH_SOURCE_MANUAL = "manual"
REFRESH_SOURCE_SCHEDULED = "scheduled"

STATE_IDLE = "idle"
STATE_REFRESHING = "refreshing"

CONF_AUTOMATIC_REFRESH = "automatic_refresh"
CONF_DAYS = "days"
CONF_TIMES = "times"

MIN_REFRESH_INTERVAL = timedelta(minutes=10)

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
