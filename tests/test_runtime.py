import asyncio
from collections.abc import Callable
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
    REFRESH_SOURCE_MANUAL,
    REFRESH_SOURCE_SCHEDULED,
    STATE_IDLE,
    STATE_REFRESHING,
)
from custom_components.hacs_refresh.hacs import (
    HacsDisabledError,
    HacsQueueBusyError,
    HacsRefreshProgress,
    HacsRefreshResult,
    HacsUnavailableError,
)
from custom_components.hacs_refresh.runtime import (
    HacsRefreshOutcome,
    HacsRefreshRuntimeData,
    HacsRefreshSkipped,
)
from custom_components.hacs_refresh.storage import LastRefreshData


def _refresh_result(
    *,
    repositories: int = 1,
    successful: int = 1,
    failed: int = 0,
    pending: int = 0,
    failed_repositories: tuple[str, ...] = (),
    pending_repositories: tuple[str, ...] = (),
    failures: tuple[str, ...] = (),
) -> HacsRefreshResult:
    """Create a refresh result for testing."""
    return HacsRefreshResult(
        repositories=repositories,
        successful=successful,
        failed=failed,
        pending=pending,
        failed_repositories=failed_repositories,
        pending_repositories=pending_repositories,
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
            "result": EVENT_TYPE_FAILED,
            "source": REFRESH_SOURCE_SCHEDULED,
            "message": "1 repository refresh task(s) failed",
            "duration": 2.5,
            "repositories": 5,
            "successful": 5,
            "failed": 0,
            "pending": 0,
        }
    )

    await runtime.async_initialize()

    assert runtime.last_completed == completed
    assert runtime.last_result == EVENT_TYPE_FAILED
    assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
    assert runtime.last_message == "1 repository refresh task(s) failed"
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 5
    assert runtime.last_successful == 5
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0


async def test_runtime_restores_legacy_refresh_state_without_message(
    hass: HomeAssistant,
) -> None:
    """Test that runtime restores legacy refresh state without a message."""
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

    with patch.object(
        runtime._store,
        "async_load",
        new_callable=AsyncMock,
        return_value={
            "completed": completed.isoformat(),
            "result": EVENT_TYPE_SUCCESS,
            "source": REFRESH_SOURCE_SCHEDULED,
            "duration": 2.5,
            "repositories": 5,
            "successful": 5,
            "failed": 0,
            "pending": 0,
        },
    ):
        await runtime.async_initialize()

    assert runtime.last_completed == completed
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
    assert runtime.last_message is None
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
            "result": EVENT_TYPE_SUCCESS,
            "source": REFRESH_SOURCE_SCHEDULED,
            "message": None,
            "duration": 2.5,
            "repositories": 5,
            "successful": 5,
            "failed": 0,
            "pending": 0,
        }
    )

    await runtime.async_initialize()

    assert runtime.last_completed is None
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
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
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_unavailable"
    assert exc_info.value.translation_placeholders is None
    assert runtime.state == STATE_IDLE


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
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_disabled"
    assert exc_info.value.translation_placeholders is None
    assert runtime.state == STATE_IDLE


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
        outcome = await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    mock_refresh.assert_awaited_once()
    assert outcome is not None
    assert outcome.repositories == 1
    assert outcome.successful == 1
    assert outcome.failed == 0
    assert outcome.pending == 0
    assert outcome.failed_repositories == ()
    assert outcome.pending_repositories == ()
    assert outcome.duration == 2.5

    assert runtime.state == STATE_IDLE
    assert runtime.last_completed is not None
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    assert runtime.last_source == REFRESH_SOURCE_MANUAL
    assert runtime.last_repositories == 1
    assert runtime.last_successful == 1
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_duration == 2.5
    assert runtime.last_message is None

    stored = await runtime._store.async_load()

    assert stored is not None
    assert stored["completed"] == runtime.last_completed.isoformat()
    assert stored["result"] == EVENT_TYPE_SUCCESS
    assert stored["source"] == REFRESH_SOURCE_MANUAL
    assert stored["message"] is None
    assert stored["duration"] == 2.5
    assert stored["repositories"] == 1
    assert stored["successful"] == 1
    assert stored["failed"] == 0
    assert stored["pending"] == 0


