"""Unit and property-based tests for the engine, portfolio and metrics."""

from bisect import bisect_right
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backtesting_cripto.domain.contracts import StrategyContext
from backtesting_cripto.domain.exceptions import ConfigurationError, InsufficientDataError
from backtesting_cripto.domain.models import (
    BacktestConfig,
    Fill,
    OrderIntent,
    PriceBar,
    quantize_btc,
    quantize_eur,
)
from backtesting_cripto.engine.calendar import (
    available_date_bounds,
    is_monday,
    iter_days,
    validate_window,
)
from backtesting_cripto.engine.execution import CloseExecutionModel
from backtesting_cripto.engine.portfolio import Portfolio
from backtesting_cripto.engine.runner import run_backtest
from backtesting_cripto.metrics.calculator import build_equity_curve, calculate_metrics
from backtesting_cripto.validation.consistency_checks import verify_backtest_result

START = date(2020, 1, 1)


def make_bar(day: date, close: str | Decimal) -> PriceBar:
    close_decimal = Decimal(str(close))
    return PriceBar(
        asset="BTC",
        quote="EUR",
        day=day,
        open=close_decimal,
        high=close_decimal,
        low=close_decimal,
        close=close_decimal,
        volume=Decimal("1.0"),
        source="test",
    )


class FakePriceSeries:
    """PriceSeries backed by a dict of day → close price."""

    def __init__(self, closes: dict[date, Decimal]) -> None:
        self._bars = {day: make_bar(day, close) for day, close in sorted(closes.items())}
        self._days = list(self._bars)

    def bar_on(self, day: date) -> PriceBar | None:
        return self._bars.get(day)

    def last_close_on_or_before(self, day: date) -> PriceBar | None:
        index = bisect_right(self._days, day) - 1
        if index < 0:
            return None
        return self._bars[self._days[index]]

    def date_bounds(self) -> tuple[date, date]:
        return self._days[0], self._days[-1]


class FakeIndicatorSeries:
    """IndicatorSeries backed by a dict of day → value."""

    def __init__(self, values: dict[date, Decimal]) -> None:
        self._values = dict(sorted(values.items()))
        self._days = list(self._values)

    def value_on(self, day: date) -> Decimal | None:
        return self._values.get(day)

    def date_bounds(self) -> tuple[date, date]:
        return self._days[0], self._days[-1]


class FixedIntentsStrategy:
    """Strategy emitting a fixed list of intents (for engine tests)."""

    strategy_id = "fixed_intents"
    name = "Fixed intents"
    required_indicators: tuple[str, ...] = ()

    def __init__(self, intents: list[OrderIntent]) -> None:
        self._intents = intents

    def generate_intents(self, ctx: StrategyContext) -> Iterator[OrderIntent]:
        yield from self._intents


def make_intent(day: date, amount: str = "100.00", reason: str = "test") -> OrderIntent:
    return OrderIntent(
        decision_day=day,
        asset="BTC",
        amount_eur=Decimal(amount),
        reason=reason,
        index_value=None,
    )


def make_fill(
    day: date, amount: str = "100.00", close: str = "10000.00", reason: str = "test"
) -> Fill:
    amount_eur = quantize_eur(Decimal(amount))
    price_eur = quantize_eur(Decimal(close))
    return Fill(
        execution_day=day,
        decision_day=day,
        asset="BTC",
        index_value=None,
        amount_eur=amount_eur,
        price_eur=price_eur,
        btc_quantity=quantize_btc(amount_eur / price_eur),
        reason=reason,
    )


def consecutive_days(count: int, start: date = START) -> list[date]:
    return [start + timedelta(days=index) for index in range(count)]


# --- calendar -----------------------------------------------------------------


def test_iter_days_is_inclusive() -> None:
    assert list(iter_days(date(2020, 1, 1), date(2020, 1, 3))) == consecutive_days(3)


def test_iter_days_rejects_inverted_range() -> None:
    with pytest.raises(ConfigurationError):
        list(iter_days(date(2020, 1, 3), date(2020, 1, 1)))


def test_is_monday() -> None:
    assert is_monday(date(2024, 1, 1))  # Monday
    assert not is_monday(date(2024, 1, 2))


def test_available_date_bounds_intersects_series() -> None:
    prices = FakePriceSeries({day: Decimal("100.00") for day in consecutive_days(5)})
    indicator = FakeIndicatorSeries(
        {day: Decimal("50") for day in consecutive_days(3, start=date(2020, 1, 2))}
    )
    bounds = available_date_bounds(prices, {"fear_greed": indicator}, ["fear_greed"])
    assert bounds == (date(2020, 1, 2), date(2020, 1, 4))


