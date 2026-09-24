from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant

from custom_components.hacs_refresh.button import (
    HacsRefreshButton,
    async_setup_entry,
)
from custom_components.hacs_refresh.const import BUTTON_ENTITY_UNIQUE_ID


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

    runtime.refresh_in_progress = False
    assert button.available is True

    runtime.refresh_in_progress = True
    assert button.available is False


async def test_refresh_button_registers_runtime_listener() -> None:
    """Test that the button registers its runtime listener when added to HA."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    remove_listener = MagicMock()
    runtime.add_listener.return_value = remove_listener

    button = HacsRefreshButton(runtime)

    with (
        patch(
            "custom_components.hacs_refresh.button.ButtonEntity.async_added_to_hass",
            new_callable=AsyncMock,
        ) as mock_super,
        patch.object(button, "async_on_remove") as mock_async_on_remove,
    ):
        await button.async_added_to_hass()

    mock_super.assert_awaited_once_with()
    runtime.add_listener.assert_called_once_with(button._async_runtime_updated)
    mock_async_on_remove.assert_called_once_with(remove_listener)


def test_refresh_button_runtime_update_writes_state() -> None:
    """Test that a runtime update causes the button to write its state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    button = HacsRefreshButton(runtime)

    with patch.object(button, "async_write_ha_state") as mock_write_state:
        button._async_runtime_updated()

    mock_write_state.assert_called_once_with()


async def test_refresh_button_triggers_manual_refresh() -> None:
    """Test that the refresh button triggers a manual refresh."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.async_refresh = AsyncMock()

    button = HacsRefreshButton(runtime)

    await button.async_press()

    runtime.async_refresh.assert_awaited_once_with(source="manual")
