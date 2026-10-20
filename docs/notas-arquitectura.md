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
| **F4 — Estrategia Fear & Greed** | ✅ Aprobada | `StrategyRegistry`, `FearGreedStrategy`, `indicators/registry.py` y test de regresión offline `[2018-02-01, 2026-10-18]` en verde. |
| **F5 — Persistencia de runs y API REST** | 🔧 Pendiente saneamiento (4 puntos) | Funcionalidad completa y 151 tests pasando hoy, pero se detectaron **4 fallos técnicos** (incluida una bomba de tiempo en `_consolidate_from_raw` que fallaría mañana). Ver sección abajo. |
| **F6 — Interfaz web** | ⏳ Pendiente (tras sanear F5) | Seguir `docs/design/DESIGN_SYSTEM.md`, `docs/design/tokens.css` y `docs/design/plotly-theme.js` (ya validados: 3 vistas `/`, `/backtests`, `/data`). |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Correcciones obligatorias de la Fase F5 (aplicar y verificar antes de empezar F6)

En la auditoría experta de F5 se han detectado **4 problemas técnicos** que debes corregir y cubrir con tests:

### 1. Bomba de tiempo en `DataService._consolidate_from_raw` (`src/backtesting_cripto/services/data_service.py`)
- **El bug:** El fichero crudo de BGeometrics (`data/raw/bgeometrics/fear_greed_bgeometrics_81b1300bee9697ff.json`) contiene registros hasta el `2026-10-20` (día en curso en el momento de la descarga), mientras que Bitstamp solo contiene velas cerradas hasta el `2026-10-19`.
  En `_consolidate_from_raw()` (líneas 199–212):
  ```python
  closed_day = last_closed_utc_day()
  fng_values = [value for value in self._load_raw_fear_greed() if value.day <= closed_day]
  bars = [bar for bar in self._load_raw_prices() if bar.day <= closed_day]
  ...
  available_last = min(fng_values[-1].day, bars[-1].day)
  validate_fear_greed_series(fng_values, last_closed_day=available_last)
  ```
  Hoy (`2026-10-20`), `closed_day` es `2026-10-19` y filtra el `2026-10-20` de `fng_values`. **Pero a partir de mañana (`2026-10-21`) o en cualquier clon offline futuro**, `closed_day` será `>= 2026-10-20`, por lo que `fng_values[-1].day` será `2026-10-20`, `bars[-1].day` será `2026-10-19`, `available_last` será `2026-10-19`, y `validate_fear_greed_series(fng_values, last_closed_day=available_last)` **lanzará `DataValidationError: fear_greed: 2026-10-20 is after the last closed day 2026-10-19`**.
- **Corrección obligatoria:**
  1. Permitir pasar `now: datetime | None = None` a `ensure_populated(self, now: datetime | None = None) -> bool` y `_consolidate_from_raw(self, now: datetime | None = None) -> None`.
  2. En `_consolidate_from_raw`, después de calcular `available_last = min(closed_day, fng_values[-1].day, bars[-1].day)`, **recortar ambas listas a `<= available_last` antes de validar e insertar en SQLite**:
     ```python
     fng_values = [value for value in fng_values if value.day <= available_last]
     bars = [bar for bar in bars if bar.day <= available_last]
     validate_fear_greed_series(fng_values, last_closed_day=available_last)
     validate_price_bars(bars, last_closed_day=available_last)
     ```
  3. Añadir un test en `tests/integration/test_api_and_services.py` (`test_ensure_populated_works_when_clock_is_in_the_future`) llamando a `service.ensure_populated(now=datetime(2027, 6, 1, tzinfo=UTC))` sobre `REAL_RAW_DIR` y comprobando que hidrata limpiamente hasta `2026-10-19` sin lanzar `DataValidationError`.

### 2. Orden determinista en `_load_raw_prices` y limpieza de archivos duplicados en `data/raw/`
- **El bug:**
  1. En `data/raw/MANIFEST.json` quedaron duplicados los 5 archivos del `2026-10-19` junto con los 5 archivos nuevos del `2026-10-20` (10 archivos en total en git).
  2. Además, en `DataService._load_raw_prices()` (y en los helpers `load_frozen_price_bars` / `load_frozen_series` de `tests/`), se itera `sorted(manifest, key=lambda item: item.relative_path)` usando `bars_by_day.setdefault(bar.day, bar)`, lo cual elige qué vela gana según el orden alfabético del hash SHA-256 en lugar de usar la descarga más reciente (`retrieved_at`).
- **Corrección obligatoria:**
  1. En `DataService._load_raw_prices()` (y en `tests/data/test_frozen_dataset.py` y `tests/integration/test_fear_greed_regression.py`), ordenar las entradas del manifiesto por `(entry.retrieved_at, entry.relative_path)` y asignar `bars_by_day[bar.day] = bar` (para que prevalezca siempre la entrada más reciente).
  2. Eliminar de `data/raw/` los 5 archivos antiguos del `2026-10-19` (`fear_greed_bgeometrics_671b9a1ec59f69f4.json` y las 4 páginas `4ece8b1c3fcdd17c`, `791a42920f9b35bb`, `dbb4826db0264d26`, `941f318fd6683ed7`) y dejar en `data/raw/MANIFEST.json` únicamente las 5 entradas vigentes del `2026-10-20` (que cubren todo el histórico hasta el `2026-10-19`).

### 3. Ciclo de vida de conexiones SQLite en `api/app.py` y reutilización de `self._repo` en `BacktestService.get_backtest`
- **El bug:**
  1. `create_app` en `src/backtesting_cripto/api/app.py` abre `repo = BacktestRepository(...)` y `run_store = RunStore(...)`, pero nunca los cierra al apagar la aplicación (falta un `lifespan` con `@asynccontextmanager` en FastAPI que haga `repo.close()` y `run_store.close()` al finalizar).
  2. `BacktestService.get_backtest(run_id)` llama a `self._run_store.get_run(run_id)` sin pasar `prices`, haciendo que `RunStore.get_run` abra y cierre una conexión `BacktestRepository(self._db_path)` nueva en cada petición `GET /api/backtests/{run_id}` pese a que `BacktestService` ya tiene `self._repo`.
- **Corrección obligatoria:**
  1. En `api/app.py`, añadir un `lifespan` en `FastAPI(..., lifespan=lifespan)` que cierre `repo.close()` y `run_store.close()` al salir del contexto de la aplicación.
  2. En `BacktestService.get_backtest(run_id)`, cargar los precios con `self._repo` (o pasar `self._repo` / `prices` a `self._run_store.get_run`) para no abrir conexiones SQLite extra innecesarias.

### 4. Silenciar el `StarletteDeprecationWarning` de `starlette.testclient` en `pyproject.toml`
- Añadir en `[tool.pytest.ini_options]` de `pyproject.toml`:
  ```toml
  filterwarnings = [
      "ignore:Using `httpx` with `starlette.testclient` is deprecated:DeprecationWarning",
  ]
  ```
  para que `uv run pytest` termine con **0 warnings**.
