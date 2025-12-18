"""Constants for the Envoy Web integration."""

from __future__ import annotations

# Re-export from api.py so HA code can import from const as usual.
from .api import ALLOWED_PROFILES as ALLOWED_PROFILES  # noqa: F401

DOMAIN = "envoy_web"

CONF_BATTERY_ID = "battery_id"
CONF_USER_ID = "user_id"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL_SECONDS = 60
CONF_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"

SERVICE_SET_PROFILE = "set_profile"

ATTR_ENTRY_ID = "entry_id"
ATTR_PROFILE = "profile"
ATTR_BATTERY_BACKUP_PERCENTAGE = "battery_backup_percentage"

