"""Persistent storage for HACS Refresh."""

from __future__ import annotations

from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_VERSION


class LastRefreshData(TypedDict):
    """Persisted data for the last completed refresh."""

    completed: str
    result: str
    source: str
    duration: float
    repositories: int
    successful: int
    failed: int
    pending: int


class HacsRefreshStore(Store[LastRefreshData]):
    """Store for HACS Refresh persistent state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
    ) -> None:
        """Initialize the HACS Refresh store."""
        super().__init__(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
        )
