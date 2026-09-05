from unittest.mock import MagicMock

import pytest
from homeassistant.helpers.schema_config_entry_flow import SchemaFlowError

from custom_components.hacs_refresh.config_flow import (
    _options_schema,
    _parse_times,
    _sort_days,
    _suggested_values,
    _validate_options,
)
from custom_components.hacs_refresh.const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DEFAULT_AUTOMATIC_REFRESH,
    DEFAULT_DAYS,
    DEFAULT_TIMES,
    MAX_TIMES,
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
    from custom_components.hacs_refresh.config_flow import (
        _validate_refresh_intervals,
    )

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


async def test_options_schema_uses_defaults() -> None:
    """Test that the options schema uses the configured defaults."""
    handler = MagicMock()
    handler.options = {}

    schema = await _options_schema(handler)

    result = schema({})

    assert result == {
        CONF_AUTOMATIC_REFRESH: DEFAULT_AUTOMATIC_REFRESH,
        CONF_DAYS: DEFAULT_DAYS,
        CONF_TIMES: ", ".join(DEFAULT_TIMES),
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
        CONF_TIMES: "06:30, 18:00",
    }


def test_config_flow_can_be_initialized() -> None:
    """Test that the HACS Refresh config flow can be initialized."""
    from custom_components.hacs_refresh.config_flow import (
        HacsRefreshConfigFlow,
    )

    flow = HacsRefreshConfigFlow()

    assert flow.async_config_entry_title({}) == "HACS Refresh"
