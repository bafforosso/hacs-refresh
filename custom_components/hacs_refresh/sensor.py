"""Sensor platform for HACS Refresh."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    PROGRESS_SENSOR_UNIQUE_ID,
    STATUS_SENSOR_UNIQUE_ID,
)
from .entity import HacsRefreshEntity
from .hacs import HacsRefreshProgress
from .runtime import HacsRefreshRuntimeData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HACS Refresh sensors."""
    runtime: HacsRefreshRuntimeData = entry.runtime_data
    async_add_entities(
        [
            HacsRefreshStatusSensor(runtime),
            HacsRefreshProgressSensor(runtime),
        ]
    )


class HacsRefreshStatusSensor(
    HacsRefreshEntity,
    SensorEntity,
):
    """Represent HACS Refresh status."""

    _attr_translation_key = "status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _attr_unique_id = STATUS_SENSOR_UNIQUE_ID

    async def async_added_to_hass(self) -> None:
        """Register the runtime listener."""
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.add_listener(self._async_runtime_updated))

    @property
    def native_value(self) -> str:
        """Return the current status."""
        return self.runtime.state

    @callback
    def _async_runtime_updated(self) -> None:
        """Update the sensor."""
        self.async_write_ha_state()


class HacsRefreshProgressSensor(
    HacsRefreshEntity,
    SensorEntity,
):
    """Represent HACS Refresh progress."""

    _attr_translation_key = "progress"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "%"
    _attr_should_poll = False
    _attr_unique_id = PROGRESS_SENSOR_UNIQUE_ID

    async def async_added_to_hass(self) -> None:
        """Register the runtime progress listener."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.runtime.add_progress_listener(self._async_progress_updated)
        )

    @property
    def native_value(self) -> int | None:
        """Return the current refresh progress."""
        progress = self.runtime.refresh_progress

        if progress is None:
            return None

        if progress.total == 0:
            return 100

        return progress.processed * 100 // progress.total

    @callback
    def _async_progress_updated(
        self,
        _progress: HacsRefreshProgress | None,
    ) -> None:
        """Update the sensor."""
        self.async_write_ha_state()
