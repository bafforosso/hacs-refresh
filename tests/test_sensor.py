from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
)
from custom_components.hacs_refresh.sensor import (
    HacsRefreshStatusSensor,
    async_setup_entry,
)


def test_status_sensor_initializes() -> None:
    """Test that the status sensor initializes correctly."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.state = "idle"

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.runtime is runtime
    assert sensor.native_value == "idle"
    assert sensor.unique_id == "hacs_refresh_status"
    assert sensor._attr_translation_key == "status"
    runtime.add_listener.assert_not_called()


async def test_status_sensor_setup_entry(hass: HomeAssistant) -> None:
    """Test that the status sensor is created for the config entry."""
    runtime = MagicMock()
    entry = MagicMock()
    entry.runtime_data = runtime
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], HacsRefreshStatusSensor)
    assert entities[0].runtime is runtime


async def test_status_sensor_registers_runtime_listener() -> None:
    """Test that the sensor registers its runtime listener when added to HA."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    remove_listener = MagicMock()
    runtime.add_listener.return_value = remove_listener

    sensor = HacsRefreshStatusSensor(runtime)

    with patch.object(sensor, "async_on_remove") as mock_async_on_remove:
        await sensor.async_added_to_hass()

    runtime.add_listener.assert_called_once_with(sensor._async_runtime_updated)
    mock_async_on_remove.assert_called_once_with(remove_listener)


def test_status_sensor_extra_state_attributes(freezer) -> None:
    """Test that the status sensor exposes runtime information."""
    freezer.move_to("2026-09-04 10:00:00+00:00")

    runtime = MagicMock()
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

    with patch.object(Entity, "async_write_ha_state") as mock_write_state:
        sensor._async_runtime_updated()

    mock_write_state.assert_called_once_with()


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


def test_status_sensor_next_refresh_without_valid_schedule_day() -> None:
    """Test that next_refresh is unavailable when no valid schedule day is configured."""
    runtime = MagicMock()
    runtime.options = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["invalid"],
        CONF_TIMES: ["02:30"],
    }

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.extra_state_attributes["next_refresh"] is None
