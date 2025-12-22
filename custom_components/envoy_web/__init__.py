"""The Envoy Web integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import EnvoyWebApi, EnvoyWebAuthError, EnvoyWebConfig
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
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    SERVICE_SET_PROFILE,
)
from .coordinator import EnvoyWebCoordinator
from .data import EnvoyWebConfigEntry, EnvoyWebData

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

_DATA_COORDINATORS = "coordinators"
_DATA_SERVICE_REGISTERED = "service_registered"

_SERVICE_SET_PROFILE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): vol.Coerce(str),
        vol.Required(ATTR_PROFILE): vol.In(ALLOWED_PROFILES),
        vol.Required(ATTR_BATTERY_BACKUP_PERCENTAGE): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up integration (YAML not supported)."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(_DATA_COORDINATORS, {})
    hass.data[DOMAIN].setdefault(_DATA_SERVICE_REGISTERED, False)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EnvoyWebConfigEntry) -> bool:
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
    try:
        await coordinator.async_config_entry_first_refresh()
    except EnvoyWebAuthError as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err
    except Exception as err:  # noqa: BLE001
        raise ConfigEntryNotReady("Failed to initialize Envoy Web") from err

    entry.runtime_data = EnvoyWebData(
        api=api,
        coordinator=coordinator,
        integration=async_get_loaded_integration(hass, entry.domain),
    )
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
            if coordinator_for_call is None:
                raise HomeAssistantError(f"Unknown config entry id: {entry_id}")
        else:
            # Default to the first configured entry.
            coordinator_for_call = next(iter(coordinators.values()), None)
        if coordinator_for_call is None:
            raise HomeAssistantError("No Envoy Web config entries are set up")

        try:
            updated = await coordinator_for_call.api.async_set_profile(
                profile=call.data[ATTR_PROFILE],
                battery_backup_percentage=call.data[ATTR_BATTERY_BACKUP_PERCENTAGE],
            )
            coordinator_for_call.async_set_updated_data(updated)
        except EnvoyWebAuthError as err:
            raise HomeAssistantError("Authentication failed") from err

    # Register once globally.
    if not hass.data[DOMAIN][_DATA_SERVICE_REGISTERED]:
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_PROFILE,
            _handle_set_profile,
            schema=_SERVICE_SET_PROFILE_SCHEMA,
        )
        hass.data[DOMAIN][_DATA_SERVICE_REGISTERED] = True

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EnvoyWebConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][_DATA_COORDINATORS].pop(entry.entry_id, None)
        # If no entries remain, remove the service.
        if not hass.data[DOMAIN][_DATA_COORDINATORS]:
            hass.services.async_remove(DOMAIN, SERVICE_SET_PROFILE)
            hass.data[DOMAIN][_DATA_SERVICE_REGISTERED] = False
    return unload_ok
