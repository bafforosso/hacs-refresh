import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import (
    DOMAIN,
    EVENT_TYPE_FAILED,
    EVENT_TYPE_PARTIAL,
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
) -> HacsRefreshResult:
    """Create a refresh result for testing."""
    return HacsRefreshResult(
        repositories=repositories,
        successful=successful,
        failed=failed,
        pending=pending,
        failures=failures,
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


async def test_runtime_ignores_invalid_last_completed_timestamp(
    hass: HomeAssistant,
) -> None:
    """Test that an invalid persisted timestamp does not break state restoration."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    await runtime._store.async_save(
        {
            "completed": "not-a-datetime",
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

    assert runtime.last_completed is None
    assert runtime.last_result == "success"
    assert runtime.last_source == "scheduled"
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 5
    assert runtime.last_successful == 5
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0


def test_runtime_listener_can_be_added_and_removed(
    hass: HomeAssistant,
) -> None:
    """Test that runtime listeners are notified and can be removed."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    listener = MagicMock()

    remove_listener = runtime.add_listener(listener)

    runtime.notify_listeners()
    listener.assert_called_once_with()

    remove_listener()

    runtime.notify_listeners()
    listener.assert_called_once_with()


async def test_refresh_fails_when_hacs_is_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test that refresh raises an error when HACS is unavailable."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            side_effect=HacsUnavailableError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
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

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            side_effect=HacsDisabledError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
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

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=_refresh_result(
                repositories=1,
                successful=1,
            ),
        ) as mock_refresh,
        patch(
            "custom_components.hacs_refresh.runtime.perf_counter",
            side_effect=[10.0, 12.5],
        ),
    ):
        await runtime.async_refresh(source="manual")

    mock_refresh.assert_awaited_once_with()

    assert runtime.state == "idle"
    assert runtime.last_completed is not None
    assert runtime.last_result == "success"
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 1
    assert runtime.last_successful == 1
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_duration == 2.5
    assert runtime.last_message is None

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

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=_refresh_result(),
        ),
        patch(
            "custom_components.hacs_refresh.runtime.perf_counter",
            side_effect=[10.0, 12.5],
        ),
    ):
        await runtime.async_refresh(source="manual")

    listener.assert_called_once()
    assert listener.call_args.args[1]["duration"] == 2.5


@pytest.mark.parametrize(
    ("refresh_result", "event_type", "message"),
    [
        (
            _refresh_result(
                repositories=1,
                successful=1,
                pending=1,
            ),
            EVENT_TYPE_PARTIAL,
            "1 repository refresh task(s) remain pending",
        ),
        (
            _refresh_result(
                repositories=2,
                successful=1,
                failed=1,
                failures=("example/failed-repository: Something went wrong",),
            ),
            EVENT_TYPE_FAILED,
            "1 repository refresh task(s) failed",
        ),
    ],
)
async def test_refresh_result_message_is_propagated_to_event(
    hass: HomeAssistant,
    refresh_result: HacsRefreshResult,
    event_type: str,
    message: str,
) -> None:
    """Test that partial and failed refresh messages are included in the event."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    listener = MagicMock()
    runtime.add_event_listener(listener)

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=refresh_result,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await runtime.async_refresh(source="manual")

    listener.assert_called_once()
    assert listener.call_args.args[0] == event_type
    assert listener.call_args.args[1]["message"] == message


def test_runtime_event_listener_can_be_added_and_removed(
    hass: HomeAssistant,
) -> None:
    """Test event listener registration, notification, and removal."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    listener = MagicMock()

    remove_listener = runtime.add_event_listener(listener)

    runtime._notify_refresh_completed()
    listener.assert_not_called()

    runtime.last_result = EVENT_TYPE_SUCCESS
    runtime.last_source = "manual"
    runtime.last_repositories = 1
    runtime.last_successful = 1
    runtime.last_failed = 0
    runtime.last_pending = 0
    runtime.last_duration = 2.5

    runtime._notify_refresh_completed()

    listener.assert_called_once_with(
        EVENT_TYPE_SUCCESS,
        {
            "source": "manual",
            "repositories": 1,
            "successful": 1,
            "failed": 0,
            "pending": 0,
            "duration": 2.5,
        },
    )

    remove_listener()

    runtime._notify_refresh_completed()
    listener.assert_called_once()


