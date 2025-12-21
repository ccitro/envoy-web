"""Config flow for Envoy Web integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

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
        vol.Required(CONF_BATTERY_ID): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
            vol.Range(min=1),
        ),
        vol.Required(CONF_USER_ID): vol.All(
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Coerce(int),
            vol.Range(min=1),
        ),
        vol.Required(CONF_EMAIL): vol.All(
            selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Coerce(str),
        ),
        vol.Required(CONF_PASSWORD): vol.All(
            selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Coerce(str),
        ),
    }
)

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): vol.All(
            selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.EMAIL)
            ),
            vol.Coerce(str),
        ),
        vol.Required(CONF_PASSWORD): vol.All(
            selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Coerce(str),
        ),
    }
)


async def _validate_input(hass: HomeAssistant, data: dict) -> None:
    """Validate user input by attempting to authenticate."""
    # TODO: Call API to verify credentials
    _ = (hass, data)


class EnvoyWebConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Envoy Web."""

    VERSION = 1
    _reauth_entry: config_entries.ConfigEntry | None = None

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

    async def async_step_reauth(self, entry_data: dict) -> FlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None and self._reauth_entry is not None:
            data = {**self._reauth_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return EnvoyWebOptionsFlowHandler(config_entry)


class EnvoyWebOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

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
                    ): vol.All(
                        selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=10, max=3600, mode=selector.NumberSelectorMode.BOX
                            )
                        ),
                        vol.Coerce(int),
                        vol.Range(min=10, max=3600),
                    ),
                }
            ),
        )
