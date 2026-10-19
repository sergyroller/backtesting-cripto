# AGENTS.md — backtesting-cripto

Sistema modular de backtesting de acumulación de criptomonedas (v1: BTC/EUR con estrategia configurable basada en el Crypto Fear & Greed Index).

- **Documentos de lectura obligatoria antes de tocar código:**
  1. `docs/planificacion.md` — arquitectura, contratos, modelos, fuentes de datos verificadas, fórmulas, plan de pruebas y fases de implementación.
  2. `docs/notas-arquitectura.md` — **bitácora de revisiones del arquitecto, estado de cada fase y checklist obligatorio de la fase activa**. Léelo siempre al empezar.
- **Idioma:**
  - **Comunicación, documentación (`docs/`, `README.md`) e interfaz web:** siempre en **español**.
  - **Código fuente (`src/`, `tests/`, nombres de carpetas, módulos, clases, funciones, tablas y variables):** siempre en **inglés**.
- **Reglas clave acordadas:**
  - Todo dato histórico descargado se guarda en `data/raw/` (inmutable, con SHA-256 en `MANIFEST.json`); los backtests nunca acceden a la red.
  - Zona horaria única: **UTC**, granularidad diaria (`datetime.date`). Un día natural **no computa** hasta que ha terminado en UTC y su vela diaria está cerrada (`last_closed_day = today_utc - 1`).
  - El inicio disponible depende de los datos requeridos por cada estrategia (`2018-02-01` para Fear & Greed; estrategias futuras podrán empezar antes).
  - Compras **100 % directas** (sin comisiones ni deslizamiento, ni duplicidad bruto/neto) y **sin benchmark DCA acoplado** (cada estrategia es independiente).
  - Dinero y cantidades: `decimal.Decimal` (BTC cuantificado a **8 decimales** con `ROUND_DOWN`; EUR y porcentajes a **2 decimales** con `ROUND_HALF_UP`), nunca `float`.
- **Apuntes activos del arquitecto (post-F1):**
  - **Antes de empezar F2 (Punto 0 de `docs/notas-arquitectura.md`):** corrige `StrategyContext` en `src/backtesting_cripto/domain/contracts.py` para que incluya `asset`, `start_date`, `end_date`, `params`, `indicators` y `prices: PriceSeries | None = None` (tal como exigen las Secciones E.2 y E.4 de `docs/planificacion.md`), y limita la validación `[0, 100]` de `IndicatorValue` a `self.indicator == "fear_greed"`.
  - **Fase actual:** **F2 — Ingesta, validación y almacenamiento de datos** (sigue el checklist completo de F2 en `docs/notas-arquitectura.md`, incluyendo ajustar `.gitignore` para ignorar solo `data/*.sqlite3*` y versionar `data/raw/`).
