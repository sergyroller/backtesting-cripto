"""SQLite storage (schema per plan section D.3) and in-memory series readers.

Decimals are stored as TEXT to preserve exact precision, and series are
loaded fully into memory so backtest lookups are O(1).
"""

import sqlite3
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from backtesting_cripto.domain.models import IndicatorValue, PriceBar

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS datasets (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        url TEXT NOT NULL,
        retrieved_at TEXT NOT NULL,
        sha256 TEXT NOT NULL,
        first_day TEXT NOT NULL,
        last_day TEXT NOT NULL,
        record_count INTEGER NOT NULL,
        license TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_bars (
        dataset_id TEXT NOT NULL,
        asset TEXT NOT NULL,
        quote TEXT NOT NULL,
        day TEXT NOT NULL,
        open TEXT NOT NULL,
        high TEXT NOT NULL,
        low TEXT NOT NULL,
        close TEXT NOT NULL,
        volume TEXT NOT NULL,
        PRIMARY KEY (asset, quote, day, dataset_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS indicator_values (
        dataset_id TEXT NOT NULL,
        indicator TEXT NOT NULL,
        day TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (indicator, day, dataset_id)
    )
    """,
)


def create_schema(connection: sqlite3.Connection) -> None:
    """Create the backtesting tables if they do not exist yet."""
    for statement in SCHEMA_STATEMENTS:
        connection.execute(statement)
    connection.commit()


class MemoryPriceSeries:
    """PriceSeries backed by an in-memory dict of daily bars."""

    def __init__(self, bars: dict[date, PriceBar]) -> None:
        self._bars = dict(sorted(bars.items()))
        self._days = list(self._bars)

    @classmethod
    def from_bars(cls, bars: Iterable[PriceBar]) -> "MemoryPriceSeries":
        return cls({bar.day: bar for bar in bars})

    def bar_on(self, day: date) -> PriceBar | None:
        return self._bars.get(day)

    def last_close_on_or_before(self, day: date) -> PriceBar | None:
        index = bisect_right(self._days, day) - 1
        if index < 0:
            return None
        return self._bars[self._days[index]]

    def date_bounds(self) -> tuple[date, date]:
        if not self._days:
            msg = "price series is empty"
            raise ValueError(msg)
        return self._days[0], self._days[-1]


class MemoryIndicatorSeries:
    """IndicatorSeries backed by an in-memory dict of daily values."""

    def __init__(self, values: dict[date, Decimal]) -> None:
        self._values = dict(sorted(values.items()))
        self._days = list(self._values)

    @classmethod
    def from_values(cls, values: Iterable[IndicatorValue]) -> "MemoryIndicatorSeries":
        return cls({value.day: value.value for value in values})

    def value_on(self, day: date) -> Decimal | None:
        return self._values.get(day)

    def to_dict(self) -> dict[date, Decimal]:
        """All readings keyed by day (used by the web layer for charts)."""
        return dict(self._values)

    def date_bounds(self) -> tuple[date, date]:
        if not self._days:
            msg = "indicator series is empty"
            raise ValueError(msg)
        return self._days[0], self._days[-1]


@dataclass(frozen=True)
class DatasetRecord:
    """A dataset row as stored in SQLite."""

    id: str
    source: str
    url: str
    retrieved_at: str
    sha256: str
    first_day: date
    last_day: date
    record_count: int
    license: str


class BacktestRepository:
    """SQLite repository for datasets, price bars and indicator values."""

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

    def __enter__(self) -> "BacktestRepository":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def has_datasets(self) -> bool:
        """True when at least one dataset row exists."""
        row = self._connection.execute("SELECT 1 FROM datasets LIMIT 1").fetchone()
        return row is not None

    def list_datasets(self) -> list[DatasetRecord]:
        """All stored datasets, ordered by id."""
        rows = self._connection.execute(
            """
            SELECT id, source, url, retrieved_at, sha256, first_day, last_day,
                   record_count, license
            FROM datasets ORDER BY id
            """
        ).fetchall()
        return [
            DatasetRecord(
                id=row[0],
                source=row[1],
                url=row[2],
                retrieved_at=row[3],
                sha256=row[4],
                first_day=date.fromisoformat(row[5]),
                last_day=date.fromisoformat(row[6]),
                record_count=row[7],
                license=row[8],
            )
            for row in rows
        ]

    def upsert_dataset(
        self,
        *,
        dataset_id: str,
        source: str,
        url: str,
        retrieved_at: str,
        sha256: str,
        first_day: date,
        last_day: date,
        record_count: int,
        license: str,
    ) -> None:
        self._connection.execute(
            """
            INSERT OR REPLACE INTO datasets
                (id, source, url, retrieved_at, sha256, first_day, last_day,
                 record_count, license)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dataset_id,
                source,
                url,
                retrieved_at,
                sha256,
                first_day.isoformat(),
                last_day.isoformat(),
                record_count,
                license,
            ),
        )
        self._connection.commit()

    def replace_price_bars(self, *, dataset_id: str, bars: Sequence[PriceBar]) -> None:
        self._connection.execute(
            "DELETE FROM price_bars WHERE dataset_id = ?", (dataset_id,)
        )
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO price_bars
                (dataset_id, asset, quote, day, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    dataset_id,
                    bar.asset,
                    bar.quote,
                    bar.day.isoformat(),
                    str(bar.open),
                    str(bar.high),
                    str(bar.low),
                    str(bar.close),
                    str(bar.volume),
                )
                for bar in bars
            ],
        )
        self._connection.commit()

    def replace_indicator_values(
        self, *, dataset_id: str, values: Sequence[IndicatorValue]
    ) -> None:
        self._connection.execute(
            "DELETE FROM indicator_values WHERE dataset_id = ?", (dataset_id,)
        )
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO indicator_values
                (dataset_id, indicator, day, value)
            VALUES (?, ?, ?, ?)
            """,
            [
                (dataset_id, value.indicator, value.day.isoformat(), str(value.value))
                for value in values
            ],
        )
        self._connection.commit()

    def _latest_dataset_id(self, table: str, conditions: dict[str, str]) -> str | None:
        where = " AND ".join(f"{column} = ?" for column in conditions)
        row = self._connection.execute(
            f"""
            SELECT t.dataset_id FROM {table} t
            JOIN datasets d ON t.dataset_id = d.id
            WHERE {where}
            ORDER BY d.last_day DESC LIMIT 1
            """,
            tuple(conditions.values()),
        ).fetchone()
        if row is None:
            return None
        dataset_id: str = row[0]
        return dataset_id

    def price_series(
        self, *, asset: str, quote: str, dataset_id: str | None = None
    ) -> MemoryPriceSeries:
        if dataset_id is None:
            dataset_id = self._latest_dataset_id(
                "price_bars", {"asset": asset, "quote": quote}
            )
        if dataset_id is None:
            msg = f"no price bars stored for {asset}/{quote}"
            raise LookupError(msg)
        rows = self._connection.execute(
            """
            SELECT day, open, high, low, close, volume, asset, quote
            FROM price_bars
            WHERE asset = ? AND quote = ? AND dataset_id = ?
            ORDER BY day
            """,
            (asset, quote, dataset_id),
        ).fetchall()
        bars = [
            PriceBar(
                asset=row[6],
                quote=row[7],
                day=date.fromisoformat(row[0]),
                open=Decimal(row[1]),
                high=Decimal(row[2]),
                low=Decimal(row[3]),
                close=Decimal(row[4]),
                volume=Decimal(row[5]),
                source=dataset_id,
            )
            for row in rows
        ]
        return MemoryPriceSeries.from_bars(bars)

    def indicator_series(
        self, *, indicator: str, dataset_id: str | None = None
    ) -> MemoryIndicatorSeries:
        if dataset_id is None:
            dataset_id = self._latest_dataset_id("indicator_values", {"indicator": indicator})
        if dataset_id is None:
            msg = f"no indicator values stored for {indicator}"
            raise LookupError(msg)
        rows = self._connection.execute(
            """
            SELECT day, value FROM indicator_values
            WHERE indicator = ? AND dataset_id = ?
            ORDER BY day
            """,
            (indicator, dataset_id),
        ).fetchall()
        values = {
            date.fromisoformat(row[0]): Decimal(row[1]) for row in rows
        }
        return MemoryIndicatorSeries(values)
