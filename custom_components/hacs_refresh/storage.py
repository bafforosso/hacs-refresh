"""Persistent storage for HACS Refresh."""

from __future__ import annotations

from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    STORAGE_KEY,
    STORAGE_VERSION_MAJOR,
    STORAGE_VERSION_MINOR,
)


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

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the HACS Refresh store."""
        super().__init__(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            minor_version=STORAGE_VERSION_MINOR,
        )
