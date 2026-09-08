"""Config flow for HACS Refresh."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from itertools import pairwise
from typing import Any, override

import voluptuous as vol
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaCommonFlowHandler,
    SchemaConfigFlowHandler,
    SchemaFlowError,
    SchemaFlowFormStep,
)

from .const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DEFAULT_AUTOMATIC_REFRESH,
    DEFAULT_DAYS,
    DEFAULT_TIMES,
    DOMAIN,
    INTEGRATION_NAME,
    MAX_TIMES,
    MIN_REFRESH_INTERVAL,
    WEEKDAYS,
)


async def _options_schema(
    handler: SchemaCommonFlowHandler,
) -> vol.Schema:
    """Build the HACS Refresh configuration schema."""
    options = handler.options

    return vol.Schema(
        {
            vol.Required(
                CONF_AUTOMATIC_REFRESH,
                default=options.get(
                    CONF_AUTOMATIC_REFRESH,
                    DEFAULT_AUTOMATIC_REFRESH,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_DAYS,
                default=options.get(
                    CONF_DAYS,
                    DEFAULT_DAYS,
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(WEEKDAYS),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="weekday",
                )
            ),
            vol.Optional(
                CONF_TIMES,
                default=", ".join(
                    options.get(
                        CONF_TIMES,
                        DEFAULT_TIMES,
                    )
                ),
            ): selector.TextSelector(),
        }
    )


async def _suggested_values(
    handler: SchemaCommonFlowHandler,
) -> dict[str, Any]:
    """Return stored options in the form's expected representation."""
    options = handler.options

    suggested = dict(options)

    if CONF_TIMES in suggested:
        suggested[CONF_TIMES] = ", ".join(suggested[CONF_TIMES])

    return suggested


async def _validate_options(
    handler: SchemaCommonFlowHandler,
    user_input: dict[str, Any],
) -> dict[str, Any]:
    """Validate and normalize HACS Refresh options."""
    automatic_refresh = user_input[CONF_AUTOMATIC_REFRESH]
    days = user_input.get(CONF_DAYS, [])

    try:
        times = _parse_times(user_input.get(CONF_TIMES, ""))
    except ValueError as err:
        raise SchemaFlowError("invalid_time") from err

    if automatic_refresh:
        if not days:
            raise SchemaFlowError("no_days")

        if not times:
            raise SchemaFlowError("no_times")

    if len(times) > MAX_TIMES:
        raise SchemaFlowError("too_many_times")

    try:
        _validate_refresh_intervals(times)
    except ValueError as err:
        raise SchemaFlowError("times_too_close") from err

    return {
        CONF_AUTOMATIC_REFRESH: automatic_refresh,
        CONF_DAYS: _sort_days(days),
        CONF_TIMES: times,
    }


def _sort_days(
    days: list[str],
) -> list[str]:
    """Return weekdays in Monday-to-Sunday order."""
    selected_days = set(days)

    return [day for day in WEEKDAYS if day in selected_days]


def _parse_times(
    value: str,
) -> list[str]:
    """Parse and normalize comma-separated HH:MM times."""
    if not isinstance(value, str):
        raise TypeError

    result: set[str] = set()

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        parsed = datetime.strptime(  # noqa: DTZ007
            item,
            "%H:%M",
        )

        result.add(parsed.strftime("%H:%M"))

    return sorted(result)


def _validate_refresh_intervals(times: list[str]) -> None:
    """Validate the minimum interval between configured refresh times."""
    if len(times) < 2:
        return

    minutes = sorted(
        int(hour) * 60 + int(minute)
        for hour, minute in (time_string.split(":") for time_string in times)
    )

    minimum_minutes = int(MIN_REFRESH_INTERVAL.total_seconds() // 60)

    for current, following in pairwise(minutes):
        if following - current < minimum_minutes:
            raise ValueError

    overnight_interval = (24 * 60 - minutes[-1]) + minutes[0]

    if overnight_interval < minimum_minutes:
        raise ValueError


CONFIG_FLOW = {
    "user": SchemaFlowFormStep(
        schema=_options_schema,
        suggested_values=_suggested_values,
        validate_user_input=_validate_options,
    ),
}


OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(
        schema=_options_schema,
        suggested_values=_suggested_values,
        validate_user_input=_validate_options,
    ),
}


class HacsRefreshConfigFlow(
    SchemaConfigFlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow for HACS Refresh."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    VERSION = 1

    @override
    def async_config_entry_title(
        self,
        options: Mapping[str, Any],
    ) -> str:
        """Return the config entry title."""
        return INTEGRATION_NAME