def test_available_date_bounds_requires_the_indicator() -> None:
    prices = FakePriceSeries({day: Decimal("100.00") for day in consecutive_days(3)})
    with pytest.raises(InsufficientDataError, match="missing required indicator"):
        available_date_bounds(prices, {}, ["fear_greed"])


def test_available_date_bounds_rejects_empty_intersection() -> None:
    prices = FakePriceSeries({day: Decimal("100.00") for day in consecutive_days(3)})
    indicator = FakeIndicatorSeries(
        {day: Decimal("50") for day in consecutive_days(3, start=date(2021, 1, 1))}
    )
    with pytest.raises(InsufficientDataError, match="no overlapping data"):
        available_date_bounds(prices, {"fear_greed": indicator}, ["fear_greed"])


def test_validate_window_accepts_contained_window() -> None:
    validate_window(
        date(2020, 1, 2),
        date(2020, 1, 3),
        (date(2020, 1, 1), date(2020, 1, 5)),
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2019, 12, 31), date(2020, 1, 2)),
        (date(2020, 1, 2), date(2020, 1, 6)),
        (date(2020, 1, 4), date(2020, 1, 2)),
    ],
)
def test_validate_window_rejects_bad_windows(start: date, end: date) -> None:
    with pytest.raises(ConfigurationError):
        validate_window(start, end, (date(2020, 1, 1), date(2020, 1, 5)))


# --- execution model ----------------------------------------------------------


def test_execution_rounds_down_to_satoshi() -> None:
    model = CloseExecutionModel()
    prices = FakePriceSeries({START: Decimal("73067.27")})
    fill = model.execute(make_intent(START, "100.00"), prices)

    assert fill is not None
    assert fill.amount_eur == Decimal("100.00")
    assert fill.price_eur == Decimal("73067.27")
    assert fill.btc_quantity == Decimal("0.00136860")
    assert fill.execution_day == START


def test_execution_close_same_day_uses_decision_day() -> None:
    model = CloseExecutionModel("close_same_day")
    next_day = START + timedelta(days=1)
    prices = FakePriceSeries({START: Decimal("100.00"), next_day: Decimal("200.00")})
    fill = model.execute(make_intent(START), prices)
    assert fill is not None
    assert fill.price_eur == Decimal("100.00")


def test_execution_close_next_day_uses_following_day() -> None:
    model = CloseExecutionModel("close_next_day")
    next_day = START + timedelta(days=1)
    prices = FakePriceSeries({START: Decimal("100.00"), next_day: Decimal("200.00")})
    fill = model.execute(make_intent(START), prices)
    assert fill is not None
    assert fill.execution_day == START + timedelta(days=1)
    assert fill.price_eur == Decimal("200.00")
    assert fill.decision_day == START


def test_execution_without_exact_bar_returns_none() -> None:
    model = CloseExecutionModel()
    # Only the previous day exists: execution never falls back to it.
    prices = FakePriceSeries({START - timedelta(days=1): Decimal("100.00")})
    assert model.execute(make_intent(START), prices) is None


def test_execution_rejects_unknown_mode() -> None:
    with pytest.raises(ConfigurationError):
        CloseExecutionModel("close_previous_day")  # type: ignore[arg-type]


# --- portfolio ----------------------------------------------------------------


def test_portfolio_accumulates_fills() -> None:
    portfolio = Portfolio()
    portfolio.apply(make_fill(START, "100.00", "10000.00"))
    portfolio.apply(make_fill(START + timedelta(days=1), "200.00", "20000.00"))

    assert portfolio.total_invested_eur == Decimal("300.00")
    assert portfolio.btc_accumulated == Decimal("0.02000000")
    assert len(portfolio.fills) == 2


def test_portfolio_state_on_or_before() -> None:
    portfolio = Portfolio()
    portfolio.apply(make_fill(START, "100.00", "10000.00"))
    portfolio.apply(make_fill(START + timedelta(days=2), "100.00", "20000.00"))

    invested, btc = portfolio.state_on_or_before(START + timedelta(days=1))
    assert invested == Decimal("100.00")
    assert btc == Decimal("0.01000000")


# --- metrics ------------------------------------------------------------------


