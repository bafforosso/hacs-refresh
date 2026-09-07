from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import (
    DOMAIN,
    EVENT_ENTITY_UNIQUE_ID,
    EVENT_TYPE_SUCCESS,
    MIN_REFRESH_INTERVAL,
)
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

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_unavailable"
    assert exc_info.value.translation_placeholders is None


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
    assert runtime.last_source == "manual"
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

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_disabled"
    assert exc_info.value.translation_placeholders is None


async def test_refresh_fails_on_unexpected_error(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that unexpected refresh errors are translated."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    unexpected_error = RuntimeError("Something went wrong")
    monkeypatch.setattr(
        runtime,
        "_async_do_refresh",
        AsyncMock(side_effect=unexpected_error),
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "unexpected_refresh_error"
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is unexpected_error


async def test_manual_refresh_is_skipped_when_queue_is_running(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that a manual refresh is skipped when the HACS queue is running."""
    hacs.queue.running = True
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)

    with pytest.raises(HacsRefreshSkipped) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hacs_queue_running"
    assert exc_info.value.translation_placeholders is None

    hacs.async_process_queue.assert_not_awaited()


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


async def test_scheduled_refresh_is_skipped_within_minimum_interval(
    hass: HomeAssistant,
    hacs: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that scheduled refreshes respect the minimum interval."""
    repository = MagicMock()
    repository.update_repository = AsyncMock()
    hacs.repositories.list_downloaded = [repository]
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    start = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
        suggested_object_id="hacs_refresh_refresh_completed",
    )

    event_entity_id = entity_registry.async_get_entity_id(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
    )
    assert event_entity_id is not None

    hass.states.async_set(
        event_entity_id,
        start.isoformat(),
    )

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: start + MIN_REFRESH_INTERVAL - timedelta(seconds=1),
    )

    await runtime.async_refresh(source="scheduled")

    assert hacs.async_process_queue.await_count == 0


async def test_scheduled_refresh_is_allowed_at_minimum_interval(
    hass: HomeAssistant,
    hacs: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the minimum interval is inclusive."""
    repository = MagicMock()
    repository.update_repository = AsyncMock()
    hacs.repositories.list_downloaded = [repository]
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    start = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
        suggested_object_id="hacs_refresh_refresh_completed",
    )

    event_entity_id = entity_registry.async_get_entity_id(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
    )
    assert event_entity_id is not None

    hass.states.async_set(
        event_entity_id,
        start.isoformat(),
    )

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: start + MIN_REFRESH_INTERVAL,
    )

    await runtime.async_refresh(source="scheduled")

    assert hacs.async_process_queue.await_count == 1


async def test_manual_refresh_bypasses_minimum_interval(
    hass: HomeAssistant,
    hacs: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that manual refreshes bypass the minimum interval."""
    repository = MagicMock()
    repository.update_repository = AsyncMock()
    hacs.repositories.list_downloaded = [repository]
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    start = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
        suggested_object_id="hacs_refresh_refresh_completed",
    )

    event_entity_id = entity_registry.async_get_entity_id(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
    )
    assert event_entity_id is not None

    hass.states.async_set(
        event_entity_id,
        start.isoformat(),
    )

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: start + timedelta(minutes=1),
    )

    await runtime.async_refresh(source="manual")

    assert hacs.async_process_queue.await_count == 1


async def test_scheduled_refresh_respects_last_refresh_event(
    hass: HomeAssistant,
    hacs: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that scheduled refreshes respect the last completion event."""
    hacs.repositories.list_downloaded = []
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    last_refresh = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
        suggested_object_id="hacs_refresh_refresh_completed",
    )

    event_entity_id = entity_registry.async_get_entity_id(
        Platform.EVENT,
        DOMAIN,
        EVENT_ENTITY_UNIQUE_ID,
    )
    assert event_entity_id is not None

    hass.states.async_set(
        event_entity_id,
        last_refresh.isoformat(),
    )

    monkeypatch.setattr(
        "custom_components.hacs_refresh.runtime.dt_util.now",
        lambda: last_refresh + MIN_REFRESH_INTERVAL - timedelta(seconds=1),
    )

    await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    hacs.async_process_queue.assert_not_awaited()


async def test_scheduled_refresh_is_allowed_without_last_refresh_event(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that scheduled refreshes are allowed when no completion event exists."""
    repository = MagicMock()
    repository.update_repository = AsyncMock()
    hacs.repositories.list_downloaded = [repository]
    hass.data["hacs"] = hacs

    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)

    await runtime.async_refresh(source="scheduled")

    assert runtime.state == "idle"
    assert runtime.last_result == EVENT_TYPE_SUCCESS
    hacs.async_process_queue.assert_awaited_once()


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
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 0
    assert runtime.last_successful == 0
    assert runtime.last_failed == 0
    assert runtime.last_pending == 0
    assert runtime.last_error is None

    hacs.queue.add.assert_not_called()
    hacs.async_process_queue.assert_not_awaited()
    hacs.data.async_write.assert_not_awaited()


async def test_refresh_reports_pending_repositories(
    hass: HomeAssistant,
    hacs: MagicMock,
) -> None:
    """Test that pending repository refreshes are reported correctly."""
    entry = MockConfigEntry(domain=DOMAIN)

    repository = MagicMock()
    repository.update_repository = AsyncMock()

    hacs.repositories.list_downloaded = [repository]

    async def process_queue() -> None:
        await hacs.queue.add.call_args.args[0]
        hacs.queue.pending_tasks = 1

    hacs.async_process_queue = AsyncMock(side_effect=process_queue)
    hass.data["hacs"] = hacs

    runtime = HacsRefreshRuntimeData(hass, entry)

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

    with pytest.raises(HomeAssistantError) as exc_info:
        await runtime.async_refresh(source="manual")

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "refresh_tasks_failed"
    assert exc_info.value.translation_placeholders == {
        "failed": "1",
        "repositories": "2",
    }

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
    assert runtime.last_source == "manual"
    assert runtime.last_repositories == 2
    assert runtime.last_successful == 1
    assert runtime.last_failed == 1
    assert runtime.last_pending == 0
    assert runtime.last_error == "1 repository refresh task(s) failed"

    hacs.queue.add.assert_called()
    assert hacs.queue.add.call_count == 2
    hacs.async_process_queue.assert_awaited_once()
    hacs.data.async_write.assert_awaited_once()