async def test_refresh_tracks_progress(
    hass: HomeAssistant,
) -> None:
    """Test that runtime tracks HACS Refresh progress."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    runtime_states: list[str] = []

    def runtime_listener() -> None:
        runtime_states.append(runtime.state)

    runtime.add_listener(runtime_listener)

    async def async_refresh(
        *,
        progress_callback: Callable[[HacsRefreshProgress], None],
    ) -> HacsRefreshResult:
        progress_callback(
            HacsRefreshProgress(
                total=2,
                processed=0,
                successful=0,
                failed=0,
            )
        )
        progress_callback(
            HacsRefreshProgress(
                total=2,
                processed=1,
                successful=1,
                failed=0,
            )
        )
        progress_callback(
            HacsRefreshProgress(
                total=2,
                processed=2,
                successful=2,
                failed=0,
            )
        )
        return _refresh_result(
            repositories=2,
            successful=2,
        )

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new=async_refresh,
    ):
        outcome = await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert outcome is not None
    assert outcome.repositories == 2
    assert outcome.successful == 2
    assert runtime.refresh_progress == HacsRefreshProgress(
        total=2,
        processed=2,
        successful=2,
        failed=0,
    )

    # Progress updates must not notify the existing runtime listeners.
    assert runtime_states == [STATE_REFRESHING, STATE_IDLE]


async def test_refresh_notifies_runtime_listeners_after_lock_is_released(
    hass: HomeAssistant,
) -> None:
    """Test that completion notification occurs after the refresh lock is released."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    refresh_states: list[bool] = []

    def runtime_listener() -> None:
        refresh_states.append(runtime.refresh_in_progress)

    runtime.add_listener(runtime_listener)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        return_value=_refresh_result(),
    ):
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert refresh_states == [True, False]


async def test_refresh_handles_cancellation(
    hass: HomeAssistant,
) -> None:
    """Test that cancelling a refresh resets runtime state without completing it."""
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
    runtime.last_completed = completed
    runtime.last_result = EVENT_TYPE_SUCCESS
    runtime.last_source = REFRESH_SOURCE_SCHEDULED
    runtime.last_message = None
    runtime.last_duration = 2.5
    runtime.last_repositories = 5
    runtime.last_successful = 5
    runtime.last_failed = 0
    runtime.last_pending = 0

    refresh_started = asyncio.Event()
    refresh_states: list[bool] = []
    event_listener = MagicMock()

    def runtime_listener() -> None:
        refresh_states.append(runtime.refresh_in_progress)

    async def async_refresh(
        *,
        progress_callback: Callable[[HacsRefreshProgress], None],
    ) -> HacsRefreshResult:
        refresh_started.set()
        await asyncio.Event().wait()
        return _refresh_result()

    runtime.add_listener(runtime_listener)
    runtime.add_event_listener(event_listener)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new=async_refresh,
    ):
        refresh_task = asyncio.create_task(
            runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)
        )
        await refresh_started.wait()

        assert runtime.state == STATE_REFRESHING
        assert runtime.refresh_in_progress is True

        refresh_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await refresh_task

    assert runtime.state == STATE_IDLE
    assert runtime.refresh_in_progress is False
    assert refresh_states == [True, False]
    event_listener.assert_not_called()
    assert runtime.last_completed == completed
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
    assert runtime.last_message is None
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 5
    assert runtime.last_successful == 5
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0


async def test_refresh_handles_cancellation_during_persistence(
    hass: HomeAssistant,
) -> None:
    """Test that cancelling during persistence still completes the save."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    save_started = asyncio.Event()
    release_save = asyncio.Event()

    original_save = runtime._store.async_save

    async def async_save(data: LastRefreshData) -> None:
        save_started.set()
        await release_save.wait()
        await original_save(data)

    event_listener = MagicMock()
    runtime.add_event_listener(event_listener)

    with (
        patch.object(runtime._store, "async_save", new=async_save),
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=_refresh_result(
                repositories=1,
                successful=1,
            ),
        ),
    ):
        refresh_task = asyncio.create_task(
            runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)
        )

        await save_started.wait()

        assert runtime.state == STATE_IDLE
        assert runtime.last_result == EVENT_TYPE_SUCCESS
        assert runtime.refresh_in_progress is True

        refresh_task.cancel()
        await asyncio.sleep(0)

        assert refresh_task.done() is False

        release_save.set()

        with pytest.raises(asyncio.CancelledError):
            await refresh_task

    assert runtime.state == STATE_IDLE
    assert runtime.refresh_in_progress is False

    event_listener.assert_not_called()

    stored = await runtime._store.async_load()
    assert stored is not None
    assert stored["result"] == EVENT_TYPE_SUCCESS
    assert stored["source"] == REFRESH_SOURCE_MANUAL
    assert stored["repositories"] == 1
    assert stored["successful"] == 1
    assert stored["failed"] == 0
    assert stored["pending"] == 0


async def test_refresh_outcome_is_propagated_to_event(
    hass: HomeAssistant,
) -> None:
    """Test that the refresh outcome is included in the completion event."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    listener = MagicMock()
    runtime.add_event_listener(listener)
    refresh_result = _refresh_result(
        repositories=4,
        successful=2,
        failed=1,
        pending=1,
        failed_repositories=("example/failed-repository",),
        pending_repositories=("example/pending-repository",),
    )
    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            return_value=refresh_result,
        ),
        patch(
            "custom_components.hacs_refresh.runtime.perf_counter",
            side_effect=[10.0, 12.5],
        ),
        pytest.raises(HomeAssistantError),
    ):
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    listener.assert_called_once()
    event_data = listener.call_args.args[1]
    assert event_data == {
        "source": REFRESH_SOURCE_MANUAL,
        "repositories": 4,
        "successful": 2,
        "failed": 1,
        "pending": 1,
        "failed_repositories": [
            "example/failed-repository",
        ],
        "pending_repositories": [
            "example/pending-repository",
        ],
        "duration": 2.5,
        "message": "1 repository refresh task(s) remain pending",
    }


