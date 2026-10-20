# Notas de arquitectura y seguimiento de fases

Este documento recoge las revisiones del arquitecto tras cada fase y los **apuntes obligatorios** que el agente implementador debe cumplir en la siguiente fase.

---

## Estado de fases

| Fase | Estado | Resumen de revisión |
|---|---|---|
| **F0 — Esqueleto y herramientas** | ✅ Aprobada | `pyproject.toml` (uv + setuptools), 11 paquetes en `src/backtesting_cripto/`, `ruff`, `mypy --strict` y `pytest` en verde. |
| **F1 — Modelos de dominio y contratos** | ✅ Aprobada | Modelos Pydantic v2, `quantize_btc`/`quantize_eur`, `canonical_hash` y `StrategyContext` verificados. |
| **F2 — Ingesta y almacenamiento** | ✅ Aprobada | `raw_store` con SHA-256, proveedores (`bgeometrics`, `alternative.me`, `bitstamp`), `dataset_checks`, `repository` SQLite y `data/raw/` congelado en git. |
| **F3 — Motor, cartera y métricas** | ✅ Aprobada | `calendar`, `execution`, `portfolio`, `runner`, `calculator` y `consistency_checks` verificados. |
| **F4 — Estrategia Fear & Greed** | ✅ Aprobada | `StrategyRegistry`, `FearGreedStrategy`, `indicators/registry.py` y test de regresión offline `[2018-02-01, 2026-10-18]` en verde (`131 passed`). |
| **F5 — Persistencia de runs y API REST** | ⏳ Pendiente (siguiente) | Ver checklist obligatorio de F5 abajo. |
| **F6 — Interfaz web** | ⏳ Pendiente | Seguir `docs/design/DESIGN_SYSTEM.md`, `docs/design/tokens.css` y `docs/design/plotly-theme.js` (ya validados: 3 vistas `/`, `/backtests`, `/data`). |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Apuntes obligatorios tras la revisión de F4

### 1. Checklist obligatorio para la Fase F5 (Persistencia de ejecuciones, servicios y API REST)

Implementar exactamente según las **Secciones D.3, E.1, F.2 y H (F5)** de `docs/planificacion.md`:

1. **Dependencias en `pyproject.toml` (`uv lock` / `uv sync`)**:
   - Añadir a `dependencies`: `"fastapi>=0.115"`, `"uvicorn>=0.30"`.
   - Añadir a `dependency-groups.dev`: `"httpx>=0.27"` (requerido por `fastapi.testclient.TestClient`).

2. **`src/backtesting_cripto/storage/run_store.py`** (esquema SQLite exacto de la **Sección D.3**):
   - Crear las tablas `backtest_runs` y `trades` si no existen:
     ```sql
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
     );

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
     );
     ```
   - Clase `RunStore(db_path: Path | str)` (o integrada con la misma base de datos SQLite que `BacktestRepository`):
     - `save_run(result: BacktestResult) -> None`: guarda en una transacción la fila de `backtest_runs` y todas las filas de `trades` (`seq` de `1` a `len(result.fills)`, `Decimal` como `TEXT`).
     - `get_run(run_id: str, prices: PriceSeries | None = None) -> BacktestResult | None`:
       - Reconstruye `BacktestConfig`, `Metrics`, ` list[Fill]` (leyendo de `trades` ordenado por `seq`) y, si se pasa `prices` (o cargándolo del repositorio), reconstruye `equity_curve` con `build_equity_curve(fills, prices, cfg.start_date, cfg.end_date)` para devolver el `BacktestResult` completo.
     - `list_runs(limit: int = 100) -> list[RunSummary]` (ordenadas por `created_at DESC`): devuelve un modelo/dataclass `RunSummary` con `run_id`, `created_at`, `code_version`, `dataset_hash`, `config`, `config_hash`, `metrics`, `result_hash`.

3. **`src/backtesting_cripto/services/data_service.py`**:
   - Clase/funciones de servicio que encapsulan la gestión de datos locales y la sincronización:
     - **Auto-hidratación inicial desde `data/raw/` (`ensure_populated`):** si la base de datos SQLite (`data/backtesting.sqlite3`) aún no tiene los datasets cargados pero `data/raw/MANIFEST.json` sí existe en disco, consolida automáticamente los archivos crudos de `data/raw/` en SQLite **sin acceder a la red**. Así un clon fresco del repositorio tiene datos listos nada más arrancar.
     - `get_data_status() -> DataStatus`: devuelve el estado de los datasets almacenados en SQLite (`datasets` con `id`, `source`, `first_day`, `last_day`, `record_count`, `retrieved_at`, `sha256`, `license`), el `dataset_hash` del `RawStore`, el `last_closed_utc_day` actual (`today_utc - 1`) y el rango disponible por estrategia (`available_start`, `available_end`).
     - `sync_data(now: datetime | None = None) -> DataStatus`: ejecuta la sincronización contra los proveedores (reutilizando o centralizando la lógica de `scripts/sync_data.py` para no duplicar código entre el script CLI y el servicio), filtrando hasta `last_closed_utc_day(now)` y actualizando `RawStore` y `BacktestRepository`.

