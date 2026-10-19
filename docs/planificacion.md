# Planificación — Sistema modular de backtesting de acumulación de criptomonedas

**Estado:** planificación validada y cerrada con el usuario (lista para implementar).
**Fecha de verificación de datos:** 2026-10-19.
**Ámbito v1:** BTC/EUR, estrategia basada en el Crypto Fear & Greed Index (con tramos e importes configurables).

---

## 0. Resumen ejecutivo y hechos verificados

El repositorio estaba **vacío**: no había código, restricciones ni decisiones previas.

Hechos **verificados empíricamente** al consultar las fuentes reales (no hipótesis):

| # | Hecho verificado | Evidencia |
|---|---|---|
| 1 | El índice Fear & Greed que publica BGeometrics **es el de alternative.me** (BGeometrics lo republica; el gráfico incluye el crédito *"Source: alternative.me"*). | HTML de `charts.bgeometrics.com/es/graphics/fear_greed.html` |
| 2 | BGeometrics sirve la serie completa como **JSON estático sin autenticación**: `https://charts.bgeometrics.com/files/fear_greed.json`, formato `[[timestamp_ms, valor_entero], ...]`. | Descarga directa: 59 695 bytes |
| 3 | Cobertura inicial del índice: empieza el **`2018-02-01`**. **No existe ningún valor anterior al 1 de febrero de 2018** en ninguna fuente (el índice nació ese día). | Análisis del JSON descargado (3 144 registros hasta el 2026-10-19) |
| 4 | La serie tiene **39 días sin dato agrupados en 22 huecos** (el mayor: 8 días en marzo de 2023). Sin fechas duplicadas; valores enteros en `[5, 95]`. | Análisis del JSON descargado |
| 5 | La API pública de alternative.me (`https://api.alternative.me/fng/?limit=0&format=json`) devuelve la **misma serie** (timestamps idénticos) con clasificación textual; exige **atribución** y permite uso comercial con atribución. | Descarga directa + términos publicados |
| 6 | El índice se publica **una vez al día** con timestamp `00:00 UTC` del día al que se refiere. La hora exacta de publicación dentro del día **no está documentada formalmente**. | Timestamps observados + countdown *"next update"* de alternative.me |
| 7 | **Bitstamp** ofrece OHLC diario BTC/EUR sin autenticación: `https://www.bitstamp.net/api/v2/ohlc/btceur/?step=86400&limit=1000&start=...&end=...`. Cobertura verificada desde `2018-01-01` (y anterior, desde 2011) hasta la **última vela diaria cerrada** (`D-1` en UTC; un día en curso no computa hasta que termina y cierra su vela). Máx. 1 000 velas por llamada. | Descargas directas |
| 8 | **Kraken** ofrece OHLC XBT/EUR sin autenticación pero solo **720 velas por llamada** paginando hacia adelante con `since`. Válido como fuente de validación cruzada (cubre desde 2013). | Descarga directa |
| 9 | **CoinGecko** limita el histórico a **365 días** en el plan público → **descartado**. **CryptoCompare (CoinDesk Data)** exige API key → descartado como fuente primaria. | Respuestas de error `401 / 10012` reales de ambas APIs |
| 10 | Sobre el rango cerrado `2018-02-01` → `2026-10-18`: hay 454 lunes; lunes con dato del índice por tramo: `<10`: 7, `10-14`: 23, `15-19`: 20, `20-24`: 36, `>=25`: 356, sin dato: 12. Días (cualquier día de la semana) con índice `<10`: 42. | Análisis del JSON descargado |

Del hecho 10 se deriva el **invariante de regresión** para la estrategia con sus parámetros por defecto sobre el rango cerrado `2018-02-01` → `2026-10-18`:
- **121 operaciones** en total:
  - **42 compras diarias** de `50 €` (`2 100 €`, incluidos los 7 lunes con índice `< 10`, ya que la regla diaria prevalece).
  - **79 compras semanales en lunes**: `23 × 200 €` (`4 600 €`) + `20 × 150 €` (`3 000 €`) + `36 × 100 €` (`3 600 €`) = `11 200 €`.
- **13 300,00 € de capital total invertido.**

---

## A. Decisiones y supuestos validados con el usuario

Todas las dudas iniciales han sido revisadas y acordadas:

1. **Alcance funcional de estrategias (v1):**
   - El sistema es un **gestor y simulador modular de estrategias cripto**.
   - En la primera versión **solo se implementa la estrategia del Fear & Greed Index sobre BTC/EUR**.
   - **No hay benchmark DCA comparativo acoplado**: cuando en el futuro se añada un DCA semanal u otras reglas, serán simplemente **otras estrategias independientes** en el selector.
2. **Inicio y fin dinámicos de los datos:**
   - **Inicio por estrategia:** la fecha mínima seleccionable para una estrategia es el primer día en que existen datos tanto del activo como de los indicadores que requiere esa estrategia:
     $$\text{available\_start}(\text{strategy}, \text{asset}) = \max\big(\text{first\_price\_day}(\text{asset}), \max_{i \in \text{strategy.indicators}} \text{first\_indicator\_day}(i)\big)$$
     Para la estrategia Fear & Greed en BTC es el **`2018-02-01`**. Futuras estrategias que solo usen precio o indicadores más antiguos podrán empezar en `2018-01-01` o antes.
   - **Fin abierto a días cerrados:** no existe una fecha fin fija en el proyecto. **Un día natural solo computa cuando ha terminado en UTC y su vela diaria está cerrada** (si hoy es `D`, los datos consolidados llegan hasta `D-1`; mañana hasta `D`, etc.).
