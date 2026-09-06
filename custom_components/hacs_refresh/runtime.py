"""Runtime support for HACS Refresh."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    EVENT_TYPE_FAILED,
    EVENT_TYPE_PARTIAL,
    EVENT_TYPE_SUCCESS,
    MIN_REFRESH_INTERVAL,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class HacsRefreshStoredData(TypedDict):
    """Persisted HACS Refresh data."""

    last_refresh: str | None
    last_result: str | None
    last_source: str | None
    last_repositories: int
    last_successful: int
    last_failed: int
    last_pending: int
    last_error: str | None


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
        self._store: Store[HacsRefreshStoredData] = Store(
            hass,
            STORAGE_VERSION,
            f"hacs_refresh.{entry.entry_id}",
        )
        self._refresh_lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._event_listeners: set[RefreshEventListener] = set()
        self.state = "idle"
        self.last_refresh: datetime | None = None
        self.last_result: str | None = None
        self.last_source: str | None = None
        self.last_error: str | None = None

        self.last_repositories = 0
        self.last_successful = 0
        self.last_failed = 0
        self.last_pending = 0

    async def async_load(self) -> None:
        """Load persisted refresh data."""
        data = await self._store.async_load()
        if data is None:
            return

        last_refresh = data.get("last_refresh")
        if last_refresh is not None:
            parsed_last_refresh = dt_util.parse_datetime(last_refresh)
            if parsed_last_refresh is not None:
                self.last_refresh = parsed_last_refresh

        self.last_result = data.get("last_result")
        self.last_source = data.get("last_source")
        self.last_repositories = data.get("last_repositories", 0)
        self.last_successful = data.get("last_successful", 0)
        self.last_failed = data.get("last_failed", 0)
        self.last_pending = data.get("last_pending", 0)
        self.last_error = data.get("last_error")

    async def _async_save_last_refresh(self) -> None:
        """Persist the latest refresh result."""
        data: HacsRefreshStoredData = {
            "last_refresh": (
                self.last_refresh.isoformat() if self.last_refresh is not None else None
            ),
            "last_result": self.last_result,
            "last_source": self.last_source,
            "last_repositories": self.last_repositories,
            "last_successful": self.last_successful,
            "last_failed": self.last_failed,
            "last_pending": self.last_pending,
            "last_error": self.last_error,
        }

        await self._store.async_save(data)

    @property
    def options(self) -> dict[str, Any]:
        """Return the current integration options."""
        return dict(self.entry.options)

    @property
    def refresh_in_progress(self) -> bool:
        """Return whether a refresh is currently in progress."""
        return self._refresh_lock.locked()

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
        if self.last_result is None or self.last_refresh is None:
            return

        event_data = {
            "source": self.last_source,
            "last_refresh": self.last_refresh.isoformat(),
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
            if source == "scheduled":
                _LOGGER.debug(
                    "Scheduled HACS refresh skipped because another refresh "
                    "is already in progress"
                )
                return

            raise HacsRefreshSkipped("A HACS refresh is already in progress")

        async with self._refresh_lock:
            try:
                await self._async_do_refresh(source=source)
            except HacsRefreshSkipped:
                if source == "scheduled":
                    _LOGGER.debug("Scheduled HACS refresh skipped")
                    return
                raise
            except HomeAssistantError:
                if source == "scheduled":
                    _LOGGER.error("Scheduled HACS refresh failed")
                    return
                raise
            except Exception as err:
                self.state = "idle"
                self.last_refresh = dt_util.now()
                self.last_result = EVENT_TYPE_FAILED
                self.last_source = source
                self.last_error = str(err)
                await self._async_save_last_refresh()
                self.notify_listeners()
                self._notify_refresh_completed()

                if source == "scheduled":
                    _LOGGER.exception("Scheduled HACS refresh failed")
                    return

                raise HomeAssistantError(
                    "Unexpected error while refreshing HACS repositories"
                ) from err

    async def _async_do_refresh(
        self,
        *,
        source: str,
    ) -> None:
        """Perform a HACS refresh."""
        hacs = self.hass.data.get("hacs")
        if hacs is None:
            raise HomeAssistantError("HACS is not available")

        if hacs.system.disabled:
            raise HomeAssistantError("HACS is disabled")

        if hacs.queue.running:
            if source == "scheduled":
                _LOGGER.warning(
                    "Scheduled HACS refresh skipped because the HACS queue "
                    "is already running"
                )
                return

            raise HacsRefreshSkipped("The HACS queue is already running")

        now = dt_util.now()
        if (
            source == "scheduled"
            and self.last_refresh is not None
            and now - self.last_refresh < MIN_REFRESH_INTERVAL
        ):
            _LOGGER.debug(
                "Scheduled HACS refresh skipped because the minimum refresh "
                "interval has not elapsed"
            )
            return

        repositories = list(hacs.repositories.list_downloaded)

        self.state = "refreshing"
        self.last_source = source
        self.last_error = None
        self.last_repositories = len(repositories)
        self.last_successful = 0
        self.last_failed = 0
        self.last_pending = len(repositories)

        self.notify_listeners()

        if not repositories:
            self.state = "idle"
            self.last_refresh = dt_util.now()
            self.last_result = EVENT_TYPE_SUCCESS
            self.last_pending = 0

            await self._async_save_last_refresh()
            self.notify_listeners()
            self._notify_refresh_completed()

            _LOGGER.debug("No installed HACS repositories found")
            return

        _LOGGER.debug(
            "Starting forced refresh of %d installed HACS repositories",
            len(repositories),
        )

        successful = 0
        failures: list[str] = []

        async def refresh_repository(
            repository: Any,
        ) -> None:
            """Refresh one repository and record its result."""
            nonlocal successful

            try:
                await repository.update_repository(
                    ignore_issues=True,
                    force=True,
                )
            except Exception as err:
                repository_name = getattr(
                    repository.data,
                    "full_name",
                    str(repository),
                )

                failures.append(f"{repository_name}: {err}")

                raise

            successful += 1

        for repository in repositories:
            hacs.queue.add(refresh_repository(repository))

        try:
            await hacs.async_process_queue()
        finally:
            await hacs.data.async_write()

            for coordinator in hacs.coordinators.values():
                coordinator.async_update_listeners()

        pending = hacs.queue.pending_tasks
        self.state = "idle"
        self.last_refresh = dt_util.now()
        self.last_repositories = len(repositories)
        self.last_successful = successful
        self.last_failed = len(failures)
        self.last_pending = pending

        if pending:
            self.last_result = EVENT_TYPE_PARTIAL
            self.last_error = f"{pending} repository refresh task(s) remain pending"
        elif failures:
            self.last_result = EVENT_TYPE_FAILED
            self.last_error = f"{len(failures)} repository refresh task(s) failed"
        else:
            self.last_result = EVENT_TYPE_SUCCESS
            self.last_error = None

        await self._async_save_last_refresh()
        self.notify_listeners()
        self._notify_refresh_completed()

        if pending:
            _LOGGER.warning(
                "HACS refresh finished with %d repositories still pending "
                "in the HACS queue",
                pending,
            )

            raise HomeAssistantError(f"{pending} HACS refresh task(s) remain pending")

        if failures:
            _LOGGER.error(
                "HACS refresh failed for %d of %d repositories",
                len(failures),
                len(repositories),
            )

            for failure in failures:
                _LOGGER.error(
                    "HACS repository refresh failed: %s",
                    failure,
                )

            raise HomeAssistantError(
                f"{len(failures)} of {len(repositories)} "
                "HACS repository refreshes failed"
            )

        _LOGGER.debug(
            "HACS forced refresh completed successfully for %d repositories",
            len(repositories),
        )
