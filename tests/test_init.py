"""Tests for Envoy Web integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.core import HomeAssistant

from custom_components.envoy_web import async_setup, async_setup_entry
from custom_components.envoy_web.const import DOMAIN, SERVICE_SET_PROFILE


async def test_setup_entry_registers_service(hass: HomeAssistant, mock_config_entry) -> None:
    """Ensure setup registers the service."""
    await async_setup(hass, {})
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.envoy_web.EnvoyWebCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.envoy_web.async_get_loaded_integration",
            return_value=Mock(),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            new=AsyncMock(return_value=True),
        ),
    ):
        assert await async_setup_entry(hass, mock_config_entry)

    assert hass.services.has_service(DOMAIN, SERVICE_SET_PROFILE)