4. **`src/backtesting_cripto/services/backtest_service.py`**:
   - Clase `BacktestService(repo: BacktestRepository, run_store: RunStore, raw_store: RawStore, registry: StrategyRegistry = default_registry)`:
     - `execute_backtest(config: BacktestConfig) -> BacktestResult`:
       1. Obtiene la estrategia del registro (`registry.get(config.strategy_id)`) y valida `config.strategy_params` con `registry.validate_params(...)` (si falla `ValidationError`, lanza `ConfigurationError`).
       2. Carga `prices = repo.price_series(asset=config.asset, quote=config.quote)` e `indicators = load_required_indicators(repo, strategy.required_indicators)` (convirtiendo `LookupError` en `InsufficientDataError`).
       3. Calcula `bounds = available_date_bounds(prices, indicators, strategy.required_indicators)` y valida la ventana solicitada con `validate_window(config.start_date, config.end_date, bounds)`.
       4. Ejecuta `result = run_backtest(config, prices, indicators, strategy, dataset_hash=raw_store.dataset_hash())`.
       5. Persiste el resultado con `run_store.save_run(result)` y lo devuelve.
     - `get_backtest(run_id: str) -> BacktestResult | None`: recupera el `BacktestResult` completo reconstruyendo su `equity_curve` con los precios locales.
     - `list_backtests(limit: int = 100) -> list[RunSummary]`: lista las ejecuciones guardadas.
     - `list_available_strategies() -> list[dict[str, Any]]`: devuelve metadatos de cada estrategia registrada (`strategy_id`, `name`, `description`, `required_indicators`, `default_params`, `available_start`, `available_end`).

5. **`src/backtesting_cripto/api/app.py` y `src/backtesting_cripto/api/routes.py`**:
   - `create_app(db_path: Path | None = None, raw_dir: Path | None = None) -> FastAPI`: factoría limpia e inyectable para tests.
   - Endpoints REST en `routes.py` (**Sección H, F5**):
     - `GET /api/strategies`: lista estrategias registradas con sus parámetros por defecto y su rango de fechas disponible `[available_start, available_end]`.
     - `GET /api/data/status`: devuelve el estado de los datasets locales, `dataset_hash`, `last_closed_utc_day` y rangos disponibles.
     - `POST /api/data/sync`: lanza la sincronización de datos y devuelve el nuevo `DataStatus`.
     - `POST /api/backtests`: recibe un payload de configuración (`BacktestConfig` o con `strategy_params` opcional usando los defaults de la estrategia), ejecuta el backtest, lo persiste en SQLite y devuelve el `BacktestResult` (código `201 Created` o `200 OK`).
     - `GET /api/backtests`: devuelve la lista de resúmenes de ejecuciones guardadas (`list[RunSummary]`).
     - `GET /api/backtests/{run_id}`: devuelve el `BacktestResult` completo (o `404` si no existe).
   - Mapeo limpio de excepciones de dominio a códigos HTTP:
     - `ConfigurationError` → `422 Unprocessable Entity` (o `400 Bad Request`) con detalle claro.
     - `InsufficientDataError` / `DataValidationError` → `400` / `409` con detalle claro.

6. **Tests en `tests/unit/test_run_store.py` y `tests/integration/test_api_and_services.py`**:
   - Verificar `RunStore`: guardar y recuperar un `BacktestResult` conserva al 100 % los `Fill` (incluyendo `index_value` y precisión `Decimal`), las métricas, los hashes y la `equity_curve`.
   - Verificar la auto-hidratación desde `data/raw/` hacia un SQLite temporal vacío en `tmp_path` (0 llamadas de red).
   - Verificar todos los endpoints con `fastapi.testclient.TestClient`:
     - `GET /api/strategies` devuelve `"fear_greed"` con `available_start == "2018-02-01"`.
     - `GET /api/data/status` devuelve los datasets y `dataset_hash`.
     - `POST /api/backtests` en `[2018-02-01, 2026-10-18]` devuelve `total_operations == 121`, `total_invested_eur == "13300.00"`, `btc_accumulated == "1.10037310"`, y persiste el run.
     - `GET /api/backtests` incluye el `run_id` recién creado y `GET /api/backtests/{run_id}` devuelve el resultado completo con el mismo `result_hash`.
     - `GET /api/backtests/nonexistent` devuelve `404`.
     - `POST /api/backtests` con tramos solapados o fechas fuera del rango disponible devuelve error `400`/`422`.
     - `POST /api/data/sync` (mockeando la descarga HTTP para no depender de internet en los tests) actualiza y devuelve el estado.
