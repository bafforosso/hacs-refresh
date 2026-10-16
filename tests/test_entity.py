from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.helpers.entity import Entity

from custom_components.hacs_refresh.entity import HacsRefreshEntity


def test_entity_availability_follows_hacs() -> None:
    """Test that entity availability follows HACS availability."""
    runtime = MagicMock()
    runtime.hacs.available = True

    entity = HacsRefreshEntity(runtime)
    assert entity.available is True

    runtime.hacs.available = False
    assert entity.available is False

    runtime.hacs.available = True
    with patch.object(Entity, "available", new_callable=PropertyMock) as available:
        available.return_value = False
        assert entity.available is False


async def test_entity_registers_runtime_listener() -> None:
    """Test that the base entity registers its runtime listener."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    remove_listener = MagicMock()
    runtime.add_listener.return_value = remove_listener

    entity = HacsRefreshEntity(runtime)

    with (
        patch.object(
            Entity,
            "async_added_to_hass",
            new_callable=AsyncMock,
        ) as mock_super,
        patch.object(entity, "async_on_remove") as mock_async_on_remove,
    ):
        await entity.async_added_to_hass()

    mock_super.assert_awaited_once_with()
    runtime.add_listener.assert_called_once_with(entity._async_runtime_updated)
    mock_async_on_remove.assert_called_once_with(remove_listener)


def test_entity_runtime_update_writes_state() -> None:
    """Test that a runtime update writes the entity state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    entity = HacsRefreshEntity(runtime)

    with patch.object(Entity, "async_write_ha_state") as mock_write_state:
        entity._async_runtime_updated()

    mock_write_state.assert_called_once_with()
