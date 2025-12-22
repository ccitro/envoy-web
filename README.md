# Envoy Web

[![HACS][hacs-shield]][hacs]
[![GitHub Release][release-shield]][releases]
[![License][license-shield]][license]

[![GitHub Activity][commits-shield]][commits]
[![GitHub Issues][issues-shield]][issues]

Home Assistant custom integration for controlling **Enphase IQ Battery** profile and backup reserve percentage via the Enphase Enlighten cloud API.

## Overview

This integration allows you to monitor and control your Enphase battery system directly from Home Assistant:

- **View** the current battery profile and backup reserve percentage
- **Change** the battery profile between Self-Consumption and Backup modes
- **Adjust** the backup reserve percentage (0-100%)
- **Automate** battery settings based on weather, time-of-use rates, or grid conditions
- **Handles sessions automatically**, renewing access when needed and prompting you to re-authenticate if credentials change

> **Note**: This integration uses the same Enphase Enlighten web API that powers the official mobile app and web dashboard. It requires your Enlighten account credentials and works with IQ Battery systems.

---

## Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations** → click the **⋮** menu → **Custom repositories**
3. Add `https://github.com/ccitro/envoy-web` with category **Integration**
4. Click **Install** on the Envoy Web card
5. **Restart Home Assistant**

### Manual Installation

1. Download the [latest release][releases]
2. Extract and copy `custom_components/envoy_web/` to your `config/custom_components/` directory
3. Restart Home Assistant

---

## Configuration

### Adding the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Envoy Web**
4. Enter your configuration:

