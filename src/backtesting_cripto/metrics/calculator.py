"""Performance metrics and the daily equity curve (plan section E.5)."""

from collections.abc import Sequence
from datetime import date, timedelta
from decimal import Decimal

from backtesting_cripto.domain.contracts import PriceSeries
from backtesting_cripto.domain.exceptions import ConfigurationError, InsufficientDataError
from backtesting_cripto.domain.models import (
    EquityPoint,
    Fill,
    Metrics,
    quantize_btc,
    quantize_eur,
)

ONE_HUNDRED = Decimal("100")
ZERO_EUR = Decimal("0.00")
ZERO_BTC = Decimal("0.00000000")


def build_equity_curve(
    fills: Sequence[Fill],
    prices: PriceSeries,
    start_date: date,
    end_date: date,
) -> list[EquityPoint]:
    """Daily portfolio state over [start_date, end_date].

    A day without its own candle is valued at the last previous close, so
    a missing price never drags the curve down to zero. Raises
    InsufficientDataError when no price at all is available for a day.
    """
    ordered_fills = sorted(fills, key=lambda fill: fill.execution_day)
    points: list[EquityPoint] = []
    invested = ZERO_EUR
    btc = ZERO_BTC
    peak = ZERO_EUR
    fill_index = 0

    if start_date > end_date:
        msg = f"start_date {start_date.isoformat()} is after end_date {end_date.isoformat()}"
        raise ConfigurationError(msg)

    cursor = start_date
    while cursor <= end_date:
        while fill_index < len(ordered_fills) and ordered_fills[fill_index].execution_day <= cursor:
            invested = quantize_eur(invested + ordered_fills[fill_index].amount_eur)
            btc = quantize_btc(btc + ordered_fills[fill_index].btc_quantity)
            fill_index += 1

        bar = prices.bar_on(cursor)
        if bar is None:
            bar = prices.last_close_on_or_before(cursor)
        if bar is None:
            msg = f"no price available on or before {cursor.isoformat()}"
            raise InsufficientDataError(msg)

        close_price_eur = quantize_eur(bar.close)
        portfolio_value_eur = quantize_eur(btc * close_price_eur)
        if portfolio_value_eur > peak:
            peak = portfolio_value_eur

        if peak > ZERO_EUR:
            drawdown_pct = quantize_eur(
                (portfolio_value_eur / peak - Decimal("1")) * ONE_HUNDRED
            )
        else:
            drawdown_pct = ZERO_EUR

        points.append(
            EquityPoint(
                day=cursor,
                invested_eur=invested,
                btc_accumulated=btc,
                close_price_eur=close_price_eur,
                portfolio_value_eur=portfolio_value_eur,
                drawdown_pct=drawdown_pct,
            )
        )
        cursor += timedelta(days=1)

    return points


def calculate_metrics(
    fills: Sequence[Fill],
    equity_curve: Sequence[EquityPoint],
    prices: PriceSeries,
    end_date: date,
) -> Metrics:
    """Aggregate metrics of a run (plan section E.5)."""
    total_invested_eur = quantize_eur(
        sum((fill.amount_eur for fill in fills), ZERO_EUR)
    )
    btc_accumulated = quantize_btc(sum((fill.btc_quantity for fill in fills), ZERO_BTC))
    total_operations = len(fills)

    operations_by_reason: dict[str, int] = {}
    for fill in fills:
        operations_by_reason[fill.reason] = operations_by_reason.get(fill.reason, 0) + 1

    if btc_accumulated > ZERO_BTC:
        average_buy_price_eur: Decimal | None = quantize_eur(
            total_invested_eur / btc_accumulated
        )
    else:
        average_buy_price_eur = None

    end_bar = prices.last_close_on_or_before(end_date)
    if end_bar is None:
        msg = f"no price available on or before {end_date.isoformat()}"
        raise InsufficientDataError(msg)
    final_price_eur = quantize_eur(end_bar.close)
    final_portfolio_value_eur = quantize_eur(btc_accumulated * final_price_eur)
    pnl_eur = quantize_eur(final_portfolio_value_eur - total_invested_eur)

    if total_invested_eur > ZERO_EUR:
        roi_pct: Decimal | None = quantize_eur(
            (pnl_eur / total_invested_eur) * ONE_HUNDRED
        )
    else:
        roi_pct = None

    max_drawdown_pct = min(
        (point.drawdown_pct for point in equity_curve), default=ZERO_EUR
    )

    return Metrics(
        total_invested_eur=total_invested_eur,
        total_operations=total_operations,
        operations_by_reason=operations_by_reason,
        btc_accumulated=btc_accumulated,
        average_buy_price_eur=average_buy_price_eur,
        final_price_eur=final_price_eur,
        final_portfolio_value_eur=final_portfolio_value_eur,
        pnl_eur=pnl_eur,
        roi_pct=roi_pct,
        max_drawdown_pct=max_drawdown_pct,
    )
