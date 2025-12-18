"""Config flow for Envoy Web integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .api import EnvoyWebConfig
from .const import (
    CONF_BATTERY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_BATTERY_ID): int,
        vol.Required(CONF_USER_ID): int,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_input(hass: HomeAssistant, data: dict) -> None:
    """Validate user input by attempting to authenticate."""
    # TODO: Call API to verify credentials
    _ = (hass, data)


class EnvoyWebConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Envoy Web."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            unique = f"{user_input[CONF_USER_ID]}_{user_input[CONF_BATTERY_ID]}"
            await self.async_set_unique_id(unique)
            self._abort_if_unique_id_configured()

            try:
                await _validate_input(self.hass, user_input)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Credential validation failed: %s", err, exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Envoy Web {user_input[CONF_BATTERY_ID]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return EnvoyWebOptionsFlowHandler(config_entry)


class EnvoyWebOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL_SECONDS,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL_SECONDS, DEFAULT_SCAN_INTERVAL_SECONDS
                        ),
                    ): vol.All(int, vol.Range(min=10, max=3600)),
                }
            ),
        )


