"""Scheduler for HACS Refresh."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    REFRESH_SOURCE_SCHEDULED,
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

        self._unsubscribers: list[Callable[[], None]] = []
        self._next_refresh: datetime | None = None

    @property
    def next_refresh(self) -> datetime | None:
        """Return the next scheduled automatic refresh."""
        return self._next_refresh

    async def async_setup(self) -> None:
        """Set up the configured schedule."""
        self.async_unload()

        options = self.runtime.options

        if not options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        ):
            _LOGGER.debug("Automatic HACS refresh is disabled")
            return

        for time_string in options.get(
            CONF_TIMES,
            [],
        ):
            hour, minute = (int(value) for value in time_string.split(":"))

            self._unsubscribers.append(
                async_track_time_change(
                    self.hass,
                    self._handle_scheduled_time,
                    hour=hour,
                    minute=minute,
                    second=0,
                )
            )

        self._next_refresh = self._calculate_next_refresh(dt_util.now())

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
        self._next_refresh = None

    def _calculate_next_refresh(
        self,
        now: datetime,
    ) -> datetime | None:
        """Calculate the next scheduled automatic refresh."""
        options = self.runtime.options

        if not options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        ):
            return None

        days = set(
            options.get(
                CONF_DAYS,
                [],
            )
        )
        times = options.get(
            CONF_TIMES,
            [],
        )

        if not days or not times:
            return None

        candidates: list[datetime] = []

        for day_offset in range(8):
            candidate_date = now.date() + timedelta(days=day_offset)

            weekday = WEEKDAYS[candidate_date.weekday()]

            if weekday not in days:
                continue

            for time_string in times:
                hour, minute = (int(value) for value in time_string.split(":"))

                candidate = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour,
                    minute,
                    tzinfo=now.tzinfo,
                )

                if candidate > now:
                    candidates.append(candidate)

        if not candidates:
            return None

        return min(candidates)

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

        self._next_refresh = self._calculate_next_refresh(now)
        self.runtime.notify_listeners()

        if self.runtime.refresh_in_progress:
            _LOGGER.warning(
                "Scheduled HACS refresh skipped because another refresh "
                "is already in progress"
            )
            return

        self.runtime.entry.async_create_background_task(
            self.hass,
            self.runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED),
            "scheduled refresh",
        )