def test_metrics_with_known_buys() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(
        {days[0]: Decimal("10000.00"), days[1]: Decimal("20000.00"), days[2]: Decimal("30000.00")}
    )
    fills = [
        make_fill(days[0], "100.00", "10000.00"),
        make_fill(days[1], "100.00", "20000.00"),
    ]

    curve = build_equity_curve(fills, prices, days[0], days[2])
    metrics = calculate_metrics(fills, curve, prices, days[2])

    assert metrics.total_invested_eur == Decimal("200.00")
    assert metrics.total_operations == 2
    assert metrics.btc_accumulated == Decimal("0.01500000")
    assert metrics.average_buy_price_eur == Decimal("13333.33")
    assert metrics.final_price_eur == Decimal("30000.00")
    assert metrics.final_portfolio_value_eur == Decimal("450.00")
    assert metrics.pnl_eur == Decimal("250.00")
    assert metrics.roi_pct == Decimal("125.00")
    assert metrics.max_drawdown_pct == Decimal("0.00")


def test_drawdown_synthetic_series() -> None:
    closes = ["100.00", "120.00", "60.00", "90.00", "150.00"]
    days = consecutive_days(len(closes))
    prices = FakePriceSeries(dict(zip(days, (Decimal(close) for close in closes), strict=True)))
    fills = [make_fill(days[0], "100.00", "100.00")]  # 1 BTC from the first day

    curve = build_equity_curve(fills, prices, days[0], days[-1])
    metrics = calculate_metrics(fills, curve, prices, days[-1])

    assert [point.portfolio_value_eur for point in curve] == [
        Decimal("100.00"),
        Decimal("120.00"),
        Decimal("60.00"),
        Decimal("90.00"),
        Decimal("150.00"),
    ]
    assert metrics.max_drawdown_pct == Decimal("-50.00")


def test_equity_curve_uses_previous_close_on_gap() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries({days[0]: Decimal("100.00"), days[2]: Decimal("200.00")})
    fills = [make_fill(days[0], "1.00", "100.00")]  # 0.01 BTC

    curve = build_equity_curve(fills, prices, days[0], days[2])

    gap_point = curve[1]
    assert gap_point.close_price_eur == Decimal("100.00")  # previous close, not zero
    assert gap_point.portfolio_value_eur == Decimal("1.00")


def test_metrics_with_zero_buys() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))

    curve = build_equity_curve([], prices, days[0], days[2])
    metrics = calculate_metrics([], curve, prices, days[2])

    assert metrics.total_operations == 0
    assert metrics.total_invested_eur == Decimal("0.00")
    assert metrics.btc_accumulated == Decimal("0.00000000")
    assert metrics.average_buy_price_eur is None
    assert metrics.roi_pct is None
    assert metrics.max_drawdown_pct == Decimal("0.00")
    assert metrics.final_portfolio_value_eur == Decimal("0.00")


def test_operations_by_reason_counts() -> None:
    days = consecutive_days(4)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    fills = [
        make_fill(days[0], reason="daily_<10"),
        make_fill(days[1], reason="daily_<10"),
        make_fill(days[2], reason="monday_10_14"),
    ]
    curve = build_equity_curve(fills, prices, days[0], days[3])
    metrics = calculate_metrics(fills, curve, prices, days[3])

    assert metrics.operations_by_reason == {"daily_<10": 2, "monday_10_14": 1}


# --- runner -------------------------------------------------------------------


def make_config(**overrides: object) -> BacktestConfig:
    payload: dict[str, object] = {
        "start_date": START,
        "end_date": START + timedelta(days=4),
        "strategy_params": {},
    }
    payload.update(overrides)
    return BacktestConfig(**payload)  # type: ignore[arg-type]


def test_runner_applies_fills_and_builds_result() -> None:
    days = consecutive_days(5)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy([make_intent(days[0], "100.00")])

    result = run_backtest(
        make_config(),
        prices,
        {},
        strategy,
        dataset_hash="d" * 64,
        run_id="run-1",
        created_at="2026-10-20T00:00:00+00:00",  # type: ignore[arg-type]
    )

    assert result.metrics.total_operations == 1
    assert result.metrics.total_invested_eur == Decimal("100.00")
    assert len(result.equity_curve) == 5
    assert result.incidents == []
    assert result.code_version


def test_runner_skips_close_next_day_on_last_window_day() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy([make_intent(days[-1], "100.00")])

    result = run_backtest(
        make_config(start_date=days[0], end_date=days[-1], execution_mode="close_next_day"),
        prices,
        {},
        strategy,
        run_id="run-next-day",
    )

    assert result.metrics.total_operations == 0
    assert result.incidents == []


