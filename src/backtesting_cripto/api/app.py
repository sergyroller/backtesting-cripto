"""FastAPI application factory (injectable storage for tests)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backtesting_cripto import __version__
from backtesting_cripto.api.routes import create_router, register_exception_handlers
from backtesting_cripto.services.backtest_service import BacktestService
from backtesting_cripto.services.data_service import DataService
from backtesting_cripto.storage.raw_store import RawStore
from backtesting_cripto.storage.repository import BacktestRepository
from backtesting_cripto.storage.run_store import RunStore
from backtesting_cripto.web.views import create_web_router

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "backtesting.sqlite3"
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static"

API_DESCRIPTION = (
    "API del sistema de backtesting de acumulación de criptomonedas. "
    "Todos los backtests se ejecutan sobre datos locales (nunca en red)."
)


def create_app(db_path: Path | None = None, raw_dir: Path | None = None) -> FastAPI:
    """Build the application, hydrating SQLite from data/raw/ when needed."""
    resolved_db_path = db_path or DEFAULT_DB_PATH
    resolved_raw_dir = raw_dir or DEFAULT_RAW_DIR

    repo = BacktestRepository(resolved_db_path)
    raw_store = RawStore(resolved_raw_dir)
    run_store = RunStore(resolved_db_path)

    data_service = DataService(repo, raw_store)
    data_service.ensure_populated()
    backtest_service = BacktestService(repo, run_store, raw_store)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        run_store.close()
        repo.close()

    app = FastAPI(
        title="backtesting-cripto",
        version=__version__,
        description=API_DESCRIPTION,
        lifespan=lifespan,
    )
    app.state.db_path = resolved_db_path
    app.state.raw_dir = resolved_raw_dir
    app.state.repo = repo
    app.state.raw_store = raw_store
    app.state.run_store = run_store
    app.state.data_service = data_service
    app.state.backtest_service = backtest_service

    register_exception_handlers(app)
    app.include_router(
        create_router(data_service=data_service, backtest_service=backtest_service),
        prefix="/api",
    )
    app.include_router(
        create_web_router(data_service=data_service, backtest_service=backtest_service)
    )
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    return app