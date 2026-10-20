"""Indicator registry: loads the series a strategy requires."""

from collections.abc import Sequence

from backtesting_cripto.domain.contracts import IndicatorSeries
from backtesting_cripto.storage.repository import BacktestRepository
from backtesting_cripto.strategies import StrategyRegistry, default_registry


def load_required_indicators(
    repo: BacktestRepository,
    required_indicators: Sequence[str],
) -> dict[str, IndicatorSeries]:
    """Load every indicator series a strategy requires from the repository.

    Raises LookupError (from the repository) when a required indicator
    has no stored data.
    """
    return {name: repo.indicator_series(indicator=name) for name in required_indicators}


def required_indicator_names(
    registry: StrategyRegistry = default_registry,
) -> list[str]:
    """Union of the indicators required by all registered strategies."""
    names: list[str] = []
    for metadata in registry.list():
        for name in metadata.required_indicators:
            if name not in names:
                names.append(name)
    return names
