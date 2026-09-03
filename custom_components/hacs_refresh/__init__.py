"""HACS Refresh integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "hacs_refresh"
SERVICE_REFRESH = "refresh"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the HACS Refresh integration."""

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up HACS Refresh from a config entry."""

    hacs = hass.data.get("hacs")

    if hacs is None:
        _LOGGER.error("HACS is not available")
        return False

    async def async_refresh(call: ServiceCall) -> None:
        """Force-refresh all installed HACS repositories."""

        if hacs.system.disabled:
            _LOGGER.error("HACS is disabled; refresh aborted")
            return

        if hacs.queue.running:
            _LOGGER.error(
                "HACS queue is already running; refresh aborted"
            )
            return

        repositories = hacs.repositories.list_downloaded

        if not repositories:
            _LOGGER.debug("No installed HACS repositories found")
            return

        _LOGGER.debug(
            "Starting forced refresh of %d installed HACS repositories",
            len(repositories),
        )

        for repository in repositories:
            hacs.queue.add(
                repository.update_repository(
                    ignore_issues=True,
                    force=True,
                )
            )

        try:
            await hacs.async_process_queue()
        except Exception:
            _LOGGER.exception(
                "Unexpected error while processing HACS refresh queue"
            )
            return

        for coordinator in hacs.coordinators.values():
            coordinator.async_update_listeners()

        await hacs.data.async_write()

        if hacs.queue.has_pending_tasks:
            _LOGGER.warning(
                "HACS refresh finished with %d repositories still "
                "pending in the HACS queue",
                hacs.queue.pending_tasks,
            )
            return

        _LOGGER.debug(
            "HACS forced refresh completed for %d repositories",
            len(repositories),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        async_refresh,
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload HACS Refresh."""

    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)

    return True
