"""HACS integration adapter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant


class HacsUnavailableError(Exception):
    """Raised when HACS is unavailable."""


class HacsDisabledError(Exception):
    """Raised when HACS is disabled."""


class HacsQueueBusyError(Exception):
    """Raised when the HACS queue is busy."""


@dataclass(frozen=True, slots=True)
class HacsRefreshResult:
    """Result of a HACS repository refresh."""

    repositories: int
    successful: int
    failed: int
    pending: int
    failed_repositories: tuple[str, ...]
    pending_repositories: tuple[str, ...]
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HacsRefreshProgress:
    """Progress of a HACS repository refresh."""

    total: int
    processed: int
    successful: int
    failed: int

    @property
    def remaining(self) -> int:
        """Return the number of repositories that remain unprocessed."""
        return self.total - self.processed


type HacsRefreshProgressCallback = Callable[[HacsRefreshProgress], None]


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

    async def async_refresh(
        self,
        *,
        progress_callback: HacsRefreshProgressCallback | None = None,
    ) -> HacsRefreshResult:
        """Refresh all installed HACS repositories."""
        hacs = self._get_hacs()

        if hacs.queue.running or hacs.queue.has_pending_tasks:
            raise HacsQueueBusyError

        repositories = list(hacs.repositories.list_downloaded)

        processed = 0
        successful = 0
        failed = 0

        def report_progress() -> None:
            """Report the current refresh progress."""
            if progress_callback is not None:
                progress_callback(
                    HacsRefreshProgress(
                        total=len(repositories),
                        processed=processed,
                        successful=successful,
                        failed=failed,
                    )
                )

        report_progress()

        if not repositories:
            return HacsRefreshResult(
                repositories=0,
                successful=0,
                failed=0,
                pending=0,
                failed_repositories=(),
                pending_repositories=(),
                failures=(),
            )

        repository_names: list[str] = []
        repository_statuses: list[bool | None] = []
        failures: list[str] = []

        async def refresh_repository(
            index: int,
            repository: Any,
            repository_name: str,
        ) -> None:
            """Refresh one repository and record its result."""
            nonlocal processed, successful, failed

            try:
                await repository.update_repository(
                    ignore_issues=True,
                    force=True,
                )
            except Exception as err:
                repository_statuses[index] = False
                failures.append(f"{repository_name}: {err}")
                failed += 1
                processed += 1
                report_progress()
                raise
            else:
                repository_statuses[index] = True
                successful += 1
                processed += 1
                report_progress()

        for index, repository in enumerate(repositories):
            repository_name = getattr(
                repository.data,
                "full_name",
                str(repository),
            )
            repository_names.append(repository_name)
            repository_statuses.append(None)

            hacs.queue.add(
                refresh_repository(
                    index,
                    repository,
                    repository_name,
                )
            )

        try:
            await hacs.async_process_queue()
        finally:
            await hacs.data.async_write()

            for coordinator in hacs.coordinators.values():
                coordinator.async_update_listeners()

        successful = 0
        failed_repositories: list[str] = []
        pending_repositories: list[str] = []

        for repository_name, status in zip(
            repository_names,
            repository_statuses,
            strict=True,
        ):
            if status is True:
                successful += 1
            elif status is False:
                failed_repositories.append(repository_name)
            else:
                pending_repositories.append(repository_name)

        return HacsRefreshResult(
            repositories=len(repository_names),
            successful=successful,
            failed=len(failed_repositories),
            pending=len(pending_repositories),
            failed_repositories=tuple(failed_repositories),
            pending_repositories=tuple(pending_repositories),
            failures=tuple(failures),
        )
