# HACS Refresh

> [!WARNING]
> **HACS Refresh is deprecated. The final release is 1.3.1.**
>
> HACS Refresh is incompatible with **Home Assistant 2026.11 and newer**.
>
> Home Assistant 2026.11 replaces the separately installed HACS custom integration with the built-in Marketplace. Although the Marketplace carries over installed repositories, it does not provide the legacy HACS integration functionality that HACS Refresh depends on.
>
> **No Marketplace compatibility update is planned.**
>
> If you are still running Home Assistant 2026.10 or older, install HACS Refresh 1.3.1 before upgrading to Home Assistant 2026.11.
>
> If you upgraded to Home Assistant 2026.11 or newer while still running HACS Refresh 1.3.0, you will not receive the deprecation Repair notification introduced in 1.3.1. Follow the [removal instructions](#removing-hacs-refresh) below.

[![Made for Home Assistant](https://img.shields.io/badge/Made_for-Home_Assistant-blue?style=flat&logo=homeassistant&logoColor=FFFFFF)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange?style=flat&logo=homeassistantcommunitystore&logoColor=FFFFFF)](https://hacs.xyz/)
[![Tests](https://img.shields.io/github/actions/workflow/status/bafforosso/hacs-refresh/ci.yml?branch=main&style=flat&label=Tests)](https://github.com/bafforosso/hacs-refresh/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/bafforosso/hacs-refresh?style=flat&label=Release&color=blueviolet&logo=github&logoColor=FFFFFF)](https://github.com/bafforosso/hacs-refresh/releases)
[![License](https://img.shields.io/github/license/bafforosso/hacs-refresh?style=flat&label=License&color=yellow)](LICENSE)

HACS Refresh is a Home Assistant custom integration that refreshes metadata for repositories installed through the legacy HACS integration.

HACS Refresh was designed to complement HACS by giving users more control over when installed repository data is refreshed, either automatically on a schedule or manually whenever needed.

> *HACS Refresh does not install or upgrade repositories; it only refreshes the metadata used by HACS to detect available updates. Any available update then appears in Home Assistant's Updates.*

## Features

- **Automatic refresh** — configure refreshes for selected days and times or disable.
- **Manual refresh** — trigger an immediate refresh from the **Refresh** button or action, optionally targeting only specific repositories.
- **Refresh progress** — monitor the progress of a currently running refresh.
- **Refresh completed event** — report details of the last refresh and trigger automations when it completes.
- **Status sensor** — monitor the current refresh state.
- **Refresh protection** — prevent scheduled refreshes from running too frequently or overlapping.
- **Diagnostics** — view configuration and runtime details for troubleshooting.

## Compatibility

HACS Refresh 1.3.1 is the final release.

| Component | Supported versions |
| --- | --- |
| Home Assistant | 2024.12.0 through 2026.10.x |
| HACS | 2.0.0 or newer, on supported Home Assistant versions |

**Home Assistant 2026.11.0 and newer are not supported.**

HACS Refresh depends on the legacy HACS custom integration. Starting with Home Assistant 2026.11, HACS is replaced by the built-in Marketplace, which does not provide the legacy HACS integration functionality required by HACS Refresh.

No Marketplace compatibility update is planned.

## Installation

The installation instructions below apply only to Home Assistant 2024.12.0 through 2026.10.x.

Do not install HACS Refresh on Home Assistant 2026.11 or newer.

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

## Automatic Refresh Configuration

HACS Refresh automatically refreshes all installed HACS repositories according to the configured schedule.

- **Automatic refresh** — enable or disable scheduled automatic refreshes.
- **Days of the week** — choose one or more days on which automatic refreshes should run.
- **Refresh times** — choose one or more times of day for the refreshes.

Refresh times must use the `HH:MM` format and be separated by commas. For example: `03:00, 15:00`

The automatic refresh settings can be configured during setup or later through the integration's configuration. It can also be enabled or disabled at any time using the **Automatic refresh** switch.

<sub>*When automatic refresh is enabled, at least one day and one time must be configured. Up to 10 refresh times can be configured, and each refresh time must be at least 10 minutes apart.*</sub>

Skipped scheduled refreshes are not retried or caught up after a restart. The next attempt occurs at the next configured time.

## Manual Refresh

Manual refreshes can be triggered regardless of whether automatic refreshes are enabled.

### Refresh Button

A manual refresh can be triggered using the **Refresh** button. It refreshes all installed HACS repositories.

### Refresh Action

The `hacs_refresh.refresh` action can be used from automations, scripts, or other Home Assistant actions. If `repositories` is omitted, all installed HACS repositories are refreshed. To refresh specific repositories, provide either a single repository name or a list of full HACS repository names in the `owner/repository` format.

```yaml
action: hacs_refresh.refresh
data:
  repositories: user/repository
response_variable: refresh_result
```

```yaml
action: hacs_refresh.refresh
data:
  repositories:
    - user/repository
    - another/repository
response_variable: refresh_result
```

The response `data` contains:

| Field | Type | Description |
| --- | :---: | --- |
| `repositories` | `int` | Total number of repositories included in the refresh. |
| `successful` | `int` | Number of repository update calls that returned without raising an exception. |
| `failed` | `int` | Number of repository update calls that raised an exception reaching HACS Refresh. |
| `pending` | `int` | Number of repositories that were not processed. |
| `failed_repositories` | `list[str]` | Full names of repositories whose update calls raised an exception reaching HACS Refresh. |
| `pending_repositories` | `list[str]` | Full names of repositories whose queued update tasks had not executed when the refresh result was finalized. |
| `duration` | `float` | Refresh duration in seconds. |

A completed refresh returns its result data even when repositories fail or remain pending. Exceptions are raised if the refresh cannot produce a completed result or the repository selection is invalid.

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
| `100 %` | The refresh has completed processing all repositories included in the refresh. |

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
| `success` | No repository update calls raised an exception, and no repositories remained pending. |
| `partial` | One or more repository update tasks remained pending when the refresh result was finalized. The result may also include repository failures. |
| `failed` | One or more repository update calls raised an exception reaching HACS Refresh, and no repositories remained pending. |

> **Result limitations:** HACS Refresh reports outcomes observable through the HACS repository update interface. HACS may handle some underlying GitHub/API failures internally without propagating an exception. Consequently, a `success` event means that no repository update call reported an exception and no repositories remained pending; it is not proof that every GitHub request succeeded.

Its `attributes` provide further details about the refresh:

| Attribute | Type | Presence | Values / Format | Description |
| --- | :---: | :---: | :---: | --- |
| `source` | `str` | Always | `scheduled`, `manual` | What triggered the refresh. |
| `duration` | `float` | Always | Seconds | Duration of the completed refresh. |
| `repositories` | `int` | Always | ≥ 0 | Total number of repositories included in the refresh. |
| `successful` | `int` | Always | ≥ 0 | Number of repository update calls that returned without raising an exception. |
| `failed` | `int` | Always | ≥ 0 | Number of repository update calls that raised an exception reaching HACS Refresh. |
| `pending` | `int` | Always | ≥ 0 | Number of repositories that remain pending. |
| `failed_repositories` | `list[str]` | Conditional | Repository full names | Repositories whose update calls raised an exception reaching HACS Refresh. Included only when one or more repositories failed. |
| `pending_repositories` | `list[str]` | Conditional | Repository full names | Repositories whose queued update tasks had not executed when the refresh result was finalized. Included only when one or more repositories remain pending. |
| `message` | `str` | Conditional | Human-readable text | Refresh issue or error. |

The `message` field is included when the refresh produces a message and omitted otherwise.

## Removing HACS Refresh

Removing HACS Refresh involves two separate steps: deleting its integration entry from Home Assistant and uninstalling its downloaded repository.

### 1. Review automations, scripts and dashboards

Before removing HACS Refresh, review your automations, scripts and dashboards for references to its action and entities.

The action is:

- `hacs_refresh.refresh`

The default entity IDs are:

- `button.hacs_refresh_refresh` — Refresh button
- `switch.hacs_refresh_automatic_refresh` — Automatic refresh switch
- `sensor.hacs_refresh_status` — Status sensor
- `sensor.hacs_refresh_progress` — Progress sensor
- `event.hacs_refresh_refresh_completed` — Refresh completed event

Entity IDs may differ if you have renamed them.

Remove or replace any references that are no longer needed.

### 2. Delete the Home Assistant integration entry

1. Go to **Settings → Devices & services → Integrations**.
2. Find **HACS Refresh**.
3. Open its three-dot menu and select **Delete**.
4. Confirm the deletion.

This removes the HACS Refresh config entry and its associated entities from Home Assistant.

### 3. Uninstall the downloaded repository

The downloaded integration files are separate from the Home Assistant config entry. Uninstall the repository using the method through which it was installed.

**If you use legacy HACS (Home Assistant 2026.10 or older):**

1. Open HACS.
2. Find **HACS Refresh**.
3. Open its three-dot menu.
4. Select **Remove**.

**If you use the built-in Marketplace (Home Assistant 2026.11 or newer):**

1. Go to **Settings → Marketplace**.
2. Open the **Installed** tab.
3. Find **HACS Refresh**.
4. Select it and choose **Uninstall**.

**If you installed HACS Refresh manually:**

1. Remove the `custom_components/hacs_refresh` directory from your Home Assistant configuration directory.
2. Restart Home Assistant.

### 4. Restart and verify

Restart Home Assistant if requested after uninstalling the repository.

Check your automations, scripts and dashboards again to ensure they no longer reference HACS Refresh.

No manual `.storage` or database editing is necessary.

### Need help?

The GitHub issue tracker remains available for bugs affecting supported Home Assistant versions and reasonable transition-related problems.

Please understand that new features and Home Assistant Marketplace compatibility are outside the scope of this project.

## License

Copyright © 2026 Frédéric Rouge

HACS Refresh is licensed under the GNU General Public License v3.0 or later.
See the [LICENSE](LICENSE) file for the full license text.