def test_runner_records_missing_price_incident() -> None:
    days = consecutive_days(3)
    closes = {days[0]: Decimal("100.00"), days[2]: Decimal("100.00")}  # gap on days[1]
    prices = FakePriceSeries(closes)
    strategy = FixedIntentsStrategy([make_intent(days[1], "100.00")])

    result = run_backtest(
        make_config(start_date=days[0], end_date=days[2]),
        prices,
        {},
        strategy,
        run_id="run-gap",
    )

    assert result.metrics.total_operations == 0
    assert result.incidents == [f"missing_price_on_{days[1].isoformat()}"]


def test_runner_ignores_intents_outside_the_window() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy(
        [
            make_intent(days[0] - timedelta(days=1)),
            make_intent(days[-1] + timedelta(days=1)),
            make_intent(days[1]),
        ]
    )

    result = run_backtest(
        make_config(start_date=days[0], end_date=days[2]),
        prices,
        {},
        strategy,
        run_id="run-window",
    )

    assert result.metrics.total_operations == 1
    assert result.fills[0].decision_day == days[1]


def test_runner_result_hash_is_reproducible() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy([make_intent(days[0], "100.00")])
    config = make_config(start_date=days[0], end_date=days[2])

    first = run_backtest(
        config, prices, {}, strategy, dataset_hash="a" * 64, run_id="run-a"
    )
    second = run_backtest(
        config,
        prices,
        {},
        strategy,
        dataset_hash="a" * 64,
        run_id="run-b",
        created_at="2027-01-01T00:00:00+00:00",  # type: ignore[arg-type]
    )

    assert first.run_id != second.run_id
    assert first.result_hash == second.result_hash
    assert first.config_hash == second.config_hash


def test_runner_result_hash_depends_on_dataset_hash() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy([make_intent(days[0], "100.00")])
    config = make_config(start_date=days[0], end_date=days[2])

    first = run_backtest(config, prices, {}, strategy, dataset_hash="a" * 64)
    second = run_backtest(config, prices, {}, strategy, dataset_hash="b" * 64)

    assert first.result_hash != second.result_hash


# --- consistency checks -------------------------------------------------------


def test_verify_backtest_result_accepts_a_valid_result() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy([make_intent(days[0], "100.00")])
    result = run_backtest(
        make_config(start_date=days[0], end_date=days[2]), prices, {}, strategy
    )
    verify_backtest_result(result)  # must not raise


def test_verify_backtest_result_rejects_broken_metrics() -> None:
    days = consecutive_days(3)
    prices = FakePriceSeries(dict(zip(days, (Decimal("100.00") for _ in days), strict=True)))
    strategy = FixedIntentsStrategy([make_intent(days[0], "100.00")])
    result = run_backtest(
        make_config(start_date=days[0], end_date=days[2]), prices, {}, strategy
    )

    result.metrics.total_operations = 99
    with pytest.raises(Exception, match="total_operations"):
        verify_backtest_result(result)


# --- property-based tests -----------------------------------------------------

amount_strategy = st.decimals(
    min_value="0.01", max_value="10000", allow_nan=False, allow_infinity=False, places=2
)
price_strategy = st.decimals(
    min_value="1", max_value="200000", allow_nan=False, allow_infinity=False, places=2
)


@settings(max_examples=100, deadline=None)
@given(
    amounts=st.lists(amount_strategy, min_size=1, max_size=5),
    prices=st.lists(price_strategy, min_size=1, max_size=5),
)
def test_property_based_portfolio_invariants(
    amounts: list[Decimal], prices: list[Decimal]
) -> None:
    days = consecutive_days(len(prices))
    closes = dict(zip(days, prices, strict=True))
    series = FakePriceSeries(closes)

    fills: list[Fill] = []
    for index, amount in enumerate(amounts):
        day = days[index % len(days)]
        fills.append(make_fill(day, amount=str(amount), close=str(closes[day])))

    portfolio = Portfolio()
    for fill in fills:
        portfolio.apply(fill)

    assert portfolio.btc_accumulated == sum(
        (fill.btc_quantity for fill in fills), Decimal("0.00000000")
    )
    assert portfolio.total_invested_eur == sum(
        (fill.amount_eur for fill in fills), Decimal("0.00")
    )

    curve = build_equity_curve(fills, series, days[0], days[-1])
    assert all(point.portfolio_value_eur >= Decimal("0.00") for point in curve)

    metrics = calculate_metrics(fills, curve, series, days[-1])
    assert metrics.max_drawdown_pct <= Decimal("0.00")
    assert metrics.total_operations == len(fills)
