"""Diagnostics support for HACS Refresh."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import HacsRefreshConfigEntry
from .const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DEFAULT_AUTOMATIC_REFRESH,
    DEFAULT_DAYS,
    DEFAULT_TIMES,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: HacsRefreshConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    options = entry.runtime_data.options
    runtime = entry.runtime_data

    return {
        "config": {
            CONF_AUTOMATIC_REFRESH: options.get(
                CONF_AUTOMATIC_REFRESH,
                DEFAULT_AUTOMATIC_REFRESH,
            ),
            CONF_DAYS: options.get(CONF_DAYS, DEFAULT_DAYS),
            CONF_TIMES: options.get(CONF_TIMES, DEFAULT_TIMES),
        },
        "runtime": {
            "state": runtime.state,
            "last_completed": (
                runtime.last_completed.isoformat()
                if runtime.last_completed is not None
                else None
            ),
            "last_result": runtime.last_result,
            "last_source": runtime.last_source,
            "last_repositories": runtime.last_repositories,
            "last_successful": runtime.last_successful,
            "last_failed": runtime.last_failed,
            "last_pending": runtime.last_pending,
            "last_duration": runtime.last_duration,
        },
    }
