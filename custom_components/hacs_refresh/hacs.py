"""HACS integration adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant


class HacsUnavailableError(Exception):
    """Raised when HACS is unavailable."""


class HacsDisabledError(Exception):
    """Raised when HACS is disabled."""


class HacsQueueRunningError(Exception):
    """Raised when the HACS queue is already running."""


@dataclass(frozen=True, slots=True)
class HacsRefreshResult:
    """Result of a HACS repository refresh."""

    repositories: int
    successful: int
    failed: int
    pending: int
    failures: tuple[str, ...]


class HacsAdapter:
    """Adapter around the HACS integration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the HACS adapter."""
        self.hass = hass

    def _get_hacs(self) -> Any:
        """Return the HACS instance."""
        hacs = self.hass.data.get("hacs")

        if hacs is None:
            raise HacsUnavailableError

        if hacs.system.disabled:
            raise HacsDisabledError

        return hacs

    async def async_refresh(self) -> HacsRefreshResult:
        """Refresh all installed HACS repositories."""
        hacs = self._get_hacs()

        if hacs.queue.running:
            raise HacsQueueRunningError

        repositories = list(hacs.repositories.list_downloaded)

        if not repositories:
            return HacsRefreshResult(
                repositories=0,
                successful=0,
                failed=0,
                pending=0,
                failures=(),
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

        return HacsRefreshResult(
            repositories=len(repositories),
            successful=successful,
            failed=len(failures),
            pending=pending,
            failures=tuple(failures),
        )
