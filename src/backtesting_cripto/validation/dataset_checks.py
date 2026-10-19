"""Dataset integrity checks run before consolidating data into SQLite.

Every failure raises DataValidationError so a broken download never
reaches the database or a backtest.
"""

from datetime import date, timedelta
from decimal import Decimal

from backtesting_cripto.domain.exceptions import DataValidationError
from backtesting_cripto.domain.models import IndicatorValue, PriceBar

FEAR_GREED_FIRST_DAY = date(2018, 2, 1)
PRICES_FIRST_DAY = date(2018, 1, 1)
FEAR_GREED_MIN_VALUE = Decimal("0")
FEAR_GREED_MAX_VALUE = Decimal("100")


def _check_no_duplicates(days: list[date], label: str) -> None:
    duplicates = sorted({day for day in days if days.count(day) > 1})
    if duplicates:
        first = duplicates[0].isoformat()
        msg = f"{label}: duplicated days (first: {first}, total: {len(duplicates)})"
        raise DataValidationError(msg)


def validate_fear_greed_series(
    values: list[IndicatorValue],
    *,
    last_closed_day: date,
    first_day: date = FEAR_GREED_FIRST_DAY,
) -> None:
    """Validate the Fear & Greed series before consolidation."""
    if not values:
        msg = "fear_greed: empty series"
        raise DataValidationError(msg)

    days = [value.day for value in values]
    actual_first = min(days)
    if actual_first != first_day:
        expected = first_day.isoformat()
        msg = f"fear_greed: first day must be {expected}, got {actual_first.isoformat()}"
        raise DataValidationError(msg)

    _check_no_duplicates(days, "fear_greed")

    for value in values:
        if value.day > last_closed_day:
            closed = last_closed_day.isoformat()
            msg = f"fear_greed: {value.day.isoformat()} is after the last closed day {closed}"
            raise DataValidationError(msg)
        if not FEAR_GREED_MIN_VALUE <= value.value <= FEAR_GREED_MAX_VALUE:
            msg = f"fear_greed: value {value.value} out of [0, 100] on {value.day.isoformat()}"
            raise DataValidationError(msg)
        if value.value != value.value.to_integral_value():
            msg = f"fear_greed: value {value.value} is not an integer on {value.day.isoformat()}"
            raise DataValidationError(msg)


def validate_price_bars(
    bars: list[PriceBar],
    *,
    last_closed_day: date,
    first_day: date = PRICES_FIRST_DAY,
) -> None:
    """Validate daily price bars: no gaps, no duplicates, coherent OHLC."""
    if not bars:
        msg = "price_bars: empty series"
        raise DataValidationError(msg)

    days = [bar.day for bar in bars]
    actual_first = min(days)
    if actual_first > first_day:
        expected = first_day.isoformat()
        msg = f"price_bars: first day must be <= {expected}, got {actual_first.isoformat()}"
        raise DataValidationError(msg)

    _check_no_duplicates(days, "price_bars")

    for bar in bars:
        if bar.day > last_closed_day:
            closed = last_closed_day.isoformat()
            msg = f"price_bars: {bar.day.isoformat()} is after the last closed day {closed}"
            raise DataValidationError(msg)

    present = set(days)
    cursor = first_day
    while cursor <= last_closed_day:
        if cursor not in present:
            msg = f"price_bars: missing daily bar on {cursor.isoformat()}"
            raise DataValidationError(msg)
        cursor += timedelta(days=1)

    for bar in bars:
        if bar.low <= 0:
            msg = f"price_bars: non-positive low on {bar.day.isoformat()}"
            raise DataValidationError(msg)
        if not bar.low <= bar.open <= bar.high:
            msg = f"price_bars: incoherent open on {bar.day.isoformat()}"
            raise DataValidationError(msg)
        if not bar.low <= bar.close <= bar.high:
            msg = f"price_bars: incoherent close on {bar.day.isoformat()}"
            raise DataValidationError(msg)
        if bar.volume < 0:
            msg = f"price_bars: negative volume on {bar.day.isoformat()}"
            raise DataValidationError(msg)
