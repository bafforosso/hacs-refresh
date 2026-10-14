from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
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


@pytest.mark.parametrize(
    ("days", "times"),
    [
        ([], ["02:30"]),
        (["mon"], []),
        ([], []),
    ],
)
async def test_automatic_refresh_switch_rejects_incomplete_schedule(
    hass: HomeAssistant,
    days: list[str],
    times: list[str],
) -> None:
    """Test that automatic refresh cannot be enabled without a complete schedule."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_AUTOMATIC_REFRESH: False,
            CONF_DAYS: days,
            CONF_TIMES: times,
        },
    )
    entry.add_to_hass(hass)

    runtime = MagicMock()
    runtime.entry = entry

    switch = HacsRefreshAutomaticRefreshSwitch(runtime)
    switch.hass = hass

    with pytest.raises(ServiceValidationError) as err:
        await switch.async_turn_on()

    assert err.value.translation_key == "automatic_refresh_schedule_required"
    assert entry.options == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: days,
        CONF_TIMES: times,
    }


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
