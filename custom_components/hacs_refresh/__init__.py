"""HACS Refresh integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, ServiceCall

DOMAIN = "hacs_refresh"
SERVICE_REFRESH = "refresh"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up HACS Refresh."""

    async def async_refresh(call: ServiceCall) -> None:
        """Force-refresh all installed HACS repositories."""

        hacs = hass.data.get("hacs")

        if hacs is None:
            _LOGGER.error("HACS is not available")
            return

        if hacs.system.disabled:
            _LOGGER.error("HACS is disabled; refresh aborted")
            return

        repositories = hacs.repositories.list_downloaded

        if not repositories:
            _LOGGER.warning("No installed HACS repositories found")
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
            _LOGGER.exception("Unexpected error while processing HACS refresh queue")
            return

        for coordinator in hacs.coordinators.values():
            coordinator.async_update_listeners()

        await hacs.data.async_write()

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