3. **Compras 100 % directas (sin comisiones ni deslizamiento):**
   - No se aplican comisiones ni deslizamiento, ni se duplican métricas en "bruto vs. neto".
   - Cada compra convierte directamente los euros configurados al precio de ejecución del día:
     $$\text{btc\_quantity} = \text{round\_down\_8}\left(\frac{\text{amount\_eur}}{\text{exec\_price}}\right)$$
4. **Redondeo y precisión (`decimal.Decimal`):**
   - **Cantidades BTC:** redondeadas en cada operación a **8 decimales** (1 satoshi: `Decimal("0.00000001")`, `ROUND_DOWN`).
   - **Importes en Euros (€) y porcentajes (%):** redondeados a **2 decimales** (`Decimal("0.01")`, `ROUND_HALF_UP`).
5. **Momento de ejecución y anti-anticipación:**
   - Por defecto: **cierre (UTC) del mismo día `D`** (`close_same_day`), asumiendo que el valor del índice publicado a `00:00 UTC` está disponible antes del cierre `23:59:59 UTC` de ese día.
   - Se mantiene en la interfaz el selector técnico para ejecutar al **cierre del día siguiente `D+1`** (`close_next_day`) como análisis de sensibilidad.
6. **Tratamiento de días sin dato:**
   - **Índice ausente (los 39 días de hueco):** por defecto, **día sin dato = no se compra** (no se imputa).
   - **Precio ausente en un día intermedio:** en Bitstamp no falta ningún día; si en el futuro o en otro activo faltase un día aislado, la curva de valoración de cartera (`equity_curve`) usa el **último precio de cierre conocido del día anterior** (`last_close_on_or_before(day)`), y si coincidiera con una orden de compra se registra como incidente omitiendo la compra.
7. **Parámetros editables en la interfaz web:**
   - Rango de fechas (`start`, `end`) dentro del rango disponible de la estrategia.
   - **Importes en euros** de cada regla (por defecto: `50 €` diario y `200 €`, `150 €`, `100 €` semanales).
   - **Tramos del índice** (por defecto: compra diaria si `< 10`; compras en lunes para `[10..14]`, `[15..19]`, `[20..24]`; no comprar si `>= 25`).
   - Modo de ejecución (`close_same_day` / `close_next_day`).
8. **Métricas en resultados:**
   - Se mantienen todas las métricas: Capital invertido (€), Número de operaciones (total y por tramo), BTC acumulados, Coste medio por BTC (€/BTC), Valor final de la cartera (€), Beneficio/Pérdida (€ y %) y **Drawdown máximo (%)**.

---

## B. Arquitectura propuesta y justificación tecnológica

### B.1 Vista general por capas

```
┌────────────────────────────────────────────────────────────┐
│  Frontend (Jinja2 + HTMX + Plotly.js, servido por FastAPI) │
├────────────────────────────────────────────────────────────┤
│  API REST (FastAPI)  ── OpenAPI autogenerada               │
├────────────────────────────────────────────────────────────┤
│  Application Services (backtest runner, data sync)         │
├──────────────┬───────────────┬──────────────┬──────────────┤
│  Backtest    │  Strategies   │  Indicators  │  Metrics     │
│  Engine      │  (plugins)    │  (plugins)   │  Calculator  │
├──────────────┴───────────────┴──────────────┴──────────────┤
│  Domain (models + Protocol/Pydantic contracts)             │
├────────────────────────────────────────────────────────────┤
│  Storage Repository (SQLite) + Immutable Raw Store         │
│  (archivos + MANIFEST.json con SHA-256)                    │
├────────────────────────────────────────────────────────────┤
│  Data Providers (BGeometrics, alternative.me,              │
│  Bitstamp, Kraken) — usados SOLO en la ingesta/sync        │
└────────────────────────────────────────────────────────────┘
```

Regla de dependencias: **las capas superiores dependen de las inferiores, nunca al revés**. El motor no conoce HTTP, ni FastAPI, ni la estrategia concreta; los proveedores externos solo se invocan al sincronizar datos, nunca durante un backtest (que corre 100 % sobre datos locales).

### B.2 Decisiones tecnológicas

