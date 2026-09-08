from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import (
    DOMAIN,
    EVENT_TYPE_SUCCESS,
    MIN_REFRESH_INTERVAL,
)
from custom_components.hacs_refresh.hacs import (
    HacsDisabledError,
    HacsQueueRunningError,
    HacsRefreshResult,
    HacsUnavailableError,
)
from custom_components.hacs_refresh.runtime import (
    HacsRefreshRuntimeData,
    HacsRefreshSkipped,
)


def _refresh_result(
    *,
    repositories: int = 1,
    successful: int = 1,
    failed: int = 0,
    pending: int = 0,
    failures: tuple[str, ...] = (),
    duration: float = 2.5,
) -> HacsRefreshResult:
    """Create a refresh result for testing."""
    return HacsRefreshResult(
        repositories=repositories,
        successful=successful,
        failed=failed,
        pending=pending,
        failures=failures,
        duration=duration,
    )


async def test_runtime_restores_last_completed_state(
    hass: HomeAssistant,
) -> None:
    """Test that runtime restores the last refresh from persistent storage."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    completed = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    await runtime._store.async_save(
        {
            "completed": completed.isoformat(),
            "result": "success",
            "source": "scheduled",
            "duration": 2.5,
            "repositories": 5,
            "successful": 5,
            "failed": 0,
            "pending": 0,
        }
    )

    await runtime.async_initialize()

    assert runtime.last_completed == completed
    assert runtime.last_result == "success"
    assert runtime.last_source == "scheduled"
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 5
    assert runtime.last_successful == 5
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0


async def test_refresh_fails_when_hacs_is_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test that refresh raises an error when HACS is unavailable."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        side_effect=HacsUnavailableError,
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_unavailable"
    assert exc_info.value.translation_placeholders is None
    assert runtime.state == "idle"


async def test_refresh_fails_when_hacs_is_disabled(
    hass: HomeAssistant,
) -> None:
    """Test that refresh raises an error when HACS is disabled."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        side_effect=HacsDisabledError,
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_disabled"
    assert exc_info.value.translation_placeholders is None
    assert runtime.state == "idle"


async def test_refresh_succeeds(
    hass: HomeAssistant,
) -> None:
    """Test a successful HACS refresh."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(
            repositories=1,
            successful=1,
        ),
    )

    await runtime.async_refresh(source="manual")

    runtime.hacs.async_refresh.assert_awaited_once()

    assert runtime.state == "idle"
    assert runtime.last_completed is not None
    assert runtime.last_result == "success"
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 1
    assert runtime.last_successful == 1
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_duration == 2.5
    assert runtime.last_error is None

    stored = await runtime._store.async_load()

    assert stored is not None
    assert stored["completed"] == runtime.last_completed.isoformat()
    assert stored["result"] == "success"
    assert stored["source"] == "manual"
    assert stored["duration"] == 2.5
    assert stored["repositories"] == 1
    assert stored["successful"] == 1
    assert stored["failed"] == 0
    assert stored["pending"] == 0


async def test_refresh_duration_is_propagated_to_event(
    hass: HomeAssistant,
) -> None:
    """Test that refresh duration is included in the completion event."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    listener = MagicMock()
    runtime.add_event_listener(listener)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(duration=2.5),
    )

    await runtime.async_refresh(source="manual")

    listener.assert_called_once()
    assert listener.call_args.args[1]["duration"] == 2.5


async def test_refresh_fails_on_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """Test that unexpected refresh errors are translated."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    unexpected_error = RuntimeError("Something went wrong")

    runtime.hacs.async_refresh = AsyncMock(
        side_effect=unexpected_error,
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "unexpected_refresh_error"
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is unexpected_error
    assert runtime.state == "idle"
    assert runtime.last_result == "failed"


async def test_manual_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
) -> None:
    """Test that a manual refresh is skipped when the HACS queue is running."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        side_effect=HacsQueueRunningError,
    )

    with pytest.raises(HacsRefreshSkipped) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_queue_running"
    assert exc_info.value.translation_placeholders is None
    assert runtime.state == "idle"


