"""BTC/EUR daily OHLC provider: Bitstamp public API (paginated)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from backtesting_cripto.domain.models import PriceBar
from backtesting_cripto.providers.http_client import DEFAULT_TIMEOUT_SECONDS, get_bytes, parse_json

ASSET = "BTC"
QUOTE = "EUR"
SOURCE = "bitstamp"
URL_TEMPLATE = (
    "https://www.bitstamp.net/api/v2/ohlc/btceur/"
    "?step=86400&limit=1000&start={start}&end={end}"
)
PAGE_DAYS = 1000


def _day_start_timestamp(day: date) -> int:
    """Unix timestamp (seconds) of 00:00:00 UTC of the given date."""
    return int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())


def parse_payload(payload: bytes) -> list[PriceBar]:
    """Parse a Bitstamp OHLC page into daily price bars (day in UTC)."""
    data = parse_json(payload)
    if not isinstance(data, dict):
        msg = "Bitstamp payload must be an object with a 'data' field"
        raise ValueError(msg)
    data_field = data.get("data")
    ohlc = data_field.get("ohlc") if isinstance(data_field, dict) else None
    if not isinstance(ohlc, list):
        msg = "Bitstamp payload must contain data.ohlc list"
        raise ValueError(msg)

    bars: list[PriceBar] = []
    for entry in ohlc:
        if not isinstance(entry, dict):
            msg = f"unexpected Bitstamp entry: {entry!r}"
            raise ValueError(msg)
        day = datetime.fromtimestamp(int(entry["timestamp"]), tz=UTC).date()
        bars.append(
            PriceBar(
                asset=ASSET,
                quote=QUOTE,
                day=day,
                open=Decimal(str(entry["open"])),
                high=Decimal(str(entry["high"])),
                low=Decimal(str(entry["low"])),
                close=Decimal(str(entry["close"])),
                volume=Decimal(str(entry["volume"])),
                source=SOURCE,
            )
        )
    return bars


def fetch_pages(
    start_day: date,
    end_day: date,
    url_template: str = URL_TEMPLATE,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[tuple[bytes, list[PriceBar]]]:
    """Download the series page by page, keeping each raw payload.

    Bitstamp returns at most PAGE_DAYS candles ending at ``end`` (``start``
    is only a hint), so pagination anchors on ``end`` and walks backwards
    until reaching start_day. Returns (raw_payload, new_bars) per page.
    """
    pages: list[tuple[bytes, list[PriceBar]]] = []
    seen: set[date] = set()
    page_end = end_day

    while page_end >= start_day:
        url = url_template.format(start=0, end=_day_start_timestamp(page_end))
        payload = get_bytes(url, timeout=timeout)
        page_bars = parse_payload(payload)
        if not page_bars:
            break

        new_bars = [bar for bar in page_bars if bar.day not in seen]
        if not new_bars:
            break
        pages.append((payload, new_bars))
        seen.update(bar.day for bar in new_bars)

        oldest = min(bar.day for bar in page_bars)
        if oldest <= start_day:
            break
        next_page_end = oldest - timedelta(days=1)
        if next_page_end >= page_end:
            break  # no progress: avoid an infinite loop on unexpected payloads
        page_end = next_page_end

    return pages


def fetch_bars(
    start_day: date,
    end_day: date,
    url_template: str = URL_TEMPLATE,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[PriceBar]:
    """Download daily candles from start_day to end_day (inclusive, UTC).

    Deduplicates by day and returns bars sorted by day.
    """
    bars_by_day: dict[date, PriceBar] = {}
    for _payload, page_bars in fetch_pages(
        start_day, end_day, url_template, timeout=timeout
    ):
        for bar in page_bars:
            if start_day <= bar.day <= end_day:
                bars_by_day[bar.day] = bar

    return [bars_by_day[day] for day in sorted(bars_by_day)]
