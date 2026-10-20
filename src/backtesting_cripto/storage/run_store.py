"""Persistence of backtest runs (plan section D.3: backtest_runs, trades)."""

import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from backtesting_cripto.domain.contracts import PriceSeries
from backtesting_cripto.domain.models import (
    BacktestConfig,
    BacktestResult,
    Fill,
    Metrics,
)
from backtesting_cripto.metrics.calculator import build_equity_curve
from backtesting_cripto.storage.repository import BacktestRepository

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        code_version TEXT NOT NULL,
        dataset_hash TEXT NOT NULL,
        config_json TEXT NOT NULL,
        config_hash TEXT NOT NULL,
        metrics_json TEXT NOT NULL,
        incidents_json TEXT NOT NULL,
        result_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trades (
        run_id TEXT NOT NULL,
        seq INTEGER NOT NULL,
        decision_day TEXT NOT NULL,
        execution_day TEXT NOT NULL,
        index_value TEXT,
        amount_eur TEXT NOT NULL,
        price_eur TEXT NOT NULL,
        btc_quantity TEXT NOT NULL,
        reason TEXT NOT NULL,
        PRIMARY KEY (run_id, seq)
    )
    """,
)


class RunSummary(BaseModel):
    """Lightweight view of a stored run for listings."""

    run_id: str
    created_at: datetime
    code_version: str
    dataset_hash: str
    config: BacktestConfig
    config_hash: str
    metrics: Metrics
    result_hash: str


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the run tables if they do not exist yet."""
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.commit()


class RunStore:
    """Saves and reloads backtest runs in the same SQLite database."""

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._db_path), check_same_thread=False)
        create_schema(self._connection)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "RunStore":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def save_run(self, result: BacktestResult) -> None:
        """Persist a run and its trades in a single transaction."""
        with self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO backtest_runs
                    (run_id, created_at, code_version, dataset_hash, config_json,
                     config_hash, metrics_json, incidents_json, result_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.run_id,
                    result.created_at.isoformat(),
                    result.code_version,
                    result.dataset_hash,
                    result.config.model_dump_json(),
                    result.config_hash,
                    result.metrics.model_dump_json(),
                    json.dumps(result.incidents, ensure_ascii=False),
                    result.result_hash,
                ),
            )
            self._connection.execute(
                "DELETE FROM trades WHERE run_id = ?", (result.run_id,)
            )
            self._connection.executemany(
                """
                INSERT INTO trades
                    (run_id, seq, decision_day, execution_day, index_value,
                     amount_eur, price_eur, btc_quantity, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        result.run_id,
                        seq,
                        fill.decision_day.isoformat(),
                        fill.execution_day.isoformat(),
                        None if fill.index_value is None else str(fill.index_value),
                        str(fill.amount_eur),
                        str(fill.price_eur),
                        str(fill.btc_quantity),
                        fill.reason,
                    )
                    for seq, fill in enumerate(result.fills, start=1)
                ],
            )

    def get_config(self, run_id: str) -> BacktestConfig | None:
        """Stored configuration of a run, or None when it does not exist."""
        row = self._connection.execute(
            "SELECT config_json FROM backtest_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return BacktestConfig.model_validate_json(row[0])

    def get_run(
        self, run_id: str, prices: PriceSeries | None = None
    ) -> BacktestResult | None:
        """Rebuild a stored run, recomputing its equity curve from prices.

        When no prices are given, the daily candles are loaded from the
        same SQLite database (asset/quote taken from the stored config).
        """
        row = self._connection.execute(
            "SELECT * FROM backtest_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None

        config = BacktestConfig.model_validate_json(row[4])
        metrics = Metrics.model_validate_json(row[6])
        incidents: list[str] = json.loads(row[7])

        trade_rows = self._connection.execute(
            """
            SELECT decision_day, execution_day, index_value, amount_eur,
                   price_eur, btc_quantity, reason
            FROM trades WHERE run_id = ? ORDER BY seq
            """,
            (run_id,),
        ).fetchall()
        fills = [
            Fill(
                execution_day=date.fromisoformat(trade[1]),
                decision_day=date.fromisoformat(trade[0]),
                asset=config.asset,
                index_value=None if trade[2] is None else Decimal(trade[2]),
                amount_eur=Decimal(trade[3]),
                price_eur=Decimal(trade[4]),
                btc_quantity=Decimal(trade[5]),
                reason=trade[6],
            )
            for trade in trade_rows
        ]

        if prices is None:
            with BacktestRepository(self._db_path) as repo:
                prices = repo.price_series(asset=config.asset, quote=config.quote)

        equity_curve = build_equity_curve(fills, prices, config.start_date, config.end_date)

        return BacktestResult(
            run_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            code_version=row[2],
            dataset_hash=row[3],
            config=config,
            config_hash=row[5],
            fills=fills,
            equity_curve=equity_curve,
            metrics=metrics,
            incidents=incidents,
            result_hash=row[8],
        )

    def list_runs(self, limit: int = 100) -> list[RunSummary]:
        """Most recent runs first."""
        rows = self._connection.execute(
            """
            SELECT run_id, created_at, code_version, dataset_hash, config_json,
                   config_hash, metrics_json, result_hash
            FROM backtest_runs ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [
            RunSummary(
                run_id=row[0],
                created_at=datetime.fromisoformat(row[1]),
                code_version=row[2],
                dataset_hash=row[3],
                config=BacktestConfig.model_validate_json(row[4]),
                config_hash=row[5],
                metrics=Metrics.model_validate_json(row[6]),
                result_hash=row[7],
            )
            for row in rows
        ]
