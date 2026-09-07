"""Event platform for HACS Refresh."""

from __future__ import annotations

from typing import Any, ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    EVENT_ENTITY_UNIQUE_ID,
    EVENT_TYPE_FAILED,
    EVENT_TYPE_PARTIAL,
    EVENT_TYPE_SUCCESS,
)
from .entity import HacsRefreshEntity
from .runtime import HacsRefreshRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HACS Refresh event entity."""
    runtime: HacsRefreshRuntimeData = entry.runtime_data

    async_add_entities([HacsRefreshCompletedEvent(runtime)])


class HacsRefreshCompletedEvent(
    HacsRefreshEntity,
    EventEntity,
):
    """Represent HACS Refresh completion events."""

    _attr_translation_key = "refresh_completed"
    _attr_should_poll = False
    _attr_unique_id = EVENT_ENTITY_UNIQUE_ID
    _attr_event_types: ClassVar[list[str]] = [
        EVENT_TYPE_SUCCESS,
        EVENT_TYPE_PARTIAL,
        EVENT_TYPE_FAILED,
    ]

    def __init__(
        self,
        runtime: HacsRefreshRuntimeData,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(runtime)

    async def async_added_to_hass(self) -> None:
        """Register the runtime listener."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.runtime.add_event_listener(self._async_refresh_completed)
        )

    @callback
    def _async_refresh_completed(
        self,
        event_type: str,
        event_data: dict[str, Any],
    ) -> None:
        """Handle a completed refresh."""
        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()