| Decisión | Elección | Justificación |
|---|---|---|
| Lenguaje | **Python 3.12** | Ecosistema maduro, tipado moderno, ideal para datos y backend. |
| Idioma del proyecto | **Código y rutas en inglés**; UI y docs en **español** | Consistencia total en imports, clases, tablas y rutas (`domain/models.py`, `PriceBar`, etc.). |
| Núcleo del motor | **stdlib + `decimal.Decimal`**, sin pandas/numpy | ~3 200 barras diarias no requieren librerías pesadas; `Decimal` garantiza aritmética exacta en satoshis y céntimos; `datetime.date` en UTC evita problemas de zonas horarias. |
| API | **FastAPI + Pydantic v2** | Validación estricta de tramos, fechas e importes; documentación OpenAPI automática. |
| Frontend v1 | **Jinja2 + HTMX + Plotly.js** servidos por FastAPI | Un único proceso Python sin necesidad de Node.js ni pasos de compilación; gráficos interactivos potentes con Plotly. |
| Persistencia | **SQLite** (fichero único) + **ficheros raw inmutables** con SHA-256 | Cero servidores externos, transaccional y reproducible. |
| Gestor de paquetes | **uv** (`pyproject.toml` + `uv.lock`) | Instalación instantánea y entorno reproducible. |
| Tests y calidad | **pytest + hypothesis**, **ruff**, **mypy** | Pruebas basadas en propiedades para invariantes financieros y tipado estricto en el núcleo. |

### B.3 Extensibilidad (multi-activo, multi-indicador, multi-estrategia)

- **Registros de componentes (`StrategyRegistry`, `IndicatorRegistry`, `AssetRegistry`):**
  - Cada estrategia declara en metadatos qué indicadores requiere (`required_indicators: tuple[str, ...]`) y cuál es su esquema de parámetros (`params_schema: type[BaseModel]`).
  - Añadir una nueva estrategia en el futuro (p. ej. DCA semanal, RSI, medias móviles) consiste únicamente en crear una clase que implemente el protocolo `Strategy` y registrarla. El motor, el almacenamiento y las métricas no cambian.

---

## C. Estructura de carpetas y responsabilidades

Todos los paquetes, módulos e identificadores de `src/` y `tests/` están en **inglés**:

```
backtesting-cripto/
├── pyproject.toml                  # dependencias, ruff, mypy, pytest
├── uv.lock
├── README.md                       # guía rápida en español
├── AGENTS.md                       # instrucciones para agentes
├── docs/
│   ├── planificacion.md            # este documento rector
│   ├── fuentes-de-datos.md         # endpoints, formatos, licencias y descargas
│   └── metricas.md                 # fórmulas exactas y ejemplos verificados
├── data/
│   ├── raw/                        # INMUTABLE: respuestas originales + MANIFEST.json
│   │   ├── fear_greed/
│   │   └── bitstamp/
│   └── backtesting.sqlite3         # series normalizadas + histórico de ejecuciones
├── src/backtesting_cripto/
│   ├── __init__.py                 # __version__
│   ├── domain/                     # modelos y contratos puros (sin I/O ni red)
│   │   ├── models.py               # PriceBar, IndicatorValue, OrderIntent, Fill, ...
│   │   ├── contracts.py            # Protocols: PriceSeries, IndicatorSeries, Strategy, ExecutionModel
│   │   └── exceptions.py
│   ├── providers/                  # SOLO ingesta desde internet
│   │   ├── bgeometrics_fng.py
│   │   ├── alternative_me_fng.py
│   │   ├── bitstamp_ohlc.py
│   │   └── kraken_ohlc.py          # validación cruzada opcional
│   ├── storage/
│   │   ├── raw_store.py            # archivo inmutable de descargas + MANIFEST.json
│   │   ├── repository.py           # SQLite: datasets, price_bars, indicator_values
│   │   └── run_store.py            # SQLite: backtest_runs, trades
│   ├── validation/
│   │   ├── dataset_checks.py       # invariantes al sincronizar datos (rangos, huecos, días cerrados)
│   │   └── consistency_checks.py   # comprobaciones financieras post-simulación
│   ├── indicators/
│   │   └── registry.py             # carga local de series de indicadores
│   ├── strategies/
│   │   ├── base.py                 # Strategy protocol + StrategyRegistry
│   │   └── fear_greed.py           # FearGreedStrategy + configuración de tramos e importes
│   ├── engine/
│   │   ├── calendar.py             # iteración de fechas UTC, detección de lunes, ventana disponible
│   │   ├── execution.py            # ExecutionModel (close_same_day / close_next_day)
│   │   ├── portfolio.py            # acumulación de BTC y registro de Fills
│   │   └── runner.py               # BacktestEngine: señales → fills → equity_curve → métricas
│   ├── metrics/
│   │   └── calculator.py           # capital invertido, BTC, coste medio, valor final, P&L, ROI, drawdown
│   ├── services/
│   │   ├── backtest_service.py     # orquesta lectura de datos, motor y guardado del run
│   │   └── data_service.py         # sincronización incremental de días cerrados y estado de datos
│   ├── api/
│   │   ├── app.py                  # FastAPI factory
│   │   └── routes.py               # endpoints REST + vistas HTML/HTMX
│   └── web/
│       ├── templates/              # plantillas Jinja2 (interfaz en español)
│       └── static/                 # estilos CSS y helpers de gráficas Plotly
├── scripts/
│   └── sync_data.py                # CLI para descargar/actualizar datos hasta el último día cerrado
└── tests/
    ├── unit/                       # tramos de estrategia, cartera, métricas, ejecución, redondeo
    ├── integration/                # flujo completo con fixtures sintéticos y con snapshot real
    └── data/                       # tests de integridad sobre el snapshot de datos
```