| Field | Description |
|-------|-------------|
| **Battery ID** | Your battery system ID (see [Finding Your IDs](#finding-your-ids)) |
| **User ID** | Your Enlighten user ID (see [Finding Your IDs](#finding-your-ids)) |
| **Email** | Your Enphase Enlighten account email |
| **Password** | Your Enphase Enlighten account password |

### Finding Your IDs

To find your Battery ID and User ID:

1. Log in to [Enphase Enlighten](https://enlighten.enphaseenergy.com)
2. Navigate to your system and open the battery settings page
3. Open your browser's Developer Tools (F12) → **Network** tab
4. Look for API calls to `batteryConfig` - the URL contains both IDs:
   ```
   /service/batteryConfig/api/v1/profile/{BATTERY_ID}?userId={USER_ID}
   ```

### Options

After setup, you can configure additional options:

| Option | Default | Description |
|--------|---------|-------------|
| **Scan interval** | 600 seconds (10 minutes) | How often to poll the API (10-3600 seconds) |

---

## Development

This repo ships a Nix flake and `.envrc` for direnv-based setup. The flake tracks
`nixos-unstable` to provide Python 3.13.2+ for Home Assistant 2025.12.x. Runtime
and test dependencies install into a local `.venv` using `uv` when available.

### Tooling setup

1. `direnv allow .`
2. `scripts/setup`
3. `scripts/lint`
4. `scripts/develop`

### Testing

Run all tests:
```bash
./scripts/test
```

Run a single test:
```bash
./scripts/test tests/test_init.py::test_setup_entry_registers_service
```

---

## Entities

This integration creates the following entities:

### Battery Profile (Select)

| Attribute | Value |
|-----------|-------|
| Entity ID | `select.envoy_web_XXX_battery_profile` |
| Options | `self-consumption`, `backup_only` |

**Profile Descriptions:**

- **`self-consumption`**: Battery prioritizes powering your home and storing excess solar. Grid is used as backup.
- **`backup_only`**: Battery reserves capacity for power outages. Does not discharge during normal operation.

### Battery Backup Percentage (Number)

| Attribute | Value |
|-----------|-------|
| Entity ID | `number.envoy_web_XXX_battery_backup_percentage` |
| Range | 0-100% |
| Step | 1% |

This controls the minimum battery charge level to maintain as backup reserve.

---

## Services

### `envoy_web.set_profile`

Set both the battery profile and backup percentage in a single API call.

```yaml
service: envoy_web.set_profile
data:
  profile: self-consumption
  battery_backup_percentage: 20
```

| Field | Required | Description |
|-------|----------|-------------|
| `profile` | Yes | `self-consumption` or `backup_only` |
| `battery_backup_percentage` | Yes | Integer from 0 to 100 |
| `entry_id` | No | Target a specific config entry (if multiple systems configured) |

---

## Automation Examples

### Switch to Backup Mode Before a Storm

```yaml
automation:
  - alias: "Storm Prep - Maximize Battery Reserve"
    trigger:
      - platform: state
        entity_id: sensor.weather_severe_warning
        to: "on"
    action:
      - service: envoy_web.set_profile
        data:
          profile: backup_only
          battery_backup_percentage: 100
```

### Time-of-Use Rate Optimization

```yaml
automation:
  - alias: "Peak Hours - Preserve Battery"
    trigger:
      - platform: time
        at: "16:00:00"
    condition:
      - condition: time
        weekday: [mon, tue, wed, thu, fri]
    action:
      - service: number.set_value
        target:
          entity_id: number.envoy_web_battery_backup_percentage
        data:
          value: 80

  - alias: "Off-Peak - Allow Full Discharge"
    trigger:
      - platform: time
        at: "21:00:00"
    action:
      - service: number.set_value
        target:
          entity_id: number.envoy_web_battery_backup_percentage
        data:
          value: 10
```

### Dashboard Card Example

```yaml
type: entities
title: Battery Control
entities:
  - entity: select.envoy_web_battery_profile
    name: Mode
  - entity: number.envoy_web_battery_backup_percentage
    name: Backup Reserve
```

---

## Troubleshooting

### Authentication Errors

- Verify your Enlighten email and password are correct
- Check that you can log in to [enlighten.enphaseenergy.com](https://enlighten.enphaseenergy.com)
- Ensure your account has access to the battery system
- If prompted, re-authenticate from **Settings → Devices & Services → Envoy Web → Reconfigure**

### Entities Unavailable

- Check Home Assistant logs for error messages
- Verify your Battery ID and User ID are correct
- The Enlighten API may be temporarily unavailable

### Rate Limiting

The integration polls every 10 minutes by default. If you experience issues, try increasing the scan interval in the integration options.

---

## Development

### Local Testing (CLI)

A CLI tool is included for testing the API without Home Assistant. It uses [uv](https://docs.astral.sh/uv/) for zero-setup dependency management:

```bash
# Create credentials file
cat > scripts/.env << 'EOF'
ENVOY_BATTERY_ID=123456
ENVOY_USER_ID=789012
ENVOY_EMAIL=you@example.com
ENVOY_PASSWORD=yourpassword
EOF

# Run commands (uv handles dependencies automatically)
uv run scripts/envoy_cli.py login
uv run scripts/envoy_cli.py get
uv run scripts/envoy_cli.py put self-consumption 30
```

Or make it executable and run directly:

```bash
chmod +x scripts/envoy_cli.py
./scripts/envoy_cli.py get
```

### Project Structure

```
envoy-web/
├── custom_components/envoy_web/   # Home Assistant integration
│   ├── api.py                     # Enlighten API client
│   ├── config_flow.py             # Setup UI
│   ├── coordinator.py             # Data polling
│   ├── select.py                  # Profile entity
│   ├── number.py                  # Backup % entity
│   └── ...
├── scripts/envoy_cli.py           # Development CLI
└── ...
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Disclaimer

This integration is not affiliated with, endorsed by, or connected to Enphase Energy, Inc. Use at your own risk. The Enlighten API is not officially documented and may change without notice.

[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs]: https://hacs.xyz
[release-shield]: https://img.shields.io/github/v/release/ccitro/envoy-web?style=for-the-badge
[releases]: https://github.com/ccitro/envoy-web/releases
[license-shield]: https://img.shields.io/github/license/ccitro/envoy-web?style=for-the-badge
[license]: LICENSE
[commits-shield]: https://img.shields.io/github/commit-activity/y/ccitro/envoy-web?style=for-the-badge
[commits]: https://github.com/ccitro/envoy-web/commits/main
[issues-shield]: https://img.shields.io/github/issues/ccitro/envoy-web?style=for-the-badge
[issues]: https://github.com/ccitro/envoy-web/issues
