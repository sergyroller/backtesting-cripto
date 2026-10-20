"""API request and response models."""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel


class BacktestRequest(BaseModel):
    """Payload of POST /api/backtests.

    ``strategy_params`` is optional: when omitted, the defaults declared
    by the strategy schema are used.
    """

    asset: str = "BTC"
    quote: str = "EUR"
    strategy_id: str = "fear_greed"
    start_date: date
    end_date: date
    execution_mode: Literal["close_same_day", "close_next_day"] = "close_same_day"
    strategy_params: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    """Uniform error body."""

    detail: str
