"""Fear & Greed Index provider: BGeometrics (mirror of alternative.me)."""

from datetime import UTC, datetime
from decimal import Decimal

from backtesting_cripto.domain.models import IndicatorValue
from backtesting_cripto.providers.http_client import DEFAULT_TIMEOUT_SECONDS, get_bytes, parse_json

INDICATOR = "fear_greed"
SOURCE = "bgeometrics"
URL = "https://charts.bgeometrics.com/files/fear_greed.json"


def fetch_payload(url: str = URL, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> bytes:
    """Download the raw JSON payload of the Fear & Greed series."""
    return get_bytes(url, timeout=timeout)


def parse_payload(payload: bytes) -> list[IndicatorValue]:
    """Parse ``[[timestamp_ms, value], ...]`` into daily values (day in UTC)."""
    data = parse_json(payload)
    if not isinstance(data, list):
        msg = "BGeometrics payload must be a list of [timestamp_ms, value] pairs"
        raise ValueError(msg)

    values: list[IndicatorValue] = []
    for entry in data:
        if not isinstance(entry, list) or len(entry) != 2:
            msg = f"unexpected BGeometrics entry: {entry!r}"
            raise ValueError(msg)
        timestamp_ms, raw_value = entry
        day = datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).date()
        values.append(
            IndicatorValue(
                indicator=INDICATOR,
                day=day,
                value=Decimal(str(raw_value)),
                source=SOURCE,
            )
        )
    return values


def fetch_values(url: str = URL, *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> list[IndicatorValue]:
    """Download and parse the full Fear & Greed history from BGeometrics."""
    return parse_payload(fetch_payload(url, timeout=timeout))
