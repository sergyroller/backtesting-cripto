"""REST API routes (plan section H, F5)."""

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backtesting_cripto.api.schemas import BacktestRequest
from backtesting_cripto.domain.exceptions import (
    ConfigurationError,
    DataValidationError,
    DomainError,
    InsufficientDataError,
)
from backtesting_cripto.domain.models import BacktestConfig, BacktestResult
from backtesting_cripto.services.backtest_service import BacktestService
from backtesting_cripto.services.data_service import DataService, DataStatus
from backtesting_cripto.storage.run_store import RunSummary


def create_router(*, data_service: DataService, backtest_service: BacktestService) -> APIRouter:
    """Build the /api router bound to the application services."""
    router = APIRouter()

    @router.get("/strategies")
    def get_strategies() -> list[dict[str, Any]]:
        """Registered strategies with defaults and their available window."""
        return backtest_service.list_available_strategies()

    @router.get("/data/status")
    def get_data_status() -> DataStatus:
        """State of the local datasets."""
        return data_service.get_data_status()

    @router.post("/data/sync")
    def post_data_sync() -> DataStatus:
        """Download fresh data up to the last closed UTC day."""
        return data_service.sync_data()

    @router.post("/backtests", status_code=201)
    def post_backtest(request: BacktestRequest) -> BacktestResult:
        """Run a backtest and persist it."""
        strategy_params = (
            request.strategy_params
            if request.strategy_params is not None
            else backtest_service.default_params(request.strategy_id)
        )
        config = BacktestConfig(
            asset=request.asset,
            quote=request.quote,
            strategy_id=request.strategy_id,
            start_date=request.start_date,
            end_date=request.end_date,
            execution_mode=request.execution_mode,
            strategy_params=strategy_params,
        )
        return backtest_service.execute_backtest(config)

    @router.get("/backtests")
    def get_backtests(limit: int = 100) -> list[RunSummary]:
        """Most recent stored runs."""
        return backtest_service.list_backtests(limit=limit)

    @router.get("/backtests/{run_id}")
    def get_backtest(run_id: str) -> BacktestResult:
        """Full result of a stored run."""
        result = backtest_service.get_backtest(run_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
        return result

    return router


def _json_error(status_code: int, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


def register_exception_handlers(app: FastAPI) -> None:
    """Map domain exceptions to HTTP status codes."""

    def configuration_handler(
        _request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        return _json_error(422, exc)

    def insufficient_data_handler(
        _request: Request, exc: InsufficientDataError
    ) -> JSONResponse:
        return _json_error(400, exc)

    def data_validation_handler(
        _request: Request, exc: DataValidationError
    ) -> JSONResponse:
        return _json_error(409, exc)

    def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return _json_error(400, exc)

    def validation_error_handler(_request: Request, exc: ValidationError) -> JSONResponse:
        return _json_error(422, ConfigurationError(str(exc)))

    app.exception_handler(ConfigurationError)(configuration_handler)
    app.exception_handler(InsufficientDataError)(insufficient_data_handler)
    app.exception_handler(DataValidationError)(data_validation_handler)
    app.exception_handler(DomainError)(domain_error_handler)
    app.exception_handler(ValidationError)(validation_error_handler)
