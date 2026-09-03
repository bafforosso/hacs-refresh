"""Sensor platform for HACS Refresh."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    DeviceEntryType,
    DeviceInfo,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DOMAIN,
    WEEKDAYS,
)
from .runtime import HacsRefreshRuntimeData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HACS Refresh sensor."""
    runtime: HacsRefreshRuntimeData = (
        entry.runtime_data
    )

    async_add_entities(
        [HacsRefreshStatusSensor(runtime)]
    )


class HacsRefreshStatusSensor(SensorEntity):
    """Represent HACS Refresh status."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _attr_unique_id = "hacs_refresh_status"

    def __init__(
        self,
        runtime: HacsRefreshRuntimeData,
    ) -> None:
        """Initialize the sensor."""
        self.runtime = runtime

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            translation_key="hacs_refresh",
            entry_type=DeviceEntryType.SERVICE,
        )

        self._remove_listener = (
            runtime.add_listener(
                self._async_runtime_updated
            )
        )

    @property
    def native_value(self) -> str:
        """Return the current status."""
        return self.runtime.state

    @property
    def extra_state_attributes(
        self,
    ) -> dict[str, Any]:
        """Return diagnostic attributes."""
        options = self.runtime.options

        return {
            "automatic_refresh": options.get(
                CONF_AUTOMATIC_REFRESH,
                False,
            ),
            "schedule_days": options.get(
                CONF_DAYS,
                [],
            ),
            "schedule_times": options.get(
                CONF_TIMES,
                [],
            ),
            "next_refresh": self._next_refresh(),
            "last_refresh": (
                self.runtime.last_refresh.isoformat()
                if self.runtime.last_refresh
                else None
            ),
            "last_result": self.runtime.last_result,
            "last_source": self.runtime.last_source,
            "repositories": self.runtime.last_repositories,
            "successful": self.runtime.last_successful,
            "failed": self.runtime.last_failed,
            "pending": self.runtime.last_pending,
            "last_error": self.runtime.last_error,
        }

    @callback
    def _async_runtime_updated(self) -> None:
        """Update the sensor."""
        self.async_write_ha_state()

    def _next_refresh(self) -> str | None:
        """Return the next configured automatic refresh."""
        options = self.runtime.options

        if not options.get(
            CONF_AUTOMATIC_REFRESH,
            False,
        ):
            return None

        days = set(
            options.get(
                CONF_DAYS,
                [],
            )
        )
        times = options.get(
            CONF_TIMES,
            [],
        )

        if not days or not times:
            return None

        now = dt_util.now()
        candidates: list[datetime] = []

        for day_offset in range(8):
            candidate_date = (
                now.date()
                + timedelta(days=day_offset)
            )

            weekday = WEEKDAYS[
                candidate_date.weekday()
            ]

            if weekday not in days:
                continue

            for time_string in times:
                hour, minute = (
                    int(value)
                    for value in time_string.split(":")
                )

                candidate = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour,
                    minute,
                    tzinfo=now.tzinfo,
                )

                if candidate > now:
                    candidates.append(candidate)

        if not candidates:
            return None

        return min(candidates).isoformat()

    async def async_will_remove_from_hass(
        self,
    ) -> None:
        """Clean up runtime listeners."""
        self._remove_listener()

        await super().async_will_remove_from_hass()
