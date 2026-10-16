from unittest.mock import MagicMock, call, patch

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from custom_components.hacs_refresh.const import (
    PROGRESS_SENSOR_UNIQUE_ID,
    STATE_IDLE,
    STATE_REFRESHING,
    STATUS_SENSOR_UNIQUE_ID,
)
from custom_components.hacs_refresh.hacs import HacsRefreshProgress
from custom_components.hacs_refresh.sensor import (
    HacsRefreshProgressSensor,
    HacsRefreshStatusSensor,
    async_setup_entry,
)


@pytest.mark.parametrize(
    "status",
    [STATE_IDLE, STATE_REFRESHING],
)
def test_status_sensor_initializes(
    status: str,
) -> None:
    """Test that the status sensor initializes correctly."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.state = status

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.runtime is runtime
    assert sensor.native_value == status
    assert sensor.unique_id == STATUS_SENSOR_UNIQUE_ID
    assert sensor._attr_translation_key == "status"
    assert sensor.entity_category is None
    assert sensor.device_class == SensorDeviceClass.ENUM

    options = sensor.options
    assert options is not None
    assert options == [STATE_IDLE, STATE_REFRESHING]
    assert status in options

    assert sensor.native_unit_of_measurement is None
    assert sensor.state_class is None
    runtime.add_listener.assert_not_called()


async def test_sensor_setup_entry(hass: HomeAssistant) -> None:
    """Test that the sensors are created for the config entry."""
    runtime = MagicMock()
    entry = MagicMock()
    entry.runtime_data = runtime
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]

    assert len(entities) == 2
    assert isinstance(entities[0], HacsRefreshStatusSensor)
    assert isinstance(entities[1], HacsRefreshProgressSensor)
    assert all(entity.runtime is runtime for entity in entities)


def test_status_sensor_has_no_extra_state_attributes() -> None:
    """Test that the status sensor exposes no extra state attributes."""
    runtime = MagicMock()
    runtime.state = "idle"

    sensor = HacsRefreshStatusSensor(runtime)

    assert sensor.extra_state_attributes is None


@pytest.mark.parametrize(
    ("progress", "expected"),
    [
        (None, None),
        (
            HacsRefreshProgress(
                total=3,
                processed=0,
                successful=0,
                failed=0,
            ),
            0,
        ),
        (
            HacsRefreshProgress(
                total=3,
                processed=1,
                successful=1,
                failed=0,
            ),
            33,
        ),
        (
            HacsRefreshProgress(
                total=3,
                processed=2,
                successful=1,
                failed=1,
            ),
            66,
        ),
        (
            HacsRefreshProgress(
                total=3,
                processed=3,
                successful=2,
                failed=1,
            ),
            100,
        ),
        (
            HacsRefreshProgress(
                total=0,
                processed=0,
                successful=0,
                failed=0,
            ),
            100,
        ),
    ],
)
def test_progress_sensor_value(
    progress: HacsRefreshProgress | None,
    expected: int | None,
) -> None:
    """Test that the progress sensor reports the expected value."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.refresh_progress = progress

    sensor = HacsRefreshProgressSensor(runtime)

    assert sensor.native_value == expected
    assert sensor.unique_id == PROGRESS_SENSOR_UNIQUE_ID
    assert sensor._attr_translation_key == "progress"
    assert sensor.native_unit_of_measurement == "%"
    assert sensor.entity_category is None
    assert sensor.should_poll is False


async def test_progress_sensor_registers_runtime_listener() -> None:
    """Test that the progress sensor registers both runtime listeners."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    remove_runtime_listener = MagicMock()
    remove_progress_listener = MagicMock()
    runtime.add_listener.return_value = remove_runtime_listener
    runtime.add_progress_listener.return_value = remove_progress_listener

    sensor = HacsRefreshProgressSensor(runtime)

    with patch.object(sensor, "async_on_remove") as mock_async_on_remove:
        await sensor.async_added_to_hass()

    runtime.add_listener.assert_called_once_with(sensor._async_runtime_updated)
    runtime.add_progress_listener.assert_called_once_with(
        sensor._async_progress_updated
    )
    mock_async_on_remove.assert_has_calls(
        [
            call(remove_runtime_listener),
            call(remove_progress_listener),
        ]
    )
    assert mock_async_on_remove.call_count == 2


def test_progress_sensor_update_writes_state() -> None:
    """Test that a progress update causes the sensor to write its state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.refresh_progress = HacsRefreshProgress(
        total=2,
        processed=1,
        successful=1,
        failed=0,
    )

    sensor = HacsRefreshProgressSensor(runtime)

    with patch.object(Entity, "async_write_ha_state") as mock_write_state:
        sensor._async_progress_updated(runtime.refresh_progress)

    mock_write_state.assert_called_once_with()