async def test_manual_refresh_is_skipped_when_refresh_is_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test that a manual refresh is skipped when another refresh is in progress."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    async with runtime._refresh_lock:
        with pytest.raises(HacsRefreshSkipped) as exc_info:
            await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_in_progress"
    assert exc_info.value.translation_placeholders is None


async def test_scheduled_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Test that a scheduled refresh is skipped when the HACS queue is running."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        side_effect=HacsQueueRunningError,
    )

    await runtime.async_refresh(source="scheduled")

    runtime.hacs.async_refresh.assert_awaited_once()

    assert runtime.state == "idle"
    assert (
        "Scheduled HACS refresh skipped because the HACS queue is already running"
        in caplog.text
    )


async def test_scheduled_refresh_is_skipped_within_minimum_interval(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that scheduled refreshes respect the minimum interval."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(),
    )

    start = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    runtime.last_completed = start

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: start + MIN_REFRESH_INTERVAL - timedelta(seconds=1),
    )

    await runtime.async_refresh(source="scheduled")

    runtime.hacs.async_refresh.assert_not_awaited()


async def test_scheduled_refresh_is_allowed_at_minimum_interval(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the minimum interval is inclusive."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(),
    )

    start = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    runtime.last_completed = start

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: start + MIN_REFRESH_INTERVAL,
    )

    await runtime.async_refresh(source="scheduled")

    runtime.hacs.async_refresh.assert_awaited_once()


async def test_manual_refresh_bypasses_minimum_interval(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that manual refreshes bypass the minimum interval."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(),
    )

    start = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    runtime.last_completed = start

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: start + timedelta(minutes=1),
    )

    await runtime.async_refresh(source="manual")

    runtime.hacs.async_refresh.assert_awaited_once()


async def test_scheduled_refresh_respects_last_completed(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that scheduled refreshes respect the last completed refresh."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(
            repositories=0,
            successful=0,
        ),
    )

    last_completed = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    runtime.last_completed = last_completed

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: last_completed + MIN_REFRESH_INTERVAL - timedelta(seconds=1),
    )

    await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    runtime.hacs.async_refresh.assert_not_awaited()


async def test_scheduled_refresh_is_allowed_without_last_completed(
    hass: HomeAssistant,
) -> None:
    """Test that scheduled refreshes are allowed without a last completed refresh."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(),
    )

    await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    runtime.hacs.async_refresh.assert_awaited_once()


async def test_refresh_succeeds_with_no_repositories(
    hass: HomeAssistant,
) -> None:
    """Test that refreshing with no repositories is a successful no-op."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(
            repositories=0,
            successful=0,
        ),
    )

    await runtime.async_refresh(source="manual")

    assert runtime.state == "idle"
    assert runtime.last_result == "success"
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_error is None

    runtime.hacs.async_refresh.assert_awaited_once()


async def test_refresh_reports_pending_repositories(
    hass: HomeAssistant,
) -> None:
    """Test that pending repository refreshes are reported correctly."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(
            repositories=1,
            successful=1,
            pending=1,
        ),
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_tasks_pending"
    assert exc_info.value.translation_placeholders == {
        "pending": "1",
    }

    assert runtime.state == "idle"
    assert runtime.last_result == "partial"
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 1
    assert runtime.last_successful == 1
    assert runtime.last_failed == 0
    assert runtime.last_pending == 1
    assert runtime.last_error == "1 repository refresh task(s) remain pending"


async def test_refresh_reports_repository_failure(
    hass: HomeAssistant,
) -> None:
    """Test that repository refresh failures are reported correctly."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime.hacs.async_refresh = AsyncMock(
        return_value=_refresh_result(
            repositories=2,
            successful=1,
            failed=1,
            failures=("example/failed-repository: Something went wrong",),
        ),
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_tasks_failed"
    assert exc_info.value.translation_placeholders == {
        "failed": "1",
        "repositories": "2",
    }

    assert runtime.state == "idle"
    assert runtime.last_result == "failed"
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 2
    assert runtime.last_successful == 1
    assert runtime.last_failed == 1
    assert runtime.last_pending == 0
    assert runtime.last_error == "1 repository refresh task(s) failed"