---

## D. Modelo de datos y contratos entre módulos

### D.1 Modelos de dominio (`src/backtesting_cripto/domain/models.py`)

```python
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

BTC_QUANT = Decimal("0.00000001")   # 8 decimales (1 satoshi)
EUR_QUANT = Decimal("0.01")         # 2 decimales (1 céntimo)

class PriceBar(BaseModel):          # vela diaria cerrada (00:00:00 a 23:59:59 UTC)
    asset: str                      # "BTC"
    quote: str                      # "EUR"
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str                     # "bitstamp"

class IndicatorValue(BaseModel):
    indicator: str                  # "fear_greed"
    day: date
    value: Decimal                  # entero 0..100
    source: str                     # "bgeometrics" | "alternative.me"

class WeeklyBandRule(BaseModel):    # tramo semanal configurable (se evalúa en lunes)
    min_value: int = Field(ge=0, le=100)
    max_value: int = Field(ge=0, le=100)
    amount_eur: Decimal = Field(gt=Decimal("0"))

    @model_validator(mode="after")
    def check_bounds(self) -> "WeeklyBandRule":
        if self.min_value > self.max_value:
            raise ValueError("min_value must be <= max_value")
        return self

class FearGreedParams(BaseModel):   # parámetros editables desde la web
    daily_below_threshold: int = Field(default=10, ge=0, le=100)
    daily_amount_eur: Decimal = Field(default=Decimal("50.00"), gt=Decimal("0"))
    weekly_bands: list[WeeklyBandRule] = Field(
        default_factory=lambda: [
            WeeklyBandRule(min_value=10, max_value=14, amount_eur=Decimal("200.00")),
            WeeklyBandRule(min_value=15, max_value=19, amount_eur=Decimal("150.00")),
            WeeklyBandRule(min_value=20, max_value=24, amount_eur=Decimal("100.00")),
        ]
    )

    @model_validator(mode="after")
    def validate_no_overlap(self) -> "FearGreedParams":
        # Garantiza que los tramos semanales no se solapen ni invadan el umbral diario
        sorted_bands = sorted(self.weekly_bands, key=lambda b: b.min_value)
        for band in sorted_bands:
            if band.min_value < self.daily_below_threshold:
                raise ValueError("Weekly bands must be >= daily_below_threshold")
        for a, b in zip(sorted_bands, sorted_bands[1:]):
            if a.max_value >= b.min_value:
                raise ValueError("Weekly bands cannot overlap")
        return self

class OrderIntent(BaseModel):       # intención de compra emitida por la estrategia
    decision_day: date
    asset: str
    amount_eur: Decimal             # redondeado a 2 decimales
    reason: str                     # p.ej. "daily_<10", "monday_10_14"

class Fill(BaseModel):              # compra ejecutada (100 % directa, sin comisiones)
    execution_day: date
    decision_day: date
    asset: str
    index_value: Decimal | None     # valor del indicador que disparó la compra (trazabilidad en UI)
    amount_eur: Decimal             # 2 decimales (EUR)
    price_eur: Decimal              # precio de cierre ejecutado (2 decimales EUR)
    btc_quantity: Decimal           # 8 decimales (ROUND_DOWN: satoshis)
    reason: str

class EquityPoint(BaseModel):
    day: date
    invested_eur: Decimal           # capital acumulado invertido hasta `day` (2 decimales)
    btc_accumulated: Decimal        # BTC acumulados hasta `day` (8 decimales)
    close_price_eur: Decimal        # cierre del día (o último cierre previo si faltase)
    portfolio_value_eur: Decimal    # round_half_up_2(btc_accumulated * close_price_eur)
    drawdown_pct: Decimal           # 2 decimales (<= 0.00)

class Metrics(BaseModel):
    total_invested_eur: Decimal     # 2 decimales
    total_operations: int
    operations_by_reason: dict[str, int]
    btc_accumulated: Decimal        # 8 decimales
    average_buy_price_eur: Decimal | None   # None si total_operations == 0
    final_price_eur: Decimal
    final_portfolio_value_eur: Decimal      # 2 decimales
    pnl_eur: Decimal                # final_portfolio_value_eur - total_invested_eur
    roi_pct: Decimal | None         # (pnl_eur / total_invested_eur) * 100 (None si 0 compras)
    max_drawdown_pct: Decimal       # mínimo de drawdown_pct (0.00 si 0 compras)

class BacktestConfig(BaseModel):
    asset: str = "BTC"
    quote: str = "EUR"
    strategy_id: str = "fear_greed"
    start_date: date
    end_date: date
    execution_mode: Literal["close_same_day", "close_next_day"] = "close_same_day"
    strategy_params: dict           # validado contra el schema de la estrategia

class BacktestResult(BaseModel):
    run_id: str
    created_at: datetime
    code_version: str
    dataset_hash: str
    config: BacktestConfig
    config_hash: str
    fills: list[Fill]
    equity_curve: list[EquityPoint]
    metrics: Metrics
    incidents: list[str] = []
    result_hash: str
```

### D.2 Contratos (`src/backtesting_cripto/domain/contracts.py`)

