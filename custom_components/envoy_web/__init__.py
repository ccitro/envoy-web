"""The Envoy Web integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EnvoyWebApi, EnvoyWebConfig
from .const import (
    ALLOWED_PROFILES,
    ATTR_BATTERY_BACKUP_PERCENTAGE,
    ATTR_ENTRY_ID,
    ATTR_PROFILE,
    CONF_BATTERY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_USER_ID,
    DOMAIN,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    SERVICE_SET_PROFILE,
)
from .coordinator import EnvoyWebCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.NUMBER]

_DATA_COORDINATORS = "coordinators"
_DATA_SERVICE_REGISTERED = "service_registered"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration (YAML not supported)."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(_DATA_COORDINATORS, {})
    hass.data[DOMAIN].setdefault(_DATA_SERVICE_REGISTERED, False)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Envoy Web from a config entry."""
    session = async_get_clientsession(hass)
    cfg = EnvoyWebConfig(
        battery_id=int(entry.data[CONF_BATTERY_ID]),
        user_id=int(entry.data[CONF_USER_ID]),
        email=str(entry.data[CONF_EMAIL]),
        password=str(entry.data[CONF_PASSWORD]),
    )
    api = EnvoyWebApi(session, cfg)

    scan_interval_seconds = int(
        entry.options.get(CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS)
    )
    coordinator = EnvoyWebCoordinator(hass, api, scan_interval_seconds=scan_interval_seconds)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][_DATA_COORDINATORS][entry.entry_id] = coordinator

    async def _update_listener(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        await hass.config_entries.async_reload(updated_entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    async def _handle_set_profile(call: ServiceCall) -> None:
        entry_id = call.data.get(ATTR_ENTRY_ID)
        coordinators: dict[str, EnvoyWebCoordinator] = hass.data[DOMAIN][_DATA_COORDINATORS]
        coordinator_for_call: EnvoyWebCoordinator | None = None
        if entry_id:
            coordinator_for_call = coordinators.get(str(entry_id))
        else:
            # Default to the first configured entry.
            coordinator_for_call = next(iter(coordinators.values()), None)
        if coordinator_for_call is None:
            raise HomeAssistantError("No Envoy Web config entries are set up")

        profile = str(call.data[ATTR_PROFILE])
        if profile not in ALLOWED_PROFILES:
            raise HomeAssistantError(f"Invalid profile: {profile!r}")
        battery_backup_percentage = int(call.data[ATTR_BATTERY_BACKUP_PERCENTAGE])
        await coordinator_for_call.api.async_set_profile(
            profile=profile,
            battery_backup_percentage=battery_backup_percentage,
        )
        await coordinator_for_call.async_request_refresh()

    # Register once globally.
    if not hass.data[DOMAIN][_DATA_SERVICE_REGISTERED]:
        hass.services.async_register(DOMAIN, SERVICE_SET_PROFILE, _handle_set_profile)
        hass.data[DOMAIN][_DATA_SERVICE_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][_DATA_COORDINATORS].pop(entry.entry_id, None)
        # If no entries remain, remove the service.
        if not hass.data[DOMAIN][_DATA_COORDINATORS]:
            hass.services.async_remove(DOMAIN, SERVICE_SET_PROFILE)
            hass.data[DOMAIN][_DATA_SERVICE_REGISTERED] = False
    return unload_ok

