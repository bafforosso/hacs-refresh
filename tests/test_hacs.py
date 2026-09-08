from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hacs_refresh.hacs import (
    HacsAdapter,
    HacsDisabledError,
    HacsQueueRunningError,
    HacsRefreshResult,
    HacsUnavailableError,
)


async def test_refresh_fails_when_hacs_is_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test that refresh fails when HACS is unavailable."""
    adapter = HacsAdapter(hass)

    with pytest.raises(HacsUnavailableError):
        await adapter.async_refresh()


async def test_refresh_fails_when_hacs_is_disabled(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that refresh fails when HACS is disabled."""
    hacs.system.disabled = True
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    with pytest.raises(HacsDisabledError):
        await adapter.async_refresh()

    hacs.async_process_queue.assert_not_awaited()


async def test_refresh_fails_when_queue_is_running(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that refresh fails when the HACS queue is already running."""
    hacs.queue.running = True
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    with pytest.raises(HacsQueueRunningError):
        await adapter.async_refresh()

    hacs.async_process_queue.assert_not_awaited()


async def test_refresh_succeeds(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test a successful HACS refresh."""
    repository = MagicMock()
    repository.update_repository = AsyncMock(return_value="update")

    hacs.repositories.list_downloaded = [repository]
    hacs.queue.pending_tasks = 0
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    result = await adapter.async_refresh()

    assert result == HacsRefreshResult(
        repositories=1,
        successful=1,
        failed=0,
        pending=0,
        failures=(),
    )

    repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )
    hacs.queue.add.assert_called_once()
    hacs.async_process_queue.assert_awaited_once()
    hacs.data.async_write.assert_awaited_once()


async def test_refresh_succeeds_with_no_repositories(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that refreshing with no repositories is a successful no-op."""
    hacs.repositories.list_downloaded = []
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    result = await adapter.async_refresh()

    assert result == HacsRefreshResult(
        repositories=0,
        successful=0,
        failed=0,
        pending=0,
        failures=(),
    )

    hacs.queue.add.assert_not_called()
    hacs.async_process_queue.assert_not_awaited()
    hacs.data.async_write.assert_not_awaited()


async def test_refresh_reports_pending_repositories(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that pending repository refreshes are reported correctly."""
    repository = MagicMock()
    repository.update_repository = AsyncMock()

    hacs.repositories.list_downloaded = [repository]
    hass.data["hacs"] = hacs

    async def process_queue() -> None:
        await hacs.queue.add.call_args.args[0]
        hacs.queue.pending_tasks = 1

    hacs.async_process_queue = AsyncMock(side_effect=process_queue)

    adapter = HacsAdapter(hass)

    result = await adapter.async_refresh()

    assert result == HacsRefreshResult(
        repositories=1,
        successful=1,
        failed=0,
        pending=1,
        failures=(),
    )

    hacs.data.async_write.assert_awaited_once()


async def test_refresh_reports_repository_failure(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that repository refresh failures are reported correctly."""
    successful_repository = MagicMock()
    successful_repository.update_repository = AsyncMock()

    failed_repository = MagicMock()
    failed_repository.update_repository = AsyncMock(
        side_effect=RuntimeError("Something went wrong")
    )
    failed_repository.data.full_name = "example/failed-repository"

    hacs.repositories.list_downloaded = [
        successful_repository,
        failed_repository,
    ]
    hacs.queue.pending_tasks = 0
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    result = await adapter.async_refresh()

    assert result == HacsRefreshResult(
        repositories=2,
        successful=1,
        failed=1,
        pending=0,
        failures=("example/failed-repository: Something went wrong",),
    )

    successful_repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )
    failed_repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )

    assert hacs.queue.add.call_count == 2
    hacs.async_process_queue.assert_awaited_once()
    hacs.data.async_write.assert_awaited_once()


async def test_refresh_updates_hacs_coordinators(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that HACS coordinators are notified after refresh."""
    repository = MagicMock()
    repository.update_repository = AsyncMock()

    coordinator = MagicMock()
    hacs.coordinators = {"test": coordinator}

    hacs.repositories.list_downloaded = [repository]
    hacs.queue.pending_tasks = 0
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    await adapter.async_refresh()

    coordinator.async_update_listeners.assert_called_once()
