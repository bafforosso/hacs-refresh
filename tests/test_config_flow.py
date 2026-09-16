from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowError,
)
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockModule,
    mock_integration,
)

from custom_components.hacs_refresh.config_flow import (
    _options_schema,
    _parse_times,
    _sort_days,
    _suggested_values,
    _validate_options,
    _validate_refresh_intervals,
)
from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DEFAULT_AUTOMATIC_REFRESH,
    DEFAULT_DAYS,
    DEFAULT_TIMES,
    DOMAIN,
    MAX_TIMES,
)


@pytest.fixture
def mock_hacs_integration(hass: HomeAssistant) -> None:
    """Mock the HACS integration dependency."""
    mock_integration(
        hass,
        MockModule("hacs"),
        built_in=False,
    )


def test_parse_times_normalizes_and_sorts() -> None:
    """Test that times are normalized, sorted, and deduplicated."""
    assert _parse_times("15:30, 03:00, 15:30, 9:05") == [
        "03:00",
        "09:05",
        "15:30",
    ]


@pytest.mark.parametrize(
    "value",
    [
        "25:00",
        "12:60",
        "abc",
        "12",
        "12:30:00",
    ],
)
def test_parse_times_rejects_invalid_times(value: str) -> None:
    """Test that invalid time values raise ValueError."""
    with pytest.raises(ValueError):
        _parse_times(value)


def test_parse_times_rejects_non_string() -> None:
    """Test that non-string values are rejected."""
    with pytest.raises(TypeError):
        _parse_times(None)  # type: ignore[arg-type]


def test_sort_days_returns_monday_to_sunday_order() -> None:
    """Test that selected weekdays are returned in calendar order."""
    assert _sort_days(["sun", "wed", "mon", "sat"]) == [
        "mon",
        "wed",
        "sat",
        "sun",
    ]


async def test_validate_options_returns_normalized_options() -> None:
    """Test that valid options are normalized correctly."""
    handler = MagicMock()
    handler.options = {}

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["sun", "mon", "wed"],
        CONF_TIMES: "15:30, 03:00, 15:30",
    }

    result = await _validate_options(
        handler,
        user_input,
    )

    assert result == {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon", "wed", "sun"],
        CONF_TIMES: ["03:00", "15:30"],
    }


async def test_validate_options_allows_disabled_automatic_refresh() -> None:
    """Test that automatic refresh can be disabled without a schedule."""
    handler = MagicMock()

    user_input = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: [],
        CONF_TIMES: "",
    }

    result = await _validate_options(
        handler,
        user_input,
    )

    assert result == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: [],
        CONF_TIMES: [],
    }


async def test_validate_options_accepts_schedule_when_disabled() -> None:
    """Test that a schedule can be configured while automatic refresh is disabled."""
    handler = MagicMock()

    user_input = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["fri"],
        CONF_TIMES: "22:00",
    }

    result = await _validate_options(
        handler,
        user_input,
    )

    assert result == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["fri"],
        CONF_TIMES: ["22:00"],
    }


async def test_validate_options_allows_partial_schedule_when_disabled() -> None:
    """Test that an incomplete schedule is allowed when automatic refresh is disabled."""
    handler = MagicMock()

    user_input = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["fri"],
        CONF_TIMES: "",
    }

    result = await _validate_options(
        handler,
        user_input,
    )

    assert result == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["fri"],
        CONF_TIMES: [],
    }


async def test_validate_options_rejects_no_days() -> None:
    """Test that at least one weekday must be selected."""
    handler = MagicMock()
    handler.options = {}

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: [],
        CONF_TIMES: "03:00",
    }

    with pytest.raises(
        SchemaFlowError,
        match="no_days",
    ):
        await _validate_options(
            handler,
            user_input,
        )


async def test_validate_options_rejects_invalid_time() -> None:
    """Test that invalid time input raises the expected flow error."""
    handler = MagicMock()
    handler.options = {}

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon"],
        CONF_TIMES: "25:00",
    }

    with pytest.raises(
        SchemaFlowError,
        match="invalid_time",
    ):
        await _validate_options(
            handler,
            user_input,
        )


async def test_validate_options_rejects_invalid_time_when_disabled() -> None:
    """Test that invalid times are rejected when automatic refresh is disabled."""
    handler = MagicMock()

    user_input = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: [],
        CONF_TIMES: "25:00",
    }

    with pytest.raises(
        SchemaFlowError,
        match="invalid_time",
    ):
        await _validate_options(
            handler,
            user_input,
        )


async def test_validate_options_rejects_no_times() -> None:
    """Test that at least one refresh time must be provided."""
    handler = MagicMock()
    handler.options = {}

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon"],
        CONF_TIMES: "",
    }

    with pytest.raises(
        SchemaFlowError,
        match="no_times",
    ):
        await _validate_options(
            handler,
            user_input,
        )


async def test_validate_options_rejects_too_many_times() -> None:
    """Test that more than the allowed number of times is rejected."""
    handler = MagicMock()
    handler.options = {}

    times = ", ".join(f"{hour:02d}:00" for hour in range(MAX_TIMES + 1))

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon"],
        CONF_TIMES: times,
    }

    with pytest.raises(
        SchemaFlowError,
        match="too_many_times",
    ):
        await _validate_options(
            handler,
            user_input,
        )


