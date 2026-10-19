"""Unit tests for domain models, rounding helpers and canonical hashing."""

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from backtesting_cripto.domain.contracts import StrategyContext
from backtesting_cripto.domain.models import (
    BacktestConfig,
    BacktestResult,
    EquityPoint,
    FearGreedParams,
    Fill,
    IndicatorValue,
    Metrics,
    OrderIntent,
    PriceBar,
    WeeklyBandRule,
    canonical_hash,
    quantize_btc,
    quantize_eur,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Modules the pure domain layer must never import (network, DB, web).
FORBIDDEN_ROOT_MODULES = frozenset(
    {
        "aiohttp",
        "fastapi",
        "ftplib",
        "http",
        "httpx",
        "psycopg",
        "psycopg2",
        "pymongo",
        "redis",
        "requests",
        "socket",
        "sqlalchemy",
        "sqlite3",
        "urllib",
        "urllib3",
    }
)


def make_price_bar(**overrides: Any) -> PriceBar:
    payload: dict[str, Any] = {
        "asset": "BTC",
        "quote": "EUR",
        "day": date(2024, 1, 1),
        "open": Decimal("40000.00"),
        "high": Decimal("41000.00"),
        "low": Decimal("39000.00"),
        "close": Decimal("40500.00"),
        "volume": Decimal("1234.5678"),
        "source": "bitstamp",
    }
    payload.update(overrides)
    return PriceBar(**payload)


def make_fill(**overrides: Any) -> Fill:
    payload: dict[str, Any] = {
        "execution_day": date(2024, 1, 1),
        "decision_day": date(2024, 1, 1),
        "asset": "BTC",
        "index_value": Decimal("12"),
        "amount_eur": Decimal("100.00"),
        "price_eur": Decimal("10000.00"),
        "btc_quantity": Decimal("0.01000000"),
        "reason": "monday_10_14",
    }
    payload.update(overrides)
    return Fill(**payload)


def make_metrics(**overrides: Any) -> Metrics:
    payload: dict[str, Any] = {
        "total_invested_eur": Decimal("200.00"),
        "total_operations": 2,
        "operations_by_reason": {"monday_10_14": 1, "daily_<10": 1},
        "btc_accumulated": Decimal("0.01500000"),
        "average_buy_price_eur": Decimal("13333.33"),
        "final_price_eur": Decimal("30000.00"),
        "final_portfolio_value_eur": Decimal("450.00"),
        "pnl_eur": Decimal("250.00"),
        "roi_pct": Decimal("125.00"),
        "max_drawdown_pct": Decimal("0.00"),
    }
    payload.update(overrides)
    return Metrics(**payload)


def make_backtest_result(**overrides: Any) -> BacktestResult:
    config = BacktestConfig(
        start_date=date(2018, 2, 1),
        end_date=date(2026, 10, 18),
        strategy_params={},
    )
    payload: dict[str, Any] = {
        "run_id": "run-001",
        "created_at": "2026-10-19T10:00:00",
        "code_version": "0.1.0",
        "dataset_hash": "a" * 64,
        "config": config,
        "config_hash": canonical_hash(config),
        "fills": [make_fill()],
        "equity_curve": [
            EquityPoint(
                day=date(2024, 1, 1),
                invested_eur=Decimal("100.00"),
                btc_accumulated=Decimal("0.01000000"),
                close_price_eur=Decimal("10000.00"),
                portfolio_value_eur=Decimal("100.00"),
                drawdown_pct=Decimal("0.00"),
            )
        ],
        "metrics": make_metrics(),
        "incidents": [],
        "result_hash": "b" * 64,
    }
    payload.update(overrides)
    return BacktestResult(**payload)


# --- WeeklyBandRule ----------------------------------------------------------


def test_weekly_band_rule_accepts_valid_bounds() -> None:
    band = WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("200.00"))
    assert band.min_value == 10
    assert band.max_value == 14
    assert band.amount_eur == Decimal("200.00")


def test_weekly_band_rule_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError):
        WeeklyBandRule(min_value=14, max_value=10, amount_eur=Decimal("200.00"))


def test_weekly_band_rule_rejects_out_of_range_bounds() -> None:
    with pytest.raises(ValidationError):
        WeeklyBandRule(min_value=-1, max_value=10, amount_eur=Decimal("200.00"))
    with pytest.raises(ValidationError):
        WeeklyBandRule(min_value=10, max_value=101, amount_eur=Decimal("200.00"))


