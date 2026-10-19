"""CLI to download, validate and consolidate historical data.

Usage (from the project root)::

    uv run python scripts/sync_data.py

Downloads the Fear & Greed index (BGeometrics with alternative.me
fallback) and BTC/EUR daily candles (Bitstamp), stores the immutable raw
files under data/raw/, validates the datasets and populates
data/backtesting.sqlite3 with data up to the last closed UTC day.
"""

import json
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from backtesting_cripto.domain.models import IndicatorValue, PriceBar
from backtesting_cripto.providers import (
    alternative_me_fng,
    bgeometrics_fng,
    bitstamp_ohlc,
)
from backtesting_cripto.storage.raw_store import RawDatasetEntry, RawStore
from backtesting_cripto.storage.repository import BacktestRepository
from backtesting_cripto.validation.dataset_checks import (
    PRICES_FIRST_DAY,
    validate_fear_greed_series,
    validate_price_bars,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "backtesting.sqlite3"

FNG_DATASET_ID = "fear_greed_bgeometrics"
FNG_DATASET_ID_FALLBACK = "fear_greed_alternative_me"
PRICES_DATASET_ID = "prices_btceur_bitstamp"

FNG_LICENSE = "alternative.me Fear & Greed Index (CC BY 4.0)"
PRICES_LICENSE = "Bitstamp public market data"


def last_closed_utc_day(now: datetime | None = None) -> date:
    """Last day whose UTC candle is fully closed (today_utc - 1 day)."""
    return (now or datetime.now(UTC)).date() - timedelta(days=1)


def consolidated_hash(payload: object) -> str:
    """Deterministic SHA-256 over the canonical JSON of a consolidated dataset."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(canonical.encode("utf-8")).hexdigest()


def sync_fear_greed(
    store: RawStore, closed_day: date
) -> tuple[RawDatasetEntry, list[IndicatorValue]]:
    """Download, filter, validate and store the Fear & Greed series."""
    try:
        payload = bgeometrics_fng.fetch_payload()
        dataset_id = FNG_DATASET_ID
        source = bgeometrics_fng.SOURCE
        url = bgeometrics_fng.URL
        parse: Callable[[bytes], list[IndicatorValue]] = bgeometrics_fng.parse_payload
    except OSError:
        print("  BGeometrics no responde; usando alternative.me como respaldo")
        payload = alternative_me_fng.fetch_payload()
        dataset_id = FNG_DATASET_ID_FALLBACK
        source = alternative_me_fng.SOURCE
        url = alternative_me_fng.URL
        parse = alternative_me_fng.parse_payload

    values = [value for value in parse(payload) if value.day <= closed_day]
    validate_fear_greed_series(values, last_closed_day=closed_day)

    entry = store.save(
        dataset_id=dataset_id,
        source=source,
        url=url,
        payload=payload,
        first_day=values[0].day.isoformat(),
        last_day=values[-1].day.isoformat(),
        record_count=len(values),
        license=FNG_LICENSE,
    )
    return entry, values


def sync_prices(
    store: RawStore, closed_day: date
) -> tuple[list[RawDatasetEntry], list[PriceBar]]:
    """Download page by page, validate and store BTC/EUR daily candles."""
    entries: list[RawDatasetEntry] = []
    bars_by_day: dict[date, PriceBar] = {}

    pages = bitstamp_ohlc.fetch_pages(PRICES_FIRST_DAY, closed_day)
    for page_index, (payload, page_bars) in enumerate(pages):
        entry = store.save(
            dataset_id=f"{PRICES_DATASET_ID}_p{page_index:04d}",
            source=bitstamp_ohlc.SOURCE,
            url=bitstamp_ohlc.URL_TEMPLATE,
            payload=payload,
            first_day=min(bar.day for bar in page_bars).isoformat(),
            last_day=max(bar.day for bar in page_bars).isoformat(),
            record_count=len(page_bars),
            license=PRICES_LICENSE,
        )
        entries.append(entry)

        for bar in page_bars:
            if PRICES_FIRST_DAY <= bar.day <= closed_day:
                bars_by_day[bar.day] = bar

    bars = [bars_by_day[day] for day in sorted(bars_by_day)]
    validate_price_bars(bars, last_closed_day=closed_day)
    return entries, bars


def main() -> int:
    """Run the full synchronization pipeline."""
    closed_day = last_closed_utc_day()
    print(f"Sincronizando datos hasta el último día cerrado (UTC): {closed_day.isoformat()}")

    store = RawStore(RAW_DIR)

    fng_entry, fng_values = sync_fear_greed(store, closed_day)
    print(
        f"  Fear & Greed: {len(fng_values)} registros "
        f"({fng_values[0].day.isoformat()} → {fng_values[-1].day.isoformat()})"
    )

    price_entries, bars = sync_prices(store, closed_day)
    print(
        f"  BTC/EUR: {len(bars)} velas diarias "
        f"({bars[0].day.isoformat()} → {bars[-1].day.isoformat()})"
    )

    prices_sha = consolidated_hash([bar.model_dump(mode="json") for bar in bars])
    fng_sha = consolidated_hash([value.model_dump(mode="json") for value in fng_values])

    with BacktestRepository(DB_PATH) as repo:
        repo.upsert_dataset(
            dataset_id=fng_entry.id,
            source=fng_entry.source,
            url=fng_entry.url,
            retrieved_at=fng_entry.retrieved_at,
            sha256=fng_sha,
            first_day=fng_values[0].day,
            last_day=fng_values[-1].day,
            record_count=len(fng_values),
            license=FNG_LICENSE,
        )
        repo.replace_indicator_values(dataset_id=fng_entry.id, values=fng_values)

        repo.upsert_dataset(
            dataset_id=PRICES_DATASET_ID,
            source=bitstamp_ohlc.SOURCE,
            url=bitstamp_ohlc.URL_TEMPLATE,
            retrieved_at=price_entries[-1].retrieved_at,
            sha256=prices_sha,
            first_day=bars[0].day,
            last_day=bars[-1].day,
            record_count=len(bars),
            license=PRICES_LICENSE,
        )
        repo.replace_price_bars(dataset_id=PRICES_DATASET_ID, bars=bars)

    print(f"Base de datos actualizada: {DB_PATH.relative_to(PROJECT_ROOT)}")
    print(f"Entradas crudas en {RAW_DIR.relative_to(PROJECT_ROOT)}: {len(store.load_manifest())}")
    print(f"dataset_hash del manifiesto: {store.dataset_hash()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
