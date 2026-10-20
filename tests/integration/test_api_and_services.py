"""Integration tests for the REST API and the application services."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backtesting_cripto.api.app import create_app
from backtesting_cripto.providers import bgeometrics_fng, bitstamp_ohlc
from backtesting_cripto.services.data_service import DataService, last_closed_utc_day
from backtesting_cripto.storage.raw_store import RawStore
from backtesting_cripto.storage.repository import BacktestRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_RAW_DIR = PROJECT_ROOT / "data" / "raw"
FNG_FIRST_DAY = date(2018, 2, 1)
PRICES_FIRST_DAY = date(2018, 1, 1)
WINDOW_START = date(2018, 2, 1)
WINDOW_END = date(2026, 10, 18)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """App backed by a temporary SQLite and the real frozen data/raw/."""
    app = create_app(db_path=tmp_path / "api.sqlite3", raw_dir=REAL_RAW_DIR)
    with TestClient(app) as test_client:
        yield test_client


# --- Offline hydration --------------------------------------------------------


def test_ensure_populated_hydrates_from_raw(tmp_path: Path) -> None:
    db_path = tmp_path / "hydrated.sqlite3"
    with BacktestRepository(db_path) as repo:
        service = DataService(repo, RawStore(REAL_RAW_DIR))
        assert repo.has_datasets() is False

        assert service.ensure_populated() is True
        assert repo.has_datasets() is True

        # A second call is a no-op.
        assert service.ensure_populated() is False


def test_ensure_populated_makes_no_network_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def exploding_get_bytes(url: str, *, timeout: int = 30) -> bytes:
        msg = f"unexpected network access during hydration: {url}"
        raise AssertionError(msg)

    monkeypatch.setattr(bgeometrics_fng, "get_bytes", exploding_get_bytes)
    monkeypatch.setattr(bitstamp_ohlc, "get_bytes", exploding_get_bytes)

    db_path = tmp_path / "offline.sqlite3"
    with BacktestRepository(db_path) as repo:
        service = DataService(repo, RawStore(REAL_RAW_DIR))
        assert service.ensure_populated() is True

        prices = repo.price_series(asset="BTC", quote="EUR")
        indicators = repo.indicator_series(indicator="fear_greed")
        assert prices.date_bounds()[0] == PRICES_FIRST_DAY
        assert indicators.date_bounds()[0] == FNG_FIRST_DAY


def test_ensure_populated_works_when_clock_is_in_the_future(tmp_path: Path) -> None:
    """The frozen F&G payload contains the still-open day (2026-10-20).

    With a clock far in the future the hydration must still succeed,
    trimming both series to the last day with data (2026-10-19) instead
    of raising DataValidationError.
    """
    db_path = tmp_path / "future.sqlite3"
    with BacktestRepository(db_path) as repo:
        service = DataService(repo, RawStore(REAL_RAW_DIR))

        assert service.ensure_populated(now=datetime(2027, 6, 1, tzinfo=UTC)) is True
        assert repo.has_datasets() is True

        prices = repo.price_series(asset="BTC", quote="EUR")
        indicators = repo.indicator_series(indicator="fear_greed")
        assert prices.date_bounds()[1] == date(2026, 10, 19)
        assert indicators.date_bounds()[1] == date(2026, 10, 19)


def test_app_closes_sqlite_connections_on_shutdown(tmp_path: Path) -> None:
    import sqlite3

    app = create_app(db_path=tmp_path / "lifecycle.sqlite3", raw_dir=REAL_RAW_DIR)
    with TestClient(app) as client:
        assert client.get("/api/data/status").status_code == 200
        repo = app.state.repo
        run_store = app.state.run_store

    # The lifespan must close both connections when the app shuts down.
    with pytest.raises(sqlite3.ProgrammingError):
        repo.connection.execute("SELECT 1")
    with pytest.raises(sqlite3.ProgrammingError):
        run_store.connection.execute("SELECT 1")


def test_get_backtest_reuses_the_service_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /api/backtests/{run_id} must not open extra SQLite connections."""
    app = create_app(db_path=tmp_path / "reuse.sqlite3", raw_dir=REAL_RAW_DIR)
    with TestClient(app) as client:
        created = client.post(
            "/api/backtests",
            json={"start_date": "2020-01-01", "end_date": "2020-12-31"},
        )
        assert created.status_code == 201
        run_id = created.json()["run_id"]

        opened: list[object] = []
        original_init = BacktestRepository.__init__

        def counting_init(self: BacktestRepository, db_path: object) -> None:
            opened.append(db_path)
            original_init(self, db_path)  # type: ignore[arg-type]

        monkeypatch.setattr(BacktestRepository, "__init__", counting_init)
        fetched = client.get(f"/api/backtests/{run_id}")

        assert fetched.status_code == 200
        assert fetched.json()["result_hash"] == created.json()["result_hash"]
        assert opened == []  # no new repository was opened for the request


