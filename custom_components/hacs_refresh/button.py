"""Button platform for HACS Refresh."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BUTTON_ENTITY_UNIQUE_ID,
    REFRESH_SOURCE_MANUAL,
)
from .entity import HacsRefreshEntity
from .runtime import HacsRefreshRuntimeData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HACS Refresh button."""
    runtime: HacsRefreshRuntimeData = entry.runtime_data

    async_add_entities([HacsRefreshButton(runtime)])


class HacsRefreshButton(
    HacsRefreshEntity,
    ButtonEntity,
):
    """Represent the HACS Refresh manual refresh button."""

    _attr_translation_key = "refresh"
    _attr_unique_id = BUTTON_ENTITY_UNIQUE_ID

    @property
    def available(self) -> bool:
        """Return whether a refresh can be started."""
        return super().available and not self.runtime.refresh_in_progress

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)
