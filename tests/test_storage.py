"""Test HACS Refresh persistent storage."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import DOMAIN
from custom_components.hacs_refresh.storage import HacsRefreshStore


async def test_ignores_legacy_refresh_storage(
    hass: HomeAssistant,
) -> None:
    """Test that the current store does not load the legacy refresh store."""
    entry = MockConfigEntry(domain=DOMAIN)

    legacy_store = Store[dict[str, Any]](
        hass,
        1,
        f"{DOMAIN}.{entry.entry_id}",
    )

    await legacy_store.async_save(
        {
            "last_refresh": "2026-01-01T02:30:00+00:00",
            "last_result": "success",
            "last_source": "scheduled",
            "last_repositories": 5,
            "last_successful": 5,
            "last_failed": 0,
            "last_pending": 0,
            "last_error": None,
        }
    )

    store = HacsRefreshStore(hass)

    assert await store.async_load() is None
