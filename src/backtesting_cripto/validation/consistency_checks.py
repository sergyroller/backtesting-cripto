"""Post-simulation financial consistency checks."""

from decimal import Decimal

from backtesting_cripto.domain.exceptions import DataValidationError
from backtesting_cripto.domain.models import BacktestResult, quantize_btc, quantize_eur

ZERO_EUR = Decimal("0.00")


def verify_backtest_result(result: BacktestResult) -> None:
    """Check the financial invariants of a finished backtest.

    Raises DataValidationError on the first broken invariant.
    """
    metrics = result.metrics
    fills = result.fills

    if metrics.total_operations != len(fills):
        msg = f"total_operations {metrics.total_operations} != {len(fills)} fills"
        raise DataValidationError(msg)

    invested = quantize_eur(sum((fill.amount_eur for fill in fills), ZERO_EUR))
    if metrics.total_invested_eur != invested:
        msg = f"total_invested_eur {metrics.total_invested_eur} != {invested}"
        raise DataValidationError(msg)

    btc = quantize_btc(sum((fill.btc_quantity for fill in fills), Decimal("0.00000000")))
    if metrics.btc_accumulated != btc:
        msg = f"btc_accumulated {metrics.btc_accumulated} != {btc}"
        raise DataValidationError(msg)

    if sum(metrics.operations_by_reason.values()) != len(fills):
        msg = "operations_by_reason does not add up to the number of fills"
        raise DataValidationError(msg)

    if metrics.max_drawdown_pct > ZERO_EUR:
        msg = f"max_drawdown_pct {metrics.max_drawdown_pct} is positive"
        raise DataValidationError(msg)
