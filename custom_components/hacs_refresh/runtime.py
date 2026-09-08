"""Runtime support for HACS Refresh."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    EVENT_ENTITY_UNIQUE_ID,
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
        self._refresh_lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._event_listeners: set[RefreshEventListener] = set()
        self.state = STATE_IDLE
        self.last_result: str | None = None
        self.last_source: str | None = None
        self.last_error: str | None = None

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

    def _last_refresh_time(self) -> datetime | None:
        """Return the timestamp of the last completed refresh event.

        Return None when the event entity has no valid timestamp, allowing
        scheduled refreshes to proceed when no previous completion is known.
        """
        entity_id = er.async_get(self.hass).async_get_entity_id(
            Platform.EVENT,
            DOMAIN,
            EVENT_ENTITY_UNIQUE_ID,
        )
        if entity_id is None:
            return None

        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return None

        last_refresh = dt_util.parse_datetime(state.state)
        if last_refresh is None:
            return None

        return last_refresh

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
            "last_error": self.last_error,
        }

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
            except Exception as err:
                self.state = STATE_IDLE
                self.last_result = EVENT_TYPE_FAILED
                self.last_source = source
                self.last_error = str(err)
                self.notify_listeners()
                self._notify_refresh_completed()

                if source == REFRESH_SOURCE_SCHEDULED:
                    _LOGGER.exception("Scheduled HACS refresh failed")
                    return

                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="unexpected_refresh_error",
                ) from err

    async def _async_refresh(
        self,
        *,
        source: str,
    ) -> None:
        """Run a HACS refresh and update runtime state."""
        now = dt_util.now()
        last_refresh = self._last_refresh_time()

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
        self.last_source = source
        self.last_error = None
        self.last_repositories = 0
        self.last_successful = 0
        self.last_failed = 0
        self.last_pending = 0

        self.notify_listeners()

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

        self._update_refresh_result(result, source=source)

    def _update_refresh_result(
        self,
        result: HacsRefreshResult,
        *,
        source: str,
    ) -> None:
        """Update runtime state from a HACS refresh result."""
        self.state = STATE_IDLE
        self.last_source = source
        self.last_repositories = result.repositories
        self.last_successful = result.successful
        self.last_failed = result.failed
        self.last_pending = result.pending

        if result.pending:
            self.last_result = EVENT_TYPE_PARTIAL
            self.last_error = (
                f"{result.pending} repository refresh task(s) remain pending"
            )
        elif result.failed:
            self.last_result = EVENT_TYPE_FAILED
            self.last_error = f"{result.failed} repository refresh task(s) failed"
        else:
            self.last_result = EVENT_TYPE_SUCCESS
            self.last_error = None

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
