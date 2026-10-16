from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.hacs_refresh.button import (
    HacsRefreshButton,
    async_setup_entry,
)
from custom_components.hacs_refresh.const import (
    BUTTON_ENTITY_UNIQUE_ID,
    REFRESH_SOURCE_MANUAL,
)


def test_refresh_button_initializes() -> None:
    """Test that the refresh button initializes correctly."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    button = HacsRefreshButton(runtime)

    assert button.runtime is runtime
    assert button.unique_id == BUTTON_ENTITY_UNIQUE_ID
    assert button._attr_translation_key == "refresh"
    runtime.add_listener.assert_not_called()


async def test_refresh_button_setup_entry(hass: HomeAssistant) -> None:
    """Test that the refresh button is created for the config entry."""
    runtime = MagicMock()
    entry = MagicMock()
    entry.runtime_data = runtime
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert isinstance(entities[0], HacsRefreshButton)
    assert entities[0].runtime is runtime


def test_refresh_button_availability() -> None:
    """Test that the refresh button reflects the refresh state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    button = HacsRefreshButton(runtime)

    runtime.hacs.available = True
    runtime.refresh_in_progress = False
    assert button.available is True

    runtime.refresh_in_progress = True
    assert button.available is False

    runtime.refresh_in_progress = False
    runtime.hacs.available = False
    assert button.available is False


async def test_refresh_button_triggers_manual_refresh() -> None:
    """Test that the refresh button triggers a manual refresh."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.async_refresh = AsyncMock()

    button = HacsRefreshButton(runtime)

    await button.async_press()

    runtime.async_refresh.assert_awaited_once_with(source=REFRESH_SOURCE_MANUAL)


async def test_refresh_button_propagates_execution_failure() -> None:
    """Test that genuine runtime execution failures propagate from the button."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.async_refresh = AsyncMock(
        side_effect=RuntimeError("Unexpected refresh execution failure")
    )

    button = HacsRefreshButton(runtime)

    with pytest.raises(
        RuntimeError,
        match="Unexpected refresh execution failure",
    ):
        await button.async_press()

    runtime.async_refresh.assert_awaited_once_with(source=REFRESH_SOURCE_MANUAL)
