"""Runtime data for Envoy Web."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import EnvoyWebApi
    from .coordinator import EnvoyWebCoordinator


type EnvoyWebConfigEntry = ConfigEntry[EnvoyWebData]


@dataclass
class EnvoyWebData:
    """Data stored for each config entry."""

    api: EnvoyWebApi
    coordinator: EnvoyWebCoordinator
    integration: Integration
