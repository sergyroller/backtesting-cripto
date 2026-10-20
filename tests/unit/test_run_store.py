"""Unit tests for the run store (persistence of backtest runs)."""

from bisect import bisect_right
from collections.abc import Iterator
from datetime import date, timedelta
from decimal import Decimal

from backtesting_cripto.domain.contracts import StrategyContext
from backtesting_cripto.domain.models import BacktestConfig, OrderIntent, PriceBar
from backtesting_cripto.engine.runner import run_backtest
from backtesting_cripto.storage.repository import BacktestRepository
from backtesting_cripto.storage.run_store import RunStore

START = date(2020, 1, 1)
CLOSES = {START: Decimal("10000.00"), START + timedelta(days=1): Decimal("20000.00")}


def make_bar(day: date, close: Decimal) -> PriceBar:
    return PriceBar(
        asset="BTC",
        quote="EUR",
        day=day,
        open=close,
        high=close,
        low=close,
        close=close,
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


class FixedIntentsStrategy:
    """Strategy emitting a fixed list of intents."""

    strategy_id = "fixed_intents"
    name = "Fixed intents"
    required_indicators: tuple[str, ...] = ()

    def __init__(self, intents: list[OrderIntent]) -> None:
        self._intents = intents

    def generate_intents(self, ctx: StrategyContext) -> Iterator[OrderIntent]:
        yield from self._intents


def make_result(run_id: str, created_at: str) -> object:
    from backtesting_cripto.domain.models import BacktestResult

    prices = FakePriceSeries(CLOSES)
    config = BacktestConfig(
        start_date=START,
        end_date=START + timedelta(days=1),
        strategy_params={},
    )
    intents = [
        OrderIntent(
            decision_day=START,
            asset="BTC",
            amount_eur=Decimal("100.00"),
            reason="daily_<10",
            index_value=Decimal("7"),
        ),
        OrderIntent(
            decision_day=START + timedelta(days=1),
            asset="BTC",
            amount_eur=Decimal("200.00"),
            reason="monday_10_14",
            index_value=Decimal("12"),
        ),
    ]
    result: BacktestResult = run_backtest(
        config,
        prices,
        {},
        FixedIntentsStrategy(intents),
        run_id=run_id,
        created_at=created_at,  # type: ignore[arg-type]
    )
    return result


def populate_repository(repo: BacktestRepository, dataset_id: str = "prices_test") -> None:
    repo.upsert_dataset(
        dataset_id=dataset_id,
        source="test",
        url="https://example.com",
        retrieved_at="2026-10-20T00:00:00+00:00",
        sha256="abc",
        first_day=START,
        last_day=START + timedelta(days=1),
        record_count=2,
        license="MIT",
    )
    repo.replace_price_bars(
        dataset_id=dataset_id,
        bars=[make_bar(day, close) for day, close in sorted(CLOSES.items())],
    )


def test_save_and_get_run_round_trip(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    prices = FakePriceSeries(CLOSES)
    result = make_result("run-1", "2026-10-20T10:00:00+00:00")

    with RunStore(tmp_path / "runs.sqlite3") as store:
        store.save_run(result)
        loaded = store.get_run("run-1", prices=prices)

    assert loaded is not None
    assert loaded.run_id == result.run_id
    assert loaded.created_at == result.created_at
    assert loaded.code_version == result.code_version
    assert loaded.dataset_hash == result.dataset_hash
    assert loaded.config == result.config
    assert loaded.config_hash == result.config_hash
    assert loaded.metrics == result.metrics
    assert loaded.fills == result.fills
    assert loaded.equity_curve == result.equity_curve
    assert loaded.incidents == result.incidents
    assert loaded.result_hash == result.result_hash


def test_fills_preserve_index_value_and_decimal_precision(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    prices = FakePriceSeries(CLOSES)
    result = make_result("run-precision", "2026-10-20T10:00:00+00:00")

    with RunStore(tmp_path / "runs.sqlite3") as store:
        store.save_run(result)
        loaded = store.get_run("run-precision", prices=prices)

    assert loaded is not None
    assert [fill.index_value for fill in loaded.fills] == [Decimal("7"), Decimal("12")]
    assert all(
        fill.amount_eur == fill.amount_eur.quantize(Decimal("0.01"))
        for fill in loaded.fills
    )
    assert all(
        fill.btc_quantity == fill.btc_quantity.quantize(Decimal("0.00000001"))
        for fill in loaded.fills
    )


def test_get_run_rebuilds_equity_curve_from_database(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    db_path = tmp_path / "shared.sqlite3"
    result = make_result("run-db", "2026-10-20T10:00:00+00:00")

    with BacktestRepository(db_path) as repo:
        populate_repository(repo)
    with RunStore(db_path) as store:
        store.save_run(result)
        loaded = store.get_run("run-db")  # prices loaded from the same database

    assert loaded is not None
    assert loaded.equity_curve == result.equity_curve


def test_get_run_missing_returns_none(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    with RunStore(tmp_path / "runs.sqlite3") as store:
        assert store.get_run("nope") is None


def test_save_run_is_idempotent(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    result = make_result("run-idem", "2026-10-20T10:00:00+00:00")

    with RunStore(tmp_path / "runs.sqlite3") as store:
        store.save_run(result)
        store.save_run(result)

        summaries = store.list_runs()
        assert len(summaries) == 1
        assert summaries[0].run_id == "run-idem"
        trade_rows = store.connection.execute(
            "SELECT COUNT(*) FROM trades WHERE run_id = ?", ("run-idem",)
        ).fetchone()
        assert trade_rows[0] == len(result.fills)


def test_list_runs_orders_by_created_at_desc(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    older = make_result("run-older", "2026-10-18T10:00:00+00:00")
    newer = make_result("run-newer", "2026-10-20T10:00:00+00:00")

    with RunStore(tmp_path / "runs.sqlite3") as store:
        store.save_run(older)
        store.save_run(newer)
        summaries = store.list_runs()

    assert [summary.run_id for summary in summaries] == ["run-newer", "run-older"]


def test_run_summary_contains_metadata(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    result = make_result("run-summary", "2026-10-20T10:00:00+00:00")

    with RunStore(tmp_path / "runs.sqlite3") as store:
        store.save_run(result)
        summary = store.list_runs()[0]

    assert summary.code_version == result.code_version
    assert summary.dataset_hash == result.dataset_hash
    assert summary.config == result.config
    assert summary.config_hash == result.config_hash
    assert summary.metrics == result.metrics
    assert summary.result_hash == result.result_hash
