"""Domain models for the backtesting system (pure Python, no I/O).

All monetary amounts and BTC quantities use ``decimal.Decimal`` and are
quantized explicitly: BTC to 8 decimal places with ``ROUND_DOWN``
(satoshis) and EUR to 2 decimal places with ``ROUND_HALF_UP`` (cents).
"""

import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

BTC_QUANT = Decimal("0.00000001")  # 8 decimal places (1 satoshi)
EUR_QUANT = Decimal("0.01")  # 2 decimal places (1 cent)

ZERO_EUR = Decimal("0.00")


def quantize_btc(value: Decimal) -> Decimal:
    """Quantize a BTC amount to 8 decimals, rounding down (never inflates satoshis)."""
    return value.quantize(BTC_QUANT, rounding=ROUND_DOWN)


def quantize_eur(value: Decimal) -> Decimal:
    """Quantize a EUR amount to 2 decimals, rounding half up."""
    return value.quantize(EUR_QUANT, rounding=ROUND_HALF_UP)


class PriceBar(BaseModel):
    """Closed daily candle (00:00:00 to 23:59:59 UTC)."""

    asset: str
    quote: str
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str

    @model_validator(mode="after")
    def check_ohlc(self) -> "PriceBar":
        if self.low <= 0:
            raise ValueError("low must be > 0")
        if not self.low <= self.open <= self.high:
            raise ValueError("open must satisfy low <= open <= high")
        if not self.low <= self.close <= self.high:
            raise ValueError("close must satisfy low <= close <= high")
        if self.volume < 0:
            raise ValueError("volume must be >= 0")
        return self


class IndicatorValue(BaseModel):
    """Daily indicator reading (e.g. fear_greed, an integer in [0, 100])."""

    indicator: str
    day: date
    value: Decimal
    source: str

    @model_validator(mode="after")
    def check_value(self) -> "IndicatorValue":
        if not Decimal("0") <= self.value <= Decimal("100"):
            raise ValueError("value must be in [0, 100]")
        if self.value != self.value.to_integral_value():
            raise ValueError("value must be an integer")
        return self


class WeeklyBandRule(BaseModel):
    """Configurable weekly band, evaluated on Mondays only."""

    min_value: int = Field(ge=0, le=100)
    max_value: int = Field(ge=0, le=100)
    amount_eur: Decimal = Field(gt=Decimal("0"))

    @model_validator(mode="after")
    def check_bounds(self) -> "WeeklyBandRule":
        if self.min_value > self.max_value:
            raise ValueError("min_value must be <= max_value")
        return self


class FearGreedParams(BaseModel):
    """Editable parameters of the Fear & Greed strategy."""

    daily_below_threshold: int = Field(default=10, ge=0, le=100)
    daily_amount_eur: Decimal = Field(default=Decimal("50.00"), gt=Decimal("0"))
    weekly_bands: list[WeeklyBandRule] = Field(
        default_factory=lambda: [
            WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("200.00")),
            WeeklyBandRule(min_value=15, max_value=19, amount_eur=Decimal("150.00")),
            WeeklyBandRule(min_value=20, max_value=24, amount_eur=Decimal("100.00")),
        ]
    )

    @model_validator(mode="after")
    def validate_no_overlap(self) -> "FearGreedParams":
        """Weekly bands must not overlap nor invade the daily threshold."""
        sorted_bands = sorted(self.weekly_bands, key=lambda band: band.min_value)
        for band in sorted_bands:
            if band.min_value < self.daily_below_threshold:
                raise ValueError("weekly band min_value must be >= daily_below_threshold")
        for index in range(len(sorted_bands) - 1):
            if sorted_bands[index].max_value >= sorted_bands[index + 1].min_value:
                raise ValueError("weekly bands cannot overlap")
        return self


class OrderIntent(BaseModel):
    """Buy intention emitted by a strategy for a given decision day."""

    decision_day: date
    asset: str
    amount_eur: Decimal
    reason: str
    index_value: Decimal | None = None


class Fill(BaseModel):
    """Executed buy (100% direct: no fees, no slippage)."""

    execution_day: date
    decision_day: date
    asset: str
    index_value: Decimal | None
    amount_eur: Decimal
    price_eur: Decimal
    btc_quantity: Decimal
    reason: str


class EquityPoint(BaseModel):
    """Portfolio state at the close of a given day."""

    day: date
    invested_eur: Decimal
    btc_accumulated: Decimal
    close_price_eur: Decimal
    portfolio_value_eur: Decimal
    drawdown_pct: Decimal


class Metrics(BaseModel):
    """Aggregated results of a backtest run."""

    total_invested_eur: Decimal
    total_operations: int
    operations_by_reason: dict[str, int]
    btc_accumulated: Decimal
    average_buy_price_eur: Decimal | None
    final_price_eur: Decimal
    final_portfolio_value_eur: Decimal
    pnl_eur: Decimal
    roi_pct: Decimal | None
    max_drawdown_pct: Decimal


class BacktestConfig(BaseModel):
    """Configuration of a single backtest run."""

    asset: str = "BTC"
    quote: str = "EUR"
    strategy_id: str = "fear_greed"
    start_date: date
    end_date: date
    execution_mode: Literal["close_same_day", "close_next_day"] = "close_same_day"
    strategy_params: dict[str, Any]

    @model_validator(mode="after")
    def check_dates(self) -> "BacktestConfig":
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        return self


class BacktestResult(BaseModel):
    """Full result of a backtest run, including its canonical hash."""

    run_id: str
    created_at: datetime
    code_version: str
    dataset_hash: str
    config: BacktestConfig
    config_hash: str
    fills: list[Fill]
    equity_curve: list[EquityPoint]
    metrics: Metrics
    incidents: list[str] = []
    result_hash: str


def canonical_hash(obj: object) -> str:
    """Return a deterministic SHA-256 hash of a domain object.

    Pydantic models are dumped as JSON (Decimals become strings, dates use
    ISO format) and mappings are serialized with sorted keys, so equivalent
    payloads always produce the same digest.
    """
    if isinstance(obj, BaseModel):
        payload: object = obj.model_dump(mode="json")
    else:
        payload = obj
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
