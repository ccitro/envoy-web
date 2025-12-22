"""Tests for Envoy Web config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.envoy_web.api import EnvoyWebApiError, EnvoyWebAuthError
from custom_components.envoy_web.const import (
    CONF_BATTERY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL_SECONDS,
    CONF_USER_ID,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)


async def test_user_flow_success(hass: HomeAssistant, mock_config_entry_data: dict) -> None:
    """Test successful user flow."""
    with patch(
        "custom_components.envoy_web.config_flow.EnvoyWebApi.async_get_profile",
        new=AsyncMock(return_value={"profile": "self-consumption", "batteryBackupPercentage": 50}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], mock_config_entry_data
        )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == f"Envoy Web {mock_config_entry_data[CONF_BATTERY_ID]}"
        assert result2["data"][CONF_USER_ID] == mock_config_entry_data[CONF_USER_ID]


async def test_user_flow_auth_error(hass: HomeAssistant, mock_config_entry_data: dict) -> None:
    """Test auth error during user flow."""
    with patch(
        "custom_components.envoy_web.config_flow.EnvoyWebApi.async_get_profile",
        new=AsyncMock(side_effect=EnvoyWebAuthError("bad creds")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], mock_config_entry_data
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "auth"}


async def test_user_flow_cannot_connect(hass: HomeAssistant, mock_config_entry_data: dict) -> None:
    """Test connection error during user flow."""
    with patch(
        "custom_components.envoy_web.config_flow.EnvoyWebApi.async_get_profile",
        new=AsyncMock(side_effect=EnvoyWebApiError("api down")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], mock_config_entry_data
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass: HomeAssistant, mock_config_entry_data: dict) -> None:
    """Test unknown error during user flow."""
    with patch(
        "custom_components.envoy_web.config_flow.EnvoyWebApi.async_get_profile",
        new=AsyncMock(side_effect=RuntimeError("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], mock_config_entry_data
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "unknown"}


async def test_reauth_success(hass: HomeAssistant, mock_config_entry_data: dict) -> None:
    """Test successful reauthentication flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=mock_config_entry_data)
    entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.envoy_web.config_flow.EnvoyWebApi.async_get_profile",
            new=AsyncMock(),
        ),
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "new@example.com",
                CONF_PASSWORD: "new-password",
            },
        )
        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert entry.data[CONF_EMAIL] == "new@example.com"


async def test_options_flow(hass: HomeAssistant, mock_config_entry_data: dict) -> None:
    """Test options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data,
        options={CONF_SCAN_INTERVAL_SECONDS: DEFAULT_SCAN_INTERVAL_SECONDS},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL_SECONDS: 120},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL_SECONDS] == 120
