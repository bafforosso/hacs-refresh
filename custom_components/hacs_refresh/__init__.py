"""HACS Refresh integration."""

from __future__ import annotations

from typing import Any

from awesomeversion import AwesomeVersion
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as HAVERSION
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    MIN_HA_VERSION,
    REFRESH_SOURCE_MANUAL,
    SERVICE_REFRESH,
)
from .runtime import HacsRefreshRuntimeData
from .scheduler import HacsRefreshScheduler

PLATFORMS = ["button", "event", "sensor"]

type HacsRefreshConfigEntry = ConfigEntry[HacsRefreshRuntimeData]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(
    hass: HomeAssistant,
    config: dict[str, Any],
) -> bool:
    """Set up HACS Refresh."""

    async def async_refresh(
        call: ServiceCall,
    ) -> ServiceResponse:
        """Force-refresh all installed HACS repositories."""
        entries = hass.config_entries.async_loaded_entries(DOMAIN)

        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="service_not_loaded",
            )

        entry = entries[0]

        runtime: HacsRefreshRuntimeData = entry.runtime_data

        outcome = await runtime.async_refresh(source=REFRESH_SOURCE_MANUAL)

        if not call.return_response:
            return None

        if outcome is None:
            return None

        return outcome.as_dict()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_refresh,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HacsRefreshConfigEntry,
) -> bool:
    """Set up HACS Refresh from a config entry."""
    if AwesomeVersion(HAVERSION) < AwesomeVersion(MIN_HA_VERSION):
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="min_ha_version",
            translation_placeholders={"version": MIN_HA_VERSION},
        )

    if hass.data.get("hacs") is None:
        raise ConfigEntryNotReady("HACS is not available yet")

    runtime = HacsRefreshRuntimeData(
        hass,
        entry,
    )

    entry.runtime_data = runtime

    await runtime.async_initialize()

    scheduler = HacsRefreshScheduler(
        hass,
        runtime,
    )

    entry.async_on_unload(scheduler.async_unload)

    async def _async_options_updated(
        hass: HomeAssistant,
        updated_entry: HacsRefreshConfigEntry,
    ) -> None:
        """Handle configuration option updates."""
        await scheduler.async_setup()
        runtime.notify_listeners()

    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

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
