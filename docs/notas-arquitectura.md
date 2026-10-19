# Notas de arquitectura y seguimiento de fases

Este documento recoge las revisiones del arquitecto tras cada fase y los **apuntes obligatorios** que el agente implementador debe cumplir en la siguiente fase.

---

## Estado de fases

| Fase | Estado | Resumen de revisión |
|---|---|---|
| **F0 — Esqueleto y herramientas** | ✅ Aprobada | `pyproject.toml` (uv + setuptools), 11 paquetes en `src/backtesting_cripto/`, `ruff`, `mypy --strict` y `pytest` en verde. |
| **F1 — Modelos de dominio y contratos** | ✅ Aprobada | Modelos Pydantic v2, `quantize_btc`/`quantize_eur`, `canonical_hash` y `StrategyContext` verificados con 37 tests unitarios. |
| **F2 — Ingesta y almacenamiento** | ✅ Aprobada | `raw_store` con SHA-256, proveedores (`bgeometrics`, `alternative.me`, `bitstamp`), `dataset_checks`, `repository` SQLite y `data/raw/` congelado en git (73 tests en verde). |
| **F3 — Motor, cartera y métricas** | ⏳ Pendiente (siguiente) | Ver checklist obligatorio de F3 abajo. |
| **F4 — Estrategia Fear & Greed** | ⏳ Pendiente | En el test de regresión `[2018-02-01, 2026-10-18]`: `121` compras, `13 300,00 €` invertidos, `1,10037310 BTC`, coste medio `12 086,81 €/BTC`, valor final `80 401,26 €`, P&L `+67 101,26 €` (`+504,52 %`). |
| **F5 — Persistencia de runs y API REST** | ⏳ Pendiente | — |
| **F6 — Interfaz web** | ⏳ Pendiente | Seguir `docs/design/DESIGN_SYSTEM.md`, `docs/design/tokens.css` y `docs/design/plotly-theme.js` (ya validados: 3 vistas `/`, `/backtests`, `/data`). |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Apuntes obligatorios tras la revisión de F2

### 1. Checklist obligatorio para la Fase F3 (Motor, cartera y métricas)

Implementar exactamente según las **Secciones E.1, E.2, E.3, E.5 y G.1** de `docs/planificacion.md`:

1. **`src/backtesting_cripto/engine/calendar.py`**:
   - `iter_days(start_date: date, end_date: date) -> Iterator[date]`: iterador diario inclusivo `[start_date, end_date]` (lanza `ConfigurationError` si `start_date > end_date`).
   - `is_monday(day: date) -> bool`: devuelve `day.weekday() == 0`.
   - `available_date_bounds(prices: PriceSeries, indicators: Mapping[str, IndicatorSeries], required_indicators: Sequence[str]) -> tuple[date, date]`:
     - Calcula el rango disponible para una estrategia según la Sección E.1:
       - `min_available_date = max([prices.date_bounds()[0], *(indicators[i].date_bounds()[0] for i in required_indicators)])`
       - `max_available_date = min([prices.date_bounds()[1], *(indicators[i].date_bounds()[1] for i in required_indicators)])`
     - Si falta algún indicador requerido en `indicators` o si `min_available_date > max_available_date`, lanza `InsufficientDataError`.
   - `validate_window(start_date: date, end_date: date, available_bounds: tuple[date, date]) -> None`:
     - Lanza `ConfigurationError` si `start_date > end_date` o si `[start_date, end_date]` se sale de `[min_available_date, max_available_date]`.