```python
from datetime import date
from decimal import Decimal
from typing import Iterator, Protocol

class PriceSeries(Protocol):
    def bar_on(self, day: date) -> PriceBar | None: ...
    def last_close_on_or_before(self, day: date) -> PriceBar | None: ...
    def date_bounds(self) -> tuple[date, date]: ...

class IndicatorSeries(Protocol):
    def value_on(self, day: date) -> Decimal | None: ...
    def date_bounds(self) -> tuple[date, date]: ...

class Strategy(Protocol):
    strategy_id: str
    name: str
    required_indicators: tuple[str, ...]
    def generate_intents(self, ctx: "StrategyContext") -> Iterator[OrderIntent]: ...

class ExecutionModel(Protocol):
    def execute(self, intent: OrderIntent, prices: PriceSeries) -> Fill | None: ...
```

### D.3 Esquema SQLite (`src/backtesting_cripto/storage/`)

```sql
CREATE TABLE datasets (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    first_day TEXT NOT NULL,
    last_day TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    license TEXT NOT NULL
);

CREATE TABLE price_bars (
    dataset_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    quote TEXT NOT NULL,
    day TEXT NOT NULL,              -- YYYY-MM-DD (solo velas diarias cerradas)
    open TEXT NOT NULL,
    high TEXT NOT NULL,
    low TEXT NOT NULL,
    close TEXT NOT NULL,
    volume TEXT NOT NULL,
    PRIMARY KEY (asset, quote, day, dataset_id)
);

CREATE TABLE indicator_values (
    dataset_id TEXT NOT NULL,
    indicator TEXT NOT NULL,
    day TEXT NOT NULL,              -- YYYY-MM-DD
    value TEXT NOT NULL,
    PRIMARY KEY (indicator, day, dataset_id)
);

CREATE TABLE backtest_runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    code_version TEXT NOT NULL,
    dataset_hash TEXT NOT NULL,
    config_json TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    incidents_json TEXT NOT NULL,
    result_hash TEXT NOT NULL
);

CREATE TABLE trades (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    decision_day TEXT NOT NULL,
    execution_day TEXT NOT NULL,
    index_value TEXT,
    amount_eur TEXT NOT NULL,
    price_eur TEXT NOT NULL,
    btc_quantity TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
```

---

## E. Diseño del motor de backtesting y estrategia inicial

### E.1 Rango de fechas disponible por estrategia (`engine/calendar.py`)

Para cualquier estrategia $S$ sobre el activo $A$:
1. $\text{min\_available\_date} = \max\big(\text{prices.first\_day}, \max_{i \in S.\text{required\_indicators}} \text{ind}[i].\text{first\_day}\big)$.
   - Para `fear_greed` en `BTC/EUR`: $\max(\text{2018-01-01}, \text{2018-02-01}) = \text{2018-02-01}$.
2. $\text{max\_available\_date} = \min\big(\text{prices.last\_closed\_day}, \min_{i \in S.\text{required\_indicators}} \text{ind}[i].\text{last\_day}\big)$.
   - Como un día no computa hasta que termina en UTC y cierra su vela diaria en Bitstamp, $\text{max\_available\_date}$ es siempre como máximo **ayer en UTC** (`today_utc - 1 day`).
3. Si el usuario solicita un `start_date < min_available_date` o un `end_date > max_available_date`, la API/servicio valida o acota a $[\text{min\_available\_date}, \text{max\_available\_date}]$.

### E.2 Flujo del motor (`engine/runner.py`)

```python
def run_backtest(
    cfg: BacktestConfig,
    prices: PriceSeries,
    indicators: dict[str, IndicatorSeries],
    strategy: Strategy,
    execution_model: ExecutionModel,
) -> BacktestResult:
    ctx = StrategyContext(cfg.start_date, cfg.end_date, cfg.strategy_params, indicators)
    portfolio = Portfolio()
    incidents: list[str] = []

    for intent in strategy.generate_intents(ctx):
        if not (cfg.start_date <= intent.decision_day <= cfg.end_date):
            continue
        fill = execution_model.execute(intent, prices)
        if fill is None:
            incidents.append(f"missing_price_on_{intent.decision_day.isoformat()}")
            continue
        if fill.execution_day > cfg.end_date:
            # Caso close_next_day en el último día del rango seleccionado
            continue
        portfolio.apply(fill)

    equity_curve = build_equity_curve(portfolio, prices, cfg.start_date, cfg.end_date)
    metrics = calculate_metrics(portfolio, equity_curve, prices, cfg.end_date)
    return build_result(cfg, portfolio, equity_curve, metrics, incidents)
```

### E.3 Modelo de ejecución y redondeo (`engine/execution.py`)

- **`close_same_day` (por defecto):**
  - `exec_day = intent.decision_day`
  - `bar = prices.bar_on(exec_day)` (si es `None`, devuelve `None`).
- **`close_next_day` (análisis de sensibilidad):**
  - `exec_day = intent.decision_day + timedelta(days=1)`
  - `bar = prices.bar_on(exec_day)`.
- **Cálculo exacto de cada `Fill`:**
  - `amount_eur = intent.amount_eur.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`
  - `price_eur = bar.close.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`
  - `btc_quantity = (amount_eur / price_eur).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)`

