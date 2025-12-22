"""Minimal async client for the Enphase Enlighten 'batteryConfig' web API used by the Envoy Web UI.

This module is intentionally Home-Assistant-free so it can be used from CLI scripts.
"""

from __future__ import annotations

import asyncio
import hashlib
import html as html_lib
import logging
import os
import re
import urllib.parse
import uuid
from dataclasses import dataclass
from typing import Any

import async_timeout
from aiohttp import ClientError, ClientSession

# Defined here (not in const.py) so this module can be imported without HA dependencies.
ALLOWED_PROFILES = {"self-consumption", "backup_only"}

_LOGGER = logging.getLogger(__name__)
_MAX_REQUEST_RETRIES = 2
_MAX_TOKEN_RETRIES = 2
_RETRY_BACKOFF_SECONDS = 0.5
_BASE_URL = "https://enlighten.enphaseenergy.com"
_LOGIN_URL = f"{_BASE_URL}/login/login"
_UI_ORIGIN = "https://battery-profile-ui.enphaseenergy.com"
_LOGIN_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
)
_LOGIN_COMMON_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.7",
    "upgrade-insecure-requests": "1",
    "user-agent": _LOGIN_UA,
    "sec-ch-ua": '"Brave";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Linux"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "sec-gpc": "1",
    "priority": "u=0, i",
}
_REQUEST_TIMEOUT_SECONDS = 15


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
        self._login_csrf_token: str | None = None
        self._login_form_defaults: dict[str, str] | None = None
        self._debug_auth = bool(int(str(os.getenv("ENVOY_DEBUG_AUTH", "0"))))

    def _log_auth_debug(self, message: str) -> None:
        if self._debug_auth:
            _LOGGER.debug(message)

    @staticmethod
    def _redact_cookie_header(value: str) -> str:
        # Keep the cookie name but redact the value.
        return re.sub(r"^([^=]+)=.*$", r"\1=<redacted>", value)

    async def async_fetch_xsrf_token(self) -> str:
        """Fetch a fresh login CSRF token from the Enlighten login page."""
        headers = dict(_LOGIN_COMMON_HEADERS)
        headers["sec-fetch-site"] = "none"
        if self._debug_auth:
            self._log_auth_debug(f"Login GET headers: {headers}")
        async with (
            async_timeout.timeout(_REQUEST_TIMEOUT_SECONDS),
            self._session.get(_BASE_URL, headers=headers) as resp,
        ):
            resp.raise_for_status()
            if self._debug_auth:
                headers_dump = dict(resp.headers)
                set_cookies = resp.headers.getall("Set-Cookie", [])
                if set_cookies:
                    redacted = [self._redact_cookie_header(value) for value in set_cookies]
                    headers_dump["Set-Cookie"] = redacted
                self._log_auth_debug(f"Login GET response headers: {headers_dump}")
            html = await resp.text()

        self._login_form_defaults = self._parse_login_form(html)
        token = None
        if self._login_form_defaults:
            token = self._login_form_defaults.get("authenticity_token")
        if not token:
            match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
            if match:
                token = match.group(1).strip()
        if not token:
            raise EnvoyWebAuthError("Missing csrf-token meta tag on login page")
        self._login_csrf_token = token
        token_source = "form" if self._login_form_defaults else "meta"
        self._log_auth_debug(f"Fetched login authenticity_token from {token_source}")
        return token

    async def async_fetch_auth_token(self) -> str:
        """Authenticate and fetch the e-auth-token."""
        if not self._login_csrf_token:
            await self.async_fetch_xsrf_token()

        password_hash = hashlib.md5(self._password.encode("utf-8")).hexdigest()
        defaults = dict(self._login_form_defaults or {})
        if defaults.get("utf8") == "&#x2713;":
            defaults["utf8"] = "\u2713"
        form_items = [
            ("utf8", defaults.get("utf8") or "\u2713"),
            ("authenticity_token", self._login_csrf_token),
            ("user[email]", self._email),
            ("user[password]", password_hash),
            ("secured_user", defaults.get("secured_user", "true")),
            ("locale", defaults.get("locale", "en")),
            ("commit", defaults.get("commit", "Sign In")),
        ]
        form = dict(form_items)

        headers = dict(_LOGIN_COMMON_HEADERS)
        headers.update(
            {
                "origin": _BASE_URL,
                "referer": f"{_BASE_URL}/",
                "cache-control": "max-age=0",
                "content-type": "application/x-www-form-urlencoded",
            }
        )
        self._log_auth_debug(f"Login POST headers: {headers}")
        if self._debug_auth:
            prefix = password_hash[:4]
            suffix = password_hash[-4:]
            self._log_auth_debug(
                f"Login POST password md5 len={len(password_hash)} prefix={prefix} suffix={suffix}"
            )

        redacted_form = dict(form)
        if "user[password]" in redacted_form:
            redacted_form["user[password]"] = "<redacted>"
        self._log_auth_debug(f"Login POST form fields: {sorted(redacted_form.keys())}")
        if self._debug_auth:
            self._log_auth_debug(f"Login POST form payload: {redacted_form}")
            encoded = urllib.parse.urlencode(form_items)
            encoded_pw = urllib.parse.quote_plus(password_hash)
            encoded_redacted = encoded.replace(encoded_pw, "<redacted_hash>")
            self._log_auth_debug(f"Login POST form encoded: {encoded_redacted}")
            cookies = self._session.cookie_jar.filter_cookies(_BASE_URL)
            redacted_cookies = {name: "<redacted>" for name in cookies}
            self._log_auth_debug(f"Login POST cookies: {redacted_cookies}")

        async with (
            async_timeout.timeout(_REQUEST_TIMEOUT_SECONDS),
            self._session.post(
                _LOGIN_URL,
                data=form_items,
                headers=headers,
                allow_redirects=False,
            ) as resp,
        ):
            self._log_auth_debug(
                f"Login POST status={resp.status} location={resp.headers.get('Location')!r}"
            )
            headers_dump = dict(resp.headers)
            set_cookies = resp.headers.getall("Set-Cookie", [])
            if set_cookies:
                redacted = [self._redact_cookie_header(value) for value in set_cookies]
                headers_dump["Set-Cookie"] = redacted
                self._log_auth_debug(f"Login Set-Cookie headers: {redacted}")
            self._log_auth_debug(f"Login response headers: {headers_dump}")
            if resp.status not in (200, 302, 303):
                raise EnvoyWebAuthError(f"Login failed with HTTP {resp.status}")
            await resp.read()

        token = self._get_cookie_value("enlighten_manager_token_production")
        if not token:
            token = self._extract_token_from_set_cookie(resp)
        if not token:
            base_cookies = self._session.cookie_jar.filter_cookies(_BASE_URL)
            ui_cookies = self._session.cookie_jar.filter_cookies(_UI_ORIGIN)
            self._log_auth_debug(f"Cookie jar (base): {sorted(base_cookies.keys())}")
            self._log_auth_debug(f"Cookie jar (ui): {sorted(ui_cookies.keys())}")
            raise EnvoyWebAuthError("Missing enlighten_manager_token_production cookie after login")
        self._auth_token = token
        self._log_auth_debug("Captured enlighten_manager_token_production cookie")
        return token

    async def async_login_and_get_tokens(self) -> tuple[str | None, str]:
        """Login and return (xsrf_token, auth_token)."""
        await self.async_fetch_xsrf_token()
        auth = await self.async_fetch_auth_token()
        xsrf = self._get_xsrf_cookie()
        return xsrf, auth

    async def async_invalidate(self) -> None:
        """Clear cached tokens."""
        async with self._lock:
            self._xsrf_token = None
            self._auth_token = None

    def set_cached_tokens(self, *, xsrf_token: str | None, auth_token: str | None) -> None:
        """Seed the token cache (CLI helper)."""
        self._xsrf_token = xsrf_token
        self._auth_token = auth_token

    def get_cached_tokens(self) -> tuple[str | None, str | None]:
        """Return cached tokens (CLI helper)."""
        return self._xsrf_token, self._auth_token

    def set_xsrf_token(self, token: str) -> None:
        """Update the cached XSRF token from API responses."""
        self._xsrf_token = token

    def get_xsrf_cookie(self) -> str | None:
        """Return the XSRF cookie value if available."""
        return self._get_xsrf_cookie()

    async def _async_login_with_retry(self) -> tuple[str | None, str]:
        for attempt in range(_MAX_TOKEN_RETRIES):
            try:
                return await self.async_login_and_get_tokens()
            except EnvoyWebAuthError:
                raise
            except (TimeoutError, ClientError) as err:
                if attempt >= _MAX_TOKEN_RETRIES - 1:
                    raise EnvoyWebApiError("Failed to authenticate") from err
                await asyncio.sleep(_backoff_delay(attempt))
        raise EnvoyWebApiError("Failed to authenticate")

    async def async_get_tokens(self) -> tuple[str | None, str]:
        """Return cached tokens, fetching and caching if needed."""
        async with self._lock:
            if self._auth_token:
                return self._xsrf_token, self._auth_token
            xsrf, auth = await self._async_login_with_retry()
            self._xsrf_token = xsrf
            self._auth_token = auth
            return xsrf, auth

    def _get_cookie_value(self, name: str) -> str | None:
        cookies = self._session.cookie_jar.filter_cookies(_BASE_URL)
        morsel = cookies.get(name)
        return morsel.value if morsel else None

    def _get_xsrf_cookie(self) -> str | None:
        for name in ("XSRF-TOKEN", "BP-XSRF-Token"):
            value = self._get_cookie_value(name)
            if value:
                return value
        return None

    def _parse_login_form(self, html: str) -> dict[str, str]:
        inputs = re.findall(r"<input[^>]+>", html, flags=re.IGNORECASE)
        if not inputs:
            return {}
        result: dict[str, str] = {}
        for input_tag in inputs:
            name_match = re.search(r'name=["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
            if not name_match:
                continue
            name = name_match.group(1)
            type_match = re.search(r'type=["\']([^"\']+)["\']', input_tag, re.IGNORECASE)
            input_type = type_match.group(1).lower() if type_match else ""
            value_match = re.search(r'value=["\']([^"\']*)["\']', input_tag, re.IGNORECASE)
            value = html_lib.unescape(value_match.group(1)) if value_match else ""
            if input_type == "hidden" or name in ("utf8", "authenticity_token"):
                result[name] = value
        if result:
            self._log_auth_debug(f"Login form hidden fields: {sorted(result.keys())}")
            token = result.get("authenticity_token")
            if token:
                self._log_auth_debug(f"Login form authenticity_token length: {len(token)}")
        return result

    @staticmethod
    def _extract_token_from_set_cookie(resp: Any) -> str | None:
        for header in resp.headers.getall("Set-Cookie", []):
            match = re.search(r"enlighten_manager_token_production=([^;]+)", header)
            if match:
                return match.group(1)
        return None


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
            f"{self._cfg.battery_id}?source=enho&userId={self._cfg.user_id}&locale=en"
        )

    def _url_put(self) -> str:
        return (
            "https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/profile/"
            f"{self._cfg.battery_id}?userId={self._cfg.user_id}"
        )

    async def _headers(self) -> dict[str, str]:
        # Mirrors what the web UI uses.
        xsrf_token, auth_token = await self._tokens.async_get_tokens()
        if not xsrf_token:
            xsrf_token = self._tokens.get_xsrf_cookie()
        headers = {
            "e-auth-token": auth_token,
            "username": str(self._cfg.user_id),
            "content-type": "application/json",
            "origin": _UI_ORIGIN,
            "referer": f"{_UI_ORIGIN}/",
            "requestid": str(uuid.uuid4()),
        }
        if xsrf_token:
            headers["x-xsrf-token"] = xsrf_token
        return headers

    async def async_login(self) -> dict[str, str | None]:
        """Login and return the raw tokens (debug helper for CLI)."""
        await self._tokens.async_invalidate()
        xsrf_token, auth_token = await self._tokens.async_get_tokens()
        return {
            "xsrf_token": xsrf_token,
            "auth_token": auth_token,
        }

    def load_cached_tokens(self, *, xsrf_token: str | None, auth_token: str | None) -> None:
        """Seed cached tokens (CLI helper)."""
        self._tokens.set_cached_tokens(xsrf_token=xsrf_token, auth_token=auth_token)

    def cached_tokens(self) -> tuple[str | None, str | None]:
        """Return cached tokens (CLI helper)."""
        return self._tokens.get_cached_tokens()

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

    async def _request_json(
        self,
        method: str,
        *,
        payload: dict[str, Any] | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        auth_retry = False
        for attempt in range(_MAX_REQUEST_RETRIES):
            try:
                async with (
                    async_timeout.timeout(_REQUEST_TIMEOUT_SECONDS),
                    self._session.request(
                        method, url or self._url(), headers=await self._headers(), json=payload
                    ) as resp,
                ):
                    xsrf = resp.headers.get("x-csrf-token")
                    if xsrf:
                        self._tokens.set_xsrf_token(xsrf)
                    if resp.status in (401, 403):
                        await self._tokens.async_invalidate()
                        if auth_retry or attempt >= _MAX_REQUEST_RETRIES - 1:
                            raise EnvoyWebAuthError("Authentication failed")
                        auth_retry = True
                        continue
                    resp.raise_for_status()
                    data = await resp.json()
                    if not isinstance(data, dict):
                        raise EnvoyWebApiError("Unexpected response shape (expected object)")
                    return data
            except (TimeoutError, ClientError) as err:
                if attempt >= _MAX_REQUEST_RETRIES - 1:
                    raise EnvoyWebApiError("Request failed") from err
                await asyncio.sleep(_backoff_delay(attempt))
            except EnvoyWebAuthError:
                raise
        if auth_retry:
            raise EnvoyWebAuthError("Authentication failed")
        raise EnvoyWebApiError("Request failed")

    async def async_get_profile(self) -> dict[str, Any]:
        payload = await self._request_json("GET")
        return self._extract_profile_details(payload)

    async def async_set_profile(
        self, *, profile: str, battery_backup_percentage: int
    ) -> dict[str, Any]:
        if profile not in ALLOWED_PROFILES:
            raise ValueError(f"Invalid profile: {profile!r}")
        if not isinstance(battery_backup_percentage, int) or not (
            0 <= battery_backup_percentage <= 100
        ):
            raise ValueError("battery_backup_percentage must be an integer between 0 and 100")
        if profile == "backup_only" and battery_backup_percentage != 100:
            raise ValueError("backup_only requires battery_backup_percentage to be 100")

        payload = {"profile": profile, "batteryBackupPercentage": battery_backup_percentage}
        await self._request_json("PUT", payload=payload, url=self._url_put())
        return {
            "profile": profile,
            "batteryBackupPercentage": battery_backup_percentage,
        }
