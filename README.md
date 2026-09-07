# HACS Refresh

[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Homeassistant-blue?style=flat&logo=homeassistant&logoColor=FFFFFF)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat&logo=homeassistantcommunitystore&logoColor=FFFFFF)](https://hacs.xyz/)
[![Tests](https://img.shields.io/github/actions/workflow/status/bafforosso/hacs-refresh/tests.yml?style=flat&label=Tests)](https://github.com/bafforosso/hacs-refresh/actions/workflows/tests.yml)
[![GitHub Release](https://img.shields.io/github/v/release/bafforosso/hacs-refresh?style=flat&logo=github&logoColor=FFFFFF)](https://github.com/bafforosso/hacs-refresh/releases)
![GitHub License](https://img.shields.io/github/license/bafforosso/hacs-refresh?style=flat)

A Home Assistant custom integration that lets you manually or automatically refresh the metadata of all installed HACS repositories.

## Features

- **Manual refresh** — refresh all installed HACS repositories from the **Refresh** button or action.
- **Automatic refresh** — schedule refreshes for selected days and times.
- **Refresh protection** — prevent scheduled refreshes from running too frequently.
- **Status sensor** — see the current refresh status and next scheduled refresh.
- **Refresh completed event** — trigger automations when a refresh finishes.
- **Configurable** — enable or disable automatic refresh and customize its schedule.

## Requirements

- **Home Assistant 2024.12.0 or newer**
- **HACS 2.0.0 or newer**

## Installation

### HACS (recommended)

HACS Refresh is currently installed as a custom repository.

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

1. Download the integration files from the GitHub repository.
2. Place the `custom_components/hacs_refresh` directory into your Home Assistant `custom_components` directory.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **HACS Refresh** and configure it.

## Configuration

HACS Refresh lets you control when automatic refreshes run.

- **Automatic refresh** — enable or disable scheduled refreshes.
- **Days of the week** — choose one or more days on which automatic refreshes should run.
- **Refresh times** — choose one or more times of day for the refreshes.

Refresh times must use the `HH:MM` format and be separated by commas.

For example:

`03:00, 15:00`

The configured schedule applies only to automatic refreshes. Manual refreshes can also be triggered regardless of whether automatic refresh is enabled.

Refresh state is persisted across Home Assistant restarts, so the integration retains information about the most recent refresh.

## Manual Refresh

A manual refresh can be triggered using the **Refresh** button.

The `hacs_refresh.refresh` action can be used from automations, scripts, or other Home Assistant actions.

## Status Sensor

The integration creates:

`sensor.hacs_refresh_status`

The sensor **state** shows whether a refresh is currently running:

- `idle` — no refresh is currently running.
- `refreshing` — a refresh is currently in progress.

The sensor's **attributes** provide details about the most recent refresh and the configured automatic refresh schedule:

| Attribute | Description |
| --- | --- |
| `automatic_refresh` | Whether automatic refresh is enabled. |
| `schedule_days` | Days configured for automatic refreshes. |
| `schedule_times` | Times configured for automatic refreshes. |
| `next_refresh` | Date and time of the next scheduled automatic refresh, or `null` when automatic refresh is disabled. |

## Refresh Completed Event

The integration provides an event entity:

`event.hacs_refresh_refresh_completed`

The event fires whenever an actual refresh completes. The event state contains the timestamp of the most recent completed refresh and the event type indicates the result:

- `success` — all repositories refreshed successfully.
- `partial` — one or more repositories remain pending.
- `failed` — one or more repositories failed to refresh.

The event data includes the refresh source and repository counts, for example:

```yaml
event_type: success
source: scheduled
repositories: 47
successful: 47
failed: 0
pending: 0
last_error: null
```

The event type is available to automations as `success`, `partial`, or `failed`.
