from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    ServiceValidationError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh import (
    PLATFORMS,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.hacs_refresh.const import DOMAIN, SERVICE_REFRESH


def test_platforms() -> None:
    """Test the integration platforms."""
    assert PLATFORMS == ["button", "event", "sensor"]


async def test_service_is_registered(hass: HomeAssistant) -> None:
    """Test that the refresh service is registered."""
    assert not hass.services.has_service(DOMAIN, SERVICE_REFRESH)

    assert await async_setup(hass, {})

    assert hass.services.has_service(DOMAIN, SERVICE_REFRESH)


async def test_refresh_service_requires_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test that refresh fails when HACS Refresh is not configured."""
    await async_setup(hass, {})

    with pytest.raises(
        ServiceValidationError,
        match="service_not_loaded",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            blocking=True,
        )


async def test_refresh_service_triggers_manual_refresh(
    hass: HomeAssistant,
) -> None:
    """Test that the refresh service triggers a manual refresh."""
    await async_setup(hass, {})

    runtime = MagicMock()
    config_entry = MagicMock()
    config_entry.runtime_data = runtime

    with patch.object(
        hass.config_entries,
        "async_loaded_entries",
        return_value=[config_entry],
    ), patch.object(
        runtime,
        "async_refresh",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            blocking=True,
        )

    mock_refresh.assert_awaited_once_with(source="manual")


async def test_setup_entry_requires_hacs(
    hass: HomeAssistant,
) -> None:
    """Test that setup waits for HACS to become available."""
    hass.data.pop("hacs", None)

    config_entry = MockConfigEntry(domain=DOMAIN)

    with pytest.raises(
        ConfigEntryNotReady,
        match="HACS is not available yet",
    ):
        await async_setup_entry(hass, config_entry)


async def test_setup_entry_initializes_integration(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that setup initializes runtime, scheduler, and platforms."""
    config_entry = MockConfigEntry(domain=DOMAIN)

    hass.data["hacs"] = MagicMock()

    forward_entry_setups = AsyncMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        forward_entry_setups,
    )

    with (
        patch("custom_components.hacs_refresh.HacsRefreshScheduler") as scheduler_class,
        patch(
            "custom_components.hacs_refresh.HacsRefreshRuntimeData.async_initialize",
            new_callable=AsyncMock,
        ) as async_initialize,
    ):
        scheduler = scheduler_class.return_value
        scheduler.async_setup = AsyncMock()

        assert await async_setup_entry(hass, config_entry)

    assert config_entry.runtime_data is not None
    async_initialize.assert_awaited_once()
    scheduler_class.assert_called_once_with(
        hass,
        config_entry.runtime_data,
    )
    scheduler.async_setup.assert_awaited_once()
    forward_entry_setups.assert_awaited_once_with(
        config_entry,
        PLATFORMS,
    )


async def test_setup_entry_options_update_reconfigures_scheduler(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that option updates reconfigure the scheduler and notify listeners."""
    config_entry = MockConfigEntry(domain=DOMAIN)

    hass.data["hacs"] = MagicMock()

    forward_entry_setups = AsyncMock()
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        forward_entry_setups,
    )

    with (
        patch("custom_components.hacs_refresh.HacsRefreshScheduler") as scheduler_class,
        patch.object(
            config_entry,
            "add_update_listener",
            return_value=MagicMock(),
        ) as add_update_listener,
    ):
        scheduler = scheduler_class.return_value
        scheduler.async_setup = AsyncMock()

        await async_setup_entry(hass, config_entry)

        update_listener = add_update_listener.call_args.args[0]

        scheduler.async_setup.reset_mock()

        with patch.object(
            config_entry.runtime_data,
            "notify_listeners",
        ) as mock_notify_listeners:
            await update_listener(hass, config_entry)

        scheduler.async_setup.assert_awaited_once()
        mock_notify_listeners.assert_called_once_with()


async def test_unload_entry_unloads_platforms(
    hass: HomeAssistant,
) -> None:
    """Test that unloading the integration unloads its platforms."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    unload_platforms = AsyncMock(return_value=True)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        unload_platforms,
    ):
        assert await async_unload_entry(hass, config_entry)

    unload_platforms.assert_awaited_once_with(
        config_entry,
        PLATFORMS,
    )
