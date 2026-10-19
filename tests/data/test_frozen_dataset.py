"""Integrity tests over the frozen real dataset stored in data/raw/.

These tests run 100% offline: they read the immutable raw files that are
versioned in git, so they must pass on any fresh clone of the repository.
"""

from datetime import date, timedelta
from pathlib import Path

import pytest

from backtesting_cripto.domain.models import IndicatorValue, PriceBar
from backtesting_cripto.providers import (
    alternative_me_fng,
    bgeometrics_fng,
    bitstamp_ohlc,
)
from backtesting_cripto.storage.raw_store import RawStore
from backtesting_cripto.validation.dataset_checks import (
    PRICES_FIRST_DAY,
    validate_fear_greed_series,
    validate_price_bars,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

WINDOW_START = date(2018, 2, 1)
WINDOW_END = date(2026, 10, 18)
EXPECTED_MONDAYS = 454
EXPECTED_FNG_BELOW_THRESHOLD = 42


def load_frozen_fear_greed() -> list[IndicatorValue]:
    """Parse the frozen Fear & Greed raw file (no network)."""
    if not RAW_DIR.exists():
        pytest.fail(f"missing {RAW_DIR}: run 'uv run python scripts/sync_data.py' first")
    store = RawStore(RAW_DIR)
    entry = store.latest_entry("fear_greed_bgeometrics") or store.latest_entry(
        "fear_greed_alternative_me"
    )
    if entry is None:
        pytest.fail(f"no frozen fear_greed dataset in {RAW_DIR}")
    provider = (
        bgeometrics_fng if entry.source == bgeometrics_fng.SOURCE else alternative_me_fng
    )
    return provider.parse_payload(store.read_payload(entry))


def load_frozen_price_bars() -> list[PriceBar]:
    """Parse every frozen Bitstamp raw page (no network), deduplicated by day."""
    if not RAW_DIR.exists():
        pytest.fail(f"missing {RAW_DIR}: run 'uv run python scripts/sync_data.py' first")
    store = RawStore(RAW_DIR)
    bars_by_day: dict[date, PriceBar] = {}
    for entry in sorted(store.load_manifest(), key=lambda item: item.relative_path):
        if entry.source == bitstamp_ohlc.SOURCE:
            for bar in bitstamp_ohlc.parse_payload(store.read_payload(entry)):
                bars_by_day.setdefault(bar.day, bar)
    if not bars_by_day:
        pytest.fail(f"no frozen bitstamp dataset in {RAW_DIR}")
    return [bars_by_day[day] for day in sorted(bars_by_day)]


def test_frozen_fear_greed_covers_the_regression_window() -> None:
    values = load_frozen_fear_greed()
    window = [value for value in values if WINDOW_START <= value.day <= WINDOW_END]
    assert len(window) > 3000
    assert min(value.day for value in values) == WINDOW_START
    assert max(value.day for value in values) >= WINDOW_END


def test_frozen_window_has_454_mondays() -> None:
    bars = load_frozen_price_bars()
    days = {bar.day for bar in bars}
    mondays = [
        day
        for day in sorted(days)
        if WINDOW_START <= day <= WINDOW_END and day.weekday() == 0
    ]
    assert len(mondays) == EXPECTED_MONDAYS


def test_frozen_fear_greed_has_42_days_below_threshold() -> None:
    values = load_frozen_fear_greed()
    window = [value for value in values if WINDOW_START <= value.day <= WINDOW_END]
    below = [value for value in window if value.value < 10]
    assert len(below) == EXPECTED_FNG_BELOW_THRESHOLD


def test_frozen_prices_are_daily_continuous_from_2018() -> None:
    bars = load_frozen_price_bars()
    days = {bar.day for bar in bars}
    cursor = PRICES_FIRST_DAY
    while cursor <= WINDOW_END:
        assert cursor in days, f"missing daily price bar on {cursor.isoformat()}"
        cursor += timedelta(days=1)


def test_frozen_datasets_pass_dataset_checks() -> None:
    values = [value for value in load_frozen_fear_greed() if value.day <= WINDOW_END]
    validate_fear_greed_series(values, last_closed_day=WINDOW_END)

    bars = [bar for bar in load_frozen_price_bars() if bar.day <= WINDOW_END]
    validate_price_bars(bars, last_closed_day=WINDOW_END)
