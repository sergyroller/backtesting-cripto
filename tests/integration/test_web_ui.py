"""Integration tests for the web UI (HTML views and HTMX fragments)."""

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from backtesting_cripto.api.app import create_app
from backtesting_cripto.providers import bgeometrics_fng, bitstamp_ohlc
from backtesting_cripto.services.data_service import last_closed_utc_day

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REAL_RAW_DIR = PROJECT_ROOT / "data" / "raw"
FNG_FIRST_DAY = date(2018, 2, 1)

THIN_SPACE = "\u202f"
NNBSP = "\u2009"
INVESTED = f"13{THIN_SPACE}300,00{NNBSP}€"
BTC_TOTAL = "1,10037310 BTC"
FINAL_VALUE = f"80{THIN_SPACE}401,26{NNBSP}€"
ROI_PCT = f"+504,52{NNBSP}%"

DEFAULT_PARAMS = json.dumps(
    {
        "daily_below_threshold": 10,
        "daily_amount_eur": "50,00",
        "weekly_bands": [
            {"min_value": 10, "max_value": 14, "amount_eur": "200.00"},
            {"min_value": 15, "max_value": 19, "amount_eur": "150.00"},
            {"min_value": 20, "max_value": 24, "amount_eur": "100.00"},
        ],
    }
)
OVERLAPPING_PARAMS = json.dumps(
    {
        "daily_below_threshold": 10,
        "daily_amount_eur": "50,00",
        "weekly_bands": [
            {"min_value": 10, "max_value": 14, "amount_eur": "200.00"},
            {"min_value": 14, "max_value": 19, "amount_eur": "150.00"},
        ],
    }
)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """App backed by a temporary SQLite hydrated from the frozen data/raw/."""
    app = create_app(db_path=tmp_path / "ui.sqlite3", raw_dir=REAL_RAW_DIR)
    with TestClient(app) as test_client:
        yield test_client


def post_simulation(
    client: TestClient, headers: dict[str, str] | None = None, **overrides: object
) -> object:
    payload: dict[str, object] = {
        "start_date": "2018-02-01",
        "end_date": "2026-10-18",
        "strategy_id": "fear_greed",
        "execution_mode": "close_same_day",
        "daily_below_threshold": "10",
        "daily_amount_eur": "50,00",
        "strategy_params_json": DEFAULT_PARAMS,
    }
    payload.update(overrides)
    return client.post("/ui/backtests", data=payload, headers=headers or {})


# --- GET / --------------------------------------------------------------------


