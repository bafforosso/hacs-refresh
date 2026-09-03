# HACS Refresh

A Home Assistant custom integration that forces HACS to refresh the metadata of all installed HACS repositories.

## Why?

HACS normally refreshes downloaded repositories periodically. In some situations, repository update information can become stale.

HACS Refresh provides a Home Assistant action that forces HACS to refresh all installed repositories.

## Features

- Force-refresh all installed HACS repositories
- Uses HACS's own repository refresh mechanism
- Uses HACS's own queue and GitHub rate-limit handling
- No GitHub token or external service required
- Can be run manually from Home Assistant automations, scripts, or Tools

## Action

```yaml
action: hacs_refresh.refresh
