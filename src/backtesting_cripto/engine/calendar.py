"""Date utilities and available-window computation for backtests."""

from collections.abc import Iterator, Mapping, Sequence
from datetime import date, timedelta

from backtesting_cripto.domain.contracts import IndicatorSeries, PriceSeries
from backtesting_cripto.domain.exceptions import ConfigurationError, InsufficientDataError


def iter_days(start_date: date, end_date: date) -> Iterator[date]:
    """Inclusive daily iteration over [start_date, end_date]."""
    if start_date > end_date:
        msg = f"start_date {start_date.isoformat()} is after end_date {end_date.isoformat()}"
        raise ConfigurationError(msg)
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def is_monday(day: date) -> bool:
    """True when the given UTC day is a Monday."""
    return day.weekday() == 0


def available_date_bounds(
    prices: PriceSeries,
    indicators: Mapping[str, IndicatorSeries],
    required_indicators: Sequence[str],
) -> tuple[date, date]:
    """Available [min, max] date range for a strategy (plan section E.1).

    The window is the intersection of the price series bounds and the
    bounds of every indicator the strategy requires.
    """
    price_first, price_last = prices.date_bounds()
    first_days = [price_first]
    last_days = [price_last]

    for name in required_indicators:
        series = indicators.get(name)
        if series is None:
            msg = f"missing required indicator: {name}"
            raise InsufficientDataError(msg)
        indicator_first, indicator_last = series.date_bounds()
        first_days.append(indicator_first)
        last_days.append(indicator_last)

    min_available = max(first_days)
    max_available = min(last_days)
    if min_available > max_available:
        msg = (
            f"no overlapping data: available window would be "
            f"[{min_available.isoformat()}, {max_available.isoformat()}]"
        )
        raise InsufficientDataError(msg)
    return min_available, max_available


def validate_window(
    start_date: date,
    end_date: date,
    available_bounds: tuple[date, date],
) -> None:
    """Ensure the requested window is ordered and inside the available bounds."""
    min_available, max_available = available_bounds
    if start_date > end_date:
        msg = f"start_date {start_date.isoformat()} is after end_date {end_date.isoformat()}"
        raise ConfigurationError(msg)
    if start_date < min_available or end_date > max_available:
        msg = (
            f"window [{start_date.isoformat()}, {end_date.isoformat()}] is outside the "
            f"available range [{min_available.isoformat()}, {max_available.isoformat()}]"
        )
        raise ConfigurationError(msg)