@pytest.mark.parametrize(
    ("times", "valid"),
    [
        (["03:00"], True),
        (["03:00", "03:10"], True),
        (["03:00", "03:09"], False),
        (["03:00", "03:11", "12:00"], True),
        (["23:55", "00:04"], False),
        (["23:55", "00:05"], True),
    ],
)
def test_validate_refresh_intervals(
    times: list[str],
    valid: bool,
) -> None:
    """Test minimum intervals between configured refresh times."""
    if valid:
        _validate_refresh_intervals(times)
    else:
        with pytest.raises(ValueError):
            _validate_refresh_intervals(times)


async def test_validate_options_rejects_times_too_close() -> None:
    """Test that refresh times closer than the minimum are rejected."""
    handler = MagicMock()
    handler.options = {}

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon"],
        CONF_TIMES: "03:00, 03:09",
    }

    with pytest.raises(
        SchemaFlowError,
        match="times_too_close",
    ):
        await _validate_options(
            handler,
            user_input,
        )


async def test_suggested_values_formats_stored_times() -> None:
    """Test that stored options are converted to form values."""
    handler = MagicMock()
    handler.options = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon", "fri"],
        CONF_TIMES: ["03:00", "15:30"],
    }

    result = await _suggested_values(handler)

    assert result == {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon", "fri"],
        CONF_TIMES: "03:00, 15:30",
    }


async def test_suggested_values_without_times_returns_options() -> None:
    """Test that options without times are returned unchanged."""
    handler = MagicMock()
    handler.options = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["mon", "fri"],
    }

    result = await _suggested_values(handler)

    assert result == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["mon", "fri"],
    }


async def test_suggested_values_uses_defaults_for_config_flow() -> None:
    """Test that the initial config flow uses default suggested values."""
    handler = MagicMock()
    handler.options = {}
    handler.parent_handler = MagicMock(spec=SchemaConfigFlowHandler)

    result = await _suggested_values(handler)

    assert result == {
        CONF_AUTOMATIC_REFRESH: DEFAULT_AUTOMATIC_REFRESH,
        CONF_DAYS: DEFAULT_DAYS,
        CONF_TIMES: ", ".join(DEFAULT_TIMES),
    }


async def test_options_schema_uses_defaults() -> None:
    """Test that the options schema uses the configured defaults."""
    handler = MagicMock()
    handler.options = {}

    schema = await _options_schema(handler)

    result = schema({})

    assert result == {
        CONF_AUTOMATIC_REFRESH: DEFAULT_AUTOMATIC_REFRESH,
        CONF_DAYS: DEFAULT_DAYS,
    }


async def test_options_schema_uses_existing_options() -> None:
    """Test that the options schema uses existing options."""
    handler = MagicMock()
    handler.options = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["tue", "fri"],
        CONF_TIMES: ["06:30", "18:00"],
    }

    schema = await _options_schema(handler)

    result = schema({})

    assert result == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: ["tue", "fri"],
    }


async def test_user_flow(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_hacs_integration: None,
) -> None:
    """Test the user config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") is None

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["sun", "mon", "wed"],
        CONF_TIMES: "15:30, 03:00, 15:30",
    }

    with patch(
        "custom_components.hacs_refresh.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "HACS Refresh"
    assert result.get("data") == {}
    assert result.get("options") == {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon", "wed", "sun"],
        CONF_TIMES: ["03:00", "15:30"],
    }

    assert mock_setup_entry.await_count == 1

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].options == result.get("options")


async def test_user_flow_recovers_from_validation_error(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_hacs_integration: None,
) -> None:
    """Test that the user flow recovers from invalid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    invalid_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: [],
        CONF_TIMES: "03:00",
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        invalid_input,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": "no_days"}

    valid_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon"],
        CONF_TIMES: "03:00",
    }

    with patch(
        "custom_components.hacs_refresh.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            valid_input,
        )
        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "HACS Refresh"
    assert result.get("data") == {}
    assert result.get("options") == {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["mon"],
        CONF_TIMES: ["03:00"],
    }

    assert mock_setup_entry.await_count == 1


async def test_user_flow_rejects_second_config_entry(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_hacs_integration: None,
) -> None:
    """Test that only one config entry can be configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_AUTOMATIC_REFRESH: False,
            CONF_DAYS: [],
            CONF_TIMES: [],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_options_flow(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_hacs_integration: None,
) -> None:
    """Test the options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon", "fri"],
            CONF_TIMES: ["03:00", "15:30"],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert result.get("errors") is None

    user_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["sun", "tue"],
        CONF_TIMES: "18:00, 06:00",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input,
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: ["tue", "sun"],
        CONF_TIMES: ["06:00", "18:00"],
    }
    assert entry.options == result.get("data")


async def test_options_flow_recovers_from_validation_error(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_hacs_integration: None,
) -> None:
    """Test that the options flow recovers from invalid input."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_AUTOMATIC_REFRESH: True,
            CONF_DAYS: ["mon"],
            CONF_TIMES: ["03:00"],
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    invalid_input = {
        CONF_AUTOMATIC_REFRESH: True,
        CONF_DAYS: [],
        CONF_TIMES: "03:00",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        invalid_input,
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert result.get("errors") == {"base": "no_days"}

    valid_input = {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: [],
        CONF_TIMES: "",
    }

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        valid_input,
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("data") == {
        CONF_AUTOMATIC_REFRESH: False,
        CONF_DAYS: [],
        CONF_TIMES: [],
    }
    assert entry.options == result.get("data")
