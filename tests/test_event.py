from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.hacs_refresh.const import (
    EVENT_TYPE_FAILED,
    EVENT_TYPE_PARTIAL,
    EVENT_TYPE_SUCCESS,
)
from custom_components.hacs_refresh.event import HacsRefreshCompletedEvent


def test_refresh_completed_event_initializes() -> None:
    """Test that the refresh completed event initializes correctly."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    event = HacsRefreshCompletedEvent(runtime)

    assert event.runtime is runtime
    assert event.unique_id == "hacs_refresh_refresh_completed"
    assert event._attr_translation_key == "refresh_completed"
    assert event._attr_should_poll is False
    assert event._attr_event_types == [
        EVENT_TYPE_SUCCESS,
        EVENT_TYPE_PARTIAL,
        EVENT_TYPE_FAILED,
    ]


def test_refresh_completed_event_triggers_event() -> None:
    """Test that a refresh completion triggers the event entity."""
    runtime = MagicMock()
    event = HacsRefreshCompletedEvent(runtime)

    event._trigger_event = MagicMock()
    event.async_write_ha_state = MagicMock()

    event_data = {
        "source": "scheduled",
        "duration": 2.5,
        "repositories": 5,
        "successful": 5,
        "failed": 0,
        "pending": 0,
        "last_error": None,
    }

    event._async_refresh_completed(
        EVENT_TYPE_SUCCESS,
        event_data,
    )

    event._trigger_event.assert_called_once_with(
        EVENT_TYPE_SUCCESS,
        event_data,
    )
    event.async_write_ha_state.assert_called_once()


async def test_refresh_completed_event_registers_listener(
    hass: HomeAssistant,
) -> None:
    """Test that the event registers its runtime listener when added to HA."""
    runtime = MagicMock()
    event = HacsRefreshCompletedEvent(runtime)

    await event.async_added_to_hass()

    runtime.add_event_listener.assert_called_once_with(
        event._async_refresh_completed,
    )
