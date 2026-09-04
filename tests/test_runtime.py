from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import DOMAIN
from custom_components.hacs_refresh.runtime import (
    HacsRefreshRuntimeData,
    HacsRefreshSkipped,
)


async def test_refresh_fails_when_hacs_is_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test that refresh raises an error when HACS is unavailable."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with pytest.raises(
        HomeAssistantError,
        match="HACS is not available",
    ):
        await runtime.async_refresh(source="manual")


async def test_refresh_succeeds(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test a successful HACS refresh."""
    entry = MockConfigEntry(domain=DOMAIN)

    repository = MagicMock()
    repository.update_repository = AsyncMock(return_value="update")

    hacs.repositories.list_downloaded = [repository]

    hass.data["hacs"] = hacs

    runtime = HacsRefreshRuntimeData(hass, entry)

    await runtime.async_refresh(source="manual")

    repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )
    hacs.queue.add.assert_called_once()
    hacs.async_process_queue.assert_awaited_once()
    hacs.data.async_write.assert_awaited_once()
    assert runtime.state == "idle"
    assert runtime.last_result == "success"
    assert runtime.last_repositories == 1
    assert runtime.last_successful == 1
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_error is None


async def test_refresh_fails_when_hacs_is_disabled(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that refresh fails when HACS is disabled."""
    hacs.system.disabled = True
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with pytest.raises(
        HomeAssistantError,
        match="HACS is disabled",
    ):
        await runtime.async_refresh(source="manual")


async def test_manual_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that a manual refresh is skipped when the HACS queue is running."""
    hacs.queue.running = True
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with pytest.raises(
        HacsRefreshSkipped,
        match="The HACS queue is already running",
    ):
        await runtime.async_refresh(source="manual")

    hacs.async_process_queue.assert_not_awaited()


async def test_scheduled_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
    hacs: MagicMock,
    caplog,
) -> None:
    """Test that a scheduled refresh is skipped when the HACS queue is running."""
    hacs.queue.running = True
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    await runtime.async_refresh(source="scheduled")

    hacs.async_process_queue.assert_not_awaited()

    assert (
        "Scheduled HACS refresh skipped because the HACS queue is already running"
        in caplog.text
    )


async def test_refresh_succeeds_with_no_repositories(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that refreshing with no repositories is a successful no-op."""
    hacs.repositories.list_downloaded = []
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    await runtime.async_refresh(source="manual")

    assert runtime.state == "idle"
    assert runtime.last_result == "success"
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_error is None

    hacs.queue.add.assert_not_called()
    hacs.async_process_queue.assert_not_awaited()
    hacs.data.async_write.assert_not_awaited()


async def test_refresh_reports_repository_failure(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that repository refresh failures are reported correctly."""
    entry = MockConfigEntry(domain=DOMAIN)

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
    hass.data["hacs"] = hacs

    runtime = HacsRefreshRuntimeData(hass, entry)

    with pytest.raises(
        HomeAssistantError,
        match="1 of 2 HACS repository refreshes failed",
    ):
        await runtime.async_refresh(source="manual")

    successful_repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )
    failed_repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )

    assert runtime.state == "idle"
    assert runtime.last_result == "failed"
    assert runtime.last_repositories == 2
    assert runtime.last_successful == 1
    assert runtime.last_failed == 1
    assert runtime.last_pending == 0
    assert runtime.last_error == "1 repository refresh task(s) failed"

    hacs.queue.add.assert_called()
    assert hacs.queue.add.call_count == 2
    hacs.async_process_queue.assert_awaited_once()
    hacs.data.async_write.assert_awaited_once()
