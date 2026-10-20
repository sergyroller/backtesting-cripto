# Notas de arquitectura y seguimiento de fases

Este documento recoge las revisiones del arquitecto tras cada fase y los **apuntes obligatorios** que el agente implementador debe cumplir en la siguiente fase.

---

## Estado de fases

| Fase | Estado | Resumen de revisión |
|---|---|---|
| **F0 — Esqueleto y herramientas** | ✅ Aprobada | `pyproject.toml` (uv + setuptools), 11 paquetes en `src/backtesting_cripto/`, `ruff`, `mypy --strict` y `pytest` en verde. |
| **F1 — Modelos de dominio y contratos** | ✅ Aprobada | Modelos Pydantic v2, `quantize_btc`/`quantize_eur`, `canonical_hash` y `StrategyContext` verificados. |
| **F2 — Ingesta y almacenamiento** | ✅ Aprobada | `raw_store` con SHA-256, proveedores (`bgeometrics`, `alternative.me`, `bitstamp`), `dataset_checks`, `repository` SQLite y `data/raw/` congelado en git. |
| **F3 — Motor, cartera y métricas** | ✅ Aprobada | `calendar`, `execution`, `portfolio`, `runner`, `calculator` y `consistency_checks` verificados con 104 tests (incluyendo `hypothesis`). |
| **F4 — Estrategia Fear & Greed** | ⏳ Pendiente (siguiente) | Ver checklist obligatorio de F4 abajo (incluye test de regresión sobre `[2018-02-01, 2026-10-18]`). |
| **F5 — Persistencia de runs y API REST** | ⏳ Pendiente | — |
| **F6 — Interfaz web** | ⏳ Pendiente | Seguir `docs/design/DESIGN_SYSTEM.md`, `docs/design/tokens.css` y `docs/design/plotly-theme.js` (ya validados: 3 vistas `/`, `/backtests`, `/data`). |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Apuntes obligatorios tras la revisión de F3

### 1. Checklist obligatorio para la Fase F4 (Estrategia Fear & Greed, registros y test de regresión)

Implementar exactamente según las **Secciones B.3, E.4, G.1 y G.2** de `docs/planificacion.md`:

1. **`src/backtesting_cripto/strategies/base.py`**:
   - Definir `StrategyRegistry` (y una instancia por defecto o funciones de módulo `register_strategy`, `get_strategy`, `list_strategies`) que permita:
     - Registrar estrategias que cumplan el protocolo `Strategy` de `domain.contracts`, junto con su `params_schema: type[BaseModel]` (por ejemplo mediante un atributo `params_schema` en la estrategia o un descriptor `StrategyMetadata(strategy_id, name, description, required_indicators, params_schema)`).
     - Obtener una estrategia por `strategy_id` (lanzando `ConfigurationError` si no existe).
     - Listar las estrategias registradas y validar sus parámetros con `params_schema.model_validate(raw_params)`.

2. **`src/backtesting_cripto/strategies/fear_greed.py`**:
   - Implementar `FearGreedStrategy` siguiendo exactamente la **Sección E.4** de `docs/planificacion.md`:
     - `strategy_id = "fear_greed"`
     - `name = "Acumulación por Crypto Fear & Greed Index"`
     - `required_indicators = ("fear_greed",)`
     - `params_schema = FearGreedParams`
     - En `generate_intents(self, ctx: StrategyContext) -> Iterator[OrderIntent]`:
       - Validar `params = FearGreedParams.model_validate(ctx.params)` (si `ValidationError`, relanzar como `ConfigurationError` o dejar que fluya de forma coherente; documentarlo y cubrirlo con test).
       - Obtener `fng = ctx.indicators.get("fear_greed")` (si es `None`, lanzar `InsufficientDataError`).
       - Recorrer cada día con `iter_days(ctx.start_date, ctx.end_date)`:
         - `val = fng.value_on(day)`
         - Si `val is None`: no emitir orden (`continue`, política explícita para los 39 días sin dato).
         - **Regla 1 (diaria, prevalece siempre incluso en lunes):** si `val < params.daily_below_threshold`, emitir:
           ```python
           OrderIntent(
               decision_day=day,
               asset=ctx.asset,
               amount_eur=params.daily_amount_eur,
               reason=f"daily_<{params.daily_below_threshold}",
               index_value=val,
           )
           ```
           y hacer `continue` (nunca evaluar además los tramos semanales ese lunes).
         - **Regla 2 (semanal, solo lunes `is_monday(day)`):** recorrer `params.weekly_bands` (ordenados por `min_value`) y, si `band.min_value <= val <= band.max_value`, emitir:
           ```python
           OrderIntent(
               decision_day=day,
               asset=ctx.asset,
               amount_eur=band.amount_eur,
               reason=f"monday_{band.min_value}_{band.max_value}",
               index_value=val,
           )
           ```
           y hacer `break`.
         - **Regla 3:** si no entra en ningún tramo (p. ej. `val >= 25`), no emitir orden.
   - Registrar `FearGreedStrategy` por defecto en el registro de estrategias.

