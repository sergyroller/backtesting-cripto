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
| **F5 — Persistencia de runs y API REST** | ✅ Aprobada | `RunStore`, `DataService` (hidratación offline blindada a futuro + sync), `BacktestService`, API REST (`/api/*`) con `lifespan` y 154 tests en verde (0 warnings). |
| **F6 — Interfaz web** | 🔧 Pendiente saneamiento (4 puntos) | Las 3 vistas, tokens CSS, HTMX, Plotly, filtros españoles y 196 tests están en marcha, pero se han detectado **4 bugs funcionales de interacción** que deben corregirse antes de aprobar F6. Ver sección abajo. |
| **F7 — Documentación final y pulido** | ⏳ Pendiente (tras sanear F6) | — |

---

## Correcciones obligatorias de la Fase F6 (aplicar y verificar antes de pasar a F7)

En la auditoría de arquitectura de la Fase F6 se han detectado **4 bugs reales de interacción/renderizado** que los tests actuales no cubrían:

### 1. Paginación inicial y pérdida de `run_id` al filtrar/paginar operaciones (`views.py` y `operations_table.html`)
- **El bug (doble):**
  1. En `src/backtesting_cripto/web/views.py` (`result_context`, líneas 229–253), se construye `rows = build_operation_rows(result.fills)` y se pasa `"rows": rows` **sin paginar** (las 121 filas enteras en la primera carga de `/` y `/backtests/{run_id}`), aunque el caption dice `página 1 de 3`.
  2. En `src/backtesting_cripto/web/templates/partials/fragments/operations_table.html` (líneas 58–78), los botones HTMX de filtro y paginación llaman a `/ui/operations?reason=...` y `/ui/operations?page=...&reason=...` **sin pasar `run_id`**. Por tanto, cuando el usuario está viendo el detalle de una simulación concreta en `/backtests/{run_id}` (o un `load_run` en `/`) y filtra o pasa a la página 2, `/ui/operations` recibe `run_id=None` y devuelve las operaciones de `latest_result()` (¡mezclando simulaciones distintas!).
- **Corrección obligatoria:**
  1. En `result_context(result)` (`views.py`), usar `page_rows, total_pages, safe_page = paginate_rows(rows, 1)` y pasar `"rows": page_rows`, `"page": safe_page`, `"total_pages": total_pages`, `"total": len(rows)` y `"run_id": result.run_id`.
  2. En `operations()` (`views.py`, línea 474), incluir `"run_id": result.run_id` en el `context` que renderiza `partials/fragments/operations_table.html`.
  3. En `partials/fragments/operations_table.html`, incluir `run_id={{ run_id }}` en todas las URLs `hx-get="/ui/operations?..."` (tanto en los chips de filtro por regla como en los botones *Anterior* / *Siguiente*).
  4. Añadir un test en `tests/integration/test_web_ui.py` que verifique:
     - Que la carga inicial de una simulación con 121 compras renderiza exactamente 50 filas de operaciones en la página 1 (y no las 121).
     - Que si existen 2 simulaciones distintas guardadas y se pide `/ui/operations?run_id=<primera>&page=2`, devuelve la página 2 de esa `run_id` y mantiene `run_id=<primera>` en los enlaces HTMX.

### 2. Duplicación de listeners en `app.js` tras swaps HTMX (`src/backtesting_cripto/web/static/js/app.js`)
- **El bug:** En `app.js` (líneas 107–161 y 189–198), el listener de `htmx:load` invoca `initTabs()`, `initRowDetails()` e `initToasts()`, las cuales hacen `document.querySelectorAll(...)` sobre todo el documento sin acotar a `root` ni marcar los nodos ya enlazados.
  Cada vez que HTMX reemplaza un fragmento (por ejemplo, al cambiar de página en `#operations-panel` o al recibir un toast OOB), se vuelve a registrar otro `addEventListener("click", ...)` sobre las pestañas y botones existentes; tras un par de swaps, hacer clic en un acordeón o pestaña dispara el handler varias veces seguidas.
- **Corrección obligatoria:**
  - Pasar `root` a `initTabs(root)`, `initRowDetails(root)` e `initToasts(root)` (usando `(root || document).querySelectorAll(...)`) **y** marcar cada elemento inicializado con un atributo `dataset` (p. ej. `if (button.dataset.bound) return; button.dataset.bound = "true";`, igual en `initBands` e `initRangeShortcuts`) para garantizar idempotencia total aunque `htmx:load` se dispare múltiples veces.

### 3. Fusión superficial (`Object.assign`) de `layout.xaxis` y `layout.yaxis` en `charts.js` y `plotly-theme.js`
- **El bug:** En `src/backtesting_cripto/web/static/js/charts.js` (línea 129):
  ```javascript
  var layout = Object.assign({}, baseLayout(isMobile), spec.layout || {});
  ```
  Como `spec.layout` define `xaxis` e `yaxis` (p. ej. títulos de eje, `tickvals`/`ticktext` en español, `range: [-2, 102]`, `autorange: "reversed"`), `Object.assign` superficial **sobreescribe por completo** `baseLayout.xaxis` y `baseLayout.yaxis`, perdiendo `gridcolor`, `showline: false`, `zeroline: false`, `ticks: "outside"` y `tickfont` en la carga inicial.
  Y a la inversa, al cambiar el tema (`bt:theme-changed`, línea 148), `Plotly.relayout(el, baseLayout(isMobile))` **borra** los títulos de ejes, el rango `[-2, 102]` y los `ticktext` en español de `spec.layout`.
- **Corrección obligatoria:**
  1. Añadir en `charts.js` (y sincronizar en `docs/design/plotly-theme.js`) una función `mergeLayout(base, override)` que combine de forma profunda al menos `xaxis`, `yaxis`, `margin`, `font` y `legend`:
     ```javascript
     function mergeLayout(base, override) {
       var over = override || {};
       var merged = Object.assign({}, base, over);
       merged.xaxis = Object.assign({}, base.xaxis || {}, over.xaxis || {});
       merged.yaxis = Object.assign({}, base.yaxis || {}, over.yaxis || {});
       return merged;
     }
     ```
  2. Guardar `el.__btSpecLayout = spec.layout || {};` al inicializar el gráfico en `initChartsIn`, y en `bt:theme-changed` llamar a `Plotly.relayout(el, mergeLayout(baseLayout(isMobile), el.__btSpecLayout))` para que el cambio de tema claro/oscuro conserve intactos los títulos de eje, rangos y ticks en español.

### 4. Fecha en inglés con `strftime("%b")` en `pages/backtest_detail.html`
- **El bug:** En `src/backtesting_cripto/web/templates/pages/backtest_detail.html` (línea 9):
  ```jinja
  Ejecutada el {{ result.created_at.strftime("%d") }} {{ result.created_at.strftime("%b") }} {{ result.created_at.strftime("%Y") }}
  ```
  `strftime("%b")` depende del locale C del sistema y formatea los meses en inglés (`Jan`, `Apr`, `Aug`, `Dec`).
- **Corrección obligatoria:**
  - Usar `{{ result.created_at | date_es }}` en `pages/backtest_detail.html` (en `format_date_es` de `formatters.py` ya funciona tanto para `date` como para `datetime` porque `datetime` hereda de `date`, pero conviene anotar el tipo como `date | datetime | None`).
