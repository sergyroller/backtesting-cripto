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
| **F6 — Interfaz web** | ⏳ Pendiente (siguiente) | Ver checklist obligatorio de F6 abajo (basado en `docs/planificacion.md` y `docs/design/DESIGN_SYSTEM.md`). |
| **F7 — Documentación final y pulido** | ⏳ Pendiente | — |

---

## Apuntes obligatorios tras la revisión de F5

### 1. Checklist obligatorio para la Fase F6 (Interfaz web: Jinja2 + HTMX + Plotly.js)

Implementar siguiendo **`docs/planificacion.md` (Sección H, F6)** y la especificación validada de **`docs/design/DESIGN_SYSTEM.md`**, **`docs/design/tokens.css`** y **`docs/design/plotly-theme.js`**:

1. **Dependencias en `pyproject.toml`**:
   - Añadir `"jinja2>=3.1"` y `"python-multipart>=0.0.9"` (si se reciben formularios HTML `application/x-www-form-urlencoded` en FastAPI) a `dependencies` y actualizar `uv.lock`.

2. **Activos estáticos en `src/backtesting_cripto/web/static/`**:
   - **CSS propio con `@layer tokens, base, layout, components, utilities`:**
     - Copiar `docs/design/tokens.css` a `src/backtesting_cripto/web/static/css/tokens.css` (único archivo CSS con valores hex; contiene `#0DC3A4`, paleta clara y `[data-theme="dark"]`).
     - Crear `base.css`, `layout.css`, `components.css` y `charts.css` implementando los componentes y layouts de `docs/design/DESIGN_SYSTEM.md` (§5–§7, §11–§16).
   - **JavaScript propio (≤ 250 líneas en total):**
     - `src/backtesting_cripto/web/static/js/theme.js`: `setThemePreference("light" | "dark" | "system")`, persistencia en `localStorage["theme-preference"]`, listener de `matchMedia` y emisión del evento `bt:theme-changed` (§8.3).
     - `src/backtesting_cripto/web/static/js/charts.js`: basado en `docs/design/plotly-theme.js` (lectura de tokens con `cssToken`, `baseLayout`, `initChartsIn` en `DOMContentLoaded` y `htmx:load`, y `Plotly.relayout` + `Plotly.restyle` al recibir `bt:theme-changed`).
     - `src/backtesting_cripto/web/static/js/app.js`: helpers mínimos de UI (añadir/eliminar filas de tramos semanales en el formulario, atajos de rango de fechas `1A / 3A / 5A / Todo`, pestañas *Resumen / Operaciones / Supuestos*, acordeón de filas en móvil).
   - **Librerías vendor locales (`src/backtesting_cripto/web/static/vendor/`):**
     - Descargar y servir localmente `htmx` y `plotly` (bundle cartesian minificado) desde `/static/vendor/` para cumplir la regla de cero dependencias de CDN en tiempo de ejecución (o con fallback claro si se ejecuta sin red).

3. **Formateadores españoles en servidor (`src/backtesting_cripto/web/`):**
   - Implementar y registrar en el entorno Jinja2 los filtros exactos del **§6.5 de `DESIGN_SYSTEM.md`**:
     - `eur`: `13 300,00 €` (separador de miles espacio fino `\u202f` o espacio no separable, coma decimal, 2 decimales, sufijo ` €`).
     - `signed_eur`: `+67 101,26 €` / `−380,00 €` (con signo explícito `+` o `−` U+2212).
     - `pct` / `signed_pct`: `+504,52 %` / `−50,00 %` (2 decimales con coma).
     - `btc`: `1,10037310 BTC` (8 decimales con coma).
     - `date_es`: `18 oct 2026` (formato corto en español).
     - `reason_es`: traduce `daily_<10` → `Diaria (< 10)`, `monday_10_14` → `Lunes 10–14`, etc.