def test_weekly_band_rule_rejects_non_positive_amount() -> None:
    with pytest.raises(ValidationError):
        WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("0.00"))


# --- FearGreedParams ---------------------------------------------------------


def test_fear_greed_params_defaults_match_the_plan() -> None:
    params = FearGreedParams()
    assert params.daily_below_threshold == 10
    assert params.daily_amount_eur == Decimal("50.00")
    assert [band.min_value for band in params.weekly_bands] == [10, 15, 20]
    assert [band.max_value for band in params.weekly_bands] == [14, 19, 24]
    assert [band.amount_eur for band in params.weekly_bands] == [
        Decimal("200.00"),
        Decimal("150.00"),
        Decimal("100.00"),
    ]


def test_fear_greed_params_rejects_overlapping_bands() -> None:
    with pytest.raises(ValidationError, match="cannot overlap"):
        FearGreedParams(
            weekly_bands=[
                WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("200.00")),
                WeeklyBandRule(min_value=14, max_value=19, amount_eur=Decimal("150.00")),
            ]
        )


def test_fear_greed_params_rejects_band_invading_daily_threshold() -> None:
    with pytest.raises(ValidationError, match="daily_below_threshold"):
        FearGreedParams(
            daily_below_threshold=20,
            weekly_bands=[
                WeeklyBandRule(min_value=15, max_value=19, amount_eur=Decimal("150.00")),
            ],
        )


def test_fear_greed_params_accepts_widened_band() -> None:
    params = FearGreedParams(
        weekly_bands=[
            WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("200.00")),
            WeeklyBandRule(min_value=15, max_value=19, amount_eur=Decimal("150.00")),
            WeeklyBandRule(min_value=20, max_value=30, amount_eur=Decimal("120.00")),
        ]
    )
    assert params.weekly_bands[-1].amount_eur == Decimal("120.00")


def test_fear_greed_params_tolerates_unsorted_bands() -> None:
    params = FearGreedParams(
        weekly_bands=[
            WeeklyBandRule(min_value=20, max_value=24, amount_eur=Decimal("100.00")),
            WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("200.00")),
        ]
    )
    assert len(params.weekly_bands) == 2


# --- PriceBar ----------------------------------------------------------------


def test_price_bar_accepts_coherent_ohlc() -> None:
    bar = make_price_bar()
    assert bar.close == Decimal("40500.00")


@pytest.mark.parametrize(
    "overrides",
    [
        {"open": Decimal("42000.00")},
        {"close": Decimal("38000.00")},
        {"low": Decimal("0")},
        {"volume": Decimal("-1")},
    ],
)
def test_price_bar_rejects_incoherent_ohlc(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        make_price_bar(**overrides)


# --- IndicatorValue ----------------------------------------------------------


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("50"), Decimal("100")])
def test_indicator_value_accepts_integers_in_range(value: Decimal) -> None:
    reading = IndicatorValue(
        indicator="fear_greed", day=date(2024, 1, 1), value=value, source="bgeometrics"
    )
    assert reading.value == value


@pytest.mark.parametrize("value", [Decimal("-1"), Decimal("101"), Decimal("50.5")])
def test_indicator_value_rejects_out_of_range_or_fractional(value: Decimal) -> None:
    with pytest.raises(ValidationError):
        IndicatorValue(
            indicator="fear_greed", day=date(2024, 1, 1), value=value, source="bgeometrics"
        )


# --- OrderIntent / Fill ------------------------------------------------------


def test_order_intent_index_value_is_optional() -> None:
    without_index = OrderIntent(
        decision_day=date(2024, 1, 1), asset="BTC", amount_eur=Decimal("50.00"), reason="daily_<10"
    )
    assert without_index.index_value is None

    with_index = OrderIntent(
        decision_day=date(2024, 1, 1),
        asset="BTC",
        amount_eur=Decimal("200.00"),
        reason="monday_10_14",
        index_value=Decimal("12"),
    )
    assert with_index.index_value == Decimal("12")


def test_fill_keeps_index_value_for_traceability() -> None:
    fill = make_fill()
    assert fill.index_value == Decimal("12")
    assert fill.btc_quantity == Decimal("0.01000000")


# --- BacktestConfig / BacktestResult -----------------------------------------


