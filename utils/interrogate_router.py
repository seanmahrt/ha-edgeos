#!/usr/bin/env python3
"""Interactively query EdgeOS JSON endpoints without writing any data to disk."""

from __future__ import annotations

import argparse
from getpass import getpass
import json
import ssl
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import (
    HTTPCookieProcessor,
    Request,
    build_opener,
)

from http.cookiejar import CookieJar

DEFAULT_PATHS = [
    "/api/edge/get.json",
    "/api/edge/data.json?data=sys_info",
    "/api/edge/data.json?data=dhcp_stats",
    "/api/edge/data.json?data=dhcp_leases",
]

SENSITIVE_KEYS = {
    "password",
    "plaintext-password",
    "encrypted-password",
    "login",
    "SESSION_ID",
    "key-file",
    "cert-file",
    "ca-cert-file",
    "dh-file",
}


def _redact_json(value: Any) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if key in SENSITIVE_KEYS:
                output[key] = "***REDACTED***"
            else:
                output[key] = _redact_json(item)
        return output

    if isinstance(value, list):
        return [_redact_json(item) for item in value]

    return value


def _build_https_opener() -> Any:
    cookie_jar = CookieJar()
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    https_handler = __import__("urllib.request", fromlist=["HTTPSHandler"]).HTTPSHandler(
        context=ssl_context
    )

    return build_opener(HTTPCookieProcessor(cookie_jar), https_handler)


def _login(opener: Any, base_url: str, username: str, password: str) -> None:
    body = urlencode({"username": username, "password": password}).encode("utf-8")
    request = Request(base_url, data=body, method="POST")

    with opener.open(request, timeout=15) as response:
        if response.status >= 400:
            raise RuntimeError(f"Login failed with status {response.status}")


def _get_json(opener: Any, url: str) -> Any:
    request = Request(url, method="GET")
    with opener.open(request, timeout=20) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return json.loads(payload)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Query EdgeOS JSON endpoints without persisting credentials or responses"
    )
    parser.add_argument(
        "--paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help="Endpoint paths to query (default: common EdgeOS API paths)",
    )
    parser.add_argument(
        "--no-redact",
        action="store_true",
        help="Show raw JSON without redacting sensitive keys",
    )
    args = parser.parse_args()

    host = input("Router IP/host (example: 192.168.75.1): ").strip()
    username = input("Username: ").strip()
    password = getpass("Password (input hidden): ")

    if not host or not username or not password:
        print("Host, username, and password are required.")
        return 2

    base_url = f"https://{host}"

    opener = _build_https_opener()

    try:
        _login(opener, base_url, username, password)

        print("\nLogin successful. Querying endpoints...\n")

        for path in args.paths:
            path_clean = path if path.startswith("/") else f"/{path}"
            url = f"{base_url}{path_clean}"

            print(f"### {url}")
            try:
                payload = _get_json(opener, url)
                if not args.no_redact:
                    payload = _redact_json(payload)
                print(json.dumps(payload, indent=2, sort_keys=True))
            except json.JSONDecodeError:
                print("Non-JSON response returned.")
            except HTTPError as ex:
                print(f"HTTP error: {ex.code} {ex.reason}")
            except URLError as ex:
                print(f"Connection error: {ex.reason}")
            print()

        return 0

    except HTTPError as ex:
        print(f"Login HTTP error: {ex.code} {ex.reason}")
        return 1
    except URLError as ex:
        print(f"Login connection error: {ex.reason}")
        return 1
    finally:
        # Keep data ephemeral and reduce accidental reuse in long-lived sessions.
        password = ""
        del password


if __name__ == "__main__":
    raise SystemExit(main())
