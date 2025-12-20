"""Select platform for Envoy Web.

Exposes the writable battery profile ("self-consumption" / "backup_only").
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALLOWED_PROFILES, DOMAIN, MANUFACTURER, MODEL
from .coordinator import EnvoyWebCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EnvoyWebCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([EnvoyWebProfileSelect(coordinator, entry)])


class EnvoyWebProfileSelect(CoordinatorEntity[EnvoyWebCoordinator], SelectEntity):
    """Writable battery profile entity."""

    _attr_name = "Battery Profile"
    _attr_has_entity_name = True
    _attr_options = sorted(ALLOWED_PROFILES)

    def __init__(self, coordinator: EnvoyWebCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        cfg = self.coordinator.api.cfg
        self._attr_unique_id = f"{cfg.user_id}_{cfg.battery_id}_battery_profile"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{cfg.user_id}_{cfg.battery_id}")},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"Envoy Web {cfg.battery_id}",
        )

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data or {}
        value = data.get("profile")
        return value if isinstance(value, str) else None

    async def async_select_option(self, option: str) -> None:
        data = self.coordinator.data or {}
        current_backup = data.get("batteryBackupPercentage")
        if not isinstance(current_backup, int):
            # Fall back to a refresh to populate data, then try again.
            await self.coordinator.async_request_refresh()
            data = self.coordinator.data or {}
            current_backup = data.get("batteryBackupPercentage")
        if not isinstance(current_backup, int):
            raise ValueError("Cannot set profile: current backup percentage is unknown")

        await self.coordinator.api.async_set_profile(
            profile=option,
            battery_backup_percentage=int(current_backup),
        )
        await self.coordinator.async_request_refresh()
