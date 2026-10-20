# AGENTS.md — backtesting-cripto

Sistema modular de backtesting de acumulación de criptomonedas (v1: BTC/EUR con estrategia configurable basada en el Crypto Fear & Greed Index).

- **Documentos de lectura obligatoria antes de tocar código:**
  1. `docs/planificacion.md` — arquitectura, contratos, modelos, fuentes de datos verificadas, fórmulas, plan de pruebas y fases de implementación.
  2. `docs/notas-arquitectura.md` — **bitácora de revisiones del arquitecto, estado de cada fase y checklist obligatorio de la fase activa**. Léelo siempre al empezar.
  3. `docs/design/DESIGN_SYSTEM.md` (junto con `docs/design/tokens.css` y `docs/design/plotly-theme.js`) — **especificación UX/UI validada** de lectura obligatoria para las fases F5 y F6.
- **Idioma:**
  - **Comunicación, documentación (`docs/`, `README.md`) e interfaz web:** siempre en **español**.
  - **Código fuente (`src/`, `tests/`, nombres de carpetas, módulos, clases, funciones, tablas y variables):** siempre en **inglés**.
- **Reglas clave acordadas:**
  - Todo dato histórico descargado se guarda en `data/raw/` (inmutable, con SHA-256 en `MANIFEST.json`); los backtests nunca acceden a la red.
  - Zona horaria única: **UTC**, granularidad diaria (`datetime.date`). Un día natural **no computa** hasta que ha terminado en UTC y su vela diaria está cerrada (`last_closed_day = today_utc - 1`).
  - El inicio disponible depende de los datos requeridos por cada estrategia (`2018-02-01` para Fear & Greed; estrategias futuras podrán empezar antes).
  - Compras **100 % directas** (sin comisiones ni deslizamiento, ni duplicidad bruto/neto) y **sin benchmark DCA acoplado** (cada estrategia es independiente).
  - Dinero y cantidades: `decimal.Decimal` (BTC cuantificado a **8 decimales** con `ROUND_DOWN`; EUR y porcentajes a **2 decimales** con `ROUND_HALF_UP`), nunca `float`.
- **Apuntes activos del arquitecto (revisión F5):**
  - **Fases F0, F1, F2, F3 y F4:** ✅ Aprobadas.
  - **Fase actual:** **Saneamiento obligatorio de F5** (aplicar los **4 puntos** detallados en `docs/notas-arquitectura.md`: 1) recortar `fng_values` y `bars` a `<= available_last` en `_consolidate_from_raw` + test con fecha futura `2027-06-01`, 2) ordenar manifiesto por `retrieved_at` y limpiar los 5 ficheros duplicados del 19 oct en `data/raw/`, 3) cerrar conexiones SQLite con `lifespan` en `api/app.py` y reutilizar `self._repo` en `BacktestService.get_backtest`, 4) filtrar `StarletteDeprecationWarning` en `pyproject.toml`).
