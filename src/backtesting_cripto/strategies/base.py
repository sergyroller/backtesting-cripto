"""Strategy registry: strategies declare their parameters and indicators.

A strategy is any object fulfilling the Strategy protocol (see
domain.contracts) that additionally declares its editable parameter
schema in ``params_schema``, so the web layer (F6) can build forms and
validate payloads without knowing each strategy.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

from backtesting_cripto.domain.contracts import Strategy
from backtesting_cripto.domain.exceptions import ConfigurationError


class ParametrizedStrategy(Strategy, Protocol):
    """Strategy that also declares its Pydantic parameter schema."""

    params_schema: type[BaseModel]


@dataclass(frozen=True)
class StrategyMetadata:
    """Static description of a registered strategy."""

    strategy_id: str
    name: str
    description: str
    required_indicators: tuple[str, ...]
    params_schema: type[BaseModel]


class StrategyRegistry:
    """Registry mapping strategy_id to its strategy and metadata."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[ParametrizedStrategy, StrategyMetadata]] = {}

    def register(
        self, strategy: ParametrizedStrategy, *, description: str = ""
    ) -> StrategyMetadata:
        """Register a strategy under its strategy_id (re-registering replaces)."""
        params_schema = getattr(strategy, "params_schema", None)
        if not (isinstance(params_schema, type) and issubclass(params_schema, BaseModel)):
            msg = f"strategy {strategy.strategy_id!r} must declare a params_schema (BaseModel)"
            raise ConfigurationError(msg)

        metadata = StrategyMetadata(
            strategy_id=strategy.strategy_id,
            name=strategy.name,
            description=description,
            required_indicators=tuple(strategy.required_indicators),
            params_schema=params_schema,
        )
        self._entries[strategy.strategy_id] = (strategy, metadata)
        return metadata

    def get(self, strategy_id: str) -> ParametrizedStrategy:
        """Return the strategy registered under strategy_id."""
        entry = self._entries.get(strategy_id)
        if entry is None:
            msg = f"unknown strategy_id: {strategy_id!r}"
            raise ConfigurationError(msg)
        return entry[0]

    def metadata(self, strategy_id: str) -> StrategyMetadata:
        """Return the metadata of a registered strategy."""
        entry = self._entries.get(strategy_id)
        if entry is None:
            msg = f"unknown strategy_id: {strategy_id!r}"
            raise ConfigurationError(msg)
        return entry[1]

    def list(self) -> list[StrategyMetadata]:
        """All registered strategies, sorted by strategy_id."""
        return [self._entries[key][1] for key in sorted(self._entries)]

    def validate_params(self, strategy_id: str, raw_params: Mapping[str, Any]) -> BaseModel:
        """Validate raw parameters against the strategy schema."""
        return self.metadata(strategy_id).params_schema.model_validate(raw_params)


# Default process-wide registry.
default_registry = StrategyRegistry()


def register_strategy(
    strategy: ParametrizedStrategy, *, description: str = ""
) -> StrategyMetadata:
    """Register a strategy in the default registry."""
    return default_registry.register(strategy, description=description)


def get_strategy(strategy_id: str) -> ParametrizedStrategy:
    """Return a registered strategy from the default registry."""
    return default_registry.get(strategy_id)


def list_strategies() -> list[StrategyMetadata]:
    """List the strategies of the default registry."""
    return default_registry.list()


def validate_strategy_params(strategy_id: str, raw_params: Mapping[str, Any]) -> BaseModel:
    """Validate raw parameters against a registered strategy schema."""
    return default_registry.validate_params(strategy_id, raw_params)
