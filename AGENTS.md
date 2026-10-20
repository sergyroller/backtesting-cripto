# AGENTS.md — backtesting-cripto

Sistema modular de backtesting de acumulación de criptomonedas (v1: BTC/EUR con estrategia configurable basada en el Crypto Fear & Greed Index).

- **Documentos de lectura obligatoria antes de tocar código:**
  1. `docs/planificacion.md` — arquitectura, contratos, modelos, fuentes de datos verificadas, fórmulas, plan de pruebas y fases de implementación.
  2. `docs/notas-arquitectura.md` — **bitácora de revisiones del arquitecto, estado de cada fase y checklist obligatorio de la fase activa**. Léelo siempre al empezar.
  3. `docs/design/DESIGN_SYSTEM.md` (junto con `docs/design/tokens.css` y `docs/design/plotly-theme.js`) — **especificación UX/UI validada** de lectura obligatoria para la fase F6.
- **Idioma:**
  - **Comunicación, documentación (`docs/`, `README.md`) e interfaz web:** siempre en **español**.
  - **Código fuente (`src/`, `tests/`, nombres de carpetas, módulos, clases, funciones, tablas y variables):** siempre en **inglés**.
- **Reglas clave acordadas:**
  - Todo dato histórico descargado se guarda en `data/raw/` (inmutable, con SHA-256 en `MANIFEST.json`); los backtests nunca acceden a la red.
  - Zona horaria única: **UTC**, granularidad diaria (`datetime.date`). Un día natural **no computa** hasta que ha terminado en UTC y su vela diaria está cerrada (`last_closed_day = today_utc - 1`).
  - El inicio disponible depende de los datos requeridos por cada estrategia (`2018-02-01` para Fear & Greed; estrategias futuras podrán empezar antes).
  - Compras **100 % directas** (sin comisiones ni deslizamiento, ni duplicidad bruto/neto) y **sin benchmark DCA acoplado** (cada estrategia es independiente).
  - Dinero y cantidades: `decimal.Decimal` (BTC cuantificado a **8 decimales** con `ROUND_DOWN`; EUR y porcentajes a **2 decimales** con `ROUND_HALF_UP`), nunca `float`.
- **Apuntes activos del arquitecto (revisión F6):**
  - **Fases F0, F1, F2, F3, F4 y F5:** ✅ Aprobadas.
  - **Fase actual:** **Saneamiento obligatorio de F6** (aplicar los **4 puntos** detallados en `docs/notas-arquitectura.md`: 1) paginar `rows` en `result_context` y propagar `run_id` en `/ui/operations` y `operations_table.html`, 2) hacer idempotentes y acotados a `root` los listeners de `app.js` ante `htmx:load`, 3) usar `mergeLayout` para fusionar `xaxis`/`yaxis` en `charts.js` y `docs/design/plotly-theme.js` tanto al iniciar como en `bt:theme-changed`, 4) usar `| date_es` en lugar de `strftime("%b")` en `pages/backtest_detail.html`).
