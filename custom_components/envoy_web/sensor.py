"""Sensor platform for Envoy Web."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
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
    async_add_entities([EnvoyWebLastUpdateSensor(coordinator, entry)])


class EnvoyWebLastUpdateSensor(CoordinatorEntity[EnvoyWebCoordinator], SensorEntity):
    """Timestamp for the last successful update."""

    _attr_name = "Last Update"
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EnvoyWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        cfg = self.coordinator.api.cfg
        self._attr_unique_id = f"{cfg.user_id}_{cfg.battery_id}_last_update"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{cfg.user_id}_{cfg.battery_id}")},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"Envoy Web {cfg.battery_id}",
        )

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.last_successful_update
