from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hacs_refresh.hacs import (
    HacsAdapter,
    HacsDisabledError,
    HacsInvalidRepositoriesError,
    HacsQueueBusyError,
    HacsRefreshProgress,
    HacsRefreshResult,
    HacsUnavailableError,
)


def assert_progress_accounting(
    progress_updates: list[HacsRefreshProgress],
) -> None:
    """Assert that progress accounting remains internally consistent."""
    for progress in progress_updates:
        assert progress.processed == progress.successful + progress.failed
        assert progress.remaining == progress.total - progress.processed


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


@pytest.mark.parametrize(
    ("queue_running", "queue_has_pending_tasks"),
    [
        (True, False),
        (False, True),
        (True, True),
    ],
)
async def test_refresh_fails_when_queue_is_busy(
    hass: HomeAssistant,
    hacs: MagicMock,
    queue_running: bool,
    queue_has_pending_tasks: bool,
) -> None:
    """Test that refresh fails when the HACS queue is busy."""
    hacs.queue.running = queue_running
    hacs.queue.has_pending_tasks = queue_has_pending_tasks
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    with pytest.raises(HacsQueueBusyError):
        await adapter.async_refresh()

    hacs.async_process_queue.assert_not_awaited()


def test_validate_repositories_returns_normalized_names(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that repository validation normalizes and deduplicates names."""
    first_repository = MagicMock()
    first_repository.data.full_name = "example/first-repository"
    first_repository.data.installed = True

    second_repository = MagicMock()
    second_repository.data.full_name = "example/second-repository"
    second_repository.data.installed = True

    hacs.repositories.get_by_full_name.side_effect = lambda name: {
        "example/first-repository": first_repository,
        "example/second-repository": second_repository,
    }.get(name.lower())
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    result = adapter.validate_repositories(
        (
            "EXAMPLE/FIRST-REPOSITORY",
            "example/first-repository",
            "example/second-repository",
        )
    )

    assert result == (
        "example/first-repository",
        "example/second-repository",
    )


def test_validate_repositories_reports_all_invalid_repositories(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that repository validation reports all invalid names."""
    installed_repository = MagicMock()
    installed_repository.data.full_name = "example/installed"
    installed_repository.data.installed = True

    hacs.repositories.get_by_full_name.side_effect = lambda name: (
        installed_repository if name.lower() == "example/installed" else None
    )
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    with pytest.raises(HacsInvalidRepositoriesError) as err:
        adapter.validate_repositories(
            (
                "example/installed",
                "example/unknown-one",
                "example/unknown-two",
            )
        )

    assert err.value.repositories == (
        "example/unknown-one",
        "example/unknown-two",
    )


async def test_refresh_succeeds(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test a successful HACS refresh."""
    repository = MagicMock()
    repository.data.full_name = "example/successful-repository"
    repository.update_repository = AsyncMock(return_value="update")

    hacs.repositories.list_downloaded = [repository]
    hass.data["hacs"] = hacs

    progress_updates: list[HacsRefreshProgress] = []

    adapter = HacsAdapter(hass)
    result = await adapter.async_refresh(
        progress_callback=progress_updates.append,
    )

    assert result == HacsRefreshResult(
        repositories=1,
        successful=1,
        failed=0,
        pending=0,
        failed_repositories=(),
        pending_repositories=(),
        failures=(),
    )

    assert progress_updates == [
        HacsRefreshProgress(
            total=1,
            processed=0,
            successful=0,
            failed=0,
        ),
        HacsRefreshProgress(
            total=1,
            processed=1,
            successful=1,
            failed=0,
        ),
    ]
    assert_progress_accounting(progress_updates)

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
        failed_repositories=(),
        pending_repositories=(),
        failures=(),
    )

    hacs.queue.add.assert_not_called()
    hacs.async_process_queue.assert_not_awaited()
    hacs.data.async_write.assert_not_awaited()


async def test_refresh_reports_pending_repositories(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that unprocessed repositories are reported as pending."""
    processed_repository = MagicMock()
    processed_repository.data.full_name = "example/processed-repository"
    processed_repository.update_repository = AsyncMock()

    pending_repository = MagicMock()
    pending_repository.data.full_name = "example/pending-repository"
    pending_repository.update_repository = AsyncMock()

    hacs.repositories.list_downloaded = [
        processed_repository,
        pending_repository,
    ]
    hass.data["hacs"] = hacs

    async def process_queue() -> None:
        await hacs.queue.add.call_args_list[0].args[0]

    hacs.async_process_queue = AsyncMock(side_effect=process_queue)

    progress_updates: list[HacsRefreshProgress] = []

    adapter = HacsAdapter(hass)
    result = await adapter.async_refresh(
        progress_callback=progress_updates.append,
    )

    pending_task = hacs.queue.add.call_args_list[1].args[0]

    assert result == HacsRefreshResult(
        repositories=2,
        successful=1,
        failed=0,
        pending=1,
        failed_repositories=(),
        pending_repositories=("example/pending-repository",),
        failures=(),
    )

    assert progress_updates == [
        HacsRefreshProgress(
            total=2,
            processed=0,
            successful=0,
            failed=0,
        ),
        HacsRefreshProgress(
            total=2,
            processed=1,
            successful=1,
            failed=0,
        ),
    ]
    assert_progress_accounting(progress_updates)

    assert processed_repository.update_repository.await_count == 1
    pending_repository.update_repository.assert_not_awaited()

    pending_task.close()
    hacs.data.async_write.assert_awaited_once()


async def test_refresh_reports_repository_failure(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that repository refresh failures are reported correctly."""
    successful_repository = MagicMock()
    successful_repository.data.full_name = "example/successful-repository"
    successful_repository.update_repository = AsyncMock()

    failed_repository = MagicMock()
    failed_repository.data.full_name = "example/failed-repository"
    failed_repository.update_repository = AsyncMock(
        side_effect=RuntimeError("Something went wrong")
    )

    hacs.repositories.list_downloaded = [
        successful_repository,
        failed_repository,
    ]
    hass.data["hacs"] = hacs

    progress_updates: list[HacsRefreshProgress] = []

    adapter = HacsAdapter(hass)
    result = await adapter.async_refresh(
        progress_callback=progress_updates.append,
    )

    assert result == HacsRefreshResult(
        repositories=2,
        successful=1,
        failed=1,
        pending=0,
        failed_repositories=("example/failed-repository",),
        pending_repositories=(),
        failures=("example/failed-repository: Something went wrong",),
    )

    assert len(progress_updates) == 3
    assert progress_updates[0] == HacsRefreshProgress(
        total=2,
        processed=0,
        successful=0,
        failed=0,
    )
    assert {
        (
            progress.processed,
            progress.successful,
            progress.failed,
            progress.remaining,
        )
        for progress in progress_updates[1:]
    } == {
        (1, 1, 0, 1),
        (2, 1, 1, 0),
    }
    assert_progress_accounting(progress_updates)

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


async def test_refreshes_selected_repositories_only(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that only selected repositories are refreshed."""
    first_repository = MagicMock()
    first_repository.data.full_name = "example/first-repository"
    first_repository.data.installed = True
    first_repository.update_repository = AsyncMock()

    second_repository = MagicMock()
    second_repository.data.full_name = "example/second-repository"
    second_repository.data.installed = True
    second_repository.update_repository = AsyncMock()

    third_repository = MagicMock()
    third_repository.data.full_name = "example/third-repository"
    third_repository.data.installed = True
    third_repository.update_repository = AsyncMock()

    hacs.repositories.list_downloaded = [
        first_repository,
        second_repository,
        third_repository,
    ]
    hacs.repositories.get_by_full_name.side_effect = lambda name: {
        "example/first-repository": first_repository,
        "example/second-repository": second_repository,
        "example/third-repository": third_repository,
    }.get(name.lower())
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    result = await adapter.async_refresh(
        repositories=(
            "EXAMPLE/FIRST-REPOSITORY",
            "example/first-repository",
            "example/third-repository",
        )
    )

    assert result.repositories == 2
    assert result.successful == 2
    assert result.failed == 0
    assert result.pending == 0
    assert result.failed_repositories == ()
    assert result.pending_repositories == ()

    first_repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )
    second_repository.update_repository.assert_not_awaited()
    third_repository.update_repository.assert_awaited_once_with(
        ignore_issues=True,
        force=True,
    )


def test_validate_repositories_rejects_non_installed_repository(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that a known but non-installed repository is rejected."""
    repository = MagicMock()
    repository.data.full_name = "example/not-installed"
    repository.data.installed = False

    hacs.repositories.get_by_full_name.return_value = repository
    hass.data["hacs"] = hacs

    adapter = HacsAdapter(hass)

    with pytest.raises(HacsInvalidRepositoriesError) as err:
        adapter.validate_repositories(
            ("example/not-installed",),
        )

    assert err.value.repositories == ("example/not-installed",)


async def test_refresh_reports_selected_repository_count_in_progress(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that targeted refresh progress uses the selected count."""
    first_repository = MagicMock()
    first_repository.data.full_name = "example/first-repository"
    first_repository.data.installed = True
    first_repository.update_repository = AsyncMock()

    second_repository = MagicMock()
    second_repository.data.full_name = "example/second-repository"
    second_repository.data.installed = True
    second_repository.update_repository = AsyncMock()

    hacs.repositories.get_by_full_name.side_effect = lambda name: {
        "example/first-repository": first_repository,
        "example/second-repository": second_repository,
    }.get(name.lower())
    hass.data["hacs"] = hacs

    progress_updates: list[HacsRefreshProgress] = []

    adapter = HacsAdapter(hass)

    await adapter.async_refresh(
        repositories=(
            "example/first-repository",
            "example/second-repository",
        ),
        progress_callback=progress_updates.append,
    )

    assert progress_updates[0] == HacsRefreshProgress(
        total=2,
        processed=0,
        successful=0,
        failed=0,
    )
    assert progress_updates[-1] == HacsRefreshProgress(
        total=2,
        processed=2,
        successful=2,
        failed=0,
    )