@pytest.mark.parametrize(
    ("refresh_result", "event_type", "message"),
    [
        (
            _refresh_result(
                repositories=2,
                successful=1,
                pending=1,
                pending_repositories=("example/pending-repository",),
            ),
            EVENT_TYPE_PARTIAL,
            "1 repository refresh task(s) remain pending",
        ),
        (
            _refresh_result(
                repositories=2,
                successful=1,
                failed=1,
                failed_repositories=("example/failed-repository",),
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
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

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

    runtime._notify_refresh_completed(
        HacsRefreshOutcome(
            repositories=1,
            successful=1,
            failed=0,
            pending=0,
            failed_repositories=(),
            pending_repositories=(),
            duration=2.5,
        )
    )
    listener.assert_not_called()

    runtime.last_result = EVENT_TYPE_SUCCESS
    runtime.last_source = REFRESH_SOURCE_MANUAL
    outcome = HacsRefreshOutcome(
        repositories=1,
        successful=1,
        failed=0,
        pending=0,
        failed_repositories=(),
        pending_repositories=(),
        duration=2.5,
    )

    runtime._notify_refresh_completed(outcome)

    listener.assert_called_once_with(
        EVENT_TYPE_SUCCESS,
        {
            "source": REFRESH_SOURCE_MANUAL,
            "repositories": 1,
            "successful": 1,
            "failed": 0,
            "pending": 0,
            "failed_repositories": [],
            "pending_repositories": [],
            "duration": 2.5,
        },
    )

    remove_listener()

    runtime._notify_refresh_completed(outcome)
    listener.assert_called_once()


async def test_refresh_fails_on_unexpected_error(
    hass: HomeAssistant,
) -> None:
    """Test that unexpected refresh errors are recorded without exposing details."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    listener = MagicMock()
    runtime.add_event_listener(listener)

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
    runtime.last_source = REFRESH_SOURCE_SCHEDULED
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
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    expected_error = HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="unexpected_refresh_error",
    )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "unexpected_refresh_error"
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is unexpected_error

    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_FAILED
    assert runtime.last_source == REFRESH_SOURCE_MANUAL
    assert runtime.last_message == str(expected_error)
    assert runtime.last_message != str(unexpected_error)
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_completed is not None
    assert runtime.last_completed == new_completed

    listener.assert_called_once()
    assert listener.call_args.args[0] == EVENT_TYPE_FAILED
    assert listener.call_args.args[1]["source"] == REFRESH_SOURCE_MANUAL
    assert listener.call_args.args[1]["message"] == str(expected_error)
    assert listener.call_args.args[1]["message"] != str(unexpected_error)
    assert listener.call_args.args[1]["duration"] == runtime.last_duration

    stored = await runtime._store.async_load()
    assert stored is not None
    assert stored["completed"] == runtime.last_completed.isoformat()
    assert stored["result"] == EVENT_TYPE_FAILED
    assert stored["source"] == REFRESH_SOURCE_MANUAL
    assert stored["message"] == str(expected_error)
    assert stored["message"] != str(unexpected_error)
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
    runtime.last_source = REFRESH_SOURCE_SCHEDULED
    runtime.last_repositories = 5
    runtime.last_successful = 5
    runtime.last_failed = 0
    runtime.last_pending = 0
    runtime.last_duration = 2.5

    refresh_started = asyncio.Event()
    release_refresh = asyncio.Event()

    async def async_refresh(
        *,
        progress_callback: Callable[[HacsRefreshProgress], None],
    ) -> HacsRefreshResult:
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
        refresh_task = asyncio.create_task(
            runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)
        )
        await refresh_started.wait()

        assert runtime.state == STATE_REFRESHING
        assert runtime.last_completed == completed
        assert runtime.last_result == EVENT_TYPE_SUCCESS
        assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
        assert runtime.last_repositories == 5
        assert runtime.last_successful == 5
        assert runtime.last_failed == 0
        assert runtime.last_pending == 0
        assert runtime.last_duration == 2.5

        release_refresh.set()
        await refresh_task

        assert runtime.state == STATE_IDLE
        assert runtime.last_completed is not None
        assert runtime.last_completed == new_completed
        assert runtime.last_result == EVENT_TYPE_SUCCESS
        assert runtime.last_source == REFRESH_SOURCE_MANUAL
        assert runtime.last_repositories == 1
        assert runtime.last_successful == 1
        assert runtime.last_failed == 0
        assert runtime.last_pending == 0
        assert runtime.last_duration == 2.5


async def test_scheduled_refresh_suppresses_unexpected_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unexpected scheduled refresh errors are recorded and suppressed."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    listener = MagicMock()
    runtime.add_event_listener(listener)

    new_completed = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

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
        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

    expected_error = HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="unexpected_refresh_error",
    )
    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_FAILED
    assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
    assert runtime.last_message == str(expected_error)
    assert runtime.last_message != str(unexpected_error)
    assert runtime.last_completed is not None
    assert runtime.last_completed == new_completed
    assert runtime.last_duration == 2.5
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0

    listener.assert_called_once()
    assert listener.call_args.args[0] == EVENT_TYPE_FAILED
    assert listener.call_args.args[1]["source"] == REFRESH_SOURCE_SCHEDULED
    assert listener.call_args.args[1]["message"] == str(expected_error)
    assert listener.call_args.args[1]["message"] != str(unexpected_error)
    assert listener.call_args.args[1]["duration"] == runtime.last_duration

    assert "Scheduled HACS refresh failed" in caplog.text
    assert str(unexpected_error) in caplog.text


async def test_manual_refresh_is_skipped_when_queue_is_busy(
    hass: HomeAssistant,
) -> None:
    """Test that a manual refresh is skipped when the HACS queue is busy."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with (
        patch.object(
            runtime.hacs,
            "async_refresh",
            new_callable=AsyncMock,
            side_effect=HacsQueueBusyError,
        ),
        pytest.raises(HacsRefreshSkipped) as exc_info,
    ):
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_queue_busy"
    assert exc_info.value.translation_placeholders is None
    assert runtime.state == STATE_IDLE


async def test_manual_refresh_is_skipped_when_refresh_is_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test that a manual refresh is skipped when another refresh is in progress."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    async with runtime._refresh_lock:
        with pytest.raises(HacsRefreshSkipped) as exc_info:
            await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_in_progress"
    assert exc_info.value.translation_placeholders is None


async def test_scheduled_refresh_is_skipped_when_refresh_is_in_progress(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that scheduled refreshes are skipped while another refresh is running."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    async with runtime._refresh_lock:
        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

    assert (
        "Scheduled HACS refresh skipped because another refresh is already in progress"
        in caplog.text
    )


async def test_scheduled_refresh_is_skipped_when_queue_is_busy(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a scheduled refresh is skipped when the HACS queue is busy."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with patch.object(
        runtime.hacs,
        "async_refresh",
        new_callable=AsyncMock,
        side_effect=HacsQueueBusyError,
    ) as mock_refresh:
        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

    mock_refresh.assert_awaited_once()

    assert runtime.state == STATE_IDLE
    assert (
        "Scheduled HACS refresh skipped because the HACS queue is busy" in caplog.text
    )


async def test_scheduled_refresh_suppresses_refresh_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
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
        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_PARTIAL
    assert runtime.last_source == REFRESH_SOURCE_SCHEDULED
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

        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

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

        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

    mock_refresh.assert_awaited_once()


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

        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    mock_refresh.assert_awaited_once()


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
        await runtime.async_refresh(source=REFRESH_SOURCE_SCHEDULED)

    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    mock_refresh.assert_awaited_once()


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
        runtime.last_source = REFRESH_SOURCE_MANUAL
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
        outcome = await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert outcome is not None
    assert outcome.successful == 0

    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    assert runtime.last_source == REFRESH_SOURCE_MANUAL
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_message is None

    mock_refresh.assert_awaited_once()


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
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_tasks_pending"
    assert exc_info.value.translation_placeholders == {
        "pending": "1",
    }

    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_PARTIAL
    assert runtime.last_source == REFRESH_SOURCE_MANUAL
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
        await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_tasks_failed"
    assert exc_info.value.translation_placeholders == {
        "failed": "1",
        "repositories": "2",
    }

    assert runtime.state == STATE_IDLE
    assert runtime.last_result == EVENT_TYPE_FAILED
    assert runtime.last_source == REFRESH_SOURCE_MANUAL
    assert runtime.last_repositories == 2
    assert runtime.last_successful == 1
    assert runtime.last_failed == 1
    assert runtime.last_pending == 0
    assert runtime.last_message == "1 repository refresh task(s) failed"
