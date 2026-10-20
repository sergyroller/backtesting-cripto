"""Indicator registry: loads the series a strategy requires."""

from collections.abc import Sequence

from backtesting_cripto.domain.contracts import IndicatorSeries
from backtesting_cripto.storage.repository import BacktestRepository


def load_required_indicators(
    repo: BacktestRepository,
    required_indicators: Sequence[str],
) -> dict[str, IndicatorSeries]:
    """Load every indicator series a strategy requires from the repository.

    Raises LookupError (from the repository) when a required indicator
    has no stored data.
    """
    return {
        name: repo.indicator_series(indicator=name) for name in required_indicators
    }
