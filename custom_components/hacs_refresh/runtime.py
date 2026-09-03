"""Runtime support for HACS Refresh."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


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

        self._refresh_lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()

        self.state = "idle"

        self.last_refresh = None
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

    def add_listener(
        self,
        listener: Callable[[], None],
    ) -> Callable[[], None]:
        """Register a listener for runtime changes."""
        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    def _notify_listeners(self) -> None:
        """Notify listeners of a runtime state change."""
        for listener in tuple(self._listeners):
            listener()

    async def async_refresh(self, *, source: str) -> None:
        """Force-refresh all installed HACS repositories."""
        if self.refresh_in_progress:
            raise HomeAssistantError(
                "A HACS refresh is already in progress"
            )

        async with self._refresh_lock:
            try:
                await self._async_do_refresh(source=source)
            except HomeAssistantError:
                if source == "scheduled":
                    _LOGGER.error("Scheduled HACS refresh failed")
                    return
                raise
            except Exception as err:
                self.state = "idle"
                self.last_refresh = dt_util.now()
                self.last_result = "failed"
                self.last_source = source
                self.last_error = str(err)
                self._notify_listeners()

                if source == "scheduled":
                    _LOGGER.exception("Scheduled HACS refresh failed")
                    return

                raise HomeAssistantError(
                    "Unexpected error while refreshing HACS repositories"
                ) from err

    async def _async_do_refresh(self, *, source: str) -> None:
        """Perform a HACS refresh."""
        hacs = self.hass.data.get("hacs")

        if hacs is None:
            raise HomeAssistantError("HACS is not available")

        if hacs.system.disabled:
            raise HomeAssistantError("HACS is disabled")

        if hacs.queue.running:
            raise HomeAssistantError(
                "The HACS queue is already running"
            )

        repositories = list(hacs.repositories.list_downloaded)

        self.state = "refreshing"
        self.last_source = source
        self.last_error = None
        self.last_repositories = len(repositories)
        self.last_successful = 0
        self.last_failed = 0
        self.last_pending = len(repositories)
        self._notify_listeners()

        if not repositories:
            self.state = "idle"
            self.last_refresh = dt_util.now()
            self.last_result = "success"
            self.last_pending = 0
            self._notify_listeners()
            return

        _LOGGER.debug(
            "Starting forced refresh of %d installed HACS repositories",
            len(repositories),
        )

        successful = 0
        failures: list[str] = []

        async def refresh_repository(repository: Any) -> None:
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
                failures.append(
                    f"{repository_name}: {err}"
                )
                raise

            successful += 1

        for repository in repositories:
            hacs.queue.add(
                refresh_repository(repository)
            )

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
            self.last_result = "partial"
            self.last_error = (
                f"{pending} repository refresh task(s) remain "
                "pending in the HACS queue"
            )
        elif failures:
            self.last_result = "failed"
            self.last_error = "; ".join(failures)
        else:
            self.last_result = "success"
            self.last_error = None

        self._notify_listeners()

        if pending:
            _LOGGER.warning(
                "HACS refresh finished with %d repositories still "
                "pending in the HACS queue",
                pending,
            )
            raise HomeAssistantError(
                f"{pending} HACS refresh task(s) remain pending"
            )

        if failures:
            _LOGGER.error(
                "HACS refresh failed for %d of %d repositories",
                len(failures),
                len(repositories),
            )
            raise HomeAssistantError(
                f"{len(failures)} of {len(repositories)} "
                "HACS repository refreshes failed"
            )

        _LOGGER.debug(
            "HACS forced refresh completed successfully for %d repositories",
            len(repositories),
        )