async def test_refresh_fails_on_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """Test that unexpected refresh errors are recorded correctly."""
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
    new_completed = completed + timedelta(seconds=5)

    runtime.last_completed = completed
    runtime.last_result = EVENT_TYPE_SUCCESS
    runtime.last_source = "scheduled"
    runtime.last_repositories = 5
    runtime.last_successful = 5
    runtime.last_failed = 0
    runtime.last_pending = 0
    runtime.last_duration = 2.5

    unexpected_error = RuntimeError("Something went wrong")

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            side_effect=unexpected_error,
        ),
        patch(
            "custom_components.hacs_refresh.runtime.perf_counter",
            side_effect=[10.0, 12.5],
        ),
        patch(
            "custom_components.hacs_refresh.runtime.dt_util.now",
            return_value=new_completed,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "unexpected_refresh_error"
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is unexpected_error

    assert runtime.state == "idle"
    assert runtime.last_result == EVENT_TYPE_FAILED
    assert runtime.last_source == "manual"
    assert runtime.last_message == "Something went wrong"
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_completed is not None
    assert runtime.last_completed == new_completed

    stored = await runtime._store.async_load()
    assert stored is not None
    assert stored["completed"] == runtime.last_completed.isoformat()
    assert stored["result"] == EVENT_TYPE_FAILED
    assert stored["source"] == "manual"
    assert stored["duration"] == 2.5
    assert stored["repositories"] == 0
    assert stored["successful"] == 0
    assert stored["failed"] == 0
    assert stored["pending"] == 0


async def test_refresh_preserves_last_completed_state_while_running(
    hass: HomeAssistant,
) -> None:
    """Test that an in-progress refresh does not overwrite the last result."""
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
    new_completed = completed + timedelta(seconds=5)

    runtime.last_completed = completed
    runtime.last_result = EVENT_TYPE_SUCCESS
    runtime.last_source = "scheduled"
    runtime.last_repositories = 5
    runtime.last_successful = 5
    runtime.last_failed = 0
    runtime.last_pending = 0
    runtime.last_duration = 2.5

    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()

    async def async_refresh() -> HacsRefreshResult:
        refresh_started.set()
        await release_refresh.wait()
        return _refresh_result()

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new=async_refresh,
        ),
        patch(
            "custom_components.hacs_refresh.runtime.dt_util.now",
            return_value=new_completed,
        ),
        patch(
            "custom_components.hacs_refresh.runtime.perf_counter",
            side_effect=[10.0, 12.5],
        ),
    ):
        refresh_task = asyncio.create_task(runtime.async_refresh(source="manual"))
        await refresh_started.wait()

        assert runtime.state == "refreshing"
        assert runtime.last_completed == completed
        assert runtime.last_result == EVENT_TYPE_SUCCESS
        assert runtime.last_source == "scheduled"
        assert runtime.last_repositories == 5
        assert runtime.last_successful == 5
        assert runtime.last_failed == 0
        assert runtime.last_pending == 0
        assert runtime.last_duration == 2.5

        release_refresh.set()
        await refresh_task

        assert runtime.state == "idle"
        assert runtime.last_completed is not None
        assert runtime.last_completed == new_completed
        assert runtime.last_result == EVENT_TYPE_SUCCESS
        assert runtime.last_source == "manual"
        assert runtime.last_repositories == 1
        assert runtime.last_successful == 1
        assert runtime.last_failed == 0
        assert runtime.last_pending == 0
        assert runtime.last_duration == 2.5


async def test_scheduled_refresh_suppresses_unexpected_error(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Test that unexpected scheduled refresh errors are recorded and suppressed."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    listener = MagicMock()

    new_completed = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    runtime.add_event_listener(listener)

    unexpected_error = RuntimeError("Something went wrong")
    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            side_effect=unexpected_error,
        ),
        patch(
            "custom_components.hacs_refresh.runtime.dt_util.now",
            return_value=new_completed,
        ),
        patch(
            "custom_components.hacs_refresh.runtime.perf_counter",
            side_effect=[10.0, 12.5],
        ),
    ):
        await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    assert runtime.last_result == EVENT_TYPE_FAILED
    assert runtime.last_source == "scheduled"
    assert runtime.last_message == "Something went wrong"
    assert runtime.last_completed is not None
    assert runtime.last_completed == new_completed
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0

    listener.assert_called_once()
    assert listener.call_args.args[0] == EVENT_TYPE_FAILED
    assert listener.call_args.args[1]["source"] == "scheduled"
    assert listener.call_args.args[1]["message"] == "Something went wrong"
    assert listener.call_args.args[1]["duration"] == runtime.last_duration

    assert "Scheduled HACS refresh failed" in caplog.text


