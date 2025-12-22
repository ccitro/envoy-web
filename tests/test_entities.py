"""Tests for Envoy Web entities."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.envoy_web.api import EnvoyWebConfig
from custom_components.envoy_web.binary_sensor import EnvoyWebApiOnlineBinarySensor
from custom_components.envoy_web.button import EnvoyWebForceRefreshButton
from custom_components.envoy_web.coordinator import EnvoyWebCoordinator
from custom_components.envoy_web.number import EnvoyWebBackupPercentageNumber
from custom_components.envoy_web.sensor import EnvoyWebLastUpdateSensor
from custom_components.envoy_web.select import EnvoyWebProfileSelect


@pytest.fixture
def mock_api() -> AsyncMock:
    """Return a mock API with config."""
    api = AsyncMock()
    api.cfg = EnvoyWebConfig(
        battery_id=12345,
        user_id=67890,
        email="test@example.com",
        password="password",
    )
    api.async_set_profile = AsyncMock(
        return_value={"profile": "self-consumption", "batteryBackupPercentage": 50}
    )
    return api


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_api: AsyncMock) -> EnvoyWebCoordinator:
    """Return a coordinator with a mock API."""
    return EnvoyWebCoordinator(hass, mock_api, scan_interval_seconds=60)


async def test_profile_select_uses_current_backup(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test select uses current backup percentage."""
    coordinator.async_set_updated_data(
        {"profile": "self-consumption", "batteryBackupPercentage": 50}
    )
    entity = EnvoyWebProfileSelect(coordinator, mock_config_entry)

    await entity.async_select_option("self-consumption")

    coordinator.api.async_set_profile.assert_awaited_once_with(
        profile="self-consumption",
        battery_backup_percentage=50,
    )
    assert coordinator.data == {"profile": "self-consumption", "batteryBackupPercentage": 50}


async def test_profile_select_refreshes_missing_backup(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test select refreshes when backup percentage missing."""
    coordinator.async_set_updated_data({"profile": "self-consumption"})

    async def _refresh() -> None:
        coordinator.async_set_updated_data(
            {"profile": "self-consumption", "batteryBackupPercentage": 42}
        )

    coordinator.async_request_refresh = AsyncMock(side_effect=_refresh)
    entity = EnvoyWebProfileSelect(coordinator, mock_config_entry)

    await entity.async_select_option("self-consumption")

    coordinator.async_request_refresh.assert_awaited_once()
    coordinator.api.async_set_profile.assert_awaited_once_with(
        profile="self-consumption",
        battery_backup_percentage=42,
    )


async def test_backup_percentage_number_clamps(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test number clamps values and uses current profile."""
    coordinator.async_set_updated_data(
        {"profile": "self-consumption", "batteryBackupPercentage": 50}
    )
    entity = EnvoyWebBackupPercentageNumber(coordinator, mock_config_entry)

    await entity.async_set_native_value(133.3)

    coordinator.api.async_set_profile.assert_awaited_once_with(
        profile="self-consumption",
        battery_backup_percentage=100,
    )


async def test_backup_percentage_number_refreshes_profile(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test number refreshes when profile missing."""
    coordinator.async_set_updated_data({"batteryBackupPercentage": 50})

    async def _refresh() -> None:
        coordinator.async_set_updated_data(
            {"profile": "self-consumption", "batteryBackupPercentage": 50}
        )

    coordinator.async_request_refresh = AsyncMock(side_effect=_refresh)
    entity = EnvoyWebBackupPercentageNumber(coordinator, mock_config_entry)

    await entity.async_set_native_value(75)

    coordinator.async_request_refresh.assert_awaited_once()
    coordinator.api.async_set_profile.assert_awaited_once_with(
        profile="self-consumption",
        battery_backup_percentage=75,
    )


async def test_backup_percentage_number_missing_profile_raises(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test number raises when profile remains unknown."""
    coordinator.async_set_updated_data({"batteryBackupPercentage": 50})
    coordinator.async_request_refresh = AsyncMock()
    entity = EnvoyWebBackupPercentageNumber(coordinator, mock_config_entry)

    with pytest.raises(ValueError):
        await entity.async_set_native_value(50)


def test_profile_select_current_option(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test select current option reads coordinator data."""
    coordinator.async_set_updated_data(
        {"profile": "self-consumption", "batteryBackupPercentage": 50}
    )
    entity = EnvoyWebProfileSelect(coordinator, mock_config_entry)

    assert entity.current_option == "self-consumption"


def test_backup_percentage_native_value(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test number native value conversion."""
    coordinator.async_set_updated_data(
        {"profile": "self-consumption", "batteryBackupPercentage": 33}
    )
    entity = EnvoyWebBackupPercentageNumber(coordinator, mock_config_entry)

    assert entity.native_value == 33.0


async def test_force_refresh_button(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test button triggers refresh."""
    coordinator.async_request_refresh = AsyncMock()
    entity = EnvoyWebForceRefreshButton(coordinator, mock_config_entry)

    await entity.async_press()

    coordinator.async_request_refresh.assert_awaited_once()


def test_last_update_sensor(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test last update timestamp sensor."""
    now = dt_util.utcnow()
    coordinator.last_successful_update = now
    entity = EnvoyWebLastUpdateSensor(coordinator, mock_config_entry)

    assert entity.native_value == now


def test_api_online_binary_sensor(
    coordinator: EnvoyWebCoordinator, mock_config_entry
) -> None:
    """Test API online binary sensor."""
    entity = EnvoyWebApiOnlineBinarySensor(coordinator, mock_config_entry)
    assert entity.is_on is None

    coordinator.last_update_time = dt_util.utcnow()
    coordinator.last_update_success = False
    assert entity.available is False
    assert entity.is_on is False

    coordinator.last_update_success = True
    assert entity.available is True
    assert entity.is_on is True
