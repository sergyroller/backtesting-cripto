"""Minimal stdlib HTTP client used by data providers (no heavy dependencies)."""

import json
import urllib.request

USER_AGENT = (
    "backtesting-cripto/0.1 (+https://github.com/sergyroller/backtesting-cripto)"
)
DEFAULT_TIMEOUT_SECONDS = 30


def get_bytes(url: str, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    """Download the raw body of a URL with a clear User-Agent and timeout."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload: bytes = response.read()
    return payload


def parse_json(payload: bytes) -> object:
    """Parse a JSON body into plain Python objects."""
    parsed: object = json.loads(payload.decode("utf-8"))
    return parsed