# --- GET /api/strategies ------------------------------------------------------


def test_get_strategies(client: TestClient) -> None:
    response = client.get("/api/strategies")
    assert response.status_code == 200

    strategies = response.json()
    fear_greed = next(
        item for item in strategies if item["strategy_id"] == "fear_greed"
    )
    assert fear_greed["available_start"] == "2018-02-01"
    assert fear_greed["available_end"] >= "2026-10-18"
    assert fear_greed["required_indicators"] == ["fear_greed"]
    assert fear_greed["default_params"]["daily_amount_eur"] == "50.00"


# --- GET /api/data/status -----------------------------------------------------


def test_get_data_status(client: TestClient) -> None:
    response = client.get("/api/data/status")
    assert response.status_code == 200

    status = response.json()
    assert status["dataset_hash"]
    assert status["last_closed_day"] == last_closed_utc_day().isoformat()

    ids = {dataset["id"] for dataset in status["datasets"]}
    assert "fear_greed_bgeometrics" in ids
    assert "prices_btceur_bitstamp" in ids
    assert status["available_start"] == "2018-02-01"


# --- POST /api/backtests ------------------------------------------------------


def test_post_backtest_regression(client: TestClient) -> None:
    response = client.post(
        "/api/backtests",
        json={"start_date": "2018-02-01", "end_date": "2026-10-18"},
    )
    assert response.status_code == 201

    result = response.json()
    metrics = result["metrics"]
    assert metrics["total_operations"] == 121
    assert metrics["total_invested_eur"] == "13300.00"
    assert metrics["btc_accumulated"] == "1.10037310"
    assert metrics["average_buy_price_eur"] == "12086.81"
    assert metrics["final_portfolio_value_eur"] == "80401.26"
    assert metrics["roi_pct"] == "504.52"
    assert result["incidents"] == []

    run_id = result["run_id"]

    stored = client.get(f"/api/backtests/{run_id}")
    assert stored.status_code == 200
    assert stored.json()["result_hash"] == result["result_hash"]

    listing = client.get("/api/backtests").json()
    assert run_id in [summary["run_id"] for summary in listing]


def test_get_backtest_not_found(client: TestClient) -> None:
    response = client.get("/api/backtests/nonexistent-run")
    assert response.status_code == 404


def test_post_backtest_with_overlapping_bands_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/backtests",
        json={
            "start_date": "2020-01-01",
            "end_date": "2020-06-30",
            "strategy_params": {
                "weekly_bands": [
                    {"min_value": 10, "max_value": 14, "amount_eur": "200.00"},
                    {"min_value": 14, "max_value": 19, "amount_eur": "150.00"},
                ]
            },
        },
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_post_backtest_with_window_out_of_range_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/backtests",
        json={"start_date": "2018-02-01", "end_date": "2030-01-01"},
    )
    assert response.status_code == 422


def test_post_backtest_with_inverted_dates_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/backtests",
        json={"start_date": "2020-06-30", "end_date": "2020-01-01"},
    )
    assert response.status_code == 422


def test_post_backtest_without_data_returns_400(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "empty.sqlite3", raw_dir=tmp_path / "no-raw")
    with TestClient(app) as client:
        response = client.post(
            "/api/backtests",
            json={"start_date": "2018-02-01", "end_date": "2026-10-18"},
        )
    assert response.status_code == 400


def test_post_backtest_with_custom_params(client: TestClient) -> None:
    response = client.post(
        "/api/backtests",
        json={
            "start_date": "2018-02-01",
            "end_date": "2026-10-18",
            "strategy_params": {
                "daily_below_threshold": 8,
                "daily_amount_eur": "75.50",
            },
        },
    )
    assert response.status_code == 201
    metrics = response.json()["metrics"]
    assert metrics["operations_by_reason"]["daily_<8"] >= 1
    assert metrics["total_invested_eur"] != "13300.00"


