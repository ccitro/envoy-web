"""Button platform for Envoy Web."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import EnvoyWebCoordinator
from .data import EnvoyWebConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnvoyWebConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([EnvoyWebForceRefreshButton(entry.runtime_data.coordinator, entry)])


class EnvoyWebForceRefreshButton(CoordinatorEntity[EnvoyWebCoordinator], ButtonEntity):
    """Trigger a manual refresh."""

    _attr_name = "Force Refresh"
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: EnvoyWebCoordinator, entry: EnvoyWebConfigEntry) -> None:
        super().__init__(coordinator)
        cfg = self.coordinator.api.cfg
        self._attr_unique_id = f"{cfg.user_id}_{cfg.battery_id}_force_refresh"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{cfg.user_id}_{cfg.battery_id}")},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"Envoy Web {cfg.battery_id}",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