### E.4 Pseudocódigo de la estrategia Fear & Greed (`strategies/fear_greed.py`)

```python
class FearGreedStrategy:
    strategy_id = "fear_greed"
    name = "Acumulación por Crypto Fear & Greed Index"
    required_indicators = ("fear_greed",)

    def generate_intents(self, ctx: StrategyContext) -> Iterator[OrderIntent]:
        params = FearGreedParams.model_validate(ctx.params)
        fng = ctx.indicators["fear_greed"]

        for day in iter_days(ctx.start_date, ctx.end_date):
            val = fng.value_on(day)
            if val is None:
                # Día dentro de los 39 huecos históricos: sin dato = no comprar
                continue

            # 1) La regla de compra diaria (< umbral diario, por defecto < 10) prevalece siempre,
            #    incluso si el día es lunes.
            if val < params.daily_below_threshold:
                yield OrderIntent(
                    decision_day=day,
                    asset=ctx.asset,
                    amount_eur=params.daily_amount_eur,
                    reason=f"daily_<{params.daily_below_threshold}",
                    index_value=val,
                )
                continue

            # 2) El resto de tramos solo se evalúan los lunes (weekday == 0)
            if day.weekday() == 0:
                for band in params.weekly_bands:
                    if band.min_value <= val <= band.max_value:
                        yield OrderIntent(
                            decision_day=day,
                            asset=ctx.asset,
                            amount_eur=band.amount_eur,
                            reason=f"monday_{band.min_value}_{band.max_value}",
                            index_value=val,
                        )
                        break
            # 3) Si no entra en ningún tramo (p.ej. >= 25), no se compra.
```

### E.5 Fórmulas de métricas (`metrics/calculator.py`)

Sea $F = [\text{Fill}_1, \dots, \text{Fill}_n]$ la lista de compras ejecutadas y $P_{\text{end}}$ el precio de cierre de `end_date` (o `last_close_on_or_before(end_date)`):

1. **Capital invertido (€):**
   $$\text{total\_invested\_eur} = \sum_{i=1}^{n} \text{amount\_eur}_i$$
2. **Número de operaciones:** $n$ (y diccionario `operations_by_reason` con el conteo por cada tramo).
3. **BTC acumulado:**
   $$\text{btc\_accumulated} = \sum_{i=1}^{n} \text{btc\_quantity}_i$$
4. **Coste medio por BTC (€/BTC):**
   $$\text{average\_buy\_price\_eur} = \begin{cases} \text{round\_half\_up\_2}\left(\dfrac{\text{total\_invested\_eur}}{\text{btc\_accumulated}}\right) & \text{si } \text{btc\_accumulated} > 0 \\ \text{None} & \text{si } n = 0 \end{cases}$$
5. **Valor final de la cartera (€):**
   $$\text{final\_portfolio\_value\_eur} = \text{round\_half\_up\_2}\big(\text{btc\_accumulated} \times P_{\text{end}}\big)$$
6. **Beneficio o pérdida (`pnl_eur`):**
   $$\text{pnl\_eur} = \text{final\_portfolio\_value\_eur} - \text{total\_invested\_eur}$$
7. **Rentabilidad porcentual (`roi_pct`):**
   $$\text{roi\_pct} = \begin{cases} \text{round\_half\_up\_2}\left(\dfrac{\text{pnl\_eur}}{\text{total\_invested\_eur}} \times 100\right) & \text{si } \text{total\_invested\_eur} > 0 \\ \text{None} & \text{si } n = 0 \end{cases}$$
8. **Curva diaria (`equity_curve`) y Drawdown máximo (`max_drawdown_pct`):**
   - Para cada día $t \in [\text{start\_date}, \text{end\_date}]$:
     - $P_t = \text{close}(t)$ si existe vela en $t$; en caso contrario $P_t = \text{last\_close\_on\_or\_before}(t)$ (para que un hipotético día sin precio no hunda la gráfica a cero).
     - $V_t = \text{round\_half\_up\_2}(\text{btc\_accumulated}_t \times P_t)$.
     - $\text{peak}_t = \max_{u \le t} V_u$.
     - Si $\text{peak}_t > 0$: $\text{dd}_t = \text{round\_half\_up\_2}\left(\left(\dfrac{V_t}{\text{peak}_t} - 1\right) \times 100\right)$; si $\text{peak}_t = 0$: $\text{dd}_t = 0{,}00$.
   - $\text{max\_drawdown\_pct} = \min_{t} \text{dd}_t$ (valor $\le 0{,}00\%$).

---

## F. Adquisición, validación y almacenamiento de datos históricos

### F.1 Fuentes verificadas

