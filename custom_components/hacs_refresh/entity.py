"""Base entity for HACS Refresh."""

from __future__ import annotations

from homeassistant.helpers.device_registry import (
    DeviceEntryType,
    DeviceInfo,
)

from .const import DOMAIN
from .runtime import HacsRefreshRuntimeData


class HacsRefreshEntity:
    """Base entity for HACS Refresh."""

    _attr_has_entity_name = True
    _attr_device_info: DeviceInfo | None

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
