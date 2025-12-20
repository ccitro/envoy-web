"""Number platform for Envoy Web.

Exposes the writable battery backup percentage (0-100).
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EnvoyWebCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnvoyWebCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([EnvoyWebBackupPercentageNumber(coordinator, entry)])


class EnvoyWebBackupPercentageNumber(CoordinatorEntity[EnvoyWebCoordinator], NumberEntity):
    """Writable backup percentage entity."""

    _attr_name = "Battery Backup Percentage"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "%"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, coordinator: EnvoyWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        cfg = self.coordinator.api.cfg
        self._attr_unique_id = f"{cfg.user_id}_{cfg.battery_id}_battery_backup_percentage"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{cfg.user_id}_{cfg.battery_id}")},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"Envoy Web {cfg.battery_id}",
        )

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data or {}
        value = data.get("batteryBackupPercentage")
        if isinstance(value, int):
            return float(value)
        return None

    async def async_set_native_value(self, value: float) -> None:
        # HA can give floats; normalize to int 0-100.
        pct = int(round(value))
        pct = max(0, min(100, pct))

        data = self.coordinator.data or {}
        current_profile = data.get("profile")
        if not isinstance(current_profile, str):
            await self.coordinator.async_request_refresh()
            data = self.coordinator.data or {}
            current_profile = data.get("profile")
        if not isinstance(current_profile, str):
            raise ValueError("Cannot set backup percentage: current profile is unknown")

        await self.coordinator.api.async_set_profile(
            profile=current_profile,
            battery_backup_percentage=pct,
        )
        await self.coordinator.async_request_refresh()
