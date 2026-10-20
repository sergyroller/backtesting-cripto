"""Execution model: turns order intents into fills at the daily close (section E.3)."""

from datetime import date, timedelta
from typing import Literal

from backtesting_cripto.domain.contracts import PriceSeries
from backtesting_cripto.domain.exceptions import ConfigurationError
from backtesting_cripto.domain.models import (
    Fill,
    OrderIntent,
    quantize_btc,
    quantize_eur,
)

ExecutionMode = Literal["close_same_day", "close_next_day"]
EXECUTION_MODES: tuple[str, ...] = ("close_same_day", "close_next_day")


class CloseExecutionModel:
    """Executes buys at the close of the decision day (or the following one).

    Purchases are 100% direct: no fees and no slippage. The BTC quantity
    is quantized down to satoshis, so the paid amount never exceeds the
    intended EUR amount.
    """

    def __init__(self, mode: ExecutionMode = "close_same_day") -> None:
        if mode not in EXECUTION_MODES:
            msg = f"unknown execution mode: {mode!r}"
            raise ConfigurationError(msg)
        self._mode = mode

    @property
    def mode(self) -> ExecutionMode:
        return self._mode

    def execution_day(self, decision_day: date) -> date:
        """Day whose close executes a decision taken on decision_day."""
        if self._mode == "close_next_day":
            return decision_day + timedelta(days=1)
        return decision_day

    def execute(self, intent: OrderIntent, prices: PriceSeries) -> Fill | None:
        """Execute an intent at the strict close of its execution day.

        Returns None when there is no candle for that exact day (never
        falls back to an earlier close for executions).
        """
        exec_day = self.execution_day(intent.decision_day)
        bar = prices.bar_on(exec_day)
        if bar is None:
            return None

        amount_eur = quantize_eur(intent.amount_eur)
        price_eur = quantize_eur(bar.close)
        btc_quantity = quantize_btc(amount_eur / price_eur)
        return Fill(
            execution_day=exec_day,
            decision_day=intent.decision_day,
            asset=intent.asset,
            index_value=intent.index_value,
            amount_eur=amount_eur,
            price_eur=price_eur,
            btc_quantity=btc_quantity,
            reason=intent.reason,
        )


__all__ = ["EXECUTION_MODES", "CloseExecutionModel", "ExecutionMode"]