| Dato | Fuente primaria | Endpoint verificado | Cobertura | Regla de cierre diario |
|---|---|---|---|---|
| Fear & Greed diario | **BGeometrics** (republica alternative.me) | `https://charts.bgeometrics.com/files/fear_greed.json` | Desde `2018-02-01` (39 días sin dato en 22 huecos) | Se importan los registros con fecha $\le \text{last\_closed\_utc\_day}$. |
| Fear & Greed (respaldo) | **alternative.me** | `https://api.alternative.me/fng/?limit=0&format=json` | Idéntica (`2018-02-01` → hoy) | Respaldo automático si BGeometrics no responde. |
| Precios BTC/EUR diarios | **Bitstamp** | `https://www.bitstamp.net/api/v2/ohlc/btceur/?step=86400&limit=1000&start=...&end=...` | Desde `2018-01-01` (y antes) sin un solo hueco | Solo se consolidan velas de días UTC ya finalizados ($\text{day} < \text{today\_utc}$). |
| Precios BTC/EUR (validación) | **Kraken** | `https://api.kraken.com/0/public/OHLC?pair=XXBTZEUR&interval=1440&since=...` | Desde 2013 | Uso opcional para contraste de precios. |

### F.2 Sincronización y regla de "día cerrado" (`services/data_service.py`)

- Sea `last_closed_day = datetime.now(UTC).date() - timedelta(days=1)`.
- Cuando se ejecuta `sync_data.py` (o el botón *"Actualizar datos"* desde la web):
  1. Se descargan los ficheros crudos en `data/raw/` (inmutables, con su hash SHA-256 en `MANIFEST.json`).
  2. Se filtran e insertan en SQLite **únicamente los registros con `day <= last_closed_day`**, garantizando que ningún día a medio terminar entre jamás en un backtest.
  3. Se ejecutan las validaciones (`dataset_checks.py`):
     - Ningún valor del índice fuera de `[0, 100]` ni fechas duplicadas.
     - Coherencia OHLC en cada vela (`low <= open <= high`, `low <= close <= high`, `low > 0`).
     - Continuidad diaria de precios desde `2018-01-01` hasta `last_closed_day`.

---

## G. Plan de pruebas

### G.1 Tests unitarios (`tests/unit/`)

| Caso de prueba | Resultado esperado |
|---|---|
| Bordes de los tramos por defecto en lunes: valores `9`, `10`, `14`, `15`, `19`, `20`, `24`, `25` | `9` → diaria `50 €`; `10` y `14` → `200 €`; `15` y `19` → `150 €`; `20` y `24` → `100 €`; `25` → sin compra. |
| Prevalencia de la regla diaria en lunes: lunes con índice `8` | Se ejecuta **una sola compra de `50 €`** (`daily_<10`), nunca una semanal. |
| Día entre martes y domingo con índice `12` | Sin compra (los tramos `10..24` solo aplican en lunes). |
| Día entre martes y domingo con índice `7` | Compra diaria de `50 €`. |
| Lunes sin dato de índice (hueco) | Sin compra. |
| Personalización de tramos e importes desde `FearGreedParams` | Si se cambia el tramo `[20..24]` a `[20..30]` con `120 €`, compra `120 €` los lunes con valor `28`; si dos tramos se solapan, Pydantic lanza `ValidationError`. |
| Redondeo exacto a satoshi (`ROUND_DOWN`) | `100,00 €` a precio `73 067,27 €` → `0,00136860 BTC` (`0,0013686018...` truncado al 8º decimal). |
| Cálculo de métricas con compras conocidas: `100 € @ 10 000 €` (`0,01000000 BTC`) + `100 € @ 20 000 €` (`0,00500000 BTC`), precio final `30 000 €` | Invertido = `200,00 €`; BTC = `0,01500000`; Coste medio = `13 333,33 €`; Valor final = `450,00 €`; P&L = `+250,00 €`; ROI = `+125,00 %`. |
| Drawdown sintético: `1 BTC` constante, cierres `[100, 120, 60, 90, 150]` | `max_drawdown_pct = -50,00 %`. |
| Día intermedio sin vela de precio en `build_equity_curve` | Usa el cierre del día anterior (`last_close_on_or_before`); el valor de la cartera no cae a `0 €`. |
| Simulación con 0 compras (p. ej. rango corto donde el índice siempre es `>= 25`) | `total_operations = 0`, `total_invested_eur = 0,00`, `average_buy_price_eur = None`, `roi_pct = None`, `max_drawdown_pct = 0,00` (sin errores de división por cero). |
| Property-based (`hypothesis`) | Para cualquier lista de `Fill` y precios positivos: `btc_accumulated == sum(f.btc_quantity)`, `portfolio_value_eur >= 0`, `max_drawdown_pct <= 0`. |

### G.2 Tests de integración y regresión sobre datos reales (`tests/integration/`)

- **Test de regresión en ventana fija `2018-02-01` → `2026-10-18`** con parámetros por defecto:
  - Como la ventana `[2018-02-01, 2026-10-18]` ya está cerrada en el pasado, aunque en el futuro se sincronicen datos de nuevos días (20 oct, 21 oct, 2027…), ejecutar el backtest acotando `start_date = 2018-02-01` y `end_date = 2026-10-18` debe producir **siempre**:
    - **`total_operations == 121`** (`42` diarias `<10`, `23` en `10-14`, `20` en `15-19`, `36` en `20-24`).
    - **`total_invested_eur == Decimal("13300.00")`**.
- **Test de reproducibilidad:** dos ejecuciones con la misma configuración y el mismo `dataset_hash` producen exactamente el mismo `result_hash`.

---

## H. Fases de implementación (ordenadas por dependencias)

