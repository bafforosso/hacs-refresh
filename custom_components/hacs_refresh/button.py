"""Button platform for HACS Refresh."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HacsRefreshEntity
from .runtime import HacsRefreshRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HACS Refresh button."""
    runtime: HacsRefreshRuntimeData = entry.runtime_data

    async_add_entities(
        [HacsRefreshButton(runtime)]
    )


class HacsRefreshButton(
    HacsRefreshEntity,
    ButtonEntity,
):
    """Represent the HACS Refresh manual refresh button."""

    _attr_translation_key = "refresh"
    _attr_unique_id = "hacs_refresh_manual_refresh"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.runtime.async_refresh(
            source="manual"
        )
