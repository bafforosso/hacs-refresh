from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DOMAIN,
)
from custom_components.hacs_refresh.runtime import HacsRefreshRuntimeData
from custom_components.hacs_refresh.scheduler import HacsRefreshScheduler


async def test_scheduler_does_not_register_when_disabled(
    hass: HomeAssistant,
) -> None:
    """Test that no schedule is registered when automatic refresh is disabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: False,
            CONF_DAYS: ["mon", "tue"],
            CONF_TIMES: ["03:00"],
        },
    )

    runtime = HacsRefreshRuntimeData(hass, entry)
    scheduler = HacsRefreshScheduler(hass, runtime)

    with patch(
        "custom_components.hacs_refresh.scheduler.async_track_time_change"
    ) as track_time_change:
        await scheduler.async_setup()

    track_time_change.assert_not_called()


async def test_scheduler_registers_configured_times(
    hass: HomeAssistant,
) -> None:
    """Test that configured refresh times are registered."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon", "tue"],
            CONF_TIMES: ["03:00", "15:30"],
        },
    )

    runtime = HacsRefreshRuntimeData(hass, entry)
    scheduler = HacsRefreshScheduler(hass, runtime)

    unsubscribe_1 = MagicMock()
    unsubscribe_2 = MagicMock()

    with patch(
        "custom_components.hacs_refresh.scheduler.async_track_time_change",
        side_effect=[unsubscribe_1, unsubscribe_2],
    ) as track_time_change:
        await scheduler.async_setup()

    assert track_time_change.call_count == 2

    track_time_change.assert_any_call(
        hass,
        scheduler._handle_scheduled_time,
        hour=3,
        minute=0,
        second=0,
    )
    track_time_change.assert_any_call(
        hass,
        scheduler._handle_scheduled_time,
        hour=15,
        minute=30,
        second=0,
    )

    assert scheduler._unsubscribers == [
        unsubscribe_1,
        unsubscribe_2,
    ]


async def test_scheduler_triggers_refresh_on_configured_day(
    hass: HomeAssistant,
) -> None:
    """Test that a scheduled time triggers a refresh on a configured day."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon"],
            CONF_TIMES: ["03:00"],
        },
    )

    runtime = HacsRefreshRuntimeData(hass, entry)
    scheduler = HacsRefreshScheduler(hass, runtime)

    with (
        patch.object(
            runtime,
            "async_refresh",
            new_callable=AsyncMock,
        ) as mock_refresh,
        patch.object(
            hass,
            "async_create_task",
        ) as create_task_mock,
    ):
        scheduler._handle_scheduled_time(
            datetime(2026, 8, 31, 3, 0),  # noqa: DTZ001
        )

        create_task_mock.assert_called_once()

        refresh_coroutine = create_task_mock.call_args.args[0]
        await refresh_coroutine

    mock_refresh.assert_awaited_once_with(source="scheduled")


async def test_scheduler_skips_non_configured_day(
    hass: HomeAssistant,
) -> None:
    """Test that a scheduled time is ignored on a non-configured day."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon"],
            CONF_TIMES: ["03:00"],
        },
    )

    runtime = HacsRefreshRuntimeData(hass, entry)
    scheduler = HacsRefreshScheduler(hass, runtime)

    with (
        patch.object(
            runtime,
            "async_refresh",
            new_callable=AsyncMock,
        ) as mock_refresh,
        patch.object(
            hass,
            "async_create_task",
        ) as create_task_mock,
    ):
        # Tuesday — Monday is the only configured day.
        scheduler._handle_scheduled_time(
            datetime(2026, 9, 1, 3, 0),  # noqa: DTZ001
        )

    create_task_mock.assert_not_called()
    mock_refresh.assert_not_awaited()


async def test_scheduler_skips_when_refresh_is_in_progress(
    hass: HomeAssistant,
) -> None:
    """Test that a scheduled refresh is skipped while another is running."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon"],
            CONF_TIMES: ["03:00"],
        },
    )

    runtime = HacsRefreshRuntimeData(hass, entry)
    scheduler = HacsRefreshScheduler(hass, runtime)

    async with runtime._refresh_lock:
        assert runtime.refresh_in_progress is True

        with patch.object(
            hass,
            "async_create_task",
        ) as create_task_mock:
            scheduler._handle_scheduled_time(
                datetime(2026, 8, 31, 3, 0),  # noqa: DTZ001
            )

        create_task_mock.assert_not_called()


def test_scheduler_unload_removes_registered_listeners(
    hass: HomeAssistant,
) -> None:
    """Test that unloading the scheduler removes all listeners."""
    entry = MockConfigEntry(domain=DOMAIN)

    runtime = HacsRefreshRuntimeData(hass, entry)
    scheduler = HacsRefreshScheduler(hass, runtime)

    unsubscribe_1 = MagicMock()
    unsubscribe_2 = MagicMock()

    scheduler._unsubscribers = [
        unsubscribe_1,
        unsubscribe_2,
    ]

    scheduler.async_unload()

    unsubscribe_1.assert_called_once_with()
    unsubscribe_2.assert_called_once_with()
    assert scheduler._unsubscribers == []