| Fase | Descripción | Criterios de aceptación verificables |
|---|---|---|
| **F0 — Esqueleto y herramientas** | `pyproject.toml` (uv), estructura `src/backtesting_cripto/` en inglés, ruff, mypy, pytest. | `uv run ruff check`, `uv run mypy src` y `uv run pytest` pasan en verde. |
| **F1 — Modelos de dominio y contratos** | `domain/models.py`, `domain/contracts.py`, validación de tramos e importes (`FearGreedParams`). | Tests unitarios de validación de tramos (solapamientos rechazados) y serialización canónica en verde. |
| **F2 — Ingesta y almacenamiento de datos** | Proveedores (`bgeometrics_fng`, `alternative_me_fng`, `bitstamp_ohlc`), `raw_store` con SHA-256, SQLite `repository` y `sync_data.py` filtrando hasta el último día cerrado (`D-1`). | Ejecución de `sync_data.py` crea `MANIFEST.json` y pobla SQLite desde `2018-02-01` (F&G) y `2018-01-01` (precios) hasta el último día cerrado; tests de integridad de datos en verde. |
| **F3 — Motor, cartera y métricas** | `engine/calendar.py`, `engine/execution.py` (`close_same_day` y `close_next_day`), `engine/portfolio.py`, `engine/runner.py` y `metrics/calculator.py`. | Todos los tests unitarios de cartera, redondeo a 8/2 decimales, curva con precio anterior ante hueco y métricas (§G.1) en verde. |
| **F4 — Estrategia Fear & Greed** | `strategies/fear_greed.py` con tramos e importes configurables y registro en `StrategyRegistry`. | Test de regresión sobre `[2018-02-01, 2026-10-18]` devuelve exactamente **121 compras y `13 300,00 €` invertidos**. |
| **F5 — Persistencia de ejecuciones y API REST** | `storage/run_store.py`, `services/backtest_service.py`, `api/routes.py` (`GET /api/strategies`, `GET /api/data/status`, `POST /api/data/sync`, `POST /api/backtests`, `GET /api/backtests/{id}`). | Tests de integración de API en verde; cada ejecución queda guardada con su `config_hash`, `dataset_hash` y `result_hash`. |
| **F6 — Interfaz web (Jinja2 + HTMX + Plotly.js)** | Pantalla en español: selector de activo y estrategia, selector de fechas (acotado al inicio disponible de la estrategia y al último día cerrado), edición de tramos e importes en €, selector `close_same_day`/`close_next_day`, botón de sincronizar datos, tarjetas con todas las métricas (incluido Drawdown), gráficos interactivos (Capital invertido vs. Valor de cartera; evolución del índice con marcadores de compras) y tabla detallada de las operaciones individuales. | Navegable en local; permite lanzar simulaciones cambiando fechas, tramos e importes y ver gráficas, métricas y tabla de compras al instante. |
| **F7 — Documentación final y pulido** | `README.md` con instrucciones de arranque en 3 comandos, `docs/fuentes-de-datos.md` y `docs/metricas.md`; atribución visible a alternative.me y Bitstamp. | Suite completa de tests en verde y documentación verificada. |

---

## I. Riesgos, limitaciones de los datos y medidas de mitigación

| Riesgo / limitación | Evidencia | Mitigación implementada |
|---|---|---|
| **El índice Fear & Greed no existe antes del `2018-02-01`** | Verificado en el JSON original | Cada estrategia declara sus indicadores requeridos; el sistema fija automáticamente el inicio mínimo de `fear_greed` en `2018-02-01` (mientras que estrategias futuras sin ese indicador podrán usar `2018-01-01` o anterior). |
| **El día en curso aún no tiene vela diaria cerrada** | Bitstamp cierra la vela diaria a las `23:59:59 UTC` | Regla estricta: un día no computa hasta que ha terminado en UTC y su vela diaria está cerrada (`last_closed_day = today_utc - 1`). |
| **39 días sin valor en el histórico del índice (22 huecos)** | Verificado en el JSON | Política explícita y determinista: día sin dato = no se compra. |
| **Hora exacta de publicación diaria del índice no documentada** | alternative.me solo publica timestamp `00:00 UTC` | Por defecto se ejecuta al cierre del mismo día `D` (`23:59:59 UTC`), e incluimos el modo `close_next_day` (`D+1`) en la UI para comprobar el impacto de ejecutar un día después. |
| **El JSON de BGeometrics no tiene SLA garantizado** | Servidor estático de terceros | Copia local inmutable en `data/raw/` con SHA-256 (los backtests funcionan 100 % offline) + proveedor de respaldo automático contra la API oficial de `alternative.me`. |
| **Solapamiento al editar tramos en la interfaz web** | Usuario podría introducir p. ej. `[10-16]` y `[15-20]` | Validación en `FearGreedParams` (y en el formulario web) que impide tramos solapados o por debajo del umbral diario antes de ejecutar. |
| **Errores de coma flotante** | `float` binario en Python | Uso exclusivo de `decimal.Decimal` con cuantización explícita a `8` decimales en BTC (`ROUND_DOWN`) y `2` decimales en EUR (`ROUND_HALF_UP`). |
