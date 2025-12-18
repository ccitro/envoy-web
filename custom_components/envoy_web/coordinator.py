"""Coordinator for Envoy Web integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EnvoyWebApi

_LOGGER = logging.getLogger(__name__)


class EnvoyWebCoordinator(DataUpdateCoordinator[dict]):
    """Fetch battery profile data from the web UI API."""

    def __init__(self, hass: HomeAssistant, api: EnvoyWebApi, *, scan_interval_seconds: int) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Envoy Web",
            update_interval=timedelta(seconds=scan_interval_seconds),
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            return await self.api.async_get_profile()
        except Exception as err:  # noqa: BLE001 - HA wraps failures in UpdateFailed
            raise UpdateFailed(str(err)) from err

