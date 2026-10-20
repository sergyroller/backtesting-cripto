"""Integration and regression tests over the frozen dataset (plan section G.2).

Everything runs 100% offline: the real series are parsed from the
immutable raw files versioned in data/raw/, so these tests pass on any
fresh clone without needing data/backtesting.sqlite3.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting_cripto.domain.models import BacktestConfig, BacktestResult, FearGreedParams
from backtesting_cripto.engine.runner import run_backtest
from backtesting_cripto.providers import alternative_me_fng, bgeometrics_fng, bitstamp_ohlc
from backtesting_cripto.storage.raw_store import RawStore
from backtesting_cripto.storage.repository import MemoryIndicatorSeries, MemoryPriceSeries
from backtesting_cripto.strategies import FearGreedStrategy

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

WINDOW_START = date(2018, 2, 1)
WINDOW_END = date(2026, 10, 18)
DEFAULT_PARAMS = FearGreedParams().model_dump(mode="json")


def load_frozen_series() -> tuple[MemoryPriceSeries, MemoryIndicatorSeries]:
    """Parse the frozen raw files into in-memory series (no network, no SQLite)."""
    if not RAW_DIR.exists():
        pytest.fail(f"missing {RAW_DIR}: run 'uv run python scripts/sync_data.py' first")
    store = RawStore(RAW_DIR)

    entry = store.latest_entry("fear_greed_bgeometrics") or store.latest_entry(
        "fear_greed_alternative_me"
    )
    if entry is None:
        pytest.fail(f"no frozen fear_greed dataset in {RAW_DIR}")
    parser = (
        bgeometrics_fng if entry.source == bgeometrics_fng.SOURCE else alternative_me_fng
    )
    payload_values = parser.parse_payload(store.read_payload(entry))
    values = [value for value in payload_values if value.day <= WINDOW_END]

    bars_by_day: dict[date, object] = {}
    for manifest_entry in sorted(store.load_manifest(), key=lambda item: item.relative_path):
        if manifest_entry.source == bitstamp_ohlc.SOURCE:
            for bar in bitstamp_ohlc.parse_payload(store.read_payload(manifest_entry)):
                if bar.day <= WINDOW_END:
                    bars_by_day.setdefault(bar.day, bar)
    if not bars_by_day:
        pytest.fail(f"no frozen bitstamp dataset in {RAW_DIR}")

    prices = MemoryPriceSeries.from_bars(list(bars_by_day.values()))
    indicators = MemoryIndicatorSeries.from_values(values)
    return prices, indicators


def run_fear_greed(mode: str) -> BacktestResult:
    prices, indicators = load_frozen_series()
    config = BacktestConfig(
        asset="BTC",
        quote="EUR",
        strategy_id="fear_greed",
        start_date=WINDOW_START,
        end_date=WINDOW_END,
        execution_mode=mode,  # type: ignore[arg-type]
        strategy_params=DEFAULT_PARAMS,
    )
    dataset_hash = RawStore(RAW_DIR).dataset_hash()
    return run_backtest(
        config,
        prices,
        {"fear_greed": indicators},
        FearGreedStrategy(),
        dataset_hash=dataset_hash,
        run_id=f"regression-{mode}",
    )


def test_regression_close_same_day() -> None:
    result = run_fear_greed("close_same_day")
    metrics = result.metrics

    assert metrics.total_operations == 121
    assert metrics.operations_by_reason == {
        "daily_<10": 42,
        "monday_10_14": 23,
        "monday_15_19": 20,
        "monday_20_24": 36,
    }
    assert metrics.total_invested_eur == Decimal("13300.00")
    assert metrics.btc_accumulated == Decimal("1.10037310")
    assert metrics.average_buy_price_eur == Decimal("12086.81")
    assert metrics.final_price_eur == Decimal("73067.27")
    assert metrics.final_portfolio_value_eur == Decimal("80401.26")
    assert metrics.pnl_eur == Decimal("67101.26")
    assert metrics.roi_pct == Decimal("504.52")
    assert result.incidents == []


def test_regression_close_next_day() -> None:
    result = run_fear_greed("close_next_day")
    metrics = result.metrics

    # Same decisions, executed one day later: same operations and invested
    # capital, different BTC and results.
    assert metrics.total_operations == 121
    assert metrics.operations_by_reason == {
        "daily_<10": 42,
        "monday_10_14": 23,
        "monday_15_19": 20,
        "monday_20_24": 36,
    }
    assert metrics.total_invested_eur == Decimal("13300.00")
    assert metrics.btc_accumulated == Decimal("1.09588203")
    assert metrics.average_buy_price_eur == Decimal("12136.34")
    assert metrics.final_price_eur == Decimal("73067.27")
    assert metrics.final_portfolio_value_eur == Decimal("80073.11")
    assert metrics.pnl_eur == Decimal("66773.11")
    assert metrics.roi_pct == Decimal("502.05")
    assert result.incidents == []


def test_regression_result_hash_is_reproducible() -> None:
    prices, indicators = load_frozen_series()
    config = BacktestConfig(
        asset="BTC",
        quote="EUR",
        strategy_id="fear_greed",
        start_date=WINDOW_START,
        end_date=WINDOW_END,
        execution_mode="close_same_day",
        strategy_params=DEFAULT_PARAMS,
    )
    dataset_hash = RawStore(RAW_DIR).dataset_hash()

    first = run_backtest(
        config,
        prices,
        {"fear_greed": indicators},
        FearGreedStrategy(),
        dataset_hash=dataset_hash,
        run_id="run-one",
    )
    second = run_backtest(
        config,
        prices,
        {"fear_greed": indicators},
        FearGreedStrategy(),
        dataset_hash=dataset_hash,
        run_id="run-two",
        created_at="2027-01-01T00:00:00+00:00",  # type: ignore[arg-type]
    )

    assert first.run_id != second.run_id
    assert first.result_hash == second.result_hash
    assert first.config_hash == second.config_hash
