"""Backtest engine: orchestrates strategy, execution, portfolio and metrics."""

from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from backtesting_cripto import __version__
from backtesting_cripto.domain.contracts import (
    ExecutionModel,
    IndicatorSeries,
    PriceSeries,
    Strategy,
    StrategyContext,
)
from backtesting_cripto.domain.models import (
    BacktestConfig,
    BacktestResult,
    canonical_hash,
)
from backtesting_cripto.engine.execution import CloseExecutionModel
from backtesting_cripto.engine.portfolio import Portfolio
from backtesting_cripto.metrics.calculator import build_equity_curve, calculate_metrics
from backtesting_cripto.validation.consistency_checks import verify_backtest_result


def run_backtest(
    cfg: BacktestConfig,
    prices: PriceSeries,
    indicators: Mapping[str, IndicatorSeries],
    strategy: Strategy,
    *,
    execution_model: ExecutionModel | None = None,
    dataset_hash: str = "",
    run_id: str | None = None,
    created_at: datetime | None = None,
) -> BacktestResult:
    """Run a backtest over local data and return its verified result.

    The result_hash excludes run_id and created_at so that two runs with
    the same configuration, dataset and code produce the exact same hash
    (reproducibility requirement, plan section G.2).
    """
    ctx = StrategyContext(
        asset=cfg.asset,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        params=cfg.strategy_params,
        indicators=indicators,
        prices=prices,
    )
    model = execution_model or CloseExecutionModel(cfg.execution_mode)

    portfolio = Portfolio()
    incidents: list[str] = []

    for intent in strategy.generate_intents(ctx):
        if not cfg.start_date <= intent.decision_day <= cfg.end_date:
            continue

        fill = model.execute(intent, prices)
        if fill is None:
            exec_day = model.execution_day(intent.decision_day)
            if exec_day > cfg.end_date:
                # close_next_day decision on the last day of the window:
                # the execution falls outside the simulation, skip cleanly.
                continue
            incidents.append(f"missing_price_on_{exec_day.isoformat()}")
            continue

        if fill.execution_day > cfg.end_date:
            continue

        portfolio.apply(fill)

    equity_curve = build_equity_curve(portfolio.fills, prices, cfg.start_date, cfg.end_date)
    metrics = calculate_metrics(portfolio.fills, equity_curve, prices, cfg.end_date)

    config_hash = canonical_hash(cfg)
    result_hash = canonical_hash(
        {
            "config_hash": config_hash,
            "dataset_hash": dataset_hash,
            "fills": [fill.model_dump(mode="json") for fill in portfolio.fills],
            "metrics": metrics.model_dump(mode="json"),
            "incidents": incidents,
        }
    )

    result = BacktestResult(
        run_id=run_id or uuid4().hex,
        created_at=created_at or datetime.now(UTC),
        code_version=__version__,
        dataset_hash=dataset_hash,
        config=cfg,
        config_hash=config_hash,
        fills=portfolio.fills,
        equity_curve=equity_curve,
        metrics=metrics,
        incidents=incidents,
        result_hash=result_hash,
    )

    verify_backtest_result(result)
    return result
