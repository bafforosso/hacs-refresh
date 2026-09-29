"""Switch platform for HACS Refresh."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    AUTOMATIC_REFRESH_SWITCH_UNIQUE_ID,
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
)
from .entity import HacsRefreshEntity
from .runtime import HacsRefreshRuntimeData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HACS Refresh switch."""
    runtime: HacsRefreshRuntimeData = entry.runtime_data

    async_add_entities([HacsRefreshAutomaticRefreshSwitch(runtime)])


class HacsRefreshAutomaticRefreshSwitch(
    HacsRefreshEntity,
    SwitchEntity,
):
    """Represent the HACS Refresh automatic refresh configuration."""

    _attr_translation_key = "automatic_refresh"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False
    _attr_unique_id = AUTOMATIC_REFRESH_SWITCH_UNIQUE_ID

    async def async_added_to_hass(self) -> None:
        """Register the runtime listener."""
        await super().async_added_to_hass()
        self.async_on_remove(self.runtime.add_listener(self._async_runtime_updated))

    @property
    def is_on(self) -> bool:
        """Return whether automatic refresh is enabled."""
        return self.runtime.entry.options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        )

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return automatic refresh configuration and schedule information."""
        options = self.runtime.entry.options
        scheduler = self.runtime.scheduler

        automatic_refresh = options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        )

        next_refresh = (
            scheduler.next_refresh
            if automatic_refresh and scheduler is not None
            else None
        )

        return {
            "schedule_days": options.get(
                CONF_DAYS,
                [],
            ),
            "schedule_times": options.get(
                CONF_TIMES,
                [],
            ),
            "next_refresh": (
                next_refresh.isoformat() if next_refresh is not None else None
            ),
        }

    async def async_turn_on(self, **kwargs: object) -> None:
        """Enable automatic refreshes."""
        self.hass.config_entries.async_update_entry(
            self.runtime.entry,
            options={
                **self.runtime.entry.options,
                CONF_AUTOMATIC_REFRESH: True,
            },
        )

    async def async_turn_off(self, **kwargs: object) -> None:
        """Disable automatic refreshes."""
        self.hass.config_entries.async_update_entry(
            self.runtime.entry,
            options={
                **self.runtime.entry.options,
                CONF_AUTOMATIC_REFRESH: False,
            },
        )

    @callback
    def _async_runtime_updated(self) -> None:
        """Update the switch."""
        self.async_write_ha_state()
