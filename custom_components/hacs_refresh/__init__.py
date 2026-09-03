"""HACS Refresh integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    ServiceValidationError,
)

from .const import DOMAIN, SERVICE_REFRESH
from .runtime import HacsRefreshRuntimeData
from .scheduler import HacsRefreshScheduler

PLATFORMS = ["sensor"]

type HacsRefreshConfigEntry = ConfigEntry[
    HacsRefreshRuntimeData
]


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Set up HACS Refresh."""

    async def async_refresh(
        call: ServiceCall,
    ) -> None:
        """Force-refresh all installed HACS repositories."""
        entries = hass.config_entries.async_loaded_entries(
            DOMAIN
        )

        if not entries:
            raise ServiceValidationError(
                "HACS Refresh is not configured or loaded"
            )

        entry = entries[0]

        runtime: HacsRefreshRuntimeData = (
            entry.runtime_data
        )

        await runtime.async_refresh(
            source="manual"
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_refresh,
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HacsRefreshConfigEntry,
) -> bool:
    """Set up HACS Refresh from a config entry."""
    if hass.data.get("hacs") is None:
        raise ConfigEntryNotReady(
            "HACS is not available yet"
        )

    runtime = HacsRefreshRuntimeData(
        hass,
        entry,
    )

    entry.runtime_data = runtime

    scheduler = HacsRefreshScheduler(
        hass,
        runtime,
    )

    entry.async_on_unload(
        scheduler.async_unload
    )

    async def _async_options_updated(
        hass: HomeAssistant,
        updated_entry: HacsRefreshConfigEntry,
    ) -> None:
        """Handle configuration option updates."""
        await scheduler.async_setup()
        runtime.notify_listeners()

    entry.async_on_unload(
        entry.add_update_listener(
            _async_options_updated
        )
    )

    await scheduler.async_setup()

    await hass.config_entries.async_forward_entry_setups(
        entry,
        PLATFORMS,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HacsRefreshConfigEntry,
) -> bool:
    """Unload HACS Refresh."""
    return await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )
