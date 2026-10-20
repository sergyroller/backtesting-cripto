"""Data service: local dataset management, hydration and synchronization.

Centralizes the logic shared by the CLI (scripts/sync_data.py) and the
API: consolidating the immutable raw files into SQLite without network
access (ensure_populated) and refreshing them from the providers.
"""

import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

from pydantic import BaseModel

from backtesting_cripto.domain.contracts import IndicatorSeries, PriceSeries
from backtesting_cripto.domain.exceptions import DataValidationError, InsufficientDataError
from backtesting_cripto.domain.models import IndicatorValue, PriceBar
from backtesting_cripto.engine.calendar import available_date_bounds
from backtesting_cripto.indicators.registry import (
    load_required_indicators,
    required_indicator_names,
)
from backtesting_cripto.providers import (
    alternative_me_fng,
    bgeometrics_fng,
    bitstamp_ohlc,
)
from backtesting_cripto.storage.raw_store import RawDatasetEntry, RawStore
from backtesting_cripto.storage.repository import BacktestRepository
from backtesting_cripto.strategies import StrategyRegistry, default_registry
from backtesting_cripto.validation.dataset_checks import (
    PRICES_FIRST_DAY,
    validate_fear_greed_series,
    validate_price_bars,
)

FNG_DATASET_ID = "fear_greed_bgeometrics"
FNG_DATASET_ID_FALLBACK = "fear_greed_alternative_me"
PRICES_DATASET_ID = "prices_btceur_bitstamp"

FNG_LICENSE = "alternative.me Fear & Greed Index (CC BY 4.0)"
PRICES_LICENSE = "Bitstamp public market data"

DEFAULT_ASSET = "BTC"
DEFAULT_QUOTE = "EUR"


class DatasetInfo(BaseModel):
    """Public view of a stored dataset."""

    id: str
    source: str
    first_day: date
    last_day: date
    record_count: int
    retrieved_at: str
    sha256: str
    license: str


class AvailableRange(BaseModel):
    """Date window a strategy can run on with the stored data."""

    start: date | None = None
    end: date | None = None


class DataStatus(BaseModel):
    """State of the local datasets."""

    datasets: list[DatasetInfo]
    dataset_hash: str
    last_closed_day: date
    available_ranges: dict[str, AvailableRange]
    available_start: date | None = None
    available_end: date | None = None
    total_records: int = 0
    is_stale: bool = False


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


