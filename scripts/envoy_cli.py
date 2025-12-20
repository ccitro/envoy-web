#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "aiohttp>=3.9.0",
#     "python-dotenv>=1.0.0",
# ]
# ///
"""CLI for testing the Envoy Web API client.

This imports api.py directly (bypassing the HA integration's __init__.py)
so you can iterate on the API client without Home Assistant dependencies.

Usage:
    uv run scripts/envoy_cli.py get
    uv run scripts/envoy_cli.py put self-consumption 30
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path
from yarl import URL

import aiohttp
from dotenv import load_dotenv

# Load api.py directly to avoid triggering the HA integration's __init__.py
_API_PATH = Path(__file__).resolve().parent.parent / "custom_components" / "envoy_web" / "api.py"
_spec = importlib.util.spec_from_file_location("envoy_api", _API_PATH)
_api_module = importlib.util.module_from_spec(_spec)
# Register module in sys.modules before exec (required for dataclasses)
sys.modules["envoy_api"] = _api_module
_spec.loader.exec_module(_api_module)

EnvoyWebApi = _api_module.EnvoyWebApi
EnvoyWebConfig = _api_module.EnvoyWebConfig
ALLOWED_PROFILES = _api_module.ALLOWED_PROFILES


DEFAULT_ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_CACHE_NAME = ".envoy_cli_auth.json"
_BASE_URL = "https://enlighten.enphaseenergy.com"


def _load_dotenv() -> None:
    load_dotenv(dotenv_path=DEFAULT_ENV_PATH, override=False)


def _req_str(env_key: str) -> str:
    value = os.getenv(env_key)
    if value is None or not value.strip() or value.strip() == "REPLACE_ME":
        raise SystemExit(f"Error: missing/invalid required env var: {env_key}")
    return value.strip()


def _req_int(env_key: str) -> int:
    raw = _req_str(env_key)
    try:
        return int(raw, 10)
    except ValueError:
        raise SystemExit(f"Error: invalid integer for env var {env_key}: {raw!r}")


def _load_cfg_from_env() -> EnvoyWebConfig:
    return EnvoyWebConfig(
        battery_id=_req_int("ENVOY_BATTERY_ID"),
        user_id=_req_int("ENVOY_USER_ID"),
        email=_req_str("ENVOY_EMAIL"),
        password=_req_str("ENVOY_PASSWORD"),
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CLI for the Envoy Web API client.")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    login = subparsers.add_parser("login", help="Authenticate and print tokens.")
    get = subparsers.add_parser("get", help="Fetch current battery profile config.")

    put = subparsers.add_parser("put", help="Set battery profile and backup percentage.")
    put.add_argument("profile", choices=sorted(ALLOWED_PROFILES))
    put.add_argument("battery_backup_percentage", type=int, help="Backup percentage (0-100).")

    for sub in (login, get, put):
        sub.add_argument(
            "--no-cache",
            action="store_true",
            help="Disable CLI auth cache and force login.",
        )

    args = parser.parse_args(argv)
    if args.mode == "put" and not (0 <= args.battery_backup_percentage <= 100):
        parser.error("battery_backup_percentage must be between 0 and 100")
    if args.mode == "put" and args.profile == "backup_only" and args.battery_backup_percentage != 100:
        parser.error("backup_only requires battery_backup_percentage to be 100")
    return args


def _cache_path() -> Path:
    override = os.getenv("ENVOY_CLI_CACHE_PATH")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent / DEFAULT_CACHE_NAME


def _decode_jwt_exp(token: str) -> int | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        data = base64.urlsafe_b64decode(payload + padding)
        parsed = json.loads(data.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    exp = parsed.get("exp")
    return exp if isinstance(exp, int) else None


def _load_auth_cache(session: aiohttp.ClientSession) -> dict[str, str | None] | None:
    cache_path = _cache_path()
    if not cache_path.exists():
        return None
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    auth_token = cache.get("auth_token")
    if not isinstance(auth_token, str) or not auth_token:
        return None
    exp = cache.get("auth_token_exp")
    now = int(time.time())
    if isinstance(exp, int) and exp <= now:
        _clear_auth_cache()
        return None

    cookies = cache.get("cookies")
    if isinstance(cookies, dict) and cookies:
        session.cookie_jar.update_cookies(cookies, response_url=URL(_BASE_URL))

    xsrf_token = cache.get("xsrf_token")
    if not isinstance(xsrf_token, str):
        xsrf_token = None
    return {"auth_token": auth_token, "xsrf_token": xsrf_token}


def _save_auth_cache(
    session: aiohttp.ClientSession,
    *,
    auth_token: str | None,
    xsrf_token: str | None,
) -> None:
    if not auth_token:
        if os.getenv("ENVOY_DEBUG_AUTH"):
            logging.getLogger(__name__).debug("Auth cache not saved (missing auth token)")
        return
    cookies = {
        name: morsel.value
        for name, morsel in session.cookie_jar.filter_cookies(URL(_BASE_URL)).items()
    }
    cache = {
        "auth_token": auth_token,
        "xsrf_token": xsrf_token,
        "cookies": cookies,
        "auth_token_exp": _decode_jwt_exp(auth_token),
        "saved_at": int(time.time()),
    }
    cache_path = _cache_path()
    if os.getenv("ENVOY_DEBUG_AUTH"):
        logging.getLogger(__name__).debug("Auth cache path: %s", cache_path)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        if not cache_path.parent.exists():
            raise OSError(f"cache directory missing: {cache_path.parent}")
        cache_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as err:
        print(f"Warning: failed to write auth cache: {err}", file=sys.stderr)
        return
    if os.getenv("ENVOY_DEBUG_AUTH"):
        logging.getLogger(__name__).debug("Saved auth cache to %s", cache_path)


def _clear_auth_cache() -> None:
    cache_path = _cache_path()
    try:
        cache_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


async def _async_main(argv: list[str]) -> int:
    args = _parse_args(argv)
    _load_dotenv()
    if os.getenv("ENVOY_DEBUG_AUTH"):
        logging.basicConfig(level=logging.DEBUG, format="%(message)s")
        logging.getLogger(__name__).debug("CLI cache path: %s", _cache_path())
    cfg = _load_cfg_from_env()

    async with aiohttp.ClientSession() as session:
        api = EnvoyWebApi(session, cfg)
        try:
            cached = None
            if args.mode != "login" and not args.no_cache:
                cached = _load_auth_cache(session)
                if cached:
                    api.load_cached_tokens(
                        xsrf_token=cached.get("xsrf_token"),
                        auth_token=cached.get("auth_token"),
                    )
                elif os.getenv("ENVOY_DEBUG_AUTH"):
                    logging.getLogger(__name__).debug(
                        "Auth cache missing or expired; logging in with credentials."
                    )
            if args.mode == "login":
                data = await api.async_login()
            elif args.mode == "get":
                data = await api.async_get_profile()
            else:
                data = await api.async_set_profile(
                    profile=args.profile,
                    battery_backup_percentage=args.battery_backup_percentage,
                )
            if not args.no_cache:
                cached_xsrf, cached_auth = api.cached_tokens()
                _save_auth_cache(
                    session,
                    auth_token=cached_auth,
                    xsrf_token=cached_xsrf,
                )
            print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        except NotImplementedError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
        except _api_module.EnvoyWebAuthError as err:
            if not args.no_cache:
                _clear_auth_cache()
            print(f"Error: {err}", file=sys.stderr)
            print(
                "Hint: re-run `uv run scripts/envoy_cli.py login` to refresh auth.",
                file=sys.stderr,
            )
            return 2
    return 0


def main(argv: list[str]) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
