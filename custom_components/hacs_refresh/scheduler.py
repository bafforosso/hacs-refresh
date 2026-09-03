"""Scheduler for HACS Refresh."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    WEEKDAYS,
)
from .runtime import HacsRefreshRuntimeData

_LOGGER = logging.getLogger(__name__)


class HacsRefreshScheduler:
    """Manage the fixed HACS Refresh schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        runtime: HacsRefreshRuntimeData,
    ) -> None:
        """Initialize the scheduler."""
        self.hass = hass
        self.runtime = runtime

        self._unsubscribers: list[
            Callable[[], None]
        ] = []

    async def async_setup(self) -> None:
        """Set up the configured schedule."""
        self.async_unload()

        options = self.runtime.options

        if not options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        ):
            _LOGGER.debug(
                "Automatic HACS refresh is disabled"
            )
            return

        for time_string in options.get(
            CONF_TIMES,
            [],
        ):
            hour, minute = (
                int(value)
                for value in time_string.split(":")
            )

            self._unsubscribers.append(
                async_track_time_change(
                    self.hass,
                    self._handle_scheduled_time,
                    hour=hour,
                    minute=minute,
                    second=0,
                )
            )

        _LOGGER.debug(
            "Configured HACS automatic refresh: days=%s times=%s",
            options.get(CONF_DAYS, []),
            options.get(CONF_TIMES, []),
        )

    @callback
    def async_unload(self) -> None:
        """Unload the scheduler."""
        for unsubscribe in self._unsubscribers:
            unsubscribe()

        self._unsubscribers.clear()

    @callback
    def _handle_scheduled_time(
        self,
        now: datetime,
    ) -> None:
        """Handle a configured schedule time."""
        options = self.runtime.options

        if not options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        ):
            return

        days = set(
            options.get(
                CONF_DAYS,
                [],
            )
        )

        if WEEKDAYS[now.weekday()] not in days:
            return

        if self.runtime.refresh_in_progress:
            _LOGGER.debug(
                "Skipping scheduled HACS refresh because another refresh is already in progress"
            )
            return

        self.hass.async_create_task(
            self.runtime.async_refresh(
                source="scheduled"
            )
        )
