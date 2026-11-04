"""Compatibility imports for Home Assistant test helpers.

The official pytest-homeassistant package is used by the current test stack.
The minimum-compatibility CI job still uses the legacy package because the
official package requires Python 3.14.2 or newer.
"""

try:
    from pytest_homeassistant.common import (
        MockConfigEntry,
        MockModule,
        mock_integration,
    )
except ModuleNotFoundError as err:
    if err.name != "pytest_homeassistant":
        raise

    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry,
        MockModule,
        mock_integration,
    )

__all__ = ["MockConfigEntry", "MockModule", "mock_integration"]