class DataService:
    """Encapsulates the local datasets and their synchronization."""

    def __init__(
        self,
        repo: BacktestRepository,
        raw_store: RawStore,
        registry: StrategyRegistry = default_registry,
    ) -> None:
        self._repo = repo
        self._raw_store = raw_store
        self._registry = registry

    @property
    def raw_store(self) -> RawStore:
        return self._raw_store

    @property
    def repo(self) -> BacktestRepository:
        return self._repo

    # --- Series loading -------------------------------------------------------

    def _load_series(self) -> tuple[PriceSeries, dict[str, IndicatorSeries]]:
        prices = self._repo.price_series(asset=DEFAULT_ASSET, quote=DEFAULT_QUOTE)
        required = required_indicator_names(self._registry)
        indicators = load_required_indicators(self._repo, required)
        return prices, indicators

    # --- Offline hydration ----------------------------------------------------

    def ensure_populated(self, now: datetime | None = None) -> bool:
        """Populate SQLite from data/raw/ when the database has no datasets.

        Returns True when the hydration actually ran. Never touches the
        network, so a fresh clone is ready to run backtests. ``now``
        allows injecting the reference clock (tests).
        """
        if self._repo.has_datasets():
            return False
        if not self._raw_store.manifest_path.exists():
            return False
        self._consolidate_from_raw(now)
        return True

    def _consolidate_from_raw(self, now: datetime | None = None) -> None:
        """Parse the frozen raw files and load them into SQLite (no network).

        The raw payloads may contain the still-open day (e.g. today's
        Fear & Greed reading), so both series are trimmed to the last
        day where BOTH have data and which is not after the last closed
        UTC day. This keeps the hydration correct whatever the clock
        says, even on a clone whose frozen data is months old.
        """
        closed_day = last_closed_utc_day(now)
        fng_values = [
            value for value in self._load_raw_fear_greed() if value.day <= closed_day
        ]
        bars = [bar for bar in self._load_raw_prices() if bar.day <= closed_day]

        if not fng_values or not bars:
            msg = "no usable data in the raw store for the current window"
            raise DataValidationError(msg)

        available_last = min(closed_day, fng_values[-1].day, bars[-1].day)
        fng_values = [value for value in fng_values if value.day <= available_last]
        bars = [bar for bar in bars if bar.day <= available_last]

        validate_fear_greed_series(fng_values, last_closed_day=available_last)
        validate_price_bars(bars, last_closed_day=available_last)

        fng_entry = self._raw_store.latest_entry(FNG_DATASET_ID) or (
            self._raw_store.latest_entry(FNG_DATASET_ID_FALLBACK)
        )
        fng_sha = consolidated_hash([value.model_dump(mode="json") for value in fng_values])
        self._repo.upsert_dataset(
            dataset_id=FNG_DATASET_ID,
            source=fng_entry.source if fng_entry else bgeometrics_fng.SOURCE,
            url=fng_entry.url if fng_entry else bgeometrics_fng.URL,
            retrieved_at=fng_entry.retrieved_at if fng_entry else "",
            sha256=fng_sha,
            first_day=fng_values[0].day,
            last_day=fng_values[-1].day,
            record_count=len(fng_values),
            license=FNG_LICENSE,
        )
        self._repo.replace_indicator_values(dataset_id=FNG_DATASET_ID, values=fng_values)

        prices_sha = consolidated_hash([bar.model_dump(mode="json") for bar in bars])
        self._repo.upsert_dataset(
            dataset_id=PRICES_DATASET_ID,
            source=bitstamp_ohlc.SOURCE,
            url=bitstamp_ohlc.URL_TEMPLATE,
            retrieved_at=datetime.now(UTC).isoformat(),
            sha256=prices_sha,
            first_day=bars[0].day,
            last_day=bars[-1].day,
            record_count=len(bars),
            license=PRICES_LICENSE,
        )
        self._repo.replace_price_bars(dataset_id=PRICES_DATASET_ID, bars=bars)

    def _load_raw_fear_greed(self) -> list[IndicatorValue]:
        entry = self._raw_store.latest_entry(FNG_DATASET_ID) or (
            self._raw_store.latest_entry(FNG_DATASET_ID_FALLBACK)
        )
        if entry is None:
            msg = "no frozen fear_greed dataset in the raw store"
            raise DataValidationError(msg)
        parse: Callable[[bytes], list[IndicatorValue]] = (
            bgeometrics_fng.parse_payload
            if entry.source == bgeometrics_fng.SOURCE
            else alternative_me_fng.parse_payload
        )
        return parse(self._raw_store.read_payload(entry))

    def _load_raw_prices(self) -> list[PriceBar]:
        bars_by_day: dict[date, PriceBar] = {}
        manifest = sorted(
            self._raw_store.load_manifest(),
            key=lambda item: (item.retrieved_at, item.relative_path),
        )
        for entry in manifest:
            if entry.source == bitstamp_ohlc.SOURCE:
                for bar in bitstamp_ohlc.parse_payload(self._raw_store.read_payload(entry)):
                    if bar.day >= PRICES_FIRST_DAY:
                        # Later downloads win: plain assignment, not setdefault.
                        bars_by_day[bar.day] = bar
        if not bars_by_day:
            msg = "no frozen bitstamp dataset in the raw store"
            raise DataValidationError(msg)
        return [bars_by_day[day] for day in sorted(bars_by_day)]

    # --- Network synchronization ---------------------------------------------

    def sync_data(self, now: datetime | None = None) -> DataStatus:
        """Download fresh data up to the last closed UTC day and store it."""
        closed_day = last_closed_utc_day(now)

        fng_entry, fng_values = sync_fear_greed(self._raw_store, closed_day)
        _price_entries, bars = sync_prices(self._raw_store, closed_day)

        fng_sha = consolidated_hash([value.model_dump(mode="json") for value in fng_values])
        self._repo.upsert_dataset(
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
        self._repo.replace_indicator_values(dataset_id=fng_entry.id, values=fng_values)

        prices_sha = consolidated_hash([bar.model_dump(mode="json") for bar in bars])
        self._repo.upsert_dataset(
            dataset_id=PRICES_DATASET_ID,
            source=bitstamp_ohlc.SOURCE,
            url=bitstamp_ohlc.URL_TEMPLATE,
            retrieved_at=datetime.now(UTC).isoformat(),
            sha256=prices_sha,
            first_day=bars[0].day,
            last_day=bars[-1].day,
            record_count=len(bars),
            license=PRICES_LICENSE,
        )
        self._repo.replace_price_bars(dataset_id=PRICES_DATASET_ID, bars=bars)

        return self.get_data_status()

    # --- Status ---------------------------------------------------------------

    def available_ranges(self) -> dict[str, AvailableRange]:
        """Available date window per registered strategy (None when no data)."""
        try:
            prices, indicators = self._load_series()
        except LookupError:
            return {
                metadata.strategy_id: AvailableRange()
                for metadata in self._registry.list()
            }

        ranges: dict[str, AvailableRange] = {}
        for metadata in self._registry.list():
            try:
                start, end = available_date_bounds(
                    prices, indicators, metadata.required_indicators
                )
                ranges[metadata.strategy_id] = AvailableRange(start=start, end=end)
            except (LookupError, InsufficientDataError):
                ranges[metadata.strategy_id] = AvailableRange()
        return ranges

    def get_data_status(self) -> DataStatus:
        """Current state of the local datasets."""
        datasets = [
            DatasetInfo(
                id=record.id,
                source=record.source,
                first_day=record.first_day,
                last_day=record.last_day,
                record_count=record.record_count,
                retrieved_at=record.retrieved_at,
                sha256=record.sha256,
                license=record.license,
            )
            for record in self._repo.list_datasets()
        ]
        ranges = self.available_ranges()

        primary = next(iter(ranges.values()), None)
        closed_day = last_closed_utc_day()
        newest_day = max((record.last_day for record in self._repo.list_datasets()), default=None)
        is_stale = newest_day is not None and (closed_day - newest_day).days > 2

        return DataStatus(
            datasets=datasets,
            dataset_hash=self._raw_store.dataset_hash(),
            last_closed_day=closed_day,
            available_ranges=ranges,
            available_start=primary.start if primary else None,
            available_end=primary.end if primary else None,
            total_records=sum(dataset.record_count for dataset in datasets),
            is_stale=is_stale,
        )
