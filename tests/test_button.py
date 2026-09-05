from unittest.mock import AsyncMock, MagicMock

from custom_components.hacs_refresh.button import HacsRefreshButton


def test_refresh_button_initializes() -> None:
    """Test that the refresh button initializes correctly."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    button = HacsRefreshButton(runtime)

    assert button.runtime is runtime
    assert button.unique_id == "hacs_refresh_manual_refresh"
    assert button._attr_translation_key == "refresh"


async def test_refresh_button_triggers_manual_refresh() -> None:
    """Test that the refresh button triggers a manual refresh."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.async_refresh = AsyncMock()

    button = HacsRefreshButton(runtime)

    await button.async_press()

    runtime.async_refresh.assert_awaited_once_with(
        source="manual"
    )