async def test_manual_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
) -> None:
    """Test that a manual refresh is skipped when the HACS queue is running."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            side_effect=HacsQueueRunningError,
        ),
        pytest.raises(HacsRefreshSkipped) as exc_info,
    ):
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


async def test_scheduled_refresh_is_skipped_when_refresh_is_in_progress(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Test that scheduled refreshes are skipped while another refresh is running."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    async with runtime._refresh_lock:
        await runtime.async_refresh(source="scheduled")

    assert (
        "Scheduled HACS refresh skipped because another refresh is already in progress"
        in caplog.text
    )


async def test_scheduled_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Test that a scheduled refresh is skipped when the HACS queue is running."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        side_effect=HacsQueueRunningError,
    ) as mock_refresh:
        await runtime.async_refresh(source="scheduled")

    mock_refresh.assert_awaited_once_with()

    assert runtime.state == "idle"
    assert (
        "Scheduled HACS refresh skipped because the HACS queue is already running"
        in caplog.text
    )


async def test_scheduled_refresh_suppresses_refresh_error(
    hass: HomeAssistant,
    caplog,
) -> None:
    """Test that scheduled refresh errors are logged instead of raised."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(
            repositories=1,
            successful=1,
            pending=1,
        ),
    ):
        await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    assert runtime.last_result == "partial"
    assert runtime.last_source == "scheduled"
    assert runtime.last_pending == 1
    assert "Scheduled HACS refresh failed" in caplog.text


async def test_scheduled_refresh_is_skipped_within_minimum_interval(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that scheduled refreshes respect the minimum interval."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(),
    ) as mock_refresh:
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

    mock_refresh.assert_not_awaited()


async def test_scheduled_refresh_is_allowed_at_minimum_interval(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the minimum interval is inclusive."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(),
    ) as mock_refresh:
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

    mock_refresh.assert_awaited_once_with()


async def test_manual_refresh_bypasses_minimum_interval(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that manual refreshes bypass the minimum interval."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(),
    ) as mock_refresh:
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

    mock_refresh.assert_awaited_once_with()


async def test_scheduled_refresh_respects_last_completed(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that scheduled refreshes respect the last completed refresh."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(
            repositories=0,
            successful=0,
        ),
    ) as mock_refresh:
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
    mock_refresh.assert_not_awaited()


async def test_scheduled_refresh_is_allowed_without_last_completed(
    hass: HomeAssistant,
) -> None:
    """Test that scheduled refreshes are allowed without a last completed refresh."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(),
    ) as mock_refresh:
        await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    mock_refresh.assert_awaited_once_with()


@pytest.mark.parametrize(
    "missing_field",
    [
        "last_completed",
        "last_result",
        "last_source",
        "last_duration",
    ],
)
async def test_last_refresh_is_not_saved_when_state_is_incomplete(
    hass: HomeAssistant,
    missing_field: str,
) -> None:
    """Test that incomplete refresh state is not persisted."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    with patch.object(
        runtime._store,
        "async_save",
        new_callable=AsyncMock,
    ) as mock_save:
        runtime.last_completed = datetime(
            2026,
            1,
            1,
            2,
            30,
            tzinfo=UTC,
        )
        runtime.last_result = EVENT_TYPE_SUCCESS
        runtime.last_source = "manual"
        runtime.last_duration = 2.5

        setattr(runtime, missing_field, None)

        await runtime._async_save_last_refresh()

    mock_save.assert_not_awaited()


async def test_refresh_succeeds_with_no_repositories(
    hass: HomeAssistant,
) -> None:
    """Test that refreshing with no repositories is a successful no-op."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(
            repositories=0,
            successful=0,
        ),
    ) as mock_refresh:
        await runtime.async_refresh(source="manual")

    assert runtime.state == "idle"
    assert runtime.last_result == "success"
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_message is None

    mock_refresh.assert_awaited_once_with()


async def test_refresh_reports_pending_repositories(
    hass: HomeAssistant,
) -> None:
    """Test that pending repository refreshes are reported correctly."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=_refresh_result(
                repositories=1,
                successful=1,
                pending=1,
            ),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
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
    assert runtime.last_message == "1 repository refresh task(s) remain pending"


async def test_refresh_reports_repository_failure(
    hass: HomeAssistant,
) -> None:
    """Test that repository refresh failures are reported correctly."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=_refresh_result(
                repositories=2,
                successful=1,
                failed=1,
                failures=("example/failed-repository: Something went wrong",),
            ),
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
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
    assert runtime.last_message == "1 repository refresh task(s) failed"
