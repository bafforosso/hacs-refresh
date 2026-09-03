"""Config flow for HACS Refresh."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AUTOMATIC_REFRESH,
    CONF_DAYS,
    CONF_TIMES,
    DEFAULT_AUTOMATIC_REFRESH,
    DEFAULT_DAYS,
    DEFAULT_TIMES,
    DOMAIN,
    MAX_TIMES,
)


class HacsRefreshConfigFlow(
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Handle a config flow for HACS Refresh."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the user setup step."""
        if user_input is not None:
            return self.async_create_entry(
                title="HACS Refresh",
                data={},
            )

        return self.async_show_form(
            step_id="user"
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HacsRefreshOptionsFlow:
        """Return the options flow."""
        return HacsRefreshOptionsFlow()


class HacsRefreshOptionsFlow(
    config_entries.OptionsFlowWithReload,
):
    """Handle HACS Refresh options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage HACS Refresh options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                times = _parse_times(
                    user_input[CONF_TIMES]
                )
            except ValueError:
                times = []
                errors[CONF_TIMES] = "invalid_time"

            days = user_input.get(
                CONF_DAYS,
                [],
            )

            if not days:
                errors[CONF_DAYS] = "no_days"

            if not times:
                errors[CONF_TIMES] = "no_times"
            elif len(times) > MAX_TIMES:
                errors[CONF_TIMES] = "too_many_times"

            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_AUTOMATIC_REFRESH: user_input[
                            CONF_AUTOMATIC_REFRESH
                        ],
                        CONF_DAYS: days,
                        CONF_TIMES: times,
                    }
                )

        options = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_AUTOMATIC_REFRESH,
                    default=options.get(
                        CONF_AUTOMATIC_REFRESH,
                        DEFAULT_AUTOMATIC_REFRESH,
                    ),
                ): selector.BooleanSelector(),
                vol.Required(
                    CONF_DAYS,
                    default=options.get(
                        CONF_DAYS,
                        DEFAULT_DAYS,
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value="mon",
                                label="Monday",
                            ),
                            selector.SelectOptionDict(
                                value="tue",
                                label="Tuesday",
                            ),
                            selector.SelectOptionDict(
                                value="wed",
                                label="Wednesday",
                            ),
                            selector.SelectOptionDict(
                                value="thu",
                                label="Thursday",
                            ),
                            selector.SelectOptionDict(
                                value="fri",
                                label="Friday",
                            ),
                            selector.SelectOptionDict(
                                value="sat",
                                label="Saturday",
                            ),
                            selector.SelectOptionDict(
                                value="sun",
                                label="Sunday",
                            ),
                        ],
                        multiple=True,
                    )
                ),
                vol.Required(
                    CONF_TIMES,
                    default=", ".join(
                        options.get(
                            CONF_TIMES,
                            DEFAULT_TIMES,
                        )
                    ),
                ): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )


def _parse_times(
    value: str,
) -> list[str]:
    """Parse and normalize comma-separated HH:MM times."""
    if not isinstance(value, str):
        raise ValueError

    result: set[str] = set()

    for item in value.split(","):
        item = item.strip()

        if not item:
            continue

        parsed = datetime.strptime(
            item,
            "%H:%M",
        )

        result.add(
            parsed.strftime("%H:%M")
        )

    return sorted(result)
