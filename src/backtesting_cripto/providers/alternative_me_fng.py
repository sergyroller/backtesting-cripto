"""Fear & Greed Index fallback provider: alternative.me official API."""

from datetime import UTC, datetime
from decimal import Decimal

from backtesting_cripto.domain.models import IndicatorValue
from backtesting_cripto.providers.http_client import DEFAULT_TIMEOUT_SECONDS, get_bytes, parse_json

INDICATOR = "fear_greed"
SOURCE = "alternative.me"
URL = "https://api.alternative.me/fng/?limit=0&format=json"


def fetch_payload(url: str = URL, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    """Download the raw JSON payload of the Fear & Greed series."""
    return get_bytes(url, timeout=timeout)


def parse_payload(payload: bytes) -> list[IndicatorValue]:
    """Parse ``{"data": [{"timestamp": ..., "value": ...}, ...]}`` (day in UTC)."""
    data = parse_json(payload)
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        msg = "alternative.me payload must contain a 'data' list"
        raise ValueError(msg)

    values: list[IndicatorValue] = []
    for entry in data["data"]:
        if not isinstance(entry, dict) or "timestamp" not in entry or "value" not in entry:
            msg = f"unexpected alternative.me entry: {entry!r}"
            raise ValueError(msg)
        day = datetime.fromtimestamp(int(entry["timestamp"]), tz=UTC).date()
        values.append(
            IndicatorValue(
                indicator=INDICATOR,
                day=day,
                value=Decimal(str(entry["value"])),
                source=SOURCE,
            )
        )
    return values


def fetch_values(url: str = URL, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[IndicatorValue]:
    """Download and parse the full Fear & Greed history from alternative.me."""
    return parse_payload(fetch_payload(url, timeout=timeout))
