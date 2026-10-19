# Notas de arquitectura y seguimiento de fases

Este documento recoge las revisiones del arquitecto tras cada fase y los **apuntes obligatorios** que el agente implementador debe cumplir en la siguiente fase.

---

## Estado de fases

| Fase | Estado | Resumen de revisión |
|---|---|---|
| **F0 — Esqueleto y herramientas** | ✅ Aprobada | `pyproject.toml` (uv + setuptools), 11 paquetes en `src/backtesting_cripto/`, `ruff`, `mypy --strict` y `pytest` en verde. |
| **F1 — Modelos de dominio y contratos** | ⏳ Pendiente (siguiente) | Ver checklist obligatorio abajo. |
| **F2 — Ingesta y almacenamiento** | ⏳ Pendiente | Ver apunte sobre `.gitignore` y datos congelados. |
| **F3 — Motor, cartera y métricas** | ⏳ Pendiente | — |
| **F4 — Estrategia Fear & Greed** | ⏳ Pendiente | — |
| **F5 — Persistencia de runs y API REST** | ⏳ Pendiente | — |
| **F6 — Interfaz web** | ⏳ Pendiente | — |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Apuntes obligatorios tras la revisión de F0

### 1. Checklist obligatorio para la Fase F1 (`domain/`)

Implementar exactamente según la **Sección D** de `docs/planificacion.md`:

1. **`src/backtesting_cripto/domain/exceptions.py`**:
   - Jerarquía limpia de excepciones de dominio (`DomainError`, `ConfigurationError`, `DataValidationError`, `InsufficientDataError`).
2. **`src/backtesting_cripto/domain/models.py`**:
   - Constantes y funciones auxiliares de redondeo:
     - `BTC_QUANT = Decimal("0.00000001")` con `ROUND_DOWN` (`quantize_btc`).
     - `EUR_QUANT = Decimal("0.01")` con `ROUND_HALF_UP` (`quantize_eur`).
   - Modelos Pydantic v2:
     - `PriceBar` (validando `low > 0`, `low <= open <= high`, `low <= close <= high`, `volume >= 0`).
     - `IndicatorValue` (para `fear_greed`, valor en `[0, 100]`).
     - `WeeklyBandRule` (`min_value <= max_value`, en `[0, 100]`, `amount_eur > 0`).
     - `FearGreedParams` (validando que ningún tramo semanal tenga `min_value < daily_below_threshold` y que los tramos semanales **no se solapen** entre sí).
     - `OrderIntent` (incluyendo `index_value: Decimal | None = None` para trazabilidad).
     - `Fill` (100 % directo sin comisiones: `execution_day`, `decision_day`, `asset`, `index_value`, `amount_eur`, `price_eur`, `btc_quantity`, `reason`).
     - `EquityPoint`, `Metrics`, `BacktestConfig` (validando `start_date <= end_date`), `BacktestResult`.
   - Función de **hash canónico SHA-256** (`canonical_hash(obj) -> str`) sobre JSON ordenado de forma determinista para `config_hash` y `result_hash`.
3. **`src/backtesting_cripto/domain/contracts.py`**:
   - `StrategyContext` y protocolos (`Protocol`): `PriceSeries`, `IndicatorSeries`, `Strategy`, `ExecutionModel`.
4. **Tests unitarios en `tests/unit/test_domain_models.py`**:
   - Casos válidos y casos que deben fallar (`ValidationError`) en `WeeklyBandRule`, `FearGreedParams` (solapamiento de tramos, invasión del umbral diario), `PriceBar` (OHLC incoherente) y `BacktestConfig` (`start_date > end_date`).
   - Redondeo exacto de `quantize_btc` (`ROUND_DOWN` a 8 decimales) y `quantize_eur` (`ROUND_HALF_UP` a 2 decimales).
   - Determinismo de `canonical_hash`.
   - Test arquitectónico que verifique que ningún módulo dentro de `backtesting_cripto.domain` importa librerías de red o base de datos (`sqlite3`, `urllib`, `http`, `fastapi`, etc.).

### 2. Apuntes transversales para F2–F6 (no olvidar)

- **`.gitignore` y datos congelados (para F2):**
  - Actualmente `.gitignore` ignora toda la carpeta `data/`.
  - La base de datos local `data/backtesting.sqlite3` **debe seguir ignorada**, pero los ficheros crudos congelados en `data/raw/` (incluido `MANIFEST.json`) **o** el snapshot fijo para el test de regresión (`2018-02-01` → `2026-10-18`, 121 compras / 13 300,00 €) **deben estar versionados en git** (p. ej. ajustando `.gitignore` a `data/*.sqlite3` y permitiendo `data/raw/`), para que `uv run pytest` pase siempre 100 % offline en cualquier máquina.
- **Paquete `web/` y carpetas vacías:**
  - Añadir `src/backtesting_cripto/web/__init__.py` (actualmente falta ese `__init__.py`) y no dejar carpetas requeridas sin versionar en git cuando toque usarlas.
- **Binario de `uv`:**
  - En este entorno `uv` está instalado en `~/.local/bin/uv`.
