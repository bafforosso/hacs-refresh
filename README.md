# HACS Refresh

[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Home_Assistant-blue?style=flat&logo=homeassistant&logoColor=FFFFFF)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat&logo=homeassistantcommunitystore&logoColor=FFFFFF)](https://hacs.xyz/)
[![Tests](https://img.shields.io/github/actions/workflow/status/bafforosso/hacs-refresh/ci.yml?branch=main&style=flat&label=Tests)](https://github.com/bafforosso/hacs-refresh/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/bafforosso/hacs-refresh?style=flat&label=Release&color=blueviolet&logo=github&logoColor=FFFFFF)](https://github.com/bafforosso/hacs-refresh/releases)
[![License](https://img.shields.io/github/license/bafforosso/hacs-refresh?style=flat&label=License&color=yellow)](LICENSE)

A Home Assistant custom component to help you keep your installed HACS repositories up to date with scheduled or on-demand refreshes.

HACS normally checks for repository updates automatically, but detection of newly released versions can sometimes be delayed. HACS Refresh complements HACS by giving users more control over when installed repository data is refreshed, either automatically on a schedule or manually whenever needed.

> *HACS Refresh does not install or upgrade repositories; it only refreshes the metadata HACS uses to detect available updates. Any available update will then appear in Home Assistant's Updates.*

## Features

- **Automatic refresh** — configure refreshes for selected days and times or disable.
- **Manual refresh** — trigger an immediate refresh from the **Refresh** button or action.
- **Refresh progress** — monitor the progress of a currently running refresh.
- **Refresh completed event** — report details of the last refresh and trigger automations when it completes.
- **Status sensor** — monitor the current refresh state.
- **Refresh protection** — prevent scheduled refreshes from running too frequently or overlapping.
- **Diagnostics** — view configuration and runtime details for troubleshooting.

## Requirements

- **Home Assistant 2024.12.0 or newer**
- **HACS 2.0.0 or newer**

## Installation

### HACS (recommended)

HACS Refresh is not currently available in the default repositories and needs to be installed as a custom repository.

1. Add the repository as a custom repository in HACS:

[![Open HACS Repository On My Home Assistant](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=hacs-refresh&owner=bafforosso&category=Integration)

2. Find **HACS Refresh** in HACS and **Download**.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **HACS Refresh** and configure it.

Alternatively, you can add the repository manually:

1. Open **HACS** in Home Assistant.
2. Open the **three-dot menu** in the top-right corner.
3. Select **Custom repositories**.
4. Enter the repository URL:
   `https://github.com/bafforosso/hacs-refresh`
5. Select **Integration** as the repository type.
6. Click **ADD**.
7. Find **HACS Refresh** in HACS and **Download**.
8. Restart Home Assistant.
9. Go to **Settings → Devices & services → Add integration**.
10. Search for **HACS Refresh** and configure it.

### Manual Installation

1. Download the files from the GitHub repository.
2. Place the `custom_components/hacs_refresh` directory into your Home Assistant `custom_components` directory.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **HACS Refresh** and configure it.

## Configuration

HACS Refresh lets you control when automatic refreshes run.

- **Automatic refresh** — enable or disable scheduled automatic refreshes.
- **Days of the week** — choose one or more days on which automatic refreshes should run.
- **Refresh times** — choose one or more times of day for the refreshes.

Refresh times must use the `HH:MM` format and be separated by commas. For example: `03:00, 15:00`

The automatic refresh settings can be configured during setup or later through the integration's configuration. It can also be enabled or disabled at any time using the **Automatic refresh** switch.

<sub>*When automatic refresh is enabled, at least one day and one time must be configured. Up to 10 refresh times can be configured, and each refresh time must be at least 10 minutes apart.*</sub>

## Manual Refresh

A manual refresh can be triggered using the **Refresh** button.

The `hacs_refresh.refresh` action can be used from automations, scripts, or other Home Assistant actions. The action returns the total repository count, successful, failed, and pending counts, the names of repositories that failed or were not processed, and the refresh duration.

```yaml
action: hacs_refresh.refresh
response_variable: refresh_result
```

The response `data` contains:

| Field | Type | Description |
| --- | :---: | --- |
| `repositories` | `int` | Total number of repositories included in the refresh. |
| `successful` | `int` | Number of repositories refreshed successfully. |
| `failed` | `int` | Number of repositories that failed to refresh. |
| `pending` | `int` | Number of repositories that were not processed. |
| `failed_repositories` | `list[str]` | Full names of repositories that failed to refresh. |
| `pending_repositories` | `list[str]` | Full names of repositories that were not processed. |
| `duration` | `float` | Refresh duration in seconds. |

Manual refreshes can be triggered regardless of whether automatic refreshes are enabled.

> [!WARNING]
> Manual refreshes bypass refresh protection. Use the `hacs_refresh.refresh` action carefully when calling it from automations or scripts to avoid unintended repeated refreshes.

## Automatic Refresh Switch

`switch.hacs_refresh_automatic_refresh`

The **Automatic refresh** switch controls whether scheduled automatic refreshes are enabled.

Its attributes provide the configured automatic refresh schedule and the next scheduled refresh:

| Attribute | Type | Values / Format | Description |
| --- | :---: | :---: | --- |
| `schedule_days` | `list[str]` | `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` | Days configured for automatic refreshes. |
| `schedule_times` | `list[str]` | `HH:MM` | Times configured for automatic refreshes. |
| `next_refresh` | `str \| null` | ISO 8601 datetime | Date and time of the next scheduled automatic refresh, or `null` when automatic refresh is disabled or no next refresh is scheduled. |

The configured schedule remains available when automatic refresh is disabled. `next_refresh` is `null` while automatic refresh is disabled.

## Status Sensor

`sensor.hacs_refresh_status`

Its `state` shows whether a refresh is currently running:

| State | Description |
| --- | --- |
| `idle` | No refresh is currently running. |
| `refreshing` | A refresh is currently in progress. |

## Refresh Progress Sensor

`sensor.hacs_refresh_progress`

Its `state` shows the progress of the currently running refresh as a percentage.

| State | Description |
| --- | --- |
| `unknown` | No refresh is currently running. |
| `0`–`99 %` | A refresh is in progress. |
| `100 %` | The refresh has completed processing all repositories. |

When no repositories are installed, the sensor briefly reports `100 %` before returning to `unknown`.

The progress sensor can be displayed as a horizontal progress bar using Home Assistant's native Tile card `bar-gauge` feature.

### Tile card progress bar example
```yaml
type: tile
entity: sensor.hacs_refresh_progress
features:
  - type: bar-gauge
    min: 0
    max: 100
```

## Refresh Completed Event

The integration provides an event entity:

`event.hacs_refresh_refresh_completed`

The event is triggered when a refresh completes with a recorded result and can be used in automations or other Home Assistant features for monitoring or follow-up actions.

The event is not triggered when a scheduled refresh is skipped before it starts, or when a refresh is cancelled.

Its `state` is the timestamp of the most recent completed refresh:

| Type | Format | Description |
| --- | --- | --- |
| string | ISO 8601 datetime | Timestamp of the most recent completed refresh. |

The refresh result is reported by `event_type`:

| Event type | Description |
| --- | --- |
| `success` | The refresh completed successfully for all repositories. |
| `partial` | The refresh completed with one or more repositories still pending. |
| `failed` | The refresh completed with one or more repositories failing to refresh. |

Its `attributes` provide further details about the refresh:

| Attribute | Type | Presence | Values / Format | Description |
| --- | :---: | :---: | :---: | --- |
| `source` | `str` | Always | `scheduled`, `manual` | What triggered the refresh. |
| `duration` | `float` | Always | Seconds | Duration of the completed refresh. |
| `repositories` | `int` | Always | ≥ 0 | Total number of repositories included in the refresh. |
| `successful` | `int` | Always | ≥ 0 | Number of repositories refreshed successfully. |
| `failed` | `int` | Always | ≥ 0 | Number of repositories that failed to refresh. |
| `pending` | `int` | Always | ≥ 0 | Number of repositories that remain pending. |
| `failed_repositories` | `list[str]` | Always | Repository full names | Repositories that failed to refresh. |
| `pending_repositories` | `list[str]` | Always | Repository full names | Repositories that were not processed. |
| `message` | `str` | Conditional | Human-readable text | Refresh issue or error. |

The `message` field is included when the refresh produces a message and omitted otherwise.

## License

Copyright © 2026 Frédéric Rouge

HACS Refresh is licensed under the GNU General Public License v3.0 or later.
See the [LICENSE](LICENSE) file for the full license text.
