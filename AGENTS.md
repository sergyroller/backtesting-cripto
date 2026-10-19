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
- **Apuntes activos del arquitecto (post-F0):**
  - **Fase actual:** **F1 — Modelos de dominio y contratos** (sigue el checklist detallado en `docs/notas-arquitectura.md`).
  - Añade `src/backtesting_cripto/web/__init__.py` para que los 11 subpaquetes tengan su `__init__.py`.
  - En **F2**, ajusta `.gitignore` para ignorar `data/*.sqlite3` pero permitir versionar `data/raw/` (o el snapshot en `tests/data/`) de forma que los tests de regresión (`2018-02-01` → `2026-10-18`: 121 compras / 13 300,00 €) funcionen 100 % offline tras clonar el repositorio.
