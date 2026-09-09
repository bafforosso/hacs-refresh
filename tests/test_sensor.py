from datetime import UTC, datetime
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    EVENT_TYPE_SUCCESS,
)
from custom_components.hacs_refresh.sensor import HacsRefreshStatusSensor


def test_status_sensor_initializes() -> None:
    """Test that the status sensor initializes correctly."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.state = "idle"

    remove_listener = MagicMock()
    runtime.add_listener.return_value = remove_listener

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.runtime is runtime
    assert sensor.native_value == "idle"
    assert sensor.unique_id == "hacs_refresh_status"
    assert sensor._attr_translation_key == "status"
    assert sensor._remove_listener is remove_listener
    runtime.add_listener.assert_called_once_with(sensor._async_runtime_updated)


def test_status_sensor_extra_state_attributes(freezer) -> None:
    """Test that the status sensor exposes runtime information."""
    freezer.move_to("2026-09-04 10:00:00+00:00")

    runtime = MagicMock()

    runtime.state = "idle"
    runtime.last_result = EVENT_TYPE_SUCCESS
    runtime.last_refresh = datetime(2026, 9, 4, 2, 30, tzinfo=UTC)
    runtime.last_source = "scheduled"
    runtime.last_error = None
    runtime.last_repositories = 5
    runtime.last_successful = 5
    runtime.last_failed = 0
    runtime.last_pending = 0
    runtime.options = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon", "wed", "fri"],
        CONF_TIMES: ["02:30", "14:00"],
    }

    sensor = HacsRefreshStatusSensor(runtime)

    attributes = sensor.extra_state_attributes

    assert attributes == {
        "automatic_refresh": True,
        "schedule_days": ["mon", "wed", "fri"],
        "schedule_times": ["02:30", "14:00"],
        "next_refresh": "2026-09-04T14:00:00+00:00",
    }


def test_status_sensor_runtime_update_writes_state() -> None:
    """Test that a runtime update causes the sensor to write its state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.state = "refreshing"

    sensor = HacsRefreshStatusSensor(runtime)

    sensor.async_write_ha_state = MagicMock()

    sensor._async_runtime_updated()

    sensor.async_write_ha_state.assert_called_once()


async def test_status_sensor_removes_runtime_listener_when_removed(
    hass: HomeAssistant,
) -> None:
    """Test that removing the sensor unregisters its runtime listener."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    remove_listener = MagicMock()
    runtime.add_listener.return_value = remove_listener

    sensor = HacsRefreshStatusSensor(runtime)

    await sensor.async_will_remove_from_hass()

    remove_listener.assert_called_once_with()


def test_status_sensor_next_refresh_disabled() -> None:
    """Test that next_refresh is unavailable when automatic refresh is disabled."""
    runtime = MagicMock()
    runtime.options = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["mon", "wed", "fri"],
        CONF_TIMES: ["02:30"],
    }

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.extra_state_attributes["next_refresh"] is None


def test_status_sensor_next_refresh_without_schedule() -> None:
    """Test that next_refresh is unavailable without a schedule."""
    runtime = MagicMock()
    runtime.options = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: [],
        CONF_TIMES: [],
    }

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.extra_state_attributes["next_refresh"] is None
