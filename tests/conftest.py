"""Fixtures for Envoy Web tests."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.envoy_web.const import (
    CONF_BATTERY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USER_ID,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return


@pytest.fixture
def mock_config_entry_data():
    """Return mock config entry data."""
    return {
        CONF_BATTERY_ID: 12345,
        CONF_USER_ID: 67890,
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "password",
    }


@pytest.fixture
def mock_config_entry(mock_config_entry_data):
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=mock_config_entry_data,
        unique_id="test_unique_id",
    )
