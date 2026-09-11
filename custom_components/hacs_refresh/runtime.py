"""Runtime support for HACS Refresh."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from time import perf_counter
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_TYPE_FAILED,
    EVENT_TYPE_PARTIAL,
    EVENT_TYPE_SUCCESS,
    MIN_REFRESH_INTERVAL,
    REFRESH_SOURCE_SCHEDULED,
    STATE_IDLE,
    STATE_REFRESHING,
)
from .hacs import (
    HacsAdapter,
    HacsDisabledError,
    HacsQueueRunningError,
    HacsRefreshResult,
    HacsUnavailableError,
)
from .storage import HacsRefreshStore, LastRefreshData

_LOGGER = logging.getLogger(__name__)


class HacsRefreshSkipped(HomeAssistantError):
    """Raised when a refresh should be skipped."""


type RefreshEventListener = Callable[[str, dict[str, Any]], None]


class HacsRefreshRuntimeData:
    """Runtime data for HACS Refresh."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
    ) -> None:
        """Initialize runtime data."""
        self.hass = hass
        self.entry = entry
        self.hacs = HacsAdapter(hass)
        self._store = HacsRefreshStore(hass)
        self._refresh_lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._event_listeners: set[RefreshEventListener] = set()
        self.state = STATE_IDLE
        self.last_completed: datetime | None = None
        self.last_result: str | None = None
        self.last_source: str | None = None
        self.last_message: str | None = None
        self.last_duration: float | None = None

        self.last_repositories = 0
        self.last_successful = 0
        self.last_failed = 0
        self.last_pending = 0

    @property
    def options(self) -> dict[str, Any]:
        """Return the current integration options."""
        return dict(self.entry.options)

    @property
    def refresh_in_progress(self) -> bool:
        """Return whether a refresh is currently in progress."""
        return self._refresh_lock.locked()

    async def async_initialize(self) -> None:
        """Restore persistent refresh state."""
        data = await self._store.async_load()
        if data is None:
            return

        completed = dt_util.parse_datetime(data["completed"])
        if completed is not None:
            self.last_completed = completed
        self.last_result = data["result"]
        self.last_source = data["source"]
        self.last_duration = data["duration"]
        self.last_repositories = data["repositories"]
        self.last_successful = data["successful"]
        self.last_failed = data["failed"]
        self.last_pending = data["pending"]

    def add_listener(
        self,
        listener: Callable[[], None],
    ) -> Callable[[], None]:
        """Register a listener for runtime changes."""
        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    def add_event_listener(
        self,
        listener: RefreshEventListener,
    ) -> Callable[[], None]:
        """Register a listener for refresh completion events."""
        self._event_listeners.add(listener)

        def remove_listener() -> None:
            self._event_listeners.discard(listener)

        return remove_listener

    def _notify_refresh_completed(self) -> None:
        """Notify listeners that a refresh has completed."""
        if self.last_result is None:
            return

        event_data = {
            "source": self.last_source,
            "repositories": self.last_repositories,
            "successful": self.last_successful,
            "failed": self.last_failed,
            "pending": self.last_pending,
            "duration": self.last_duration,
        }
        if self.last_message is not None:
            event_data["message"] = self.last_message

        for listener in tuple(self._event_listeners):
            listener(self.last_result, event_data)

    def notify_listeners(self) -> None:
        """Notify listeners of a runtime or configuration change."""
        for listener in tuple(self._listeners):
            listener()

    async def async_refresh(
        self,
        *,
        source: str,
    ) -> None:
        """Force-refresh all installed HACS repositories."""
        if self.refresh_in_progress:
            if source == REFRESH_SOURCE_SCHEDULED:
                _LOGGER.warning(
                    "Scheduled HACS refresh skipped because another refresh "
                    "is already in progress"
                )
                return

            raise HacsRefreshSkipped(
                translation_domain=DOMAIN,
                translation_key="refresh_in_progress",
            )

        async with self._refresh_lock:
            try:
                await self._async_refresh(source=source)
            except HacsRefreshSkipped:
                if source == REFRESH_SOURCE_SCHEDULED:
                    return
                raise
            except HomeAssistantError:
                if source == REFRESH_SOURCE_SCHEDULED:
                    _LOGGER.error("Scheduled HACS refresh failed")
                    return
                raise

    async def _async_refresh(
        self,
        *,
        source: str,
    ) -> None:
        """Run a HACS refresh and update runtime state."""
        now = dt_util.now()
        last_refresh = self.last_completed

        if (
            source == REFRESH_SOURCE_SCHEDULED
            and last_refresh is not None
            and now - last_refresh < MIN_REFRESH_INTERVAL
        ):
            _LOGGER.warning(
                "Scheduled HACS refresh skipped because the minimum refresh "
                "interval has not elapsed"
            )
            return

        self.state = STATE_REFRESHING
        self.notify_listeners()

        start = perf_counter()
        try:
            result = await self.hacs.async_refresh()
        except HacsUnavailableError as err:
            self.state = STATE_IDLE
            self.notify_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="hacs_unavailable",
            ) from err
        except HacsDisabledError as err:
            self.state = STATE_IDLE
            self.notify_listeners()
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="hacs_disabled",
            ) from err
        except HacsQueueRunningError as err:
            self.state = STATE_IDLE
            self.notify_listeners()

            if source == REFRESH_SOURCE_SCHEDULED:
                _LOGGER.warning(
                    "Scheduled HACS refresh skipped because the HACS queue "
                    "is already running"
                )
                return

            raise HacsRefreshSkipped(
                translation_domain=DOMAIN,
                translation_key="hacs_queue_running",
            ) from err
        except Exception as err:
            duration = perf_counter() - start
            self.state = STATE_IDLE
            self.last_completed = dt_util.now()
            self.last_result = EVENT_TYPE_FAILED
            self.last_source = source
            self.last_message = str(err)
            self.last_duration = duration
            self.last_repositories = 0
            self.last_successful = 0
            self.last_failed = 0
            self.last_pending = 0
            await self._async_save_last_refresh()
            self.notify_listeners()
            self._notify_refresh_completed()

            if source == REFRESH_SOURCE_SCHEDULED:
                _LOGGER.exception("Scheduled HACS refresh failed")
                return

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unexpected_refresh_error",
            ) from err
        else:
            duration = perf_counter() - start

        await self._update_refresh_result(
            result,
            source=source,
            duration=duration,
        )

    async def _async_save_last_refresh(self) -> None:
        """Persist the last completed refresh."""
        if (
            self.last_completed is None
            or self.last_result is None
            or self.last_source is None
            or self.last_duration is None
        ):
            return

        data: LastRefreshData = {
            "completed": self.last_completed.isoformat(),
            "result": self.last_result,
            "source": self.last_source,
            "duration": self.last_duration,
            "repositories": self.last_repositories,
            "successful": self.last_successful,
            "failed": self.last_failed,
            "pending": self.last_pending,
        }
        await self._store.async_save(data)

    async def _update_refresh_result(
        self,
        result: HacsRefreshResult,
        *,
        source: str,
        duration: float,
    ) -> None:
        """Update runtime state from a HACS refresh result."""
        self.state = STATE_IDLE
        self.last_completed = dt_util.now()
        self.last_source = source
        self.last_repositories = result.repositories
        self.last_successful = result.successful
        self.last_failed = result.failed
        self.last_pending = result.pending
        self.last_duration = duration

        if result.pending:
            self.last_result = EVENT_TYPE_PARTIAL
            self.last_message = (
                f"{result.pending} repository refresh task(s) remain pending"
            )
        elif result.failed:
            self.last_result = EVENT_TYPE_FAILED
            self.last_message = f"{result.failed} repository refresh task(s) failed"
        else:
            self.last_result = EVENT_TYPE_SUCCESS
            self.last_message = None

        await self._async_save_last_refresh()

        self.notify_listeners()
        self._notify_refresh_completed()

        if result.repositories == 0:
            _LOGGER.info("No installed HACS repositories found")
            return

        if result.pending:
            _LOGGER.warning(
                "HACS refresh finished with %d repositories still pending "
                "in the HACS queue",
                result.pending,
            )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_tasks_pending",
                translation_placeholders={"pending": str(result.pending)},
            )

        if result.failed:
            _LOGGER.error(
                "HACS refresh failed for %d of %d repositories",
                result.failed,
                result.repositories,
            )

            for failure in result.failures:
                _LOGGER.error(
                    "HACS repository refresh failed: %s",
                    failure,
                )

            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_tasks_failed",
                translation_placeholders={
                    "failed": str(result.failed),
                    "repositories": str(result.repositories),
                },
            )

        _LOGGER.debug(
            "HACS forced refresh completed successfully for %d repositories",
            result.repositories,
        )
