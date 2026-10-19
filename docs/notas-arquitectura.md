# Notas de arquitectura y seguimiento de fases

Este documento recoge las revisiones del arquitecto tras cada fase y los **apuntes obligatorios** que el agente implementador debe cumplir en la siguiente fase.

---

## Estado de fases

| Fase | Estado | Resumen de revisión |
|---|---|---|
| **F0 — Esqueleto y herramientas** | ✅ Aprobada | `pyproject.toml` (uv + setuptools), 11 paquetes en `src/backtesting_cripto/`, `ruff`, `mypy --strict` y `pytest` en verde. |
| **F1 — Modelos de dominio y contratos** | ✅ Aprobada con 1 ajuste en `StrategyContext` | 35 tests unitarios en verde. **Pendiente aplicar el ajuste en `domain/contracts.py` antes/al inicio de F2** (ver abajo). |
| **F2 — Ingesta y almacenamiento** | ⏳ Pendiente (siguiente) | Ver checklist obligatorio de F2 abajo. |
| **F3 — Motor, cartera y métricas** | ⏳ Pendiente | — |
| **F4 — Estrategia Fear & Greed** | ⏳ Pendiente | — |
| **F5 — Persistencia de runs y API REST** | ⏳ Pendiente | — |
| **F6 — Interfaz web** | ⏳ Pendiente | — |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Apuntes obligatorios tras la revisión de F1

### 0. Ajuste obligatorio de F1 antes de seguir (`domain/contracts.py` y `domain/models.py`)

1. **Corregir `StrategyContext` en `src/backtesting_cripto/domain/contracts.py`**:
   - En las Secciones **E.2** y **E.4** de `docs/planificacion.md`, `strategy.generate_intents(ctx)` recibe la ventana y los parámetros de la simulación, no un único `day`.
   - `StrategyContext` debe tener exactamente estos campos:
     ```python
     @dataclass(frozen=True)
     class StrategyContext:
         """Context passed to a strategy to generate order intents over a date window."""

         asset: str
         start_date: date
         end_date: date
         params: Mapping[str, Any]
         indicators: Mapping[str, "IndicatorSeries"]
         prices: "PriceSeries | None" = None
     ```
   - Añadir un test unitario en `tests/unit/test_domain_models.py` que instancie `StrategyContext` con esos campos.
2. **En `IndicatorValue.check_value` (`src/backtesting_cripto/domain/models.py`)**:
   - Aplicar la restricción de entero en `[0, 100]` cuando `self.indicator == "fear_greed"`, de modo que futuros indicadores con decimales o rangos distintos (p. ej. medias móviles, MVRV) puedan usar `IndicatorValue` sin romper los tests actuales de `fear_greed`.

---

### 1. Checklist obligatorio para la Fase F2 (Ingesta, validación y almacenamiento de datos)

Implementar según las **Secciones D.3 y F** de `docs/planificacion.md`:

1. **Ajustar `.gitignore`**:
   - Cambiar `data/` por `data/*.sqlite3` y `data/*.sqlite3-*` para que la base de datos SQLite local sea ignorada por git, pero **los archivos descargados en `data/raw/` (incluido `MANIFEST.json`) sí queden versionados en git** y los tests de regresión funcionen 100 % offline en cualquier máquina.
2. **`src/backtesting_cripto/storage/raw_store.py`**:
   - Guardado inmutable de respuestas crudas en `data/raw/<source>/` con cálculo de `sha256` y actualización de `data/raw/MANIFEST.json` (`id`, `source`, `url`, `retrieved_at`, `sha256`, `first_day`, `last_day`, `record_count`, `license`, `relative_path`).
   - Nunca sobrescribe un fichero raw con distinto contenido; calcula también el `dataset_hash` global a partir del manifiesto.
3. **`src/backtesting_cripto/providers/`**:
   - `bgeometrics_fng.py`: descarga `https://charts.bgeometrics.com/files/fear_greed.json` (`[[timestamp_ms, int_value], ...]`) y lo parsea a `list[IndicatorValue]` con `day` en UTC (`datetime.fromtimestamp(ts_ms / 1000, UTC).date()`).
   - `alternative_me_fng.py`: proveedor de respaldo para `https://api.alternative.me/fng/?limit=0&format=json`.
   - `bitstamp_ohlc.py`: descarga paginada de `https://www.bitstamp.net/api/v2/ohlc/btceur/?step=86400&limit=1000&start=...&end=...` cubriendo desde `2018-01-01` hasta `last_closed_day`, devolviendo `list[PriceBar]` ordenadas y sin duplicados.
   - Usar `urllib.request` (stdlib) con `User-Agent` claro y timeout explícito, sin depender de librerías pesadas si no hace falta.
4. **`src/backtesting_cripto/validation/dataset_checks.py`**:
   - Validación de series antes de consolidar:
     - `fear_greed`: primer día `== 2018-02-01`, sin fechas duplicadas, todos los días `<= last_closed_day`, valores enteros en `[0, 100]`.
     - `price_bars` (BTC/EUR Bitstamp): primer día `<= 2018-01-01`, sin fechas duplicadas, **continuidad diaria sin huecos** desde `2018-01-01` hasta `last_closed_day`, y coherencia OHLC.
   - Si falla cualquier invariante, lanzar `DataValidationError` (de `domain.exceptions`).
5. **`src/backtesting_cripto/storage/repository.py`**:
   - Creación de las tablas SQLite (`datasets`, `price_bars`, `indicator_values`) según el esquema exacto de la **Sección D.3** (`Decimal` guardado como `TEXT`).
   - Implementaciones de los protocolos `PriceSeries` (`bar_on`, `last_close_on_or_before`, `date_bounds`) e `IndicatorSeries` (`value_on`, `date_bounds`) leyendo de SQLite (o cargando la serie en memoria desde SQLite para consultas $O(1)$ durante el backtest).
6. **`scripts/sync_data.py`**:
   - Script ejecutable con `uv run python scripts/sync_data.py` que:
     - Calcula `last_closed_day = datetime.now(UTC).date() - timedelta(days=1)`.
     - Descarga F&G (BGeometrics, con fallback a alternative.me) y BTC/EUR (Bitstamp desde `2018-01-01`), filtra estrictamente `day <= last_closed_day`, guarda en `data/raw/`, valida con `dataset_checks` y pobla `data/backtesting.sqlite3`.
7. **Ejecutar la sincronización real y tests (`tests/unit/` y `tests/data/`)**:
   - Ejecutar `scripts/sync_data.py` para dejar poblado y commiteado `data/raw/` (incluido `MANIFEST.json`).
   - Tests unitarios en `tests/unit/test_storage_and_validation.py` (con SQLite en memoria / `tmp_path`).
   - Tests de integridad sobre los datos reales en `tests/data/test_frozen_dataset.py` verificando que en la ventana cerrada `[2018-02-01, 2026-10-18]` hay exactamente 454 lunes, 42 días con `fear_greed < 10`, y continuidad diaria de precios en Bitstamp desde `2018-01-01` hasta `2026-10-18`.
