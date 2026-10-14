"""Base entity for HACS Refresh."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import (
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .runtime import HacsRefreshRuntimeData


class HacsRefreshEntity(Entity):
    """Base entity for HACS Refresh."""

    _attr_has_entity_name = True

    def __init__(
        self,
        runtime: HacsRefreshRuntimeData,
    ) -> None:
        """Initialize the entity."""
        self.runtime = runtime
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            translation_key="hacs_refresh",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return whether the HACS dependency is available."""
        return super().available and self.runtime.hacs.available

    async def async_added_to_hass(self) -> None:
        """Register the runtime listener."""
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.add_listener(self._async_runtime_updated))

    @callback
    def _async_runtime_updated(self) -> None:
        """Update the entity when runtime state changes."""
        self.async_write_ha_state()
