"""Backtest service: runs strategies on local data and persists the runs."""

from typing import Any

from pydantic import ValidationError

from backtesting_cripto.domain.contracts import Strategy
from backtesting_cripto.domain.exceptions import ConfigurationError, InsufficientDataError
from backtesting_cripto.domain.models import BacktestConfig, BacktestResult
from backtesting_cripto.engine.calendar import available_date_bounds, validate_window
from backtesting_cripto.engine.runner import run_backtest
from backtesting_cripto.indicators.registry import load_required_indicators
from backtesting_cripto.storage.raw_store import RawStore
from backtesting_cripto.storage.repository import BacktestRepository
from backtesting_cripto.storage.run_store import RunStore, RunSummary
from backtesting_cripto.strategies import StrategyRegistry, default_registry


class BacktestService:
    """Orchestrates data access, strategy execution and run persistence."""

    def __init__(
        self,
        repo: BacktestRepository,
        run_store: RunStore,
        raw_store: RawStore,
        registry: StrategyRegistry = default_registry,
    ) -> None:
        self._repo = repo
        self._run_store = run_store
        self._raw_store = raw_store
        self._registry = registry

    def execute_backtest(self, config: BacktestConfig) -> BacktestResult:
        """Run a backtest on local data and persist its result."""
        strategy = self._registry.get(config.strategy_id)
        config = self._normalize_config(config, strategy)

        try:
            prices = self._repo.price_series(asset=config.asset, quote=config.quote)
        except LookupError as error:
            msg = f"no stored prices for {config.asset}/{config.quote}"
            raise InsufficientDataError(msg) from error

        try:
            indicators = load_required_indicators(self._repo, strategy.required_indicators)
        except LookupError as error:
            msg = f"missing indicator series: {error}"
            raise InsufficientDataError(msg) from error

        bounds = available_date_bounds(prices, indicators, strategy.required_indicators)
        validate_window(config.start_date, config.end_date, bounds)

        result = run_backtest(
            config,
            prices,
            indicators,
            strategy,
            dataset_hash=self._raw_store.dataset_hash(),
        )
        self._run_store.save_run(result)
        return result

    def get_backtest(self, run_id: str) -> BacktestResult | None:
        """Rebuild a stored run, recomputing its equity curve from local prices.

        Prices are loaded through the service's own repository, so no
        extra SQLite connection is opened per request.
        """
        config = self._run_store.get_config(run_id)
        if config is None:
            return None

        try:
            prices = self._repo.price_series(asset=config.asset, quote=config.quote)
        except LookupError as error:
            msg = f"no stored prices for {config.asset}/{config.quote}"
            raise InsufficientDataError(msg) from error

        return self._run_store.get_run(run_id, prices=prices)

    def list_backtests(self, limit: int = 100) -> list[RunSummary]:
        """Most recent stored runs."""
        return self._run_store.list_runs(limit=limit)

    def list_available_strategies(self) -> list[dict[str, Any]]:
        """Registered strategies with their defaults and available window."""
        try:
            prices = self._repo.price_series(asset="BTC", quote="EUR")
        except LookupError:
            prices = None

        strategies: list[dict[str, Any]] = []
        for metadata in self._registry.list():
            entry: dict[str, Any] = {
                "strategy_id": metadata.strategy_id,
                "name": metadata.name,
                "description": metadata.description,
                "required_indicators": list(metadata.required_indicators),
                "default_params": self.default_params(metadata.strategy_id),
                "available_start": None,
                "available_end": None,
            }
            if prices is not None:
                try:
                    indicators = load_required_indicators(
                        self._repo, metadata.required_indicators
                    )
                    start, end = available_date_bounds(
                        prices, indicators, metadata.required_indicators
                    )
                    entry["available_start"] = start.isoformat()
                    entry["available_end"] = end.isoformat()
                except (LookupError, InsufficientDataError):
                    pass
            strategies.append(entry)
        return strategies

    def default_params(self, strategy_id: str) -> dict[str, Any]:
        """Default parameters of a registered strategy, as JSON-ready data."""
        return self._registry.get(strategy_id).params_schema().model_dump(mode="json")

    def validate_request_params(
        self, strategy_id: str, raw_params: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate strategy parameters, raising ConfigurationError on failure."""
        try:
            validated = self._registry.validate_params(strategy_id, raw_params)
        except ValidationError as error:
            msg = f"invalid parameters for {strategy_id}: {error}"
            raise ConfigurationError(msg) from error
        return validated.model_dump(mode="json")

    def _normalize_config(self, config: BacktestConfig, strategy: Strategy) -> BacktestConfig:
        """Validate the config parameters against the strategy schema."""
        validated = self.validate_request_params(config.strategy_id, config.strategy_params)
        if validated != config.strategy_params:
            return config.model_copy(update={"strategy_params": validated})
        return config
