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
import importlib.util
import json
import os
import sys
from pathlib import Path

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

    subparsers.add_parser("get", help="Fetch current battery profile config.")

    put = subparsers.add_parser("put", help="Set battery profile and backup percentage.")
    put.add_argument("profile", choices=sorted(ALLOWED_PROFILES))
    put.add_argument("battery_backup_percentage", type=int, help="Backup percentage (0-100).")

    args = parser.parse_args(argv)
    if args.mode == "put" and not (0 <= args.battery_backup_percentage <= 100):
        parser.error("battery_backup_percentage must be between 0 and 100")
    return args


async def _async_main(argv: list[str]) -> int:
    args = _parse_args(argv)
    _load_dotenv()
    cfg = _load_cfg_from_env()

    async with aiohttp.ClientSession() as session:
        api = EnvoyWebApi(session, cfg)
        try:
            if args.mode == "get":
                data = await api.async_get_profile()
            else:
                data = await api.async_set_profile(
                    profile=args.profile,
                    battery_backup_percentage=args.battery_backup_percentage,
                )
            print(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        except NotImplementedError as err:
            print(f"Error: {err}", file=sys.stderr)
            return 2
    return 0


def main(argv: list[str]) -> int:
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