4. **Las 3 vistas principales y fragmentos HTMX (`src/backtesting_cripto/web/templates/` y `api/`)**:
   - Montar `/static` en `create_app` y exponer las **3 vistas acordadas en `DESIGN_SYSTEM.md` (§9.1)**:
     1. **`GET /` — Simulador / Panel (`pages/panel.html`):**
        - Cabecera de contexto con estado de datos (`"Datos hasta el …"`, último día UTC cerrado) y control de tema (`Claro / Oscuro / Sistema`) + script anti-FOUC en `<head>` (§8.2).
        - Formulario configurable en español:
          - Activo (`BTC/EUR`), estrategia (`Fear & Greed Index`).
          - Rango de fechas (`start_date`, `end_date`) acotado a `[available_start, available_end]` (`2018-02-01` → último día cerrado) + chips rápidos `1 A · 3 A · 5 A · Todo`.
          - Umbral diario (`daily_below_threshold`, por defecto `10`) e importe diario (`daily_amount_eur`, por defecto `50,00 €`).
          - Tramos semanales en lunes (`weekly_bands`: lista editable de `min_value`, `max_value`, `amount_eur` con botón de añadir/quitar tramo; por defecto `10–14: 200 €`, `15–19: 150 €`, `20–24: 100 €`).
          - Modo de ejecución (`close_same_day` — cierre del mismo día D, o `close_next_day` — cierre del día siguiente D+1).
        - Al entrar en `/`, si ya hay alguna simulación guardada muestra la más reciente (o ejecuta/muestra una simulación inicial con los parámetros por defecto sobre el rango disponible) para que el dashboard nunca aparezca vacío si hay datos.
        - Envío del formulario (por HTMX `POST /ui/backtests` o similar, además de funcionar con envío estándar) que valida parámetros, ejecuta `backtest_service.execute_backtest(config)` y actualiza el bloque de resultados (o muestra errores de validación en español si hay tramos solapados o fechas inválidas).
        - **Bloque de resultados del backtest (`partials/fragments/simulation_result.html`):**
          - **4 tarjetas de métricas primarias (§11.2 Bloque B):** Valor de la cartera (€), Beneficio/Pérdida (€ y % con signo y color semántico), Capital invertido (€ y nº de operaciones), BTC acumulado (8 decimales y coste medio €/BTC).
          - **Fila de métricas secundarias (§11.2 Bloque D):** Drawdown máximo (%), desglose de operaciones por tramo, precio final BTC/EUR, modo de ejecución.
          - **Gráficos interactivos Plotly (§12.3):**
            - `G1`: Capital invertido vs. Valor de la cartera + marcadores de compra.
            - `G2`: Evolución del índice Fear & Greed (línea violeta `--color-fng`) con marcadores de compras (`--color-brand`).
            - `G3`: Barras horizontales de operaciones por tramo del índice.
            - `G4`: Curva de drawdown (%).
            - Cada gráfico con su `<script type="application/json" data-chart-for="...">`, `role="img"` + `aria-label` y `<details class="c-chart-alt">` accesible (§17.3).
          - **Pestaña / sección de Operaciones individuales (`.c-table`, §10.4 y §13.7):**
            - Las 7 columnas en escritorio (`#`, `Fecha`, `Índice F&G`, `Regla`, `Importe`, `Precio BTC`, `BTC comprados`) y soporte de filtrado por tramo y paginación HTMX (50 por página).
          - **Pestaña / sección de Supuestos y Metadatos:** `run_id`, `created_at`, `code_version`, `config_hash`, `dataset_hash`, `result_hash`, incidentes (si los hubiera) y supuestos de simulación.
     2. **`GET /backtests` y `GET /backtests/{run_id}` — Historial y detalle (`pages/backtests.html` y `pages/backtest_detail.html`):**
        - Listado de todas las simulaciones guardadas en `RunStore` con enlace a su vista de detalle `/backtests/{run_id}` y enlace para precargar su configuración en el Simulador (`/`).
     3. **`GET /data` y `POST /ui/data/sync` — Estado de datos (`pages/data.html`):**
        - Tabla de fuentes locales (`bgeometrics`/`alternative.me` y `bitstamp`), cobertura (`first_day` → `last_day`), `record_count`, `sha256`, `dataset_hash`, explicación de los 39 días de hueco histórico del índice, botón **"Actualizar datos"** (HTMX) y atribuciones visibles a **alternative.me**, **BGeometrics** y **Bitstamp**.

5. **Tests de interfaz web en `tests/unit/test_web_filters.py` y `tests/integration/test_web_ui.py`**:
   - Tests unitarios de todos los filtros Jinja2 (`eur`, `signed_eur`, `pct`, `signed_pct`, `btc`, `date_es`, `reason_es`) y de las reglas de contraste/tokens (`tokens.css` es el único CSS con colores hex).
   - Tests de integración con `TestClient`:
     - `GET /` devuelve `200 OK`, HTML en español (`<html lang="es">`), incluye el script anti-FOUC, las tarjetas de métricas y los datos JSON de los gráficos.
     - Enviar una simulación desde la UI (`POST /ui/backtests`) con parámetros válidos en `[2018-02-01, 2026-10-18]` devuelve el fragmento/página con `13 300,00 €`, `121` operaciones, `1,10037310 BTC` y `80 401,26 €`.
     - Enviar una simulación desde la UI con tramos solapados devuelve mensaje de error claro en español sin romper la página.
     - `GET /backtests` y `GET /backtests/{run_id}` devuelven `200 OK` (y `404` en español si el `run_id` no existe).
     - `GET /data` y `POST /ui/data/sync` devuelven `200 OK` con el estado de las fuentes y las atribuciones.
     - `GET /static/css/tokens.css` y `GET /static/js/charts.js` se sirven con `200 OK`.
