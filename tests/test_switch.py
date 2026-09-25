from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hacs_refresh.const import (
    AUTOMATIC_REFRESH_SWITCH_UNIQUE_ID,
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DOMAIN,
)
from custom_components.hacs_refresh.switch import (
    HacsRefreshAutomaticRefreshSwitch,
    async_setup_entry,
)


@pytest.mark.parametrize("automatic_refresh", [True, False])
def test_automatic_refresh_switch_initializes(
    automatic_refresh: bool,
) -> None:
    """Test that the automatic refresh switch reflects its configuration."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.entry.options = {
        CONF_AUTOMATIC_REFRESH: automatic_refresh,
    }

    switch = HacsRefreshAutomaticRefreshSwitch(runtime)

    assert switch.runtime is runtime
    assert switch.is_on is automatic_refresh
    assert switch.unique_id == AUTOMATIC_REFRESH_SWITCH_UNIQUE_ID
    assert switch._attr_translation_key == "automatic_refresh"
    assert switch.entity_category == EntityCategory.CONFIG
    assert switch.should_poll is False
    runtime.add_listener.assert_not_called()


@pytest.mark.parametrize(
    ("automatic_refresh", "next_refresh", "expected_next_refresh"),
    [
        (
            True,
            datetime(2026, 9, 4, 14, 0, tzinfo=UTC),
            "2026-09-04T14:00:00+00:00",
        ),
        (True, None, None),
        (
            False,
            datetime(2026, 9, 4, 14, 0, tzinfo=UTC),
            None,
        ),
    ],
)
def test_automatic_refresh_switch_exposes_schedule_and_next_refresh(
    automatic_refresh: bool,
    next_refresh: datetime | None,
    expected_next_refresh: str | None,
) -> None:
    """Test that the switch exposes configured schedule and scheduler state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    runtime.entry.options = {
        CONF_AUTOMATIC_REFRESH: automatic_refresh,
        CONF_DAYS: ["mon", "wed", "fri"],
        CONF_TIMES: ["02:30", "14:00"],
    }
    runtime.scheduler.next_refresh = next_refresh

    switch = HacsRefreshAutomaticRefreshSwitch(runtime)

    assert switch.extra_state_attributes == {
        "schedule_days": ["mon", "wed", "fri"],
        "schedule_times": ["02:30", "14:00"],
        "next_refresh": expected_next_refresh,
    }


async def test_switch_setup_entry(hass: HomeAssistant) -> None:
    """Test that the automatic refresh switch is created for the config entry."""
    runtime = MagicMock()
    entry = MagicMock()
    entry.runtime_data = runtime
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)

    add_entities.assert_called_once()
    entities = add_entities.call_args.args[0]

    assert len(entities) == 1
    assert isinstance(entities[0], HacsRefreshAutomaticRefreshSwitch)
    assert entities[0].runtime is runtime


async def test_automatic_refresh_switch_registers_runtime_listener() -> None:
    """Test that the switch registers its runtime listener when added to HA."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"
    remove_listener = MagicMock()
    runtime.add_listener.return_value = remove_listener

    switch = HacsRefreshAutomaticRefreshSwitch(runtime)

    with patch.object(switch, "async_on_remove") as mock_async_on_remove:
        await switch.async_added_to_hass()

    runtime.add_listener.assert_called_once_with(switch._async_runtime_updated)
    mock_async_on_remove.assert_called_once_with(remove_listener)


def test_automatic_refresh_switch_runtime_update_writes_state() -> None:
    """Test that a runtime update causes the switch to write its state."""
    runtime = MagicMock()
    runtime.entry.entry_id = "test-entry"

    switch = HacsRefreshAutomaticRefreshSwitch(runtime)

    with patch.object(switch, "async_write_ha_state") as mock_write_state:
        switch._async_runtime_updated()

    mock_write_state.assert_called_once_with()


@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        (False, True),
        (True, False),
    ],
)
async def test_automatic_refresh_switch_updates_config_entry(
    hass: HomeAssistant,
    initial: bool,
    expected: bool,
) -> None:
    """Test that changing the switch updates the config entry options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: initial,
            CONF_DAYS: ["mon", "wed", "fri"],
            CONF_TIMES: ["02:30", "14:00"],
        },
    )
    entry.add_to_hass(hass)

    runtime = MagicMock()
    runtime.entry = entry

    switch = HacsRefreshAutomaticRefreshSwitch(runtime)
    switch.hass = hass

    if expected:
        await switch.async_turn_on()
    else:
        await switch.async_turn_off()

    assert entry.options == {
        CONF_AUTOMATIC_REFRESH: expected,
        CONF_DAYS: ["mon", "wed", "fri"],
        CONF_TIMES: ["02:30", "14:00"],
    }
