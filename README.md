# HACS Refresh

[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Homeassistant-blue?style=flat&logo=homeassistant&logoColor=FFFFFF)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat&logo=homeassistantcommunitystore&logoColor=FFFFFF)](https://hacs.xyz/)
[![Tests](https://img.shields.io/github/actions/workflow/status/bafforosso/hacs-refresh/ci.yml?branch=main&style=flat&label=Tests)](https://github.com/bafforosso/hacs-refresh/actions/workflows/ci.yml)
[![GitHub Release](https://img.shields.io/github/v/release/bafforosso/hacs-refresh?style=flat&logo=github&logoColor=FFFFFF)](https://github.com/bafforosso/hacs-refresh/releases)
![GitHub License](https://img.shields.io/github/license/bafforosso/hacs-refresh?style=flat)

A Home Assistant custom component to help you keep your installed HACS repositories up to date with scheduled or on-demand refreshes.

HACS normally checks for repository updates automatically, but detection of newly released versions can sometimes be delayed. HACS Refresh complements HACS by giving users more control over when installed repository data is refreshed, either automatically on a schedule or manually whenever needed.

> *HACS Refresh does not install or upgrade repositories; it only refreshes the metadata HACS uses to detect available updates. Any available update will then appear in Home Assistant's Updates.*

## Features

- **Automatic refresh** — configure refreshes for selected days and times or disable.
- **Manual refresh** — trigger an immediate refresh from the **Refresh** button or action.
- **Refresh protection** — prevent scheduled refreshes from running too frequently.
- **Refresh completed event** — report details of the last refresh and trigger automations when it completes.
- **Status sensor** — monitor refresh state and schedule configuration.
- **Diagnostics** — view configuration and runtime details for troubleshooting.

## Requirements

- **Home Assistant 2024.12.0 or newer**
- **HACS 2.0.0 or newer**

## Installation

### HACS (recommended)

HACS Refresh is not currently available in the default repositories, it needs to be installed as a custom repository.

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

## Manual Refresh

A manual refresh can be triggered using the **Refresh** button.

The `hacs_refresh.refresh` action can be used from automations, scripts, or other Home Assistant actions.

Manual refreshes can be triggered regardless of whether automatic refreshes are enabled.

> [!WARNING]
> Manual refreshes bypass refresh protection. Use the `hacs_refresh.refresh` action carefully when calling it from automations or scripts to avoid unintended repeated refreshes.

## Status Sensor

The integration creates:

`sensor.hacs_refresh_status`

The sensor **state** shows whether a refresh is currently running:

- `idle` — no refresh is currently running.
- `refreshing` — a refresh is currently in progress.

The sensor's **attributes** provide details about the configured automatic refresh schedule:

| Attribute | Description |
| --- | --- |
| `automatic_refresh` | Whether automatic refresh is enabled. |
| `schedule_days` | Days configured for automatic refreshes. |
| `schedule_times` | Times configured for automatic refreshes. |
| `next_refresh` | Date and time of the next scheduled automatic refresh, or `null` when automatic refresh is disabled. |

## Refresh Completed Event

The integration provides an event entity:

`event.hacs_refresh_refresh_completed`

The event fires whenever an actual refresh attempt completes and can be used in automations or other Home Assistant features or for monitoring.
Its state contains the timestamp of the most recent completed refresh, while the event data provides details about that refresh.

| Data | Description |
| --- | --- |
| `event_type` | Result of the refresh: `success`, `partial`, or `failed`. |
| `source` | What triggered the refresh, such as `scheduled` or `manual`. |
| `duration` | Duration of the refresh in seconds. |
| `repositories` | Total number of repositories included in the refresh. |
| `successful` | Number of repositories refreshed successfully. |
| `failed` | Number of repositories that failed to refresh. |
| `pending` | Number of repositories that remain pending. |
| `message` | Human-readable message describing a partial or failed refresh. |
