"""Tests for Envoy Web coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.envoy_web.api import EnvoyWebAuthError
from custom_components.envoy_web.coordinator import EnvoyWebCoordinator


async def test_coordinator_update_success(hass: HomeAssistant) -> None:
    """Test coordinator update succeeds and timestamps update."""
    api = AsyncMock()
    api.async_get_profile = AsyncMock(return_value={"profile": "self-consumption"})
    coordinator = EnvoyWebCoordinator(hass, api, scan_interval_seconds=60)

    data = await coordinator._async_update_data()

    assert data["profile"] == "self-consumption"
    assert coordinator.last_update_time is not None
    assert coordinator.last_successful_update == coordinator.last_update_time


async def test_coordinator_update_auth_failed(hass: HomeAssistant) -> None:
    """Test coordinator raises auth failed on auth error."""
    api = AsyncMock()
    api.async_get_profile = AsyncMock(side_effect=EnvoyWebAuthError("bad creds"))
    coordinator = EnvoyWebCoordinator(hass, api, scan_interval_seconds=60)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_failed(hass: HomeAssistant) -> None:
    """Test coordinator raises UpdateFailed on other errors."""
    api = AsyncMock()
    api.async_get_profile = AsyncMock(side_effect=RuntimeError("boom"))
    coordinator = EnvoyWebCoordinator(hass, api, scan_interval_seconds=60)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
