# backtesting-cripto

Sistema modular de backtesting de acumulación de criptomonedas (v1: BTC/EUR con estrategia configurable basada en el Crypto Fear & Greed Index).

- **Documento rector:** [`docs/planificacion.md`](docs/planificacion.md) — arquitectura, modelo de datos, fórmulas, plan de pruebas y fases de implementación.
- **Instrucciones para agentes:** [`AGENTS.md`](AGENTS.md).

## Estado actual

**Fase 0 (F0) — esqueleto y herramientas:** `pyproject.toml` (uv), estructura `src/backtesting_cripto/`, ruff, mypy y pytest.

## Requisitos

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Puesta en marcha

```bash
uv sync          # crea el entorno .venv e instala dependencias
uv run pytest    # ejecuta la suite de tests
```

## Herramientas de calidad

```bash
uv run ruff check   # linter
uv run mypy src     # tipado estricto
```