def test_panel_renders_in_spanish(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert '<html lang="es"' in html
    assert "Simulador de acumulación" in html
    # Script anti-FOUC (§8.2) y control de tema.
    assert "theme-preference" in html
    assert "Claro" in html and "Oscuro" in html and "Sistema" in html
    # Navegación de 3 vistas (§9.1).
    assert 'href="/backtests"' in html
    assert 'href="/data"' in html


def test_panel_runs_the_reference_simulation_when_empty(client: TestClient) -> None:
    """Con datos pero sin simulaciones guardadas, el panel muestra la de referencia."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Ejecuta tu primera simulación" not in response.text
    assert INVESTED in response.text
    assert 'data-chart-for="chart-g1"' in response.text


def test_run_simulation_from_the_ui(client: TestClient) -> None:
    response = post_simulation(client)
    assert response.status_code == 200
    html = response.text

    assert INVESTED in html
    assert "121 operaciones" in html
    assert BTC_TOTAL in html
    assert FINAL_VALUE in html
    assert ROI_PCT in html
    assert "Lunes 10–14" in html  # reason formateado
    assert "Diaria (&lt; 10)" in html or "Diaria (< 10)" in html

    # Gráficos: specs JSON embebidos para Plotly (§12.7).
    assert 'data-chart-for="chart-g1"' in html
    assert 'data-chart-for="chart-g2"' in html
    assert 'data-chart-for="chart-g3"' in html
    assert 'data-chart-for="chart-g4"' in html
    assert "Capital invertido vs. valor de la cartera" in html

    # Pestañas del resultado (§9.1).
    assert "Operaciones" in html
    assert "Supuestos" in html
    assert "result_hash" in html


def test_panel_shows_the_latest_run_after_simulating(client: TestClient) -> None:
    post_simulation(client)
    response = client.get("/")
    assert response.status_code == 200
    assert INVESTED in response.text
    assert 'data-chart-for="chart-g1"' in response.text


def test_run_simulation_with_overlapping_bands_shows_spanish_error(client: TestClient) -> None:
    response = post_simulation(client, strategy_params_json=OVERLAPPING_PARAMS)
    assert response.status_code == 200
    html = response.text
    assert "solapados" in html.lower()
    assert "No se pudo ejecutar la simulación" in html


def test_run_simulation_with_dates_out_of_range_shows_spanish_error(client: TestClient) -> None:
    response = post_simulation(client, end_date="2030-01-01")
    assert response.status_code == 200
    assert "fuera de la cobertura" in response.text or "rango de fechas" in response.text


# --- HTMX ---------------------------------------------------------------------


def test_htmx_request_returns_only_the_fragment(client: TestClient) -> None:
    response = post_simulation(client, headers={"HX-Request": "true"})
    assert response.status_code == 200
    html = response.text
    assert "<html" not in html  # solo el fragmento
    assert INVESTED in html


def test_htmx_response_includes_completion_toast(client: TestClient) -> None:
    response = post_simulation(client, headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text
    assert "Simulación completada" in response.text
    assert "121 operaciones" in response.text


def test_htmx_error_response_includes_toast(client: TestClient) -> None:
    response = post_simulation(
        client, headers={"HX-Request": "true"}, strategy_params_json=OVERLAPPING_PARAMS
    )
    assert response.status_code == 200
    assert 'hx-swap-oob="true"' in response.text
    assert "No se pudo ejecutar la simulación" in response.text


def test_panel_includes_loading_skeleton(client: TestClient) -> None:
    html = client.get("/").text
    assert 'id="result-skeleton"' in html
    assert "c-skeleton" in html
    assert 'hx-indicator="#result-skeleton"' in html

def test_operations_pagination_fragment(client: TestClient) -> None:
    post_simulation(client)
    response = client.get("/ui/operations?page=1&reason=all")
    assert response.status_code == 200
    html = response.text
    assert "Operaciones" in html or "operaciones" in html
    assert "Página 1 de" in html

    filtered = client.get("/ui/operations?reason=monday_10_14")
    assert filtered.status_code == 200
    assert "Lunes 10–14" in filtered.text


def test_operations_table_is_mobile_friendly(client: TestClient) -> None:
    post_simulation(client)
    html = client.get("/ui/operations?page=1").text
    # Fila expandible accesible (§10.4, §13.7).
    assert "data-row-toggle" in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="row-detail-1"' in html
    # Columnas marcadas para ocultar en móvil.
    assert "col-seq" in html
    assert "col-index" in html
    assert "col-price" in html


def test_charts_use_spanish_date_ticks(client: TestClient) -> None:
    post_simulation(client)
    html = client.get("/").text
    assert "ticktext" in html
    assert "18 oct 2026" in html  # nombres de mes en español desde el servidor


def test_charts_show_empty_state_without_operations(client: TestClient) -> None:
    params = json.dumps(
        {"daily_below_threshold": 0, "daily_amount_eur": "50,00", "weekly_bands": []}
    )
    response = post_simulation(client, strategy_params_json=params)
    assert response.status_code == 200
    assert "Sin operaciones en este periodo" in response.text
    assert 'data-chart-for="chart-g1"' not in response.text
    assert "—" in response.text  # valor ausente, nunca 0,00 € (§6.5)


# --- GET /backtests -----------------------------------------------------------


def test_backtests_history_lists_the_run(client: TestClient) -> None:
    post_simulation(client)

    response = client.get("/backtests")
    assert response.status_code == 200
    assert "Historial de simulaciones" in response.text

    detail_link = response.text.split('href="/backtests/')[1].split('"')[0]
    detail = client.get(f"/backtests/{detail_link}")
    assert detail.status_code == 200
    assert INVESTED in detail.text
    assert "Cargar estos parámetros en el simulador" in detail.text
    assert detail.text.count("data-chart-for") >= 4


def test_backtest_detail_not_found_returns_404_in_spanish(client: TestClient) -> None:
    response = client.get("/backtests/does-not-exist")
    assert response.status_code == 404
    assert "Esta simulación no existe" in response.text


# --- GET /data ----------------------------------------------------------------


def test_data_page_shows_sources_and_attributions(client: TestClient) -> None:
    response = client.get("/data")
    assert response.status_code == 200
    html = response.text
    assert "Datos históricos" in html
    assert "alternative.me" in html
    assert "Bitstamp" in html
    assert "39 días sin dato" in html
    assert "dataset_hash" in html
    assert "bgeometrics" in html
    assert "prices_btceur_bitstamp" in html


def test_data_sync_from_the_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    closed_day = last_closed_utc_day()

    def fake_fng_get_bytes(url: str, *, timeout: int = 30) -> bytes:
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

    def fake_bitstamp_get_bytes(url: str, *, timeout: int = 30) -> bytes:
        params = parse_qs(urlparse(url).query)
        end = datetime.fromtimestamp(int(params["end"][0]), tz=UTC).date()
        start = end - timedelta(days=bitstamp_ohlc.PAGE_DAYS - 1)
        days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
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

    monkeypatch.setattr(bgeometrics_fng, "get_bytes", fake_fng_get_bytes)
    monkeypatch.setattr(bitstamp_ohlc, "get_bytes", fake_bitstamp_get_bytes)

    app = create_app(db_path=tmp_path / "sync-ui.sqlite3", raw_dir=tmp_path / "raw")
    with TestClient(app) as client:
        response = client.post("/ui/data/sync")

    assert response.status_code == 200
    html = response.text
    assert "Actualizar datos" in html
    assert closed_day.isoformat()[:4] in html or "20" in html


# --- Estáticos ----------------------------------------------------------------


def test_default_paths_point_to_the_project_root() -> None:
    from backtesting_cripto.api.app import DEFAULT_DB_PATH, DEFAULT_RAW_DIR

    project_root = Path(__file__).resolve().parents[2]
    expected_db = project_root / "data" / "backtesting.sqlite3"
    expected_raw = project_root / "data" / "raw"
    assert expected_db == DEFAULT_DB_PATH
    assert expected_raw == DEFAULT_RAW_DIR
    assert expected_raw.exists(), "data/raw must exist in the repository"


def test_create_app_without_arguments_finds_the_project_data() -> None:
    """Sin argumentos, la app debe usar la base de datos del proyecto."""
    app = create_app()
    try:
        assert app.state.repo.has_datasets() is True
    finally:
        app.state.repo.close()
        app.state.run_store.close()


def test_static_assets_are_served(client: TestClient) -> None:
    tokens = client.get("/static/css/tokens.css")
    assert tokens.status_code == 200
    assert "--color-brand: #0DC3A4" in tokens.text

    charts = client.get("/static/js/charts.js")
    assert charts.status_code == 200
    assert "initChartsIn" in charts.text

    for asset in (
        "/static/css/base.css",
        "/static/css/layout.css",
        "/static/css/components.css",
        "/static/css/charts.css",
        "/static/js/theme.js",
        "/static/js/app.js",
        "/static/vendor/htmx.min.js",
        "/static/vendor/plotly-basic.min.js",
    ):
        assert client.get(asset).status_code == 200, asset
