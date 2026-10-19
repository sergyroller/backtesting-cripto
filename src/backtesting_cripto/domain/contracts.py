"""Protocols and shared context defining the backtesting contracts.

The engine and strategies depend only on these abstractions, never on
concrete storage or provider implementations.
"""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from backtesting_cripto.domain.models import Fill, OrderIntent, PriceBar


@dataclass(frozen=True)
class StrategyContext:
    """Everything a strategy needs to decide on a given day."""

    day: date
    prices: "PriceSeries"
    indicators: Mapping[str, "IndicatorSeries"]


class PriceSeries(Protocol):
    """Access to closed daily candles of an asset/quote pair."""

    def bar_on(self, day: date) -> PriceBar | None: ...

    def last_close_on_or_before(self, day: date) -> PriceBar | None: ...

    def date_bounds(self) -> tuple[date, date]: ...


class IndicatorSeries(Protocol):
    """Access to daily values of a single indicator."""

    def value_on(self, day: date) -> Decimal | None: ...

    def date_bounds(self) -> tuple[date, date]: ...


class Strategy(Protocol):
    """Accumulation strategy emitting buy intentions day by day."""

    strategy_id: str
    name: str
    required_indicators: tuple[str, ...]

    def generate_intents(self, ctx: StrategyContext) -> Iterator[OrderIntent]: ...


class ExecutionModel(Protocol):
    """Turns an order intention into a fill using the price series."""

    def execute(self, intent: OrderIntent, prices: PriceSeries) -> Fill | None: ...