2. **`src/backtesting_cripto/engine/execution.py`**:
   - Implementar el protocolo `ExecutionModel` (Sección E.3):
     - `CloseExecutionModel(mode: Literal["close_same_day", "close_next_day"] = "close_same_day")`:
       - En `"close_same_day"`: `exec_day = intent.decision_day`.
       - En `"close_next_day"`: `exec_day = intent.decision_day + timedelta(days=1)`.
       - Busca la vela estricta del día con `bar = prices.bar_on(exec_day)` (nunca usa `last_close_on_or_before` para ejecutar una compra; si `bar is None`, devuelve `None`).
       - Cuantiza según contrato:
         - `amount_eur = quantize_eur(intent.amount_eur)`
         - `price_eur = quantize_eur(bar.close)`
         - `btc_quantity = quantize_btc(amount_eur / price_eur)`
       - Devuelve `Fill(execution_day=exec_day, decision_day=intent.decision_day, asset=intent.asset, index_value=intent.index_value, amount_eur=amount_eur, price_eur=price_eur, btc_quantity=btc_quantity, reason=intent.reason)`.

3. **`src/backtesting_cripto/engine/portfolio.py`**:
   - Clase `Portfolio` que acumula los `Fill` ejecutados:
     - `apply(fill: Fill) -> None`: registra el `Fill` y actualiza `total_invested_eur` (`Decimal("0.00")` inicial) y `btc_accumulated` (`Decimal("0.00000000")` inicial).
     - Propiedades/métodos para consultar `fills: list[Fill]`, `total_invested_eur: Decimal`, `btc_accumulated: Decimal` y el estado acumulado en o antes de cada fecha para construir la curva diaria.

4. **`src/backtesting_cripto/metrics/calculator.py`**:
   - `build_equity_curve(fills: Sequence[Fill], prices: PriceSeries, start_date: date, end_date: date) -> list[EquityPoint]`:
     - Recorre cada día $t \in [\text{start\_date}, \text{end\_date}]$:
       - Acumula las compras con `fill.execution_day <= t` (`invested_eur` y `btc_accumulated`).
       - Obtiene el precio de valoración: $P_t = \text{bar.close}$ si `prices.bar_on(t)` existe; en caso contrario usa `prices.last_close_on_or_before(t)` (y si tampoco existiera ningún precio previo, lanza `InsufficientDataError`).
       - `close_price_eur = quantize_eur(P_t)`.
       - `portfolio_value_eur = quantize_eur(btc_accumulated * close_price_eur)`.
       - Actualiza `peak = max(peak, portfolio_value_eur)`.
       - Si `peak > 0`: `drawdown_pct = quantize_eur(((portfolio_value_eur / peak) - Decimal("1")) * Decimal("100"))`; si `peak == 0`: `drawdown_pct = Decimal("0.00")`.
   - `calculate_metrics(fills: Sequence[Fill], equity_curve: Sequence[EquityPoint], prices: PriceSeries, end_date: date) -> Metrics`:
     - Calcula todas las métricas exactas de la **Sección E.5**:
       - `total_invested_eur`, `total_operations`, `operations_by_reason` (conteo por `fill.reason`), `btc_accumulated`.
       - `average_buy_price_eur`: `quantize_eur(total_invested_eur / btc_accumulated)` si `btc_accumulated > 0`, o `None` si `total_operations == 0`.
       - `final_price_eur`: `quantize_eur(end_bar.close)` usando `prices.last_close_on_or_before(end_date)`.
       - `final_portfolio_value_eur`: `quantize_eur(btc_accumulated * final_price_eur)`.
       - `pnl_eur`: `final_portfolio_value_eur - total_invested_eur`.
       - `roi_pct`: `quantize_eur((pnl_eur / total_invested_eur) * Decimal("100"))` si `total_invested_eur > 0`, o `None` si `total_operations == 0`.
       - `max_drawdown_pct`: `min((pt.drawdown_pct for pt in equity_curve), default=Decimal("0.00"))`.

5. **`src/backtesting_cripto/validation/consistency_checks.py`**:
   - Función `verify_backtest_result(result: BacktestResult) -> None` que comprueba las invariantes financieras post-simulación (lanza `DataValidationError` si alguna falla):
     - `metrics.total_operations == len(result.fills)`.
     - `metrics.total_invested_eur == sum(f.amount_eur for f in result.fills)`.
     - `metrics.btc_accumulated == sum(f.btc_quantity for f in result.fills)`.
     - `sum(metrics.operations_by_reason.values()) == len(result.fills)`.
     - `metrics.max_drawdown_pct <= Decimal("0.00")`.

