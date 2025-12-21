"""Coordinator for Envoy Web integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EnvoyWebApi, EnvoyWebAuthError

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
        self.last_update_time: datetime | None = None
        self.last_successful_update: datetime | None = None

    async def _async_update_data(self) -> dict:
        self.last_update_time = dt_util.utcnow()
        try:
            data = await self.api.async_get_profile()
            self.last_successful_update = self.last_update_time
            return data
        except EnvoyWebAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except Exception as err:  # noqa: BLE001 - HA wraps failures in UpdateFailed
            raise UpdateFailed(str(err)) from err