def test_backtest_config_rejects_inverted_dates() -> None:
    with pytest.raises(ValidationError, match="start_date must be <= end_date"):
        BacktestConfig(
            start_date=date(2024, 2, 1),
            end_date=date(2024, 1, 1),
            strategy_params={},
        )


def test_backtest_config_accepts_single_day_window() -> None:
    config = BacktestConfig(
        start_date=date(2024, 1, 1), end_date=date(2024, 1, 1), strategy_params={}
    )
    assert config.asset == "BTC"
    assert config.execution_mode == "close_same_day"


def test_backtest_result_round_trips_full_payload() -> None:
    result = make_backtest_result()
    assert result.metrics.total_operations == 2
    assert len(result.fills) == 1
    assert result.incidents == []


# --- Rounding helpers --------------------------------------------------------


def test_quantize_btc_rounds_down_to_satoshi() -> None:
    amount = Decimal("100.00") / Decimal("73067.27")
    assert quantize_btc(amount) == Decimal("0.00136860")


def test_quantize_btc_never_rounds_up() -> None:
    assert quantize_btc(Decimal("0.000000019")) == Decimal("0.00000001")
    assert quantize_btc(Decimal("0.00000001")) == Decimal("0.00000001")


def test_quantize_eur_rounds_half_up_to_cent() -> None:
    assert quantize_eur(Decimal("2.345")) == Decimal("2.35")
    assert quantize_eur(Decimal("0.005")) == Decimal("0.01")
    assert quantize_eur(Decimal("0.004")) == Decimal("0.00")
    assert quantize_eur(Decimal("100")) == Decimal("100.00")


# --- Canonical hashing -------------------------------------------------------


def test_canonical_hash_is_deterministic() -> None:
    fill_a = make_fill()
    fill_b = make_fill()
    assert canonical_hash(fill_a) == canonical_hash(fill_b)


def test_canonical_hash_distinguishes_different_payloads() -> None:
    assert canonical_hash(make_fill()) != canonical_hash(make_fill(amount_eur=Decimal("200.00")))


def test_canonical_hash_ignores_mapping_key_order() -> None:
    hash_one = canonical_hash({"a": 1, "b": 2})
    hash_two = canonical_hash({"b": 2, "a": 1})
    assert hash_one == hash_two


def test_canonical_hash_matches_equivalent_model_and_mapping() -> None:
    fill = make_fill()
    as_mapping = fill.model_dump(mode="json")
    assert canonical_hash(fill) == canonical_hash(as_mapping)


def test_canonical_hash_returns_hex_sha256_digest() -> None:
    digest = canonical_hash({"x": 1})
    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)


# --- StrategyContext ---------------------------------------------------------


def test_strategy_context_holds_simulation_window() -> None:
    ctx = StrategyContext(
        asset="BTC",
        start_date=date(2018, 2, 1),
        end_date=date(2026, 10, 18),
        params={"daily_below_threshold": 10},
        indicators={},
    )
    assert ctx.asset == "BTC"
    assert ctx.start_date == date(2018, 2, 1)
    assert ctx.end_date == date(2026, 10, 18)
    assert ctx.params == {"daily_below_threshold": 10}
    assert ctx.indicators == {}
    assert ctx.prices is None


def test_indicator_value_accepts_fractional_for_non_fear_greed() -> None:
    reading = IndicatorValue(
        indicator="mvrv", day=date(2024, 1, 1), value=Decimal("2.5"), source="synthetic"
    )
    assert reading.value == Decimal("2.5")


# --- Architectural test ------------------------------------------------------


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_domain_layer_has_no_io_dependencies() -> None:
    domain_dir = PROJECT_ROOT / "src" / "backtesting_cripto" / "domain"
    module_paths = sorted(domain_dir.glob("*.py"))
    assert len(module_paths) >= 3

    for path in module_paths:
        modules = _imported_modules(path)
        forbidden = {name.split(".")[0] for name in modules} & FORBIDDEN_ROOT_MODULES
        assert not forbidden, f"{path.name} imports forbidden modules: {sorted(forbidden)}"

        # The domain may only depend on itself, never on sibling packages.
        siblings = {name for name in modules if name.startswith("backtesting_cripto.")}
        outside_domain = {
            name for name in siblings if not name.startswith("backtesting_cripto.domain")
        }
        message = f"{path.name} imports outside the domain: {sorted(outside_domain)}"
        assert not outside_domain, message