6. **`src/backtesting_cripto/engine/runner.py`**:
   - Función `run_backtest(cfg: BacktestConfig, prices: PriceSeries, indicators: Mapping[str, IndicatorSeries], strategy: Strategy, *, execution_model: ExecutionModel | None = None, dataset_hash: str = "", run_id: str | None = None, created_at: datetime | None = None) -> BacktestResult`:
     - Construye `ctx = StrategyContext(asset=cfg.asset, start_date=cfg.start_date, end_date=cfg.end_date, params=cfg.strategy_params, indicators=indicators, prices=prices)`.
     - Si `execution_model is None`, instancia `CloseExecutionModel(cfg.execution_mode)`.
     - Procesa cada `intent` de `strategy.generate_intents(ctx)` dentro de `[cfg.start_date, cfg.end_date]`:
       - Si `execution_model.execute(intent, prices)` devuelve `None`:
         - **Importante en modo `close_next_day`:** si `intent.decision_day == cfg.end_date`, su `exec_day` es `cfg.end_date + 1` (fuera de la ventana de simulación), por lo que **debe omitirse limpiamente sin registrar incidente** (según Sección E.2: *"Caso `close_next_day` en el último día del rango seleccionado: `continue`"*).
         - En cualquier otro caso en que falte el precio en la fecha de ejecución dentro del rango, añade `f"missing_price_on_{exec_day.isoformat()}"` a `incidents`.
       - Si `fill.execution_day > cfg.end_date`, lo omite sin aplicar al portfolio ni registrar incidente.
     - Construye `equity_curve`, calcula `metrics`, calcula `config_hash = canonical_hash(cfg)` y `result_hash = canonical_hash({"config_hash": config_hash, "dataset_hash": dataset_hash, "fills": ..., "metrics": ..., "incidents": ...})` (excluyendo `run_id` y `created_at` del `result_hash` para que dos ejecuciones con la misma configuración y datos produzcan **exactamente el mismo `result_hash`**, tal como exige el test de reproducibilidad de la Sección G.2).
     - Ejecuta `verify_backtest_result(result)` antes de devolverlo.

7. **Tests unitarios y basados en propiedades en `tests/unit/test_engine_and_metrics.py`**:
   - Cubrir todos los casos del plan (§G.1) correspondientes al motor y métricas:
     - Redondeo exacto a satoshi en `CloseExecutionModel`: `100,00 €` a precio `73 067,27 €` → `0,00136860 BTC`.
     - Modo `close_same_day` vs `close_next_day` (incluyendo orden en el último día del rango en `close_next_day` que se omite sin incidente).
     - Cálculo de métricas con compras conocidas: `100 € @ 10 000 €` (`0,01000000 BTC`) + `100 € @ 20 000 €` (`0,00500000 BTC`), precio final `30 000 €` → Invertido `200,00 €`, BTC `0,01500000`, Coste medio `13 333,33 €`, Valor final `450,00 €`, P&L `+250,00 €`, ROI `+125,00 %`.
     - Drawdown sintético: `1 BTC` constante, cierres `[100, 120, 60, 90, 150]` → `max_drawdown_pct == Decimal("-50.00")`.
     - Día intermedio sin vela de precio en `build_equity_curve`: usa `last_close_on_or_before` y la cartera no cae a `0 €`.
     - Simulación con 0 compras: `total_operations == 0`, `total_invested_eur == Decimal("0.00")`, `average_buy_price_eur is None`, `roi_pct is None`, `max_drawdown_pct == Decimal("0.00")`.
     - Reproducibilidad de `result_hash`: dos llamadas a `run_backtest` con distinto `run_id`/`created_at` pero misma configuración y datos producen idéntico `result_hash`.
     - Test property-based con `hypothesis`: para cualquier lista de compras e importes/precios positivos, `btc_accumulated == sum(f.btc_quantity)`, `portfolio_value_eur >= 0` y `max_drawdown_pct <= 0`.
