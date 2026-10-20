"""Strategy implementations and their registry.

Importing this package registers the built-in strategies in the default
registry, so ``get_strategy("fear_greed")`` is available right away.
"""

from backtesting_cripto.strategies.base import (
    ParametrizedStrategy,
    StrategyMetadata,
    StrategyRegistry,
    default_registry,
    get_strategy,
    list_strategies,
    register_strategy,
    validate_strategy_params,
)
from backtesting_cripto.strategies.fear_greed import (
    INDICATOR_NAME,
    STRATEGY_ID,
    FearGreedStrategy,
    register,
)

# Built-in strategies are registered by default.
register()

__all__ = [
    "INDICATOR_NAME",
    "STRATEGY_ID",
    "FearGreedStrategy",
    "ParametrizedStrategy",
    "StrategyMetadata",
    "StrategyRegistry",
    "default_registry",
    "get_strategy",
    "list_strategies",
    "register",
    "register_strategy",
    "validate_strategy_params",
]
