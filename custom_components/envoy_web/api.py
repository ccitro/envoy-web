"""Minimal async client for the Enphase Enlighten 'batteryConfig' web API used by the Envoy Web UI.

This module is intentionally Home-Assistant-free so it can be used from CLI scripts.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from aiohttp import ClientError, ClientSession

# Defined here (not in const.py) so this module can be imported without HA dependencies.
ALLOWED_PROFILES = {"self-consumption", "backup_only"}

_LOGGER = logging.getLogger(__name__)
_MAX_REQUEST_RETRIES = 3
_MAX_TOKEN_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 0.5


def _backoff_delay(attempt: int) -> float:
    return _RETRY_BACKOFF_SECONDS * (2**attempt)

@dataclass(frozen=True)
class EnvoyWebConfig:
    battery_id: int
    user_id: int
    email: str
    password: str


class EnvoyWebApiError(Exception):
    """Raised when the Envoy Web API returns an unexpected response or cannot be parsed."""


class EnvoyWebAuthError(EnvoyWebApiError):
    """Raised when authentication fails."""


class EnvoyWebTokenManager:
    """Stateful token cache for Enlighten API authentication."""

    def __init__(self, session: ClientSession, *, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._lock = asyncio.Lock()
        self._xsrf_token: str | None = None
        self._auth_token: str | None = None

    async def async_fetch_xsrf_token(self) -> str:
        """Fetch a fresh XSRF token from the Enlighten login page."""
        _LOGGER.warning("async_fetch_xsrf_token is not implemented")
        # TODO: Load Enlighten login page and extract XSRF token from cookie/response
        raise NotImplementedError("async_fetch_xsrf_token")

    async def async_fetch_auth_token(self) -> str:
        """Authenticate and fetch the e-auth-token."""
        # TODO: POST credentials to Enlighten and extract auth token
        _LOGGER.warning("async_fetch_auth_token is not implemented")
        raise NotImplementedError("async_fetch_auth_token")

    async def async_login_and_get_tokens(self) -> tuple[str, str]:
        """Login and return (xsrf_token, auth_token)."""
        xsrf = await self.async_fetch_xsrf_token()
        auth = await self.async_fetch_auth_token()
        return xsrf, auth

    async def async_invalidate(self) -> None:
        """Clear cached tokens."""
        async with self._lock:
            self._xsrf_token = None
            self._auth_token = None

    async def _async_login_with_retry(self) -> tuple[str, str]:
        for attempt in range(_MAX_TOKEN_RETRIES):
            try:
                return await self.async_login_and_get_tokens()
            except NotImplementedError:
                raise
            except EnvoyWebAuthError:
                raise
            except (ClientError, asyncio.TimeoutError) as err:
                if attempt >= _MAX_TOKEN_RETRIES - 1:
                    raise EnvoyWebApiError("Failed to authenticate") from err
                await asyncio.sleep(_backoff_delay(attempt))

    async def async_get_tokens(self) -> tuple[str, str]:
        """Return cached tokens, fetching and caching if needed."""
        async with self._lock:
            if self._xsrf_token and self._auth_token:
                return self._xsrf_token, self._auth_token
            xsrf, auth = await self._async_login_with_retry()
            self._xsrf_token = xsrf
            self._auth_token = auth
            return xsrf, auth


class EnvoyWebApi:
    """Thin wrapper over the web UI API endpoints needed for sensors + service calls."""

    def __init__(self, session: ClientSession, cfg: EnvoyWebConfig) -> None:
        self._session = session
        self._cfg = cfg
        self._tokens = EnvoyWebTokenManager(
            session,
            email=cfg.email,
            password=cfg.password,
        )

    @property
    def cfg(self) -> EnvoyWebConfig:
        return self._cfg

    def _url(self) -> str:
        return (
            "https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/profile/"
            f"{self._cfg.battery_id}?userId={self._cfg.user_id}"
        )

    async def _headers(self) -> dict[str, str]:
        # Mirrors what the web UI uses.
        xsrf_token, auth_token = await self._tokens.async_get_tokens()
        return {
            "cookie": f"BP-XSRF-Token={xsrf_token}",
            "e-auth-token": auth_token,
            "username": str(self._cfg.user_id),
            "x-xsrf-token": xsrf_token,
            "content-type": "application/json",
        }

    @staticmethod
    def _extract_profile_details(payload: Any) -> dict[str, Any]:
        """Return a minimal dict for HA sensors from the API response payload."""
        if not isinstance(payload, dict):
            raise EnvoyWebApiError("Unexpected response shape (expected object)")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise EnvoyWebApiError("Unexpected response shape (missing/invalid 'data' object)")

        profile = data.get("profile")
        if not isinstance(profile, str) or not profile:
            raise EnvoyWebApiError("Unexpected response shape (missing/invalid 'data.profile')")

        battery_backup_percentage = data.get("batteryBackupPercentage")
        if not isinstance(battery_backup_percentage, int):
            raise EnvoyWebApiError(
                "Unexpected response shape (missing/invalid 'data.batteryBackupPercentage')"
            )

        # Keep keys consistent with the API response and our sensor value_key mapping.
        return {
            "profile": profile,
            "batteryBackupPercentage": battery_backup_percentage,
        }

    async def _request_json(self, method: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(_MAX_REQUEST_RETRIES):
            try:
                async with self._session.request(
                    method, self._url(), headers=await self._headers(), json=payload
                ) as resp:
                    if resp.status in (401, 403):
                        await self._tokens.async_invalidate()
                        if attempt >= _MAX_REQUEST_RETRIES - 1:
                            raise EnvoyWebAuthError("Authentication failed")
                        continue
                    resp.raise_for_status()
                    data = await resp.json()
                    if not isinstance(data, dict):
                        raise EnvoyWebApiError("Unexpected response shape (expected object)")
                    return data
            except (ClientError, asyncio.TimeoutError) as err:
                if attempt >= _MAX_REQUEST_RETRIES - 1:
                    raise EnvoyWebApiError("Request failed") from err
                await asyncio.sleep(_backoff_delay(attempt))
        raise EnvoyWebApiError("Request failed")

    async def async_get_profile(self) -> dict[str, Any]:
        payload = await self._request_json("GET")
        return self._extract_profile_details(payload)

    async def async_set_profile(self, *, profile: str, battery_backup_percentage: int) -> dict[str, Any]:
        if profile not in ALLOWED_PROFILES:
            raise ValueError(f"Invalid profile: {profile!r}")
        if not isinstance(battery_backup_percentage, int) or not (0 <= battery_backup_percentage <= 100):
            raise ValueError("battery_backup_percentage must be an integer between 0 and 100")

        payload = {"profile": profile, "batteryBackupPercentage": battery_backup_percentage}
        return await self._request_json("PUT", payload=payload)
