"""CLI to download, validate and consolidate historical data.

Usage (from the project root)::

    uv run python scripts/sync_data.py

Downloads the Fear & Greed index (BGeometrics with alternative.me
fallback) and BTC/EUR daily candles (Bitstamp), stores the immutable raw
files under data/raw/, validates the datasets and populates
data/backtesting.sqlite3 with data up to the last closed UTC day.

The logic lives in backtesting_cripto.services.data_service so the API
and this script share exactly the same code path.
"""

import sys
from pathlib import Path

from backtesting_cripto.services.data_service import (
    FNG_DATASET_ID,
    PRICES_DATASET_ID,
    DataService,
)
from backtesting_cripto.storage.raw_store import RawStore
from backtesting_cripto.storage.repository import BacktestRepository

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "backtesting.sqlite3"


def main() -> int:
    """Run the full synchronization pipeline."""
    print("Sincronizando datos hasta el último día cerrado (UTC)...")

    repo = BacktestRepository(DB_PATH)
    try:
        service = DataService(repo, RawStore(RAW_DIR))
        status = service.sync_data()

        for dataset in status.datasets:
            print(
                f"  {dataset.id}: {dataset.record_count} registros "
                f"({dataset.first_day.isoformat()} → {dataset.last_day.isoformat()})"
            )
        print(f"  Último día cerrado considerado: {status.last_closed_day.isoformat()}")

        if FNG_DATASET_ID not in {dataset.id for dataset in status.datasets}:
            print("  Aviso: no se encontró el dataset de Fear & Greed")
        if PRICES_DATASET_ID not in {dataset.id for dataset in status.datasets}:
            print("  Aviso: no se encontró el dataset de precios BTC/EUR")
    finally:
        repo.close()

    print(f"Base de datos actualizada: {DB_PATH.relative_to(PROJECT_ROOT)}")
    print(f"dataset_hash del manifiesto: {RawStore(RAW_DIR).dataset_hash()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