3. **`src/backtesting_cripto/indicators/registry.py`**:
   - Implementar un cargador/registro limpio (`IndicatorRegistry` o helper `load_required_indicators(repo: BacktestRepository, required_indicators: Sequence[str]) -> dict[str, IndicatorSeries]`) para que el motor y el futuro `backtest_service` (F5) obtengan las series requeridas por cualquier estrategia sin acoplarse a nombres fijos.

4. **Tests unitarios en `tests/unit/test_fear_greed_strategy.py`** (todos los casos de la **Sección G.1**):
   - Bordes de los tramos por defecto en lunes para los valores `9`, `10`, `14`, `15`, `19`, `20`, `24`, `25`:
     - `9` → `50,00 €` con `reason == "daily_<10"`
     - `10` y `14` → `200,00 €` con `reason == "monday_10_14"`
     - `15` y `19` → `150,00 €` con `reason == "monday_15_19"`
     - `20` y `24` → `100,00 €` con `reason == "monday_20_24"`
     - `25` → ninguna orden emitida.
   - Prevalencia de la regla diaria en lunes: un lunes con índice `8` emite **una única compra de `50,00 €`** (`daily_<10`), nunca una semanal.
   - Día entre martes y domingo con índice `12`: ninguna compra.
   - Día entre martes y domingo con índice `7`: compra diaria de `50,00 €` (`daily_<10`).
   - Lunes sin dato de índice (`None`, hueco): ninguna compra.
   - Personalización de tramos e importes desde `FearGreedParams` (p. ej. cambiar `[20..24]` a `[20..30]` con `120,00 €` compra `120,00 €` un lunes con valor `28`).
   - Registro y consulta en `StrategyRegistry` (y error `ConfigurationError` al pedir un `strategy_id` desconocido).

5. **Test de integración y regresión sobre el dataset congelado en `tests/integration/test_fear_greed_regression.py`** (**Sección G.2**):
   - Cargando las series reales desde `data/raw/` (100 % offline, reutilizando los helpers o `RawStore` para no depender de que exista `data/backtesting.sqlite3` en un clon limpio), ejecutar `run_backtest` con `FearGreedStrategy` y los parámetros por defecto en la ventana cerrada `start_date = date(2018, 2, 1)`, `end_date = date(2026, 10, 18)`, `execution_mode = "close_same_day"`.
   - Verificar exactamente las invariantes de regresión del proyecto:
     - `result.metrics.total_operations == 121`
     - `result.metrics.operations_by_reason == {"daily_<10": 42, "monday_10_14": 23, "monday_15_19": 20, "monday_20_24": 36}`
     - `result.metrics.total_invested_eur == Decimal("13300.00")`
     - `result.metrics.btc_accumulated == Decimal("1.10037310")`
     - `result.metrics.average_buy_price_eur == Decimal("12086.81")`
     - `result.metrics.final_price_eur == Decimal("73067.27")`
     - `result.metrics.final_portfolio_value_eur == Decimal("80401.26")`
     - `result.metrics.pnl_eur == Decimal("67101.26")`
     - `result.metrics.roi_pct == Decimal("504.52")`
     - `result.incidents == []`
   - Verificar también el modo `close_next_day` sobre la misma ventana y comprobar que dos ejecuciones producen idéntico `result_hash`.
