from datetime import UTC, datetime

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DEFAULT_AUTOMATIC_REFRESH,
    DEFAULT_DAYS,
    DEFAULT_TIMES,
    DOMAIN,
)
from custom_components.hacs_refresh.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.hacs_refresh.runtime import HacsRefreshRuntimeData


async def test_diagnostics_default_values(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics with default configuration and runtime state."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    entry.runtime_data = runtime

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics == {
        "config": {
            CONF_AUTOMATIC_REFRESH: DEFAULT_AUTOMATIC_REFRESH,
            CONF_DAYS: DEFAULT_DAYS,
            CONF_TIMES: DEFAULT_TIMES,
        },
        "runtime": {
            "state": "idle",
            "last_completed": None,
            "last_result": None,
            "last_source": None,
            "last_repositories": 0,
            "last_successful": 0,
            "last_failed": 0,
            "last_pending": 0,
            "last_duration": None,
        },
    }


async def test_diagnostics_custom_configuration(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics with configured options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: False,
            CONF_DAYS: ["mon", "fri"],
            CONF_TIMES: ["03:00", "15:00"],
        },
    )
    runtime = HacsRefreshRuntimeData(hass, entry)
    entry.runtime_data = runtime

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["config"] == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["mon", "fri"],
        CONF_TIMES: ["03:00", "15:00"],
    }


async def test_diagnostics_runtime_state(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics with populated runtime state."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    entry.runtime_data = runtime

    runtime.state = "idle"
    runtime.last_completed = datetime(
        2026,
        1,
        1,
        2,
        30,
        tzinfo=UTC,
    )
    runtime.last_result = "success"
    runtime.last_source = "manual"
    runtime.last_repositories = 5
    runtime.last_successful = 4
    runtime.last_failed = 1
    runtime.last_pending = 0
    runtime.last_duration = 2.5

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["runtime"] == {
        "state": "idle",
        "last_completed": "2026-01-01T02:30:00+00:00",
        "last_result": "success",
        "last_source": "manual",
        "last_repositories": 5,
        "last_successful": 4,
        "last_failed": 1,
        "last_pending": 0,
        "last_duration": 2.5,
    }


async def test_diagnostics_excludes_error(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics do not expose the runtime error."""
    entry = MockConfigEntry(domain=DOMAIN)
    runtime = HacsRefreshRuntimeData(hass, entry)
    entry.runtime_data = runtime

    runtime.last_error = "sensitive or uncontrolled error information"

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert "last_error" not in diagnostics["runtime"]
