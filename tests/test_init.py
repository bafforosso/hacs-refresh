import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.exceptions import (
    ConfigEntryError,
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
from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DOMAIN,
    MIN_HA_VERSION,
    SERVICE_REFRESH,
)
from custom_components.hacs_refresh.runtime import HacsRefreshOutcome


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

    with (
        patch.object(
            hass.config_entries,
            "async_loaded_entries",
            return_value=[config_entry],
        ),
        patch.object(
            runtime,
            "async_refresh",
            new_callable=AsyncMock,
        ) as mock_refresh,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            blocking=True,
        )

    mock_refresh.assert_awaited_once_with(source="manual")


async def test_refresh_service_supports_optional_response(
    hass: HomeAssistant,
) -> None:
    """Test that the refresh service optionally supports response data."""
    await async_setup(hass, {})

    assert (
        hass.services.supports_response(DOMAIN, SERVICE_REFRESH)
        is SupportsResponse.OPTIONAL
    )


async def test_refresh_service_returns_response_data(
    hass: HomeAssistant,
) -> None:
    """Test that the refresh service returns response data when requested."""
    await async_setup(hass, {})

    runtime = MagicMock()
    runtime.async_refresh = AsyncMock(
        return_value=HacsRefreshOutcome(
            successful=5,
            duration=2.5,
        )
    )
    config_entry = MagicMock()
    config_entry.runtime_data = runtime

    with patch.object(
        hass.config_entries,
        "async_loaded_entries",
        return_value=[config_entry],
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            blocking=True,
            return_response=True,
        )

    assert response == {
        "successful": 5,
        "duration": 2.5,
    }
    runtime.async_refresh.assert_awaited_once_with(source="manual")


async def test_refresh_service_does_not_return_response_data_by_default(
    hass: HomeAssistant,
) -> None:
    """Test that the refresh service does not return response data by default."""
    await async_setup(hass, {})

    runtime = MagicMock()
    runtime.async_refresh = AsyncMock(
        return_value=HacsRefreshOutcome(
            successful=5,
            duration=2.5,
        )
    )
    config_entry = MagicMock()
    config_entry.runtime_data = runtime

    with patch.object(
        hass.config_entries,
        "async_loaded_entries",
        return_value=[config_entry],
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_REFRESH,
            blocking=True,
        )

    assert response is None
    runtime.async_refresh.assert_awaited_once_with(source="manual")


async def test_setup_entry_rejects_unsupported_home_assistant_version(
    hass: HomeAssistant,
) -> None:
    """Test that setup fails on an unsupported Home Assistant version."""
    config_entry = MockConfigEntry(domain=DOMAIN)

    with (
        patch(
            "custom_components.hacs_refresh.HAVERSION",
            "0.0.0",
        ),
        patch(
            "custom_components.hacs_refresh.HacsRefreshRuntimeData",
        ) as runtime_class,
        pytest.raises(ConfigEntryError) as err,
    ):
        await async_setup_entry(hass, config_entry)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "min_ha_version"
    assert err.value.translation_placeholders == {
        "version": MIN_HA_VERSION,
    }
    runtime_class.assert_not_called()


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
        patch(
            "custom_components.hacs_refresh.HAVERSION",
            MIN_HA_VERSION,
        ),
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


async def test_unload_entry_cancels_scheduled_refresh(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_hacs_integration: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that unloading the entry cancels a scheduled refresh."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon"],
            CONF_TIMES: ["03:00"],
        },
    )
    config_entry.add_to_hass(hass)

    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(),
    )

    refresh_started = asyncio.Event()
    refresh_cancelled = asyncio.Event()
    scheduled_callback: Callable[[datetime], Any] | None = None

    async def async_refresh() -> None:
        """Keep the HACS refresh running until it is cancelled."""
        refresh_started.set()

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            refresh_cancelled.set()
            raise

    def capture_callback(
        _hass: HomeAssistant,
        callback: Callable[[datetime], Any],
        **_kwargs: object,
    ) -> MagicMock:
        """Capture the scheduled callback."""
        nonlocal scheduled_callback
        scheduled_callback = callback
        return MagicMock()

    hass.data["hacs"] = MagicMock()

    with patch(
        "custom_components.hacs_refresh.scheduler.async_track_time_change",
        side_effect=capture_callback,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert scheduled_callback is not None

        runtime = config_entry.runtime_data

        with patch.object(runtime.hacs, "async_refresh", new=async_refresh):
            scheduled_callback(
                datetime(2026, 8, 31, 3, 0),  # noqa: DTZ001
            )

            await refresh_started.wait()

            assert runtime.refresh_in_progress is True

            assert await hass.config_entries.async_unload(config_entry.entry_id)
            await hass.async_block_till_done()

    assert refresh_cancelled.is_set()
    assert runtime.refresh_in_progress is False


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