# --- POST /api/data/sync ------------------------------------------------------


def _fake_fng_payload(closed_day: date) -> bytes:
    """Synthetic BGeometrics payload: one integer value per day from 2018-02-01."""
    entries = []
    cursor = FNG_FIRST_DAY
    index = 0
    while cursor <= closed_day:
        timestamp_ms = int(
            datetime(cursor.year, cursor.month, cursor.day, tzinfo=UTC).timestamp() * 1000
        )
        entries.append([timestamp_ms, (index * 7) % 101])
        cursor += timedelta(days=1)
        index += 1
    return json.dumps(entries).encode()


def _fake_bitstamp_page(days: list[date]) -> bytes:
    ohlc = [
        {
            "timestamp": str(
                int(datetime(day.year, day.month, day.day, tzinfo=UTC).timestamp())
            ),
            "open": "100.00",
            "high": "110.00",
            "low": "90.00",
            "close": "105.00",
            "volume": "10.5",
        }
        for day in days
    ]
    return json.dumps({"data": {"ohlc": ohlc}}).encode()


def _fake_bitstamp_payload_for_end(end: date) -> bytes:
    """Emulate Bitstamp: at most PAGE_DAYS candles ending at ``end``."""
    start = end - timedelta(days=bitstamp_ohlc.PAGE_DAYS - 1)
    days = [start + timedelta(days=index) for index in range((end - start).days + 1)]
    return _fake_bitstamp_page(days)


def _patch_providers(monkeypatch: pytest.MonkeyPatch, closed_day: date) -> None:
    """Replace network downloads with deterministic synthetic payloads."""

    def fake_fng_get_bytes(url: str, *, timeout: int = 30) -> bytes:
        return _fake_fng_payload(closed_day)

    def fake_bitstamp_get_bytes(url: str, *, timeout: int = 30) -> bytes:
        params = parse_qs(urlparse(url).query)
        end = datetime.fromtimestamp(int(params["end"][0]), tz=UTC).date()
        return _fake_bitstamp_payload_for_end(end)

    monkeypatch.setattr(bgeometrics_fng, "get_bytes", fake_fng_get_bytes)
    monkeypatch.setattr(bitstamp_ohlc, "get_bytes", fake_bitstamp_get_bytes)


def test_post_data_sync_updates_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed_day = last_closed_utc_day()
    _patch_providers(monkeypatch, closed_day)

    app = create_app(db_path=tmp_path / "sync.sqlite3", raw_dir=tmp_path / "raw")
    with TestClient(app) as client:
        response = client.post("/api/data/sync")

    assert response.status_code == 200
    status = response.json()
    assert status["last_closed_day"] == closed_day.isoformat()

    ids = {dataset["id"] for dataset in status["datasets"]}
    assert "fear_greed_bgeometrics" in ids
    assert "prices_btceur_bitstamp" in ids

    ranges = status["available_ranges"]["fear_greed"]
    assert ranges["start"] == "2018-02-01"
    assert ranges["end"] == closed_day.isoformat()

    # The downloaded payloads are stored as immutable raw files.
    manifest = RawStore(tmp_path / "raw").load_manifest()
    assert len(manifest) >= 2
    assert all(entry.sha256 for entry in manifest)


def test_post_backtest_after_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed_day = last_closed_utc_day()
    _patch_providers(monkeypatch, closed_day)

    app = create_app(db_path=tmp_path / "sync2.sqlite3", raw_dir=tmp_path / "raw2")
    with TestClient(app) as client:
        sync_response = client.post("/api/data/sync")
        assert sync_response.status_code == 200

        response = client.post(
            "/api/backtests",
            json={
                "start_date": "2018-02-01",
                "end_date": closed_day.isoformat(),
                "strategy_params": {
                    "daily_below_threshold": 0,  # never triggers: no daily buys
                    "weekly_bands": [],  # and no weekly bands at all
                },
            },
        )

    assert response.status_code == 201
    metrics = response.json()["metrics"]
    assert metrics["total_operations"] == 0
    assert metrics["total_invested_eur"] == "0.00"
    assert metrics["average_buy_price_eur"] is None
    assert metrics["roi_pct"] is None
