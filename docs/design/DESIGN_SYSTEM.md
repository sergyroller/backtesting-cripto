# Sistema de diseño y especificación UX/UI — backtesting-cripto

**Documento maestro de diseño.** Fuente de verdad para la implementación de la interfaz web (fase F6 y posteriores).

- **Proyecto:** backtesting-cripto — plataforma de backtesting de estrategias de acumulación de criptomonedas (v1: BTC/EUR + Crypto Fear & Greed Index).
- **Estado:** validado y aprobado con el usuario (listo para implementar en F6).
- **Versión:** 0.2.0 · **Fecha:** 2026-10-19 · **Autoría:** equipo de diseño (revisado y alineado con `docs/planificacion.md`).
- **Alcance:** diseño visual, UX, sistema de diseño y arquitectura técnica del frontend. **No** incluye implementación.
- **Documentos relacionados:** [`../planificacion.md`](../planificacion.md) (documento rector), [`../notas-arquitectura.md`](../notas-arquitectura.md) (estado de fases).
- **Recursos auxiliares:** [`tokens.css`](./tokens.css) (tokens de referencia), [`plotly-theme.js`](./plotly-theme.js) (configuración de gráficos de referencia).

---

## 1. Resumen ejecutivo

Este documento define la identidad visual, la experiencia de usuario y el sistema de diseño de la plataforma de backtesting. Las decisiones principales son:

| Área | Decisión | Motivo principal |
|---|---|---|
| Dirección visual | "Fintech premium sobrio": datos primero, jerarquía tipográfica, superficies planas con bordes finos, casi sin sombras | Transmitir rigor y confianza; evitar el aspecto de plantilla admin y de terminal de trading |
| Base CSS | **CSS propio con design tokens** (custom properties + cascade layers), sin framework | Control total de la identidad, cero CSS muerto, sin riesgo de mantenimiento externo (Pico CSS está archivado) |
| Interactividad | **htmx 2.0.10** (línea estable; 4.0.0 existe pero no es aún la línea `latest`) | Stack acordado en planificación; documentación y ecosistema estables |
| Gráficos | **Plotly.js** bundle parcial `cartesian` servido localmente, con tema derivado de los tokens CSS | Potencia sin toolchain; el bundle parcial reduce el peso ~3× frente al completo |
| Tipografía | **Inter** (variable, SIL OFL 1.1) para UI y cifras (`tnum`); **IBM Plex Mono** (SIL OFL 1.1) opcional para identificadores técnicos | Legibilidad en pantalla, cifras tabulares nativas, licencias que permiten servicio local |
| Iconos | **Lucide** (ISC), SVG inline mediante parciales Jinja2, sin JS | Trazo consistente de 2 px, servicio local, sin dependencia de runtime |
| Color de marca | `#0DC3A4` (obligatorio) como token `--color-brand` y color semántico positivo en datos; **no** se usa como texto pequeño en tema claro (2.24:1, insuficiente) | Cumple el mandato y la accesibilidad con variantes derivadas verificadas |
| Color negativo | `#CE2C31` (claro) / `#F2555A` (oscuro) | 5.21:1 y 5.07:1 verificados; rojo frío equilibrado frente al teal |
| Temas | `system` (por defecto) / `light` / `dark`, resueltos con script inline pre-pintado en `<head>`, persistencia en `localStorage` | Sin FOUC, sin dependencia de cookies, compatible con Jinja2 + HTMX |
| Navegación | **Barra superior** (tableta/escritorio) + **barra inferior** (móvil), **3 vistas claras**: **Simulador** (`/`), **Historial** (`/backtests`), **Datos** (`/data`); selector de tema en cabecera | Navegación directa sin páginas vacías ni comparador acoplado en v1; mobile first real |
| Densidad | Tres niveles de jerarquía de métricas (primarias, secundarias, supuestos) | Evita tanto la sobrecarga como la ocultación excesiva |

El sistema está diseñado para crecer (multi-activo, multi-estrategia, comparaciones) sin romper las convenciones: los tokens son semánticos y no mencionan ni estrategias ni activos concretos.

---

## 2. Objetivos y principios de diseño

### 2.1. Objetivos de producto

1. **Comprensión rápida:** el usuario debe poder evaluar el resultado de un backtest en menos de 10 segundos (valor de cartera, capital invertido, P&L, periodo).
2. **Profundización sin fricción:** desde cualquier métrica agregada se llega al detalle (operaciones individuales, curva diaria, supuestos) en un máximo de 2 interacciones.
3. **Transparencia financiera:** ninguna cifra relevante aparece sin su contexto (periodo, base de cálculo, fecha de los datos, supuestos de simulación).
4. **Confianza técnica:** los datos faltantes, parciales o desactualizados se comunican explícitamente; nunca se maquillan.
5. **Neutralidad emocional:** la interfaz no celebra ganancias ni dramatiza pérdidas; presenta hechos con formato claro y signos explícitos.

### 2.2. Principios de diseño (ordenados por prioridad)

1. **Los datos mandan.** La decoración nunca compite con la información. Si un elemento no responde a una pregunta analítica o a una acción del usuario, sobra.
2. **Jerarquía antes que densidad.** Mostrar muchos datos está bien si cada uno tiene su peso visual correcto. Prohibido mostrar todas las métricas con el mismo tamaño.
3. **Precisión visible.** Las cifras financieras usan siempre el formato exacto del dominio: EUR y % con 2 decimales, BTC con 8, con separadores españoles y signo explícito en valores con signo.
4. **Estados honestos.** Vacío, cargando, error, parcial y desactualizado son estados de primer nivel con diseño propio, no ocurrencias tardías.
5. **Mobile first de verdad.** Cada pantalla se diseña primero para 360 px de ancho y se expande con propósito; nunca se encoge un diseño de escritorio.
6. **Accesibilidad como requisito, no como capa.** WCAG 2.2 AA verificable (contraste medido, foco visible, teclado, lectores de pantalla).
7. **Consistencia mecánica.** Una decisión se toma una vez (token) y se aplica en todas partes (CSS, Plotly, plantillas).
8. **Sin magia de build.** Todo lo que se sirve al navegador es un archivo estático legible: CSS, JS y fuentes locales, sin compilación.

### 2.3. Lo que este producto no es

- No es un exchange ni una app de trading en tiempo real: no hay tickers parpadeantes, ni verdes/rojos constantes, ni sensación de urgencia.
- No es un panel de marketing: no hay hero headlines ni llamadas emocionales.
- No es una plantilla de administración genérica: cada bloque tiene una razón analítica documentada.

---

## 3. Dirección artística y personalidad visual

### 3.1. Concepto: "fintech premium sobrio"

La interfaz se sitúa deliberadamente entre tres referencias, tomando principios —no apariencia— de cada una:

| Referencia | Qué se toma | Qué se evita |
|---|---|---|
| **Linear** (herramienta de producto) | Jerarquía tipográfica estricta, superficies planas, bordes finos en lugar de sombras, foco visible elegante | Su estética "developer tool" demasiado oscura por defecto |
| **Stripe Dashboard** (fintech) | Claridad en métricas monetarias, tablas densas pero respirables, estados vacíos útiles | Su densidad de menús y su escala (producto enorme) |
| **TradingView** (analítica, solo como referencia de gráficos) | Legibilidad de series temporales, crosshair/tooltip preciso | Su estética de terminal recargada, paneles infinitos, negro absoluto |
| **Revolut / N26** (fintech consumo, solo como contra-referencia) | — | Gamificación, redondeo excesivo, ilustraciones decorativas |

Principios sintetizados (no copiados):

- **Superficies planas con bordes de 1 px** en lugar de sombras y tarjetas anidadas. La separación se consigue con espacio y con un único nivel de borde `--color-border-subtle`.
- **Un solo color de acento con trabajo real.** El teal `#0DC3A4` aparece en datos positivos, elementos interactivos clave y marca. No se usa como decoración de fondos.
- **Tipografía como ornamento.** El refinamiento viene de la escala tipográfica, el tracking de las etiquetas en versalitas, la alineación numérica tabular y el espaciado consistente.
- **Calma cromática.** Los fondos son neutros con un ligero sesgo azul-grisáceo (frio, técnico) que hace brillar el acento teal por contraste de saturación, no por estridencia.

### 3.2. Personalidad

| Dimensión | Posición |
|---|---|
| Serio ↔ Lúdico | Serio (9/10) |
| Denso ↔ Espacioso | Equilibrado con tendencia a denso en tablas (6/10) |
| Técnico ↔ Comercial | Técnico (8/10) |
| Minimalista ↔ Rico | Minimalista funcional (7/10) |
| Frío ↔ Cálido | Frío neutro con acento vivo (7/10) |

### 3.3. Reglas de estilo vinculantes

1. **Prohibido** usar degradados decorativos, glassmorphism, neomorfismo o sombras de más de 2 niveles de elevación.
2. **Prohibido** el negro puro `#000000` y el blanco puro como fondo de aplicación en modo oscuro; el oscuro usa azul-gris muy oscuro (ver §5).
3. **Prohibido** usar color como único canal semántico: todo valor con signo lleva `+`/`−` y, cuando sea relevante, etiqueta textual ("beneficio", "pérdida").
4. **Prohibido** animar cifras con contadores crecientes o efectos que exageren resultados.
5. Los iconos nunca decoran: o comunican estado o disparan acción. Sin icono "de relleno".
6. Toda pantalla muestra la **fecha de cobertura de los datos** (p. ej. "Datos hasta el 18 oct 2026") en una posición fija y predecible (cabecera de contexto, §11.3).

---

## 4. Bibliotecas y decisiones tecnológicas

### 4.1. Resumen de la selección

| Capa | Selección | Versión fijada | Licencia | Servicio |
|---|---|---|---|---|
| Interactividad parcial | htmx | **2.0.10** | Zero-Clause BSD (0BSD) | Local (`static/vendor/`) |
| Gráficos | Plotly.js, bundle parcial **cartesian** | **3.7.0** (ver §4.5) | MIT | Local (`static/vendor/`) |
| CSS base | **Propio** (tokens + componentes) | — | — | `static/css/` |
| Iconos | Lucide (SVG inline vía Jinja2) | set estable 2026 | ISC (partes Feather: MIT) | Inline en plantillas |
| Tipografía UI | Inter (variable) | 4.1 | SIL OFL 1.1 | Local WOFF2 |
| Tipografía técnica | IBM Plex Mono (Regular/Medium) | 6.x | SIL OFL 1.1 | Local WOFF2 |
| Reset/normalize | Reset propio mínimo (~40 líneas) | — | — | `static/css/base.css` |

**Total de JavaScript de terceros servido al cliente: 2 archivos** (`htmx.min.js` ≈ 14 kB gzip, `plotly-cartesian.min.js` ≈ 465–505 kB gzip). Sin CDN en producción, sin cookies de terceros, sin fuentes externas en runtime.

### 4.2. Comparativa de frameworks CSS

| Criterio | Bootstrap 5.3.8 | Bulma 1.0.4 | Pico CSS 2.1.1 | **CSS propio (elegido)** |
|---|---|---|---|---|
| Licencia | MIT | MIT | MIT | — |
| Estado (oct 2026) | Activo (v6 en alpha) | Activo (última pub. hace ~1 año) | **Archivado, sin mantenimiento (anuncio oficial)** | — |
| Peso CSS min | ~232 kB (completo) | ~226 kB (completo) | ~80–100 kB | ~25–35 kB estimado (solo lo necesario) |
| Tema claro/oscuro | `data-bs-theme` nativo | Dark mode nativo v1 | `data-theme` nativo | Nativo por diseño (custom properties) |
| JS propio | Sí (Popper + plugins; innecesario con HTMX) | No (solo CSS) | Mínimo | No |
| Aspecto por defecto | Muy reconocible ("admin genérico") | Reconocible | Sobrio pero genérico | **Identidad propia** |
| Encaje con HTMX | Correcto, pero hay que evitar su JS | Bueno | Bueno | Total |
| Riesgo | Sobrecarga conceptual y visual; difícil no parecer Bootstrap | Ecosistema menor | Dependencia de un proyecto abandonado | Coste inicial de escribir componentes (una sola vez) |

**Decisión: CSS propio apoyado en tokens.** Justificación:

1. La dirección artística (§3) exige control fino de densidad, bordes y jerarquía que los frameworks solo permiten "a golpe de override", generando CSS muerto y especificidad conflictiva.
2. El catálogo de componentes necesario es cerrado y pequeño (§13): ~18 componentes. El coste es asumible y se paga una vez.
3. Pico CSS, el candidato más afín estéticamente, fue **archivado oficialmente por su autor** (v2.1.1 es la versión final; [repositorio](https://github.com/picocss/pico)). Empezar un producto nuevo en 2026 sobre una base sin mantenimiento es un riesgo evitable.
4. Bootstrap y Bulma arrastran convenciones visuales reconocibles que el brief prohíbe expresamente ("aspecto de plantilla genérica").
5. CSS moderno (custom properties, `@layer`, grid, container queries, `:focus-visible`) cubre nativamente todo lo necesario sin polyfills en los navegadores objetivo.

**Descartadas también:** Tailwind (requiere build/Node, prohibido), UIkit (JS propio redundante con HTMX), Open Props (se evaluó como fuente de tokens: preferimos tokens propios, mínimos y auditados; su escala completa es innecesaria).

### 4.3. htmx

- **Versión fijada: 2.0.10** (línea 2.x, [releases](https://github.com/bigskysoftware/htmx/releases)). La **4.0.0** se publicó el 2026-08-28, pero los propios autores la mantienen fuera del tag `latest` de npm hasta principios de 2027 y la documentación de referencia (htmx.org) sigue describiendo la línea 2.x. Se adopta 2.0.10 por documentación, estabilidad y ecosistema (ejemplos, extensiones). La migración a 4.x se evaluará en F7+ como tarea independiente.
- **Licencia:** [Zero-Clause BSD](https://github.com/bigskysoftware/htmx/blob/master/LICENSE) — permite servicio local sin obligaciones.
- **Servicio:** `static/vendor/htmx-2.0.10.min.js` con atributo `integrity` (SRI) y `defer`.
- **Uso previsto:** envío del formulario de simulación, refresco de fragmentos (métricas, tabla de operaciones, estados de datos), validación de tramos en servidor y paginación. Todo lo demás (tema, diálogos nativos, tooltips CSS) se resuelve sin htmx.

### 4.4. Plotly.js

- **Bundle:** parcial **`cartesian`** (scatter, bar, box, histogram, heatmap…), suficiente para todas las visualizaciones de v1. El bundle completo (~1,5 MB gzip) queda descartado.
- **Versión:** la rama `main` del repositorio publica **4.1.2** en CDN; en npm el paquete `plotly.js` tiene como `latest` la línea **3.x** (3.7.0 documentada en el `dist/README` de la rama `master`, 464,8 kB gzip el cartesian). **Decisión operativa: fijar `3.7.0` del paquete `plotly.js-cartesian-dist-min` y verificar en F6 la disponibilidad/estabilidad de la línea 4.x antes de actualizar.** Lo importante para el diseño es que la API de layout/config que aquí se especifica es estable en ambas líneas.
- **Licencia:** [MIT](https://github.com/plotly/plotly.js/blob/master/LICENSE) — permite servicio local.
- **Alternativas evaluadas y descartadas:**
  - **Chart.js 4** (MIT): más ligero (~75 kB gzip) pero tooltips y crosshair temporal notablemente peores para series diarias largas; menor control de ejes de fecha. Se reconsideraría solo si el peso de Plotly resultara inaceptable en la práctica (§21).
  - **uPlot** (MIT): rendimiento excelente y ~45 kB, pero exige escribir tooltips, leyendas y responsive a mano: más JS personalizado del permitido por el brief.
  - **ApexCharts**: cambios de licencia en versiones recientes (ya no siempre MIT); descartado por prudencia.
  - **D3**: potencia innecesaria y demasiado código propio.
- **Integración con temas:** un único módulo JS (`static/js/charts.js`, basado en [`plotly-theme.js`](./plotly-theme.js)) lee las custom properties con `getComputedStyle` y construye el layout; ante un cambio de tema se llama `Plotly.relayout()` sobre los gráficos registrados (§12.7). No hay framework JS ni estado distribuido: un array `window.__btCharts` y un evento `document` personalizado.

### 4.5. Iconografía

- **Selección: [Lucide](https://lucide.dev/)** — licencia [ISC](https://lucide.dev/license) (los iconos derivados de Feather son MIT), trazo uniforme de 2 px sobre grid de 24 px, geometría sobria y técnica, catálogo amplio con todos los iconos financieros/de análisis necesarios.
- **Integración sin JS:** los ~30 iconos usados se copian como SVG a `web/templates/partials/icons/<nombre>.svg` y se incluyen con Jinja2 (`{% include %}`), con `class="icon"` para heredar `currentColor`. No se usa `lucide.js` en cliente ni sprite externo (ver §15.2).
- **Descartadas:** Bootstrap Icons (MIT; estilo mixto trazo/relleno menos consistente), Heroicons (MIT; orientado a Tailwind y menos cobertura técnica), Tabler (MIT; estética más redondeada/juvenil), Font Awesome Free (CC-BY 4.0 con atribución visible; peso).

### 4.6. Tipografías (detalle y licencias en §6)

- **Inter 4.1** (SIL OFL 1.1, [rsms/inter](https://github.com/rsms/inter)): variable con eje de peso 100–900, `tnum` (cifras tabulares), `case`, cero con barra opcional. WOFF2 local.
- **IBM Plex Mono** (SIL OFL 1.1, [IBM/plex](https://github.com/IBM/plex)): solo Regular 400 y Medium 500, para identificadores técnicos (hashes, `run_id`) y, opcionalmente, cantidades BTC de 8 decimales. Carga diferida y con `font-display: swap`.

### 4.7. Recursos locales y política de terceros

| Recurso | Origen de descarga (una vez, en desarrollo) | Destino servido |
|---|---|---|
| `htmx-2.0.10.min.js` | `https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js` (verificar hash SRI oficial) | `static/vendor/` |
| `plotly-cartesian-3.7.0.min.js` | `https://cdn.plot.ly/plotly-cartesian-3.7.0.min.js` | `static/vendor/` |
| Inter variable WOFF2 | Release oficial 4.1 en GitHub (`rsms/inter`) | `static/fonts/` |
| IBM Plex Mono WOFF2 | Release oficial en GitHub (`IBM/plex`) | `static/fonts/` |
| Iconos Lucide SVG | `https://lucide.dev/icons/` (descarga individual) | `templates/partials/icons/` |

Toda incorporación de un recurso de terceros exige: (1) registrar versión, URL, hash y licencia en `docs/fuentes-de-datos.md` o un `NOTICE` de frontend; (2) servirlo localmente; (3) no introducir nuevas dependencias sin actualizar este documento.

---

## 5. Paleta de colores y tokens semánticos

### 5.1. Método

- Todos los pares texto/fondo relevantes se han **medido con la fórmula de contraste WCAG 2.x** (luminancia relativa sRGB). Los ratios que aparecen en las tablas son valores calculados, no estimaciones.
- Objetivo: **WCAG 2.2 AA** — texto normal ≥ 4.5:1, texto grande (≥ 18,66 px bold o ≥ 24 px) y componentes de interacción ≥ 3:1.
- Los colores se organizan en **tres capas**: primitivos (escala), semánticos (función) y de componente. Las plantillas y los gráficos solo consumen tokens semánticos.
- Ningún token semántico menciona un componente concreto (`--color-positive`, no `--color-badge-green`), para que el sistema sobreviva a nuevas pantallas.

### 5.2. Color de marca y color positivo (obligatorio: `#0DC3A4`)

`#0DC3A4` es el **token de marca** (`--color-brand`) y, a la vez, el color semántico de **resultados positivos en datos** (curvas, marcadores, deltas). Es un teal luminoso: en tema claro **no** alcanza contraste como texto pequeño (2.24:1 sobre blanco — medido), por lo que se define una variante de texto derivada.

| Token | Claro | Oscuro | Función |
|---|---|---|---|
| `--color-brand` | `#0DC3A4` | `#0DC3A4` | Marca, logotipo, series positivas en gráficos, marcadores de compra |
| `--color-positive` | `#0DC3A4` | `#0DC3A4` | Deltas/P&L positivos en gráficos y elementos grandes (≥ 24 px o bold ≥ 18,66 px) |
| `--color-positive-text` | `#0A7C68` | `#0DC3A4` | Texto de tamaño normal que comunica positivo (contraste verificado: 5.13:1 / 7.63:1) |
| `--color-positive-subtle` | `#E3F6F1` | `#10302A` | Fondo de badges/indicadores positivos (texto `--color-positive-text` encima: 4.57:1 / 6.33:1) |

### 5.3. Color negativo (selección justificada)

**Elegido: `#CE2C31` (tema claro) y `#F2555A` (tema oscuro).**

Criterios aplicados:

1. **Contraste AA verificado:** 5.21:1 sobre superficie clara; 5.07:1 sobre superficie oscura (ambos como texto normal). Los candidatos más vivos (`#D64550`, 4.35:1) fallaban por poco en claro; los más suaves (`#E5484D`, 4.37:1) fallaban en oscuro.
2. **Armonía con el teal:** es un rojo ligeramente frío (carmesí), complementario cromático del teal sin caer en el rojo anaranjado de "alerta de casino".
3. **Intensidad equilibrada:** su luminancia relativa es casi simétrica a la de `#0A7C68` (el teal de texto en claro), de modo que positivo y negativo "pesan" lo mismo visualmente: ninguna ganancia brilla más que una pérdida equivalente.
4. **Procedencia probada:** coincide con `red-11` de la escala Radix Colors (light) y su pareja oscura, escalas diseñadas precisamente para contraste accesible en UI.

| Token | Claro | Oscuro | Función |
|---|---|---|---|
| `--color-negative` | `#CE2C31` | `#F2555A` | P&L negativo, drawdown, texto y series (5.21:1 / 5.07:1) |
| `--color-negative-subtle` | `#FDEEEF` | `#351B20` | Fondo de badges/alertas negativas (texto `--color-negative` encima: 4.63:1 / 4.68:1) |

### 5.4. Resto de la paleta semántica

| Token | Claro | Oscuro | Contraste (texto/superficie) | Función |
|---|---|---|---|---|
| `--color-info` | `#2F5FC7` | `#7FA6F2` | 5.86:1 / 7.04:1 | Mensajes informativos, series neutras secundarias |
| `--color-info-subtle` | `#E9EFFC` | `#1D2942` | (info encima) 5.09:1 / 5.97:1 | Fondos informativos |
| `--color-warning` | `#946200` | `#E3B25E` | 5.24:1 / 8.80:1 | Datos desactualizados, validaciones suaves |
| `--color-warning-subtle` | `#FBF1DC` | `#37291A` | (warning encima) 4.67:1 / 7.22:1 | Fondos de aviso |
| `--color-error` | `#CE2C31` | `#F2555A` | 5.21:1 / 5.07:1 | Errores de formulario y de sistema (comparte valor con negative; son tokens distintos) |
| `--color-fng` | `#6D5FD3` | `#A79CF0` | 4.97:1 / 7.06:1 | Serie del Fear & Greed Index en gráficos (violeta: deliberadamente **ni verde ni rojo**, §12.4) |

> **Regla:** `--color-error` y `--color-negative` comparten valor pero no significado: *negative* describe un resultado financiero (una pérdida no es un fallo); *error* describe un fallo de validación o de sistema. Si en el futuro se quiere diferenciarlos visualmente, solo hay que cambiar un token.

### 5.5. Neutros, fondos y texto

**Tema claro**

| Token | Valor | Contraste medido | Uso |
|---|---|---|---|
| `--color-bg-app` | `#F5F7F9` | — | Fondo de aplicación |
| `--color-surface-1` | `#FFFFFF` | — | Superficie base (tarjetas, tablas, paneles) |
| `--color-surface-2` | `#F0F2F5` | — | Superficie hundida/elevada suave (cabeceras de tabla, zonas de filtros) |
| `--color-text-1` | `#171B22` | 17.27:1 sobre surface-1 | Texto principal, cifras |
| `--color-text-2` | `#5A6372` | 6.07:1 | Texto secundario, etiquetas, ejes |
| `--color-text-3` | `#8A93A1` | 3.10:1 | Metadatos no críticos, placeholders (AA-large) |
| `--color-text-disabled` | `#9AA2AF` | 2.57:1 (exento WCAG) | Texto deshabilitado |
| `--color-border-subtle` | `#E4E8EE` | (decorativo) | Bordes de tarjetas, separadores |
| `--color-border-control` | `#7D8694` | 3.68:1 | Bordes de inputs y controles (≥ 3:1 exigido) |
| `--color-border-strong` | `#CBD2DC` | (decorativo) | Hover de bordes decorativos |
| `--color-tooltip-bg` | `#1B212B` | texto `#F4F6F8` encima: 14.92:1 | Tooltips (invertido) |

**Tema oscuro**

| Token | Valor | Contraste medido | Uso |
|---|---|---|---|
| `--color-bg-app` | `#0E131A` | — | Fondo de aplicación (azul-gris, no negro) |
| `--color-surface-1` | `#161C25` | — | Superficie base |
| `--color-surface-2` | `#1D2530` | — | Superficie elevada (menús, diálogos, cabeceras) |
| `--color-text-1` | `#E8EBF0` | 14.32:1 sobre surface-1 | Texto principal |
| `--color-text-2` | `#9AA5B3` | 6.85:1 | Texto secundario |
| `--color-text-3` | `#6B7686` | 3.72:1 | Metadatos (AA-large) |
| `--color-text-disabled` | `#5F6979` | 3.08:1 (exento WCAG) | Texto deshabilitado |
| `--color-border-subtle` | `#28303D` | (decorativo) | Bordes y separadores |
| `--color-border-control` | `#667181` | 3.46:1 | Bordes de inputs (≥ 3:1) |
| `--color-border-strong` | `#3A4554` | (decorativo) | Hover de bordes |
| `--color-tooltip-bg` | `#F4F6F8` | texto `#171B22` encima: 15.94:1 | Tooltips (invertido) |

> Las diferencias entre `surface-1`/`surface-2`/`bg-app` (~1.1:1) son **deliberadamente sutiles**: la separación de regiones la aporta `--color-border-subtle` + espaciado, no el contraste de fondo. Los bordes decorativos y las cuadrículas de gráficos (~1.2:1) no son componentes de interacción y están exentos del 3:1; los bordes de controles sí lo cumplen (`border-control`).

### 5.6. Colores de acción (botones, enlaces, foco)

Decisión deliberada de identidad (§3): **el botón primario no es verde en ambos temas.**

| Token | Claro | Oscuro | Contraste medido |
|---|---|---|---|
| `--color-action-bg` | `#171B22` (tinta) | `#0DC3A4` (marca) | — |
| `--color-action-text` | `#FFFFFF` | `#06302A` | 17.27:1 / 6.39:1 ✅ |
| `--color-action-bg-hover` | `#2A303B` | `#2BD0B2` | (texto encima) 13.25:1 / 8.76:1 ✅ |
| `--color-link` | `#0A7C68` | `#2BD0B2` | 4.77:1 sobre bg-app / 9.56:1 ✅ |
| `--color-focus` | `#0A7C68` | `#2BD0B2` | 5.13:1 / 9.56:1 (≥ 3:1 exigido) |

Justificación: en el tema claro, un botón tinta casi negro con texto blanco es lo más sobrio y "premium" (el verde queda reservado a los datos, que es donde debe mirar el usuario); en el tema oscuro, el botón en verde marca `#0DC3A4` con tinta oscura encima aporta la identidad de marca sin ruido y con 6.39:1 medidos. El verde nunca dice "compra ya": la app no ejecuta operaciones reales.

### 5.7. Reglas de uso semántico

1. Todo valor monetizado con signo usa **signo tipográfico explícito** (`+2 450,00 €` / `−380,00 €`, con U+2212 para el menos), color `--color-positive-text`/`--color-negative` y, cuando el contexto no sea obvio, etiqueta ("beneficio", "pérdida").
2. `--color-brand`/`--color-positive` puro (`#0DC3A4`) **solo** en: gráficos (series, marcadores), iconos ≥ 24 px, texto grande (≥ 24 px o bold ≥ 18,66 px) en tema claro; sin restricción de tamaño en oscuro (7.63:1).
3. El violeta `--color-fng` está reservado al índice Fear & Greed: ninguna otra serie lo usa (leyenda del sistema de gráficos, §12.4).
4. Fondos sutiles (`*-subtle`) solo con su texto semántico emparejado (tablas de la §5.2–5.5). Nunca texto `--color-text-1` sobre un fondo semántico.
5. El rojo de `--color-error` nunca se usa para resultados financieros negativos en gráficos de marketing inverso (p. ej. no "colorear de rojo" periodos sin compra).

---

## 6. Tipografía

### 6.1. Selección

| Rol | Familia | Por qué |
|---|---|---|
| UI general y cifras financieras | **Inter** (variable, 4.1) | Diseñada para pantalla (x-height alta, aperturas abiertas); `tnum` da cifras tabulares sin segunda familia; `case` mejora etiquetas con signos; SIL OFL 1.1 permite servicio local y subseteo |
| Identificadores técnicos y código | **IBM Plex Mono** 400/500 | Hashes, `run_id`, endpoints; refuerza la credibilidad técnica. Opcional para cantidades BTC de 8 decimales si se desea más carácter "terminal" |
| Fallbacks del sistema | `system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` / `ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace` | Sin FOUC tipográfico inaceptable si las WOFF2 no cargan |

**Descartadas:** IBM Plex Sans (OFL; excelente pero su doble papel UI+dato queda cubierto por Inter + `tnum` con menos peso de descarga), Roboto (aspecto genérico Android), Source Sans 3 (menos personalidad), JetBrains Mono como mono (más ancha; Plex Mono es más sobria).

### 6.2. Servicio local y formato

- Archivos en `static/fonts/`: `InterVariable.woff2` (peso 100–900) y, si se quiere itálica real, `InterVariable-Italic.woff2`; `IBMPlexMono-Regular.woff2`, `IBMPlexMono-Medium.woff2`.
- Subseteo opcional (herramienta de desarrollo, no de build en producción): latin + latin-ext con `pyftsubset` (fontTools, Python — no rompe la regla "sin Node").
- `@font-face` con `font-display: swap` y `preload` del archivo de Inter en la plantilla base.
- Licencias SIL OFL 1.1: permiten uso, redistribución y subseteo; obligación: conservar el aviso de copyright (incluir `OFL.txt` en `static/fonts/` y nota en el NOTICE de frontend).

### 6.3. Escala tipográfica

Base 16 px (`1 rem`). Escala modular ≈ 1,25 con ajustes ópticos para datos:

| Token | Tamaño | Altura de línea | Peso habitual | Uso |
|---|---|---|---|---|
| `--text-xs` | 0,75 rem (12 px) | 1,33 | 500–600 | Etiquetas de métricas (versalitas, tracking 0,04 em), badges, cabeceras de tabla |
| `--text-sm` | 0,8125 rem (13 px) | 1,4 | 400–500 | Texto auxiliar, metadatos, tabla densa |
| `--text-base` | 1 rem (16 px) | 1,5 | 400 | Cuerpo, inputs, celdas |
| `--text-md` | 1,125 rem (18 px) | 1,45 | 400–500 | Introducciones, valores secundarios |
| `--text-lg` | 1,25 rem (20 px) | 1,35 | 600 | Títulos de sección (h3) |
| `--text-xl` | 1,5 rem (24 px) | 1,25 | 600 | Títulos de página (h1/h2) |
| `--text-2xl` | 1,875 rem (30 px) | 1,2 | 600 | Valor de métrica primaria (escritorio) |
| `--text-3xl` | 2,25 rem (36 px) | 1,15 | 600 | Excepcional: hero numérico de página de detalle |

Reglas:

- **Tamaño mínimo absoluto: 12 px** (`--text-xs`), solo para etiquetas y cabeceras de tabla en versalitas. Nunca para valores que el usuario deba leer y comparar.
- **Valores monetarios principales:** `--text-xl` (24 px) en móvil → 1,75 rem (28 px) en tableta → `--text-2xl` (30 px) en escritorio, peso 600, siempre con `font-feature-settings: "tnum"` (coherente con §11.3 y §14.2).
- **Cifras en tablas y ejes de gráficos:** `tnum` obligatorio; alineación a la derecha en columnas numéricas.
- **Tracking:** solo en versalitas de etiqueta (`letter-spacing: 0.04em`). Nunca tracking negativo en cuerpo.
- Pesos disponibles: 400/500/600/700. El 300 (light) está **prohibido** en texto ≤ 16 px (legibilidad).

### 6.4. Clases tipográficas semánticas

| Clase | Composición | Uso |
|---|---|---|
| `.t-metric-label` | xs, 600, versalitas, tracking 0,04 em, `--color-text-2` | "VALOR DE CARTERA" |
| `.t-metric-value` | 28→30 px, 600, tnum, `--color-text-1` | "14 782,35 €" |
| `.t-metric-delta` | sm, 600, tnum, color semántico + signo | "+11,15 %" |
| `.t-caption` | sm, 400, `--color-text-2` | "Datos hasta el 18 oct 2026" |
| `.t-code` | Plex Mono 500, sm | `a1b2c3d4…` (hash de configuración) |

### 6.5. Formato numérico (norma de producto)

| Magnitud | Formato | Ejemplo |
|---|---|---|
| EUR | miles con espacio fino (U+202F), decimal con coma, 2 decimales, símbolo `€` pospuesto con espacio | `13 300,00 €` |
| Porcentaje | 2 decimales, coma, signo explícito si es un delta | `+125,00 %` / `−50,00 %` |
| BTC | 8 decimales, coma decimal, sufijo ` BTC` | `0,00136860 BTC` |
| Precio €/BTC | como EUR | `73 067,27 €` |
| Valor del índice F&G | entero 0–100, sin unidad, con etiqueta ("Índice: 12") | `12` |
| Fechas | formato corto español | `18 oct 2026` |
| Valor ausente | `—` (em dash) + tooltip/leyenda explicativa | nunca `0` ni cadena vacía |

El formateo se realiza **en servidor** (filtros Jinja2: `eur`, `pct`, `btc`, `date_es`) para que HTMX y la página inicial compartan exactamente el mismo formato. En gráficos Plotly, §12.5 define la equivalencia.

---

## 7. Espaciado, dimensiones y superficies

### 7.1. Escala de espaciado (base 4 px)

| Token | Valor | Uso típico |
|---|---|---|
| `--space-1` | 0,25 rem (4 px) | Separación icono-texto, huecos internos mínimos |
| `--space-2` | 0,5 rem (8 px) | Entre elementos relacionados (label-input, badge-icono) |
| `--space-3` | 0,75 rem (12 px) | Padding interno de badges y chips; gap de grupos de botones |
| `--space-4` | 1 rem (16 px) | Padding de tarjetas (móvil), gap entre campos |
| `--space-5` | 1,25 rem (20 px) | Padding de tarjetas (escritorio), separación de subgrupos |
| `--space-6` | 1,5 rem (24 px) | Separación entre bloques de una vista |
| `--space-8` | 2 rem (32 px) | Padding lateral de página (escritorio), separación de secciones |
| `--space-10` | 2,5 rem (40 px) | Aire superior de secciones principales |
| `--space-12` | 3 rem (48 px) | Separación entre grandes regiones |
| `--space-16` | 4 rem (64 px) | Estados vacíos, márgenes de páginas de baja densidad |

Excepción permitida y documentada: las filas de tabla densa usan alturas de 40 px (escritorio) / 48 px (móvil) (ver §13.7) aunque no sean múltiplos de 4 en su padding vertical (8 px + line-height), porque la métrica vinculante es la altura total de fila.

### 7.2. Márgenes y anchuras de página

| Contexto | Valor |
|---|---|
| Padding lateral de página | 16 px (móvil) · 24 px (≥ 640 px) · 32 px (≥ 1024 px) |
| Anchura máxima del contenedor | 1280 px centrado |
| Anchura máxima de texto corrido | 68 caracteres (~65 ch) |
| Anchura de columna de formularios | máx. 560 px en formularios estándar; el formulario de simulación (complejo, con filas de tramos) llega a 720 px (§14.2). Ningún formulario se estira a 1280 px |
| Altura de cabecera de app | 56 px (móvil) / 64 px (escritorio) |
| Altura de barra inferior (móvil) | 64 px + `safe-area-inset-bottom` |

### 7.3. Radios, bordes y elevación

| Token | Valor | Uso |
|---|---|---|
| `--radius-sm` | 4 px | Badges, chips, tooltips |
| `--radius-md` | 8 px | Botones, inputs, selects |
| `--radius-lg` | 12 px | Tarjetas, paneles, diálogos, contenedores de gráfico |
| `--radius-full` | 999 px | Indicadores puntuales (dots), toggle de tema |
| `--border-width` | 1 px | Todos los bordes (2 px solo en foco) |

Elevación (uso restrictivo: **solo** elementos realmente superpuestos):

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `--shadow-1` | `0 1px 2px rgb(23 27 34 / 0.06)` | `0 1px 2px rgb(0 0 0 / 0.40)` | Menús desplegables, tooltips |
| `--shadow-2` | `0 8px 24px rgb(23 27 34 / 0.12)` | `0 8px 24px rgb(0 0 0 / 0.50)` | Diálogos, sheet móvil |

Tarjetas y tablas: **borde de 1 px `--color-border-subtle`, sin sombra.** Esta es una decisión de identidad (§3).

### 7.4. Densidad de componentes (resumen; detalle en §13)

| Componente | Altura móvil | Altura escritorio |
|---|---|---|
| Botón / input / select | 44 px (objetivo táctil) | 40 px |
| Fila de tabla | 48 px (con expansión táctil) | 40 px |
| Destino de navegación | 48 px | 40 px |
| Icono en botón | 18 px | 16–18 px |
| Icono standalone | 20–24 px | 20 px |

### 7.5. Iconos

Tamaños permitidos: 16, 18, 20, 24 px (trazo 2 px, escalado por `stroke-width` constante gracias a SVG). Regla de alineación: el icono se alinea a la línea base del texto mediante `vertical-align: -0.125em` cuando va inline (§15.3).

---

## 8. Temas claro, oscuro y automático

### 8.1. Modelo de preferencias

Tres valores posibles para `theme-preference`:

| Valor | Significado |
|---|---|
| `system` (por defecto) | Sigue a `prefers-color-scheme` del SO, reaccionando a sus cambios en vivo |
| `light` | Fuerza claro |
| `dark` | Fuerza oscuro |

Reglas:

1. La selección manual (`light`/`dark`) prevalece sobre el sistema hasta que el usuario vuelve a elegir `system`.
2. Persistencia en `localStorage["theme-preference"]`. No se usa cookie: el tema se resuelve íntegramente en cliente (§8.2), por lo que el servidor nunca necesita conocerlo y HTMX no requiere sincronización adicional.
3. El tema efectivo se materializa como `data-theme="light" | "dark"` en `<html>`; los tokens CSS cuelgan de `:root` y de `[data-theme="dark"]`.

### 8.2. Resolución sin destello (anti-FOUC)

Script **inline y síncrono** en el `<head>`, antes de cualquier hoja de estilo visible (≤ 1 kB, justificado como excepción a "sin JS inline"):

```html
<script>
(function () {
  var pref = null;
  try { pref = localStorage.getItem("theme-preference"); } catch (e) {}
  if (pref !== "light" && pref !== "dark") {
    pref = "system";
  }
  var dark = pref === "dark" ||
    (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.documentElement.dataset.themePreference = pref;
})();
</script>
<meta name="color-scheme" content="light dark">
```

`color-scheme` declara al navegador que ambos temas son posibles (scrollbars, controles nativos coherentes). En CSS:

```css
:root { color-scheme: light; /* + tokens claros */ }
[data-theme="dark"] { color-scheme: dark; /* + tokens oscuros */ }
```

### 8.3. Cambio de tema en runtime

Módulo `static/js/theme.js` (~60 líneas):

1. `setThemePreference("light" | "dark" | "system")`: guarda en `localStorage`, actualiza `data-theme`/`data-theme-preference` y emite `document.dispatchEvent(new CustomEvent("bt:theme-changed", { detail: { theme } }))`.
2. Listener de `matchMedia("(prefers-color-scheme: dark)")` que solo re-aplica cuando la preferencia es `system`.
3. `charts.js` escucha `bt:theme-changed` y actualiza los gráficos registrados con `Plotly.relayout()` (§12.7).

**Compatibilidad con HTMX:** los swaps de HTMX sustituyen fragmentos internos del DOM; `<html data-theme>` nunca se toca, así que los fragmentos recibidos heredan el tema automáticamente. Única precaución: todo fragmento debe usar tokens semánticos (nunca valores hex hardcodeados en plantillas parciales). El cambio de tema **no** provoca transiciones de color masivas: la transición de colores de fondo/texto se limita a 120 ms y se desactiva por completo con `prefers-reduced-motion` (§16.5).

### 8.4. Control de tema (componente)

- Control compacto en la **cabecera superior** en todos los tamaños: segmented control (`Claro / Oscuro / Sistema`) en escritorio o botón de icono (sol/luna/monitor) con menú desplegable en móvil.
- El estado activo se comunica con `aria-checked` o `aria-pressed`, nunca solo con color.
- Especificación completa en §13.16.

---

## 9. Arquitectura de información

### 9.1. Mapa de navegación (simplificado a 3 vistas en v1)

Siguiendo el principio de simplicidad acordado con el usuario en `docs/planificacion.md` (§A.1: **sin comparador cruzado en v1** y sin páginas de relleno), la aplicación se estructura en **3 vistas claras**:

```mermaid
graph TD
    A[1. Simulador / Panel (/)] --> A1[Formulario de parámetros + Resultado en vivo]
    A1 --> A2[Pestaña Resumen y Gráficos]
    A1 --> A3[Pestaña Operaciones]
    A1 --> A4[Pestaña Supuestos y Metadatos]
    B[2. Historial (/backtests)] --> B1[Listado de simulaciones guardadas]
    B1 --> B2[Detalle de simulación (/backtests/{run_id})]
    C[3. Datos (/data)] --> C1[Estado de fuentes, cobertura hasta D-1, huecos y botón Actualizar datos]
```

| Destino | Ruta | Contenido | Frecuencia prevista |
|---|---|---|---|
| **Simulador** | `/` | Vista principal: formulario configurable (fechas, umbral e importe diario, tramos semanales, modo `close_same_day`/`close_next_day`) + resultado completo de la simulación activa (o de la simulación de referencia al entrar) | Alta |
| **Historial** | `/backtests` | Tabla de simulaciones ejecutadas y guardadas en SQLite (`run_id`, fecha, estrategia, periodo, capital invertido, BTC, P&L, ROI) con acceso a su detalle inmutable (`/backtests/{run_id}`) | Media |
| **Datos** | `/data` | Cobertura por fuente (`bgeometrics`/`alternative.me` y `bitstamp`), último día cerrado UTC (`D-1`), huecos conocidos (39 días), botón "Actualizar datos" y atribuciones | Media |

Decisiones de alcance y agrupación (validadas con el usuario):

- **Sin sección "Comparar" (`/compare`) en v1:** cada simulación es independiente (`docs/planificacion.md`, §A.1).
- **Sin página suelta de "Ajustes" (`/settings`):** el selector de tema (`Claro / Oscuro / Sistema`) vive directamente en la cabecera superior y las atribuciones en el pie y en `/data`.
- **"Historial de operaciones" no existe como sección global:** las operaciones pertenecen a un `run_id` concreto y viven en la pestaña "Operaciones" del resultado de la simulación.
- **"Estrategias" no es destino de primer nivel en v1** porque solo existe una estrategia (`fear_greed`), seleccionable directamente en el formulario del Simulador.

### 9.2. Patrón de navegación elegido (justificado)

Opciones comparadas:

| Patrón | Pros | Contras | Veredicto |
|---|---|---|---|
| Sidebar fija | Escalable a muchas secciones | Roba 240 px de ancho a los gráficos; exceso para 3 destinos; en móvil exige drawer adicional | Descartada |
| **Barra superior** | Máximo ancho para datos/gráficos; 3 destinos caben holgadamente; patrón limpio | — | **Elegida en tableta/escritorio (≥ 640 px)** |
| **Barra inferior** | Pulgar al alcance; 3 destinos con icono + etiqueta caben con aire | Ocupa 64 px verticales | **Elegida en móvil (< 640 px)** |
| Navegación por hamburguesa | Oculta todo | Añade un clic innecesario para solo 3 vistas | Descartada |

**Coherencia entre versiones:** mismo orden (`Simulador`, `Historial`, `Datos`), mismos iconos, mismas etiquetas y mismo estado activo (indicador de 2 px `--color-brand` + peso 600). La cabecera superior existe en todos los tamaños (marca + estado de datos "Datos hasta…" + selector de tema).

### 9.3. Estados de navegación

- **Activo:** `aria-current="page"`, texto peso 600, indicador de 2 px `--color-brand` (abajo en topbar, arriba en bottom bar) — nunca solo color.
- **Hover:** fondo `--color-surface-2` (escritorio/tableta).
- **Foco:** anillo `--color-focus` 2 px, offset 2 px.
- **Con badge:** el destino "Datos" muestra un punto ámbar (`--color-warning`) cuando hay datos desactualizados (> 2 días cerrados sin sincronizar) — punto + texto accesible, no solo color.

### 9.4. Acciones principales y secundarias

| Acción | Jerarquía | Ubicación |
|---|---|---|
| Ejecutar simulación | Primaria (botón `--color-action`) | Formulario del Simulador (`/`) |
| Actualizar datos | Secundaria | Cabecera de contexto (junto a "Datos hasta…") y vista Datos (`/data`) |
| Cambiar tema | Terciaria | Cabecera superior (todos los tamaños) |

---

## 10. Navegación y recorridos UX

Convención: los pasos indican pantalla → acción → resultado. Los errores posibles van al final de cada recorrido. Todos los formularios validan en servidor (Pydantic) y devuelven fragmentos HTMX con errores junto al campo (§13.15).

### 10.1. Configurar y ejecutar una simulación (flujo principal en `/`)

1. Al abrir **Simulador (`/`)**, el usuario ve el panel de configuración de la estrategia (precargado con los valores por defecto: `2018-02-01` → último día cerrado, diaria `< 10` con `50 €`, tramos en lunes `10–14: 200 €`, `15–19: 150 €`, `20–24: 100 €`, modo `close_same_day`) y los resultados de la última ejecución (o estado inicial listo para simular).
2. Edición de tramos: filas `mín–máx–importe (€)` con añadir/eliminar; validación por servidor: si hay solapamientos o invasión del umbral diario, muestra el error específico junto al campo.
3. **Ejecutar simulación** → envía por HTMX (`POST /api/backtests` o endpoint HTML parcial), muestra skeleton durante el cálculo (≤ 1 s en local), guarda el run en SQLite y actualiza el bloque de resultados (métricas, gráficos, tabla de operaciones y metadatos/hashes) con toast `"Simulación completada"`.

Errores: fechas fuera de rango disponible (mensaje con `[min_available_date, max_available_date]`), tramos solapados (error específico por fila), fallo inesperado (toast de error + el formulario conserva los valores).

### 10.2. Cambiar el periodo de análisis

1. En el formulario del Simulador (`/`), o pulsando `"Cargar estos parámetros en el simulador"` desde un detalle de `/backtests/{run_id}` (los runs pasados son inmutables).
2. Atajos de periodo: chips `1 A · 3 A · 5 A · Todo` que rellenan `start_date`/`end_date` (`end_date = last_closed_day`).
3. Ejecutar → genera un nuevo run inmutable sin sobrescribir los anteriores.

Errores: rango invertido o fuera de cobertura → validación en `<input type="date">` (`min`/`max`) + validación servidor (`ConfigurationError`).

### 10.3. Consultar una simulación guardada en el Historial (`/backtests`)

1. **Historial (`/backtests`)** → lista cada ejecución guardada con: fecha de creación, estrategia, ventana `[start_date, end_date]`, modo de ejecución, capital invertido, BTC acumulados, P&L (€) y ROI (%).
2. Clic/tap en una fila → **Detalle de simulación (`/backtests/{run_id}`)**: muestra las métricas, los gráficos y las pestañas *Resumen / Operaciones / Supuestos* de ese run junto con su `run_id`, `config_hash`, `dataset_hash` y `result_hash`.

Errores: `run_id` inexistente → página 404 con enlace a `/backtests`.

### 10.4. Inspeccionar las operaciones individuales (`Fill`)

1. En los resultados del Simulador (`/`) o en el detalle de un run (`/backtests/{run_id}`) → pestaña **Operaciones**.
2. **Columnas en escritorio (7 columnas exactas):**
   1. `#` (nº secuencial de operación `1..N`),
   2. `Fecha` (`execution_day`; si difiere de `decision_day` en modo `close_next_day`, muestra subtítulo o badge `señal: YYYY-MM-DD`),
   3. `Índice F&G` (`index_value` entero),
   4. `Regla` (`reason` formateada legible, p. ej. `Diaria (< 10)`, `Lunes 10–14`),
   5. `Importe` (`amount_eur` en €),
   6. `Precio BTC` (`price_eur` en €/BTC),
   7. `BTC comprados` (`btc_quantity` con 8 decimales).
3. **En móvil (< 640 px):** se muestran las **4 columnas prioritarias** (`Fecha`, `Regla`, `Importe`, `BTC comprados`) y al pulsar una fila se despliega el detalle completo (`#`, `Día decisión`, `Día ejecución`, `Índice F&G`, `Precio BTC`).
4. Filtrado por regla (chips: `Todas`, `Diaria <10`, `Lunes 10–14`, `Lunes 15–19`, `Lunes 20–24`) y paginación por HTMX (50 filas por página).

### 10.5. Revisar el estado de datos y sincronizar (`/data`)

1. Cualquier pantalla muestra en la cabecera la cobertura actual: `"Datos hasta el 18 oct 2026"` (último día UTC cerrado).
2. **Datos (`/data`)** → tarjetas/tabla de fuentes (`bgeometrics`/`alternative.me` y `bitstamp`): primer día, último día cerrado, total de registros, `sha256` / `dataset_hash` y botón **"Actualizar datos"** (`POST /api/data/sync` vía HTMX con estado de carga y resumen de actualización).
3. Muestra también la información de los huecos históricos conocidos del índice (39 días sin dato en 22 huecos) y la regla aplicada (`día sin dato = no se compra`).

### 10.6. Cambiar el tema (Claro / Oscuro / Sistema)

1. Desde el control de tema en la **cabecera superior** → cambio inmediato sin recarga + persistencia en `localStorage["theme-preference"]`.
2. El evento `bt:theme-changed` actualiza al instante el layout y los colores de las series de todos los gráficos Plotly vivos (`Plotly.relayout` + `Plotly.restyle`, §12.7).

---

## 11. Diseño del dashboard (Panel)

### 11.1. Objetivo

Responder en una pantalla: *"¿Cómo va la estrategia con la configuración actual, sobre qué periodo, con datos hasta qué día, y dónde profundizo?"*

### 11.2. Composición y jerarquía

Orden vertical (móvil) y rejilla (escritorio) de **cinco bloques**:

**Bloque A — Cabecera de contexto (siempre visible):** título de la estrategia + periodo analizado (`1 feb 2018 – 18 oct 2026`) + estado de datos ("Datos hasta el 18 oct 2026" + badge si está desactualizado) + botones secundarios (Editar configuración, Actualizar datos).

**Bloque B — Métricas primarias (4 tarjetas grandes, con las cifras reales del dataset congelado `2018-02-01` → `2026-10-18`):**

| Orden | Métrica | Valor real de referencia | Subtexto |
|---|---|---|---|
| 1 | **Valor de la cartera** | `80 401,26 €` | al cierre del 18 oct 2026 (`73 067,27 €/BTC`) |
| 2 | **Beneficio/Pérdida** | `+67 101,26 €` | `+504,52 %` en el periodo (color + signo) |
| 3 | **Capital invertido** | `13 300,00 €` | 121 operaciones |
| 4 | **BTC acumulado** | `1,10037310 BTC` | coste medio `12 086,81 €/BTC` |

> Orden deliberado: el resultado (valor y P&L) precede al esfuerzo (invertido). Invertido y valor **nunca** se fusionan en una sola cifra ni se presentan sin etiqueta.

**Bloque C — Gráfico principal:** *Capital invertido vs. valor de mercado* (2 series + marcadores de compra). Altura 320 px móvil / 420 px escritorio. Debajo, una línea de ayuda: "Cada punto es un día; los triángulos son compras ejecutadas."

**Bloque D — Métricas secundarias (fila compacta, 2×2 en móvil, 4×1 en escritorio):** Drawdown máximo (`−50,00 %`), Nº de operaciones por regla (resumen textual), precio final BTC/EUR, modo de ejecución (`cierre del mismo día`).

**Bloque E — Dos gráficos secundarios en tarjetas de igual altura (apilados en móvil):** *Índice Fear & Greed con compras* (línea violeta + marcadores) y *Operaciones por tramo del índice* (barras horizontales teal). Enlace "Ver todas las operaciones →" que lleva a la pestaña Operaciones del detalle.

**Supuestos (pie del bloque E, `.t-caption`):** "Simulación sin comisiones ni deslizamiento · Ejecución al cierre UTC del día de la señal · Un día computa cuando su vela cierra en UTC".

### 11.3. Variantes responsive

| Elemento | Móvil (< 640) | Tableta (640–1023) | Escritorio (≥ 1024) |
|---|---|---|---|
| Métricas primarias | 2×2 grid, valor 24 px | 2×2, valor 28 px | 4×1, valor 30 px |
| Gráfico principal | 320 px alto, leyenda inferior | 380 px | 420 px, leyenda derecha opcional |
| Secundarias | 2×2 compacto | 4×1 | 4×1 |
| Gráficos secundarios | apilados | apilados | 2 columnas 50 % |
| Supuestos | colapsado en `<details>` | línea de texto | línea de texto |

### 11.4. Estados del dashboard

| Estado | Diseño |
|---|---|
| **Sin datos sincronizados** | Empty state global: icono `database`, título "Aún no hay datos históricos", texto explicativo, botón primario "Descargar datos" (dispara `sync`) |
| **Sin simulaciones** | Panel con empty state: "Ejecuta tu primera simulación" + botón primario +, debajo, tarjeta informativa con la configuración por defecto y el invariante conocido (121 compras / 13 300,00 € en el rango de referencia) |
| **Cargando (HTMX)** | Skeletons con la misma geometría del contenido (§13.12): sin spinner a pantalla completa |
| **Datos desactualizados (> 2 días)** | Badge ámbar en cabecera de contexto + banner `--color-warning-subtle` con botón "Actualizar datos"; los resultados siguen visibles (no se bloquea nada) |
| **Error de simulación** | Toast de error + formulario con valores conservados |
| **Resultados con incidentes** | Badge info "2 incidentes" en el detalle; la pestaña Supuestos los lista (p. ej. `missing_price_on_2023-03-11`) |
| **Datos parciales (estrategia futura con menos cobertura)** | Aviso info junto al periodo: "El índice X solo existe desde el …" |

### 11.5. Anti-sobrecarga

- Máximo 4 métricas primarias; el resto son secundarias (tamaño 16 px) o viven en pestañas.
- Un solo gráfico "héroe" por pantalla; los demás son secundarios y más bajos.
- Nada parpadea ni se actualiza solo: es análisis histórico, no tiempo real.

---

## 12. Sistema de gráficos (Plotly.js)

### 12.1. Principios

1. Cada gráfico responde a **una pregunta analítica concreta** (tabla §12.3). Prohibido añadir gráficos decorativos.
2. **Un solo lenguaje visual:** mismas fuentes, mismos tokens, mismo tooltip, mismo formato numérico en todos los gráficos.
3. Los gráficos heredan el tema mediante los tokens CSS (§12.7); nunca llevan colores hex incrustados en las plantillas.
4. Todo gráfico tiene **alternativa textual** (tabla plegable o resumen `aria`) (§17.3).

### 12.2. Configuración base compartida

Archivo de referencia: [`plotly-theme.js`](./plotly-theme.js). Resumen normativo:

| Propiedad | Valor |
|---|---|
| `font.family` | Inter con fallbacks (misma pila que CSS) |
| `font.size` | 12 (ejes) / 13 (tooltip) |
| `font.color` | `--color-text-2` |
| `paper_bgcolor` / `plot_bgcolor` | transparente (hereda la superficie de la tarjeta) |
| `margin` | `{ l: 56, r: 16, t: 8, b: 40 }` (móvil: `{ l: 48, r: 8, t: 8, b: 56 }` para leyenda inferior) |
| Cuadrícula | `gridcolor`: claro `#E8ECF1` / oscuro `#242D3A` (decorativa); solo horizontal por defecto |
| Ejes | línea de eje oculta (`showline: false`), ticks externos, `tickfont` 12 px con `tnum` |
| Tooltip | `bgcolor`/`font` invertidos según `--color-tooltip-*`, borde `border-subtle`, `hovermode: "x unified"` en series temporales |
| Leyenda | horizontal, bajo el gráfico en móvil; texto 12 px |
| Config | `responsive: true`, `displaylogo: false`, `displayModeBar: false` en táctil / `"hover"` en escritorio, `modeBarButtonsToRemove: ["lasso2d","select2d","autoScale2d"]` |
| Formato numérico | `layout.separators = ",\u202F"` (decimal `,`, miles espacio fino); **fallback verificado en F6: `",."`** si el carácter U+202F diera problemas de renderizado en algún navegador (documentar la elección final en el código) |
| Locale | registrar locale `es` de Plotly si el bundle lo permite; si no, `separators` + nombres de mes propios en los ticks de fecha (`%e %b %Y` con meses ES desde servidor) |

### 12.3. Catálogo de visualizaciones (v1)

| # | Pregunta | Tipo | Series/codificación |
|---|---|---|---|
| G1 | ¿Cuánto vale mi cartera frente a lo que he invertido? | Líneas temporales superpuestas + área bajo "invertido" | Invertido: `--color-text-2` (`meta.role = "invested"`, línea 1,5 px + área al 8 %); Valor: `--color-brand` (`meta.role = "portfolio"`, 2 px); marcadores de compra: triángulos `--color-brand` (`meta.role = "buys"`) |
| G2 | ¿Qué hacía el índice cuando se compró? | Línea temporal (0–100) + marcadores | Índice: `--color-fng` (`meta.role = "fng"`, 1,5 px); compras: triángulos `--color-brand` (`meta.role = "buys"`), tamaño ∝ importe (3 tamaños discretos, leyenda) |
| G3 | ¿En qué tramos del índice se concentran las compras? | Barras horizontales | Una serie `--color-brand`; etiquetas de tramo (`0–9 diaria`, `10–14`, …); valores al final de barra |
| G4 | ¿Cuánto se ha caído desde máximos? | Área temporal (drawdown, ≤ 0) | `--color-negative` (`meta.role = "drawdown"`), área al 15 %; eje Y invertido visual (valores negativos hacia abajo), máximo anotado |
| G5 (futuro) | Distribución de precios de compra | Histograma | `--color-info` |

Regla de color por serie: **teal = la estrategia/dinero del usuario; violeta = el índice; rojo = pérdida/drawdown; azul = información neutra; ámbar = aviso**. Nunca verde y rojo en la misma escala categórica (riesgo de lectura como "bueno/malo" de categorías neutras).

### 12.4. El índice Fear & Greed sin colisión semántica

El índice tiene sus propias categorías (miedo extremo…codicia extrema), tradicionalmente coloreadas rojo→verde. En esta app **rojo/verde ya significan pérdida/ganancia de cartera**, así que:

- La línea del índice es **violeta** (`--color-fng`).
- Las zonas de fondo del índice (0–24, 25–49, 50–74, 75–100) se dibujan con **grises alternos al 4–6 % de opacidad** y etiqueta textual en el eje derecho ("Miedo extremo", …), no con rojos/verdes.
- Las compras se marcan en teal: el usuario aprende en una lectura que "compras = teal = mi dinero".

### 12.5. Formatos en ejes y tooltips

- Eje Y euros: `~s` con separadores ES (`13,3 k` se evita: mejor ticks explícitos `0`, `20 000`, `40 000`, `60 000`, `80 000` vía `tickvals` cuando el rango lo permita).
- Tooltip G1: líneas `Día: 18 oct 2026`, `Invertido: 13 300,00 €`, `Valor: 80 401,26 €`, `Diferencia: +67 101,26 € (+504,52 %)`.
- Tooltip G2: `Día`, `Índice: 12 (miedo extremo)`, `Compra: 50,00 € a 73 067,27 € → 0,00068430 BTC`.
- Los valores se formatean **en servidor** y viajan en `customdata`: JS solo los imprime. Así HTMX y gráficos comparten formato exacto.

### 12.6. Comportamiento responsive

| Aspecto | Móvil (< 640) | Escritorio |
|---|---|---|
| Altura G1 | 320 px | 420 px |
| Altura G2/G3/G4 | 240–280 px | 280–320 px |
| Leyenda | horizontal inferior, wrap | inferior o derecha |
| Eje X | 3–4 ticks (`%b %y`) | 6–10 ticks |
| Modebar | oculta (`displayModeBar: false`) | visible al hover |
| Zoom | `dragmode: "pan"` + botones de rango (1A/3A/Todo) | zoom con rueda permitido (`scrollZoom: true` solo en G1/G2) |
| Tooltip | tap fija el tooltip (comportamiento nativo Plotly en táctil) | hover |

Redimensionamiento: `responsive: true` + `Plotly.Plots.resize()` en `ResizeObserver` del contenedor (necesario tras swaps HTMX que cambian el layout; §16.4).

### 12.7. Sincronización con el tema

1. `charts.js` construye el layout leyendo tokens con `getComputedStyle(document.documentElement).getPropertyValue("--color-…")`.
2. Cada traza lleva `meta: { role: "invested" | "portfolio" | "buys" | "fng" | "drawdown" }` y cada gráfico creado se registra en `window.__btCharts`.
3. Ante `bt:theme-changed`: se ejecuta `Plotly.relayout(div, baseLayout(isMobile))` **y además `Plotly.restyle(div, ...)`** actualizando `line.color` y `marker.color` de cada traza según su `meta.role` (ya que `--color-text-2`, `--color-fng` y `--color-negative` cambian entre el tema claro y el oscuro).
4. En `DOMContentLoaded` y tras cualquier swap HTMX (`document.body.addEventListener("htmx:load", ...)`), `initChartsIn()` inicializa los nuevos `div[data-chart]` leyendo su `<script type="application/json" data-chart-for="<id>">` hermano, y redimensiona los gráficos existentes con `Plotly.Plots.resize()`.

### 12.8. Estados de los gráficos

- **Sin datos (0 compras):** el gráfico no se renderiza vacío; se muestra el empty state del bloque ("Sin operaciones en este periodo") con la curva de invertido=0 omitida.
- **Cargando:** skeleton rectangular con la altura final del gráfico (evita saltos de layout).
- **Error de datos:** tarjeta con mensaje y enlace a Datos.
- **Serie con huecos (índice):** `connectgaps: false` — los 39 días sin dato se ven como cortes honestos, con nota en la leyenda.

---

## 13. Catálogo de componentes

Convenciones: clases `.c-*` (componente), modificadores `.--*`, estados `.is-*`. Todos consumen tokens (§19). Los tamaños siguen §7.4. "HTMX" indica el patrón esperado.

### 13.1. Botón `.c-button`

- **Propósito:** acciones. **Variantes:** `--primary` (acción principal, máx. 1 visible por vista), `--secondary` (borde `border-control`, fondo transparente), `--ghost` (sin borde, para acciones terciarias), `--danger` (borde/texto `--color-error`; fondo `--color-negative-subtle` en hover).
- **Dimensiones:** altura 44 px (móvil) / 40 px (escritorio); padding `0 var(--space-4)`; radio `--radius-md`; fuente 15 px/600; icono 18 px con gap `--space-2`.
- **Estados:** hover (fondo `action-bg-hover` o `surface-2`), active (translateY(0) + oscurecido 4 %), focus-visible (anillo 2 px `--color-focus`, offset 2 px), disabled (`opacity .55`, `cursor: not-allowed`, sin hover), **loading** (`.is-loading`: spinner inline sustituye al icono, `aria-busy="true"`, texto conservado para no mover el layout).
- **HTMX:** `hx-indicator` apunta al propio botón → la clase `.htmx-request` activa el spinner vía CSS, sin JS.
- **No usar:** para navegación (usar enlace); dos `--primary` en el mismo grupo.

### 13.2. Enlace `.c-link`

Color `--color-link`, subrayado solo en hover (en texto corrido: subrayado permanente). Icono `external-link` (Lucide) solo si sale de la app. `:focus-visible` con anillo.

### 13.3. Campos `.c-field`, `.c-input`, `.c-select`

- Estructura: `<label>` visible siempre (prohibido placeholder como etiqueta), control, ayuda (`--color-text-2`, sm), error (debajo, `--color-error`, sm, icono `alert-circle` 16 px, `role="alert"`).
- Control: altura 44/40 px, borde `1px border-control`, radio md, fondo `surface-1`, padding `0 12 px`. Focus: borde `--color-focus` + anillo 2 px. Disabled: fondo `surface-2`, texto `text-disabled`. Error: borde `--color-error` (y mensaje; nunca solo borde rojo).
- `input[type=date]`: nativo, con `min`/`max`; en móvil usa el picker del SO (mejor UX que cualquier widget propio).
- **HTMX:** validación servidor con `hx-post` + `hx-trigger="change"` en grupos (tramos), devolviendo el fragmento `.c-field` con error; `aria-invalid="true"` y `aria-describedby` los pone el servidor en el fragmento devuelto.

### 13.4. Tarjeta `.c-card`

- Fondo `surface-1`, borde 1 px `border-subtle`, radio lg, padding `space-4` (móvil) / `space-5` (escritorio). **Sin sombra.** Variante `--interactive` (clicable: hover eleva borde a `border-strong` + cursor pointer; toda la tarjeta es un único `<a>`/`<button>` real para teclado, no `div` con onclick).
- **No anidar** `.c-card` dentro de `.c-card`: usar separadores o `surface-2`.

### 13.5. Tarjeta de métrica `.c-metric`

- Composición: `.t-metric-label` (versalitas), `.t-metric-value`, opcional `.t-metric-delta` con icono `trending-up`/`trending-down` y opcional `.t-caption`.
- Variantes de tamaño: `--lg` (primarias del dashboard), `--sm` (secundarias).
- Deltas: siempre signo + color +, si aplica, etiqueta ("en el periodo").
- Valor ausente: `—` + tooltip explicativo (nunca `0,00 €` cuando no hubo operaciones).

### 13.6. Badge / etiqueta semántica `.c-badge`

- Variantes `--positive`/`--negative`/`--warning`/`--info`/`--neutral`: fondo `*-subtle` + texto del color semántico emparejado (tabla §5), radio `--radius-full`, padding `2px 10px`, fuente xs 600, icono opcional 14 px.
- Usos: estado de datos ("Desactualizado"), incidentes, modo de ejecución. **No usar** como decoración ni para contadores triviales.

### 13.7. Tabla financiera `.c-table`

- Escritorio (7 columnas en tabla de operaciones: `#`, `Fecha`, `Índice F&G`, `Regla`, `Importe`, `Precio BTC`, `BTC comprados`): cabecera xs versalitas `text-2` sobre `surface-2`, filas 40 px, separador `border-subtle`, números a la derecha con `tnum`, texto a la izquierda, hover de fila `surface-2`, `th scope="col"`.
- Móvil: **columnas prioritarias** (máx. 4: `Fecha`, `Regla`, `Importe`, `BTC comprados`) + **fila expandible** (tap → detalle con `#`, `Día decisión`, `Día ejecución`, `Índice F&G` y `Precio BTC`, `aria-expanded`). El scroll horizontal se reserva como fallback para tablas > 6 columnas. Prohibido encoger cifras por debajo de 13 px.
- Paginación: 50 filas/página, controles "Anterior/Siguiente" + "Página X de Y", por HTMX (`hx-get` + `hx-target` al `<tbody>` + `hx-push-url`).

### 13.8. Tooltip `.c-tooltip`

- CSS puro con `data-tip` para casos simples (hover y focus; `tabindex="0"` en el disparador si no es interactivo). Posición preferente arriba; en móvil el equivalente es un `ⓘ` que abre un `<details>`/diálogo (los tooltips por hover no existen en táctil: toda información de tooltip debe tener vía alternativa).
- Fondo `--color-tooltip-bg`, texto invertido, radio sm, sombra 1, máx. 260 px.

### 13.9. Menú `.c-menu`

- Desplegable anclado al disparador (CSS `:focus-within`/popover API nativa), lista de `.c-menu-item` (40 px, icono 18 px opcional), fondo `surface-2`, borde `border-subtle`, sombra 1, radio md. Cierre con Esc y clic fuera; foco gestionado con JS mínimo (~30 líneas) o Popover API nativa (soporte amplio en 2026).
- Usos: selector de tema compacto, acciones de fila. **No usar** para navegación principal.

### 13.10. Navegación `.c-topnav` / `.c-bottomnav`

- Topnav: altura 64 px, 3 destinos (`Simulador`, `Historial`, `Datos`) con indicador de 2 px; bottomnav: 64 px + safe-area, 3 destinos con icono 22 px + etiqueta de 12 px (se respeta el mínimo absoluto). Estado activo: §9.3.

### 13.11. Diálogo `.c-dialog` y panel `.c-sheet`

- `<dialog>` nativo: fondo `surface-2`, radio lg, sombra 2, `::backdrop` negro al 40 % (claro) / 60 % (oscuro). Cierre Esc y botón explícito. Título h2 + contenido + acciones a la derecha (móvil: acciones apiladas, primaria arriba).
- `.c-sheet`: variante que entra desde abajo en móvil (filtros, detalle de operación). Animación §16.
- **No usar** diálogos para errores de campo (inline) ni para confirmaciones triviales.

### 13.12. Estados de carga `.c-skeleton`

- Bloques con la geometría exacta del contenido final (tarjetas métricas, rectángulo de gráfico, filas de tabla), fondo `surface-2` con shimmer (gradiente animado 1,2 s) **desactivado** con `prefers-reduced-motion` (queda estático).
- Patrón HTMX: `hx-indicator` sobre el contenedor + `aria-busy="true"`; el contenido entrante sustituye al skeleton con `hx-swap="innerHTML"`. Sin spinners a pantalla completa salvo bloqueo total de navegación (no existe ese caso).

### 13.13. Estado vacío `.c-empty`

- Icono Lucide 32 px `text-3`, título `--text-lg`, descripción sm `text-2` (máx. 2 líneas), acción primaria opcional. Padding vertical `space-16`/`space-12`. Ver §11.4 para los textos concretos.

### 13.14. Notificación `.c-toast`

- Contenedor fijo: móvil abajo-centro (sobre la bottomnav, con margen), escritorio arriba-derecha. Fondo `tooltip-bg` (invertido) o variante semántica con borde izquierdo de 3 px; icono de estado; cierre manual + auto-dismiss 6 s (pausa en hover/focus); `aria-live="polite"` (errores: `role="alert"`).
- Creación: el servidor devuelve el fragmento toast en la respuesta HTMX (oob swap). Máx. 3 apilados. Errores que requieren acción → banner persistente, no toast.

### 13.15. Errores y validación (patrón)

- Inline junto al campo (§13.3) +, en envío con varios errores, resumen al inicio del formulario con enlaces ancla a cada campo (`#error-summary`, `tabindex="-1"`, foco movido al resumen).
- Mensajes en español, específicos: "El tramo 15–20 solapa con 12–18" (nunca "valor inválido").

### 13.16. Control de tema `.c-theme-toggle`

- En cabecera (escritorio/tableta): segmented control de 3 opciones (`Claro / Oscuro / Sistema` con icono sol/luna/monitor), `role="radiogroup"` + `aria-checked`.
- En móvil: botón icono en cabecera que cicla o abre `.c-menu` con las 3 opciones.
- Ambas llaman a `setThemePreference()` (§8.3) sin recarga.

### 13.17. Filtros y chips `.c-chip`, `.c-filterbar`

- Chips de filtro (tramos de operaciones, reglas): 36 px altura, radio full, estado activo fondo `surface-2` + borde `border-control` + peso 600 (`aria-pressed`).
- Filterbar: fila con scroll horizontal en móvil (sin wrap infinito), sticky bajo la cabecera solo si la tabla/gráfico asociado ocupa > 1 viewport.
- Selectores de periodo: chips `1A · 3A · 5A · Todo` + dos `input[type=date]`.

### 13.18. Contenedor de gráfico `.c-chart`

- `.c-card` con título (lg), subtítulo/caption opcional (qué pregunta responde), div del gráfico con altura fija por breakpoint (§12.6), y `<details class="c-chart-alt">` con la tabla/resumen de datos (accesibilidad §17.3).

---

## 14. Responsive (mobile first)

### 14.1. Breakpoints (basados en contenido, no en dispositivos)

| Token | Valor | Razón |
|---|---|---|
| base | < 640 px | Móvil: una columna, bottomnav, métricas 2×2 |
| `--bp-md` | 640 px | Tableta vertical: cabe la topnav de 3 destinos + métricas 2×2 con aire |
| `--bp-lg` | 1024 px | Escritorio: métricas 4×1, gráficos secundarios en 2 columnas, tabla completa de 7 columnas (≈ 900 px de contenido útil) |
| `--bp-xl` | 1280 px | Contenedor alcanza su máximo; no hay más cambios de layout (sin breakpoint "por rellenar") |

### 14.2. Matriz de comportamiento

| Componente | < 640 px | 640–1023 px | ≥ 1024 px |
|---|---|---|---|
| Navegación | bottomnav fija | topnav | topnav |
| Métricas primarias | grid 2×2, valor 24 px | 2×2, valor 28 px | 4×1, valor 30 px |
| Métricas secundarias | 2×2 | 4×1 | 4×1 |
| Gráfico G1 | 320 px, leyenda inferior | 380 px | 420 px |
| G2+G3 | apilados | apilados | 2 columnas |
| Tabla operaciones | 4 columnas + fila expandible | 6 columnas | 7 columnas |
| Formulario simulación | 1 columna, controles 44 px | 1 columna, máx. 560 px | 2 columnas solo en tramos (mín/máx/importe en fila), máx. 720 px |
| Filtros | scroll horizontal | fila | fila |
| Diálogos | sheet inferior | centrado | centrado |
| Toasts | abajo-centro | arriba-derecha | arriba-derecha |
| Padding página | 16 px | 24 px | 32 px |

### 14.3. Orientación horizontal móvil

Altura de gráficos reducida a 240 px en `(orientation: landscape) and (max-height: 500px)`; la bottomnav permanece (es más usable que ocultarla con gestos).

### 14.4. Reglas transversales

- Ningún contenido exige scroll horizontal de página (solo contenedores de tabla/gráfico internos).
- Todo objetivo táctil ≥ 44 × 44 px en móvil (supera el 24 px mínimo de WCAG 2.2 AA).
- `100dvh` para alturas de viewport en móvil (barras dinámicas del navegador).
- Gráficos: alturas fijas por breakpoint (nunca `aspect-ratio` libre que los haga ilegibles).

---

## 15. Iconografía

### 15.1. Biblioteca: Lucide (ISC)

Trazo de 2 px sobre grid de 24 px, esquinas redondeadas sobrias, catálogo con toda la cobertura necesaria (`trending-up/down`, `database`, `calendar`, `settings`, `sun`, `moon`, `monitor`, `alert-circle`, `info`, `check-circle`, `refresh-cw`, `plus`, `filter`, `chevron-*`, `download`, `git-compare`, `wallet`, `coins`, `activity`, `x`, `menu`, `external-link`…). Licencia [ISC](https://lucide.dev/license) (partes derivadas de Feather bajo MIT): permite copia local sin atribución visible obligatoria (se mantiene aviso en NOTICE por cortesía).

### 15.2. Integración (sin JS)

- Los iconos usados (lista cerrada, ~30) se descargan como SVG a `web/templates/partials/icons/<nombre>.svg` y se incluyen con `{% include "partials/icons/trending-up.svg" %}`.
- Los SVG se normalizan a: `fill="none"`, `stroke="currentColor"`, `stroke-width="2"`, `width/height` controlados por CSS (`.icon { width: 1em; height: 1em }` escalado por `font-size` del contexto), `aria-hidden="true"` cuando son decorativos.
- No se usa `lucide.js` (evita JS y FOUC de iconos) ni sprites externos (problemas con `currentColor` y caché).

### 15.3. Reglas de uso

| Regla | Detalle |
|---|---|
| Tamaños permitidos | 16, 18, 20, 24 px (vía `font-size` del contenedor) |
| Alineación con texto | `.icon { vertical-align: -0.125em }` en contextos inline |
| Icono + etiqueta | gap `--space-2`; la etiqueta nunca se omite en botones primarios |
| Icono solo | Permitido en acciones repetitivas ya aprendidas (cerrar, refrescar) con `aria-label` obligatorio y tooltip |
| Decorativo vs funcional | Decorativo → `aria-hidden="true"`; funcional → `role="img"` + `<title>` o `aria-label` |
| Estados financieros | `trending-up`/`trending-down` + color semántico + signo tipográfico (tres canales redundantes) |
| Prohibido | Emojis como iconos funcionales; iconos de relleno; mezclar familias de iconos |

---

## 16. Transiciones y microinteracciones

### 16.1. Tokens de movimiento

| Token | Valor | Uso |
|---|---|---|
| `--duration-fast` | 120 ms | Hover de botones, cambios de color de fondo/borde |
| `--duration-base` | 180 ms | Aparición de contenido (fade), tooltips |
| `--duration-slow` | 240 ms | Entrada de sheets/diálogos, desplazamientos |
| `--ease-out` | `cubic-bezier(0.2, 0, 0, 1)` | Curva única del sistema (salidas suaves, entradas rápidas) |

Propiedades animables permitidas: `opacity`, `color`, `background-color`, `border-color`, `transform` (solo `translateY` ≤ 8 px en entradas). **Prohibido** animar `width/height/top/left` (reflow), contadores numéricos y cualquier loop decorativo.

### 16.2. Patrones

| Interacción | Patrón |
|---|---|
| Contenido nuevo (HTMX swap) | `fade-in`: `opacity 0→1`, 180 ms, sin desplazamiento en tablas (evita mareo en datos) |
| Actualización de métricas | Solo fade del bloque actualizado; **nunca** flash verde/rojo estilo exchange |
| Apertura de diálogo | `opacity` + `translateY(8px→0)`, 240 ms; cierre solo `opacity`, 120 ms |
| Sheet móvil | `translateY(100%→0)`, 240 ms |
| Toast | entrada `fade + translateY(4px)`, salida `fade`, 180 ms |
| Cambio de tema | transición de `background-color/color/border-color` 120 ms en `body` y componentes (sin animar gráficos: Plotly repinta sin transición) |
| Skeleton shimmer | gradiente en movimiento 1,2 s, infinito mientras carga |

### 16.3. HTMX y transiciones

- Uso de `hx-swap="innerHTML swap:0.05s"` solo donde el fade mejore la comprensión del reemplazo (tarjetas de métricas); el resto de swaps son instantáneos para no acumular retrasos.
- La clase `.htmx-request` gestiona indicadores de carga (§13.12) por CSS; no hay transiciones CSS duplicadas sobre el mismo elemento (una sola regla de transición por propiedad y componente).
- Prohibido `transition: all` (causa parpadeos y animaciones involuntarias tras swaps).

### 16.4. Saltos de layout

- Alturas fijas de gráficos y skeletons con la geometría final → CLS ≈ 0 en cargas HTMX.
- Las tipografías usan `font-display: swap` con métricas de fallback cercanas (system-ui) para minimizar el reflow; `size-adjust` opcional en el `@font-face` de fallback si las pruebas F6 muestran salto visible.

### 16.5. Movimiento reducido

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

Con movimiento reducido: sin shimmer (skeleton estático), sin fade de tema, sin desplazamientos. Los cambios de estado siguen siendo perceptibles porque cambia el contenido, no porque se mueva.

---

## 17. Accesibilidad (objetivo WCAG 2.2 AA)

### 17.1. Criterios verificables

| # | Criterio | Verificación |
|---|---|---|
| A1 | Contraste de texto ≥ 4.5:1 (≥ 3:1 en texto grande) | Tabla de ratios medidos §5 (todos ✅); revisar cualquier token nuevo con la misma fórmula |
| A2 | Componentes de interacción identificables ≥ 3:1 | `--color-border-control`: 3.68:1 / 3.46:1 ✅; indicador de nav activo: 2 px + peso + `aria-current` |
| A3 | Foco visible siempre | Anillo 2 px `--color-focus` offset 2 px (5.13:1 / 9.56:1 ✅) en todo elemento interactivo; `:focus-visible` (sin anillo en clic de ratón) |
| A4 | Navegación completa por teclado | Orden de tabulación = orden visual; `<dialog>` nativo atrapa foco; menús cierran con Esc; skip-link "Saltar al contenido" como primer elemento |
| A5 | Formularios | `<label>` visible asociado, `aria-invalid` + `aria-describedby` en errores, resumen de errores con anclas (§13.15), `autocomplete` donde aplique |
| A6 | Semántica y landmarks | `header/nav/main/footer`, un solo `h1` por página, tablas con `th scope`, listas reales para colecciones |
| A7 | Lectores de pantalla | `aria-live="polite"` en zona de toasts; `aria-busy` en cargas; `aria-current="page"` en nav; estados vacíos como texto real (no solo visual) |
| A8 | Objetivos táctiles | ≥ 24 × 24 px (AA 2.2); objetivo del sistema: 44 × 44 px móvil (§14.4) |
| A9 | El color no es el único canal | Signos `+`/`−`, etiquetas textuales, iconos con texto; badges con texto; zonas del F&G con etiqueta escrita |
| A10 | Movimiento | `prefers-reduced-motion` respeta todas las animaciones (§16.5) |
| A11 | Idioma | `<html lang="es">`; términos técnicos en inglés marcados con `lang="en"` cuando proceda (p. ej. `run_id`) |

### 17.2. Tablas

`<table>` real con `<caption>` (visible o `sr-only`), cabeceras `th scope="col"`, celdas de fila clave con `th scope="row"` (día), números alineados con `tnum` para lectura comparable. La fila expandible móvil es un `<button>` en la celda con `aria-expanded` y `aria-controls`.

### 17.3. Gráficos

- Todo gráfico lleva `role="img"` + `aria-label` con la respuesta a su pregunta ("La cartera vale 80 401,26 € frente a 13 300,00 € invertidos el 18 de octubre de 2026") generada en servidor.
- Además, `.c-chart-alt` (`<details>` "Ver datos en tabla") con la tabla de la serie — también usable como exportación mental para todos los usuarios.
- Los tooltips de Plotly no son accesibles por teclado: la información crítica nunca vive solo en el tooltip (está en métricas/tabla).

### 17.4. Lista de comprobación para revisión (QA de diseño)

1. Navegar toda la app solo con teclado (Tab, Shift+Tab, Enter, Esc, flechas en menús).
2. Forzar ambos temas y ambos SO-claro/oscuro en modo `system`: sin FOUC, gráficos actualizados.
3. Lector de pantalla (VoiceOver/NVDA): recorrido Panel → detalle → operaciones.
4. Zoom de texto al 200 %: sin pérdida de contenido ni scroll horizontal de página.
5. `prefers-reduced-motion`: sin animaciones perceptibles.
6. Contraste medido de cualquier color nuevo contra la tabla §5 (script `scripts/check_contrast.py` sugerido en F6, Python puro).
7. Móvil real (360 px): objetivos táctiles, bottomnav, tabla expandible, tooltips sustituidos por diálogos.
8. Estados: vacío, cargando (throttling), error, datos desactualizados, 0 operaciones.

---

## 18. Organización técnica del sistema de diseño

### 18.1. Estructura de archivos (dentro de `src/backtesting_cripto/web/`)

```
web/
├── templates/
│   ├── base.html                    # <head>: script de tema (§8.2), CSS, fonts, htmx, plotly
│   ├── pages/                       # panel.html (/), backtests.html (/backtests),
│   │                                # backtest_detail.html (/backtests/{run_id}), data.html (/data)
│   ├── partials/
│   │   ├── icons/                   # ~30 SVG de Lucide normalizados (§15.2)
│   │   ├── components/              # metric_card.html, badge.html, table.html, empty.html,
│   │   │                            # toast.html, filterbar.html, theme_toggle.html, …
│   │   ├── fragments/               # respuestas HTMX: simulation_result.html, metrics_grid.html,
│   │   │                            # trades_tbody.html, chart_block.html, data_status.html, field_error.html
│   │   └── macros.html              # macros de formato (o filtros de entorno Jinja2,
│   │                                # decisión de implementación): eur, pct, btc, date_es (§6.5)
│   └── errors/                      # 404.html, 500.html
└── static/
    ├── css/
    │   ├── tokens.css               # §19.1 — primitivos + semánticos (claro/oscuro)
    │   ├── base.css                 # reset mínimo, elementos HTML, tipografía, foco, utilidades sr-only
    │   ├── layout.css               # contenedor, topnav, bottomnav, grids de página
    │   ├── components.css           # todos los .c-* del §13
    │   └── charts.css               # contenedores de gráfico, skeletons, .c-chart-alt
    ├── js/
    │   ├── theme.js                 # preferencia de tema (§8.3)
    │   ├── charts.js                # registro de gráficos + tema (relayout + restyle) + resize (§12.7)
    │   └── app.js                   # menús, diálogos, utilidades mínimas (~100 líneas máx.)
    ├── vendor/
    │   ├── htmx-2.0.10.min.js       # SRI + defer
    │   └── plotly-cartesian-3.7.0.min.js
    └── fonts/
        ├── InterVariable.woff2
        ├── IBMPlexMono-Regular.woff2
        ├── IBMPlexMono-Medium.woff2
        └── OFL.txt                  # licencias SIL OFL 1.1
```

Servidos por FastAPI `StaticFiles` en `/static`. En producción: `Cache-Control: public, max-age=31536000, immutable` para `vendor/` y `fonts/`, y `max-age=0, must-revalidate` para `css/`/`js/` propios (cache-busting con `?v={{ app_version }}` en `base.html`).

### 18.2. Orden y capas CSS

```css
@layer tokens, base, layout, components, utilities;
```

`base.html` carga en orden: `tokens.css` → `base.css` → `layout.css` → `components.css` → `charts.css`. Las capas garantizan que ninguna utilidad quede por debajo de un componente y viceversa, sin peleas de especificidad. **Prohibido `!important`** salvo en el bloque de `prefers-reduced-motion` (§16.5) y en utilidades de accesibilidad (`sr-only`).

### 18.3. JavaScript: presupuesto y responsabilidades

Presupuesto total de JS propio: **≤ 250 líneas** en tres módulos (más Plotly/htmx de vendor):

| Módulo | Responsabilidad | Tamaño objetivo |
|---|---|---|
| inline en `base.html` | Resolver tema antes del pintado (§8.2) | ~15 líneas |
| `theme.js` | `setThemePreference`, listener del SO, evento `bt:theme-changed` | ~60 líneas |
| `charts.js` | `baseLayout()`, registro `__btCharts`, `initChartsIn()` en `DOMContentLoaded` y `htmx:load`, resize, `relayout` + `restyle` de tema | ~120 líneas |
| `app.js` | Menús/diálogos que no cubra el `<dialog>`/Popover nativos, utilidades | ~60 líneas |

No hay estado de cliente duplicado: el servidor es la fuente de verdad (HTMX). JS solo resuelve tema, gráficos y apertura/cierre de capas.

### 18.4. Contrato de fragmentos HTMX

1. Todo endpoint HTMX devuelve **fragmentos completos y válidos** (sin dependencias de contexto de página) que usan exclusivamente tokens semánticos.
2. Datos para gráficos: `<script type="application/json" data-chart-for="<id>">` hermano del `div[data-chart]` dentro del mismo fragmento (§12.7); `charts.js` lo parsea en `DOMContentLoaded` y `htmx:load`.
3. Errores de formulario: el fragmento devuelto incluye `aria-invalid` y `aria-describedby` ya puestos (el servidor conoce el error; JS no adivina).
4. Respuestas de error global (5xx): fragmento `.c-toast --error` vía out-of-band swap + código de estado real (HTMX no dispara swap en 5xx; usar `htmx:responseError` en `app.js` para mostrar el toast genérico).
5. `hx-push-url` en navegaciones que cambian de "recurso" (detalle de run, paginación) para que el botón atrás funcione.

### 18.5. Compartición de tokens CSS → JS (Plotly)

Única vía: `getComputedStyle(document.documentElement).getPropertyValue("--color-*")` en `charts.js` (ver [`plotly-theme.js`](./plotly-theme.js)). No existe un segundo juego de tokens en JS ni un JSON paralelo: una sola fuente de verdad (`tokens.css`).

---

## 19. Ejemplos de tokens y convenciones

### 19.1. Convención de nombres

| Categoría | Patrón | Ejemplos |
|---|---|---|
| Color semántico | `--color-<rol>[-<variante>]` | `--color-text-1`, `--color-positive-text`, `--color-border-control` |
| Espacio | `--space-<n>` (base 4) | `--space-4`, `--space-8` |
| Tipografía | `--text-<talla>` | `--text-sm`, `--text-2xl` |
| Radio / borde / sombra | `--radius-<t>`, `--shadow-<n>` | `--radius-md`, `--shadow-1` |
| Movimiento | `--duration-<t>`, `--ease-<t>` | `--duration-base`, `--ease-out` |
| Componente CSS | `.c-<nombre>[--<variante>]` | `.c-button--primary`, `.c-badge--warning` |
| Estado | `.is-<estado>` | `.is-loading`, `.is-active` |
| Layout | `.l-<patrón>` | `.l-container`, `.l-grid-metrics` |
| Utilidad | `.u-<cosa>` | `.u-sr-only`, `.u-tnum` |

Reglas: todo color de plantilla sale de un `--color-*` semántico; prohibido hex en `components.css` (solo `tokens.css` contiene valores hex); prohibido nombrar tokens por componente (`--color-badge-bg` ❌).

### 19.2. Extracto de `tokens.css` (archivo completo de referencia adjunto)

```css
:root {
  /* Superficies y texto — claro */
  --color-bg-app: #F5F7F9;
  --color-surface-1: #FFFFFF;
  --color-surface-2: #F0F2F5;
  --color-text-1: #171B22;
  --color-text-2: #5A6372;
  --color-text-3: #8A93A1;
  --color-text-disabled: #9AA2AF;
  --color-border-subtle: #E4E8EE;
  --color-border-control: #7D8694;
  --color-border-strong: #CBD2DC;
  --color-tooltip-bg: #1B212B;
  --color-tooltip-text: #F4F6F8;
  --color-chart-grid: #E8ECF1; /* decorativo, exento de AA */

  /* Marca y semánticos — claro */
  --color-brand: #0DC3A4;
  --color-positive: #0DC3A4;
  --color-positive-text: #0A7C68;
  --color-positive-subtle: #E3F6F1;
  --color-negative: #CE2C31;
  --color-negative-subtle: #FDEEEF;
  --color-error: #CE2C31;
  --color-error-subtle: #FDEEEF;
  --color-info: #2F5FC7;
  --color-info-subtle: #E9EFFC;
  --color-warning: #946200;
  --color-warning-subtle: #FBF1DC;
  --color-fng: #6D5FD3;

  /* Acción — claro */
  --color-action-bg: #171B22;
  --color-action-text: #FFFFFF;
  --color-action-bg-hover: #2A303B;
  --color-link: #0A7C68;
  --color-focus: #0A7C68;

  color-scheme: light;
}

[data-theme="dark"] {
  --color-bg-app: #0E131A;
  --color-surface-1: #161C25;
  --color-surface-2: #1D2530;
  --color-text-1: #E8EBF0;
  --color-text-2: #9AA5B3;
  --color-text-3: #6B7686;
  --color-text-disabled: #5F6979;
  --color-border-subtle: #28303D;
  --color-border-control: #667181;
  --color-border-strong: #3A4554;
  --color-tooltip-bg: #F4F6F8;
  --color-tooltip-text: #171B22;
  --color-chart-grid: #242D3A;

  --color-positive-text: #0DC3A4;
  --color-positive-subtle: #10302A;
  --color-negative: #F2555A;
  --color-negative-subtle: #351B20;
  --color-error: #F2555A;
  --color-error-subtle: #351B20;
  --color-info: #7FA6F2;
  --color-info-subtle: #1D2942;
  --color-warning: #E3B25E;
  --color-warning-subtle: #37291A;
  --color-fng: #A79CF0;

  --color-action-bg: #0DC3A4;
  --color-action-text: #06302A;
  --color-action-bg-hover: #2BD0B2;
  --color-link: #2BD0B2;
  --color-focus: #2BD0B2;

  color-scheme: dark;
}
```

### 19.3. Ejemplo de componente (botón)

```css
@layer components {
  .c-button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    min-height: 2.75rem;              /* 44 px táctil */
    padding: 0 var(--space-4);
    border: 1px solid transparent;
    border-radius: var(--radius-md);
    font: 600 0.9375rem/1 var(--font-sans);
    cursor: pointer;
    transition:
      background-color var(--duration-fast) var(--ease-out),
      border-color var(--duration-fast) var(--ease-out);
  }
  @media (min-width: 640px) {
    .c-button { min-height: 2.5rem; }  /* 40 px escritorio */
  }
  .c-button--primary {
    background: var(--color-action-bg);
    color: var(--color-action-text);
  }
  .c-button--primary:hover {
    background: var(--color-action-bg-hover);
  }
  .c-button:focus-visible {
    outline: 2px solid var(--color-focus);
    outline-offset: 2px;
  }
  .c-button:disabled,
  .c-button.is-loading {
    opacity: 0.55;
    cursor: not-allowed;
  }
}
```

### 19.4. Ejemplo de uso en plantilla (tarjeta de métrica)

```html
<article class="c-card c-metric c-metric--lg">
  <h3 class="t-metric-label">Valor de la cartera</h3>
  <p class="t-metric-value">{{ metrics.final_portfolio_value_eur | eur }}</p>
  <p class="t-caption">al cierre del {{ data.last_closed_day | date_es }}</p>
</article>
```

---

## 20. Criterios de aceptación del diseño

La implementación F6 se considerará conforme a este diseño cuando se verifique **todo** lo siguiente:

**Identidad y tokens**
1. `tokens.css` contiene todos los tokens del §19.2 con los valores exactos del §5 (incluido `--color-chart-grid`); ningún otro archivo CSS contiene valores hex.
2. No existe ningún framework CSS (Bootstrap/Bulma/Pico) en el HTML servido; el CSS propio total es ≤ 40 kB minificado.
3. `#0DC3A4` no se usa como texto < 24 px (o < 18,66 px bold) en tema claro.

**Temas**
4. Con `system` y SO en oscuro, la primera pintura ya es oscura (sin flash claro) — verificable con grabación a cámara lenta o DevTools.
5. La preferencia manual persiste entre sesiones y prevalece sobre el SO; `system` reacciona al cambio del SO en vivo.
6. Al cambiar de tema, los gráficos actualizan colores sin recarga ni flash blanco.

**Accesibilidad**
7. Se cumplen los 11 criterios A1–A11 del §17.1 y la lista de comprobación §17.4 completa.

**Componentes y pantallas**
8. Los 18 componentes del §13 existen con sus variantes y estados documentados (revisión en una página de catálogo interno opcional `/design-preview` solo en modo debug).
9. El Panel muestra los bloques A–E del §11.2 con la jerarquía y el orden indicados, en los tres breakpoints.
10. La tabla de operaciones funciona con columnas prioritarias + expansión en 360 px sin scroll horizontal de página.

**Gráficos**
11. Todos los gráficos usan la configuración base del §12.2 (fuentes, tooltip, cuadrícula, formato numérico español) y tienen alternativa textual (§17.3).
12. El índice F&G se dibuja en violeta con zonas neutras; las compras en teal (§12.4).

**Rendimiento y stack**
13. JS propio ≤ 250 líneas; solo 2 scripts de vendor locales (htmx, plotly-cartesian); fuentes WOFF2 locales; cero peticiones a CDN/terceros en producción (verificable en la pestaña Red).
14. CLS ≈ 0 en cargas HTMX (skeletons con geometría final); Lighthouse ≥ 95 en accesibilidad.

---

## 21. Riesgos, limitaciones y supuestos

| # | Riesgo / limitación | Impacto | Mitigación |
|---|---|---|---|
| R1 | **Peso de Plotly** (~465–505 kB gzip) en conexiones lentas | Primera carga del Panel lenta en móvil 3G | Carga `defer` + skeletons; el contenido textual (métricas) no depende de Plotly. Si resulta inaceptable: migrar a Chart.js (decisión documentada, §4.4) sin tocar tokens ni plantillas de datos |
| R2 | **CSS propio = más trabajo inicial** que adoptar un framework | F6 más larga | El catálogo §13 es cerrado y este documento da medidas exactas; la página `/design-preview` acelera la revisión |
| R3 | **htmx 2.x → 4.x**: la línea 2 dejará de ser `latest` en 2027 | Deuda técnica futura leve | API usada es estable; la migración se evalúa en F7 con la guía oficial |
| R4 | **U+202F como separador de miles en Plotly** puede no renderizar en algún navegador antiguo | Formato de miles inconsistente | Fallback documentado a `",."` (§12.2); verificación en F6 |
| R5 | **Popover API / `<dialog>`** en navegadores antiguos | Menús/diálogos degradados | Objetivo: últimas 2 versiones de Chrome/Firefox/Safari/Edge (alineado con Pico/Bootstrap); sin soporte IE |
| R6 | **Navegación de 3 destinos** si el producto añade muchas secciones en el futuro | Rediseño de navegación | La barra soporta hasta 5 destinos directos sin cambios (o sidebar futura si superase 6) sin romper tokens ni componentes |
| R7 | **Asimetría del botón primario** (tinta en claro / verde en oscuro) puede percibirse como inconsistencia | Menor | Es deliberada y está justificada (§5.6); ambos estados están medidos y cumplen AA |
| R8 | **Sin CSP estricta en v1** (data islands JSON inline) | Superficie XSS limitada (app local) | Documentar CSP en F7 si la app se expone en red; alternativa `data-*` JSON-encoded ya prevista (§12.7) |
| R9 | Iconos Lucide copiados a mano | Pueden desactualizarse | Lista cerrada de ~30; actualización consciente, no automática |

**Supuestos adoptados (documentados para no bloquear):**

- S1. Navegadores objetivo: últimas 2 versiones de Chrome, Firefox, Safari, Edge; sin IE11 (coherente con Pico CSS y Bootstrap 5).
- S2. La app se sirve en local o red de confianza en v1 (sin autenticación ni CSP estricta).
- S3. El bundle `plotly-cartesian` cubre todas las visualizaciones previstas hasta el comparador (scatter/bar/histogram).
- S4. El idioma de la interfaz es exclusivamente español; los identificadores técnicos permanecen en inglés.
- S5. Inter Variable se servirá sin subsetear en v1 (~300 kB WOFF2 variable; subseteo opcional como mejora, §6.2).

---

## 22. Decisiones validadas y aprobadas con el usuario

Todas las decisiones de arquitectura UX/UI han sido revisadas y aprobadas con el usuario:

| # | Decisión | Estado | Resolución adoptada |
|---|---|---|---|
| D1 | **CSS propio sin framework** | ✅ Aprobada | Se adopta CSS propio con tokens (`tokens.css` + `@layer`) sin frameworks externos. |
| D2 | **Botón primario asimétrico por tema** (`#171B22` en claro, `#0DC3A4` en oscuro) | ✅ Aprobada | Se adopta por sobriedad en tema claro e identidad en tema oscuro (ambos con contraste WCAG AA medido). |
| D3 | **Tipografías Inter + IBM Plex Mono** | ✅ Aprobada | `Inter` (variable, `tnum`) para UI/cifras e `IBM Plex Mono` para hashes e identificadores técnicos. |
| D4 | **Navegación simplificada a 3 vistas** | ✅ Aprobada | Topbar (≥ 640 px) + bottom bar (< 640 px) con **3 vistas**: **Simulador** (`/`), **Historial** (`/backtests` y `/backtests/{run_id}`) y **Datos** (`/data`). Selector de tema en cabecera. Sin sección "Comparar" en v1. |
| D5 | **Plotly.js cartesian local (~500 kB gzip)** | ✅ Aprobada | Se adopta `plotly-cartesian` servido en local con `defer`, skeletons y `relayout` + `restyle` automático al cambiar de tema (`plotly-theme.js`). |

**Fuera de ámbito en v1:** comparador cruzado de múltiples estrategias/runs, exportación CSV/PDF, autenticación, multi-idioma, PWA, CSP estricta.

---

## Anexo A. Referencias oficiales consultadas

| Recurso | URL | Uso en este documento |
|---|---|---|
| Pico CSS (repo, aviso de archivo) | https://github.com/picocss/pico | §4.2 — estado de mantenimiento |
| htmx (releases, licencia 0BSD) | https://github.com/bigskysoftware/htmx/releases · https://htmx.org | §4.3 |
| Plotly.js (repo, dist/README, licencia MIT) | https://github.com/plotly/plotly.js | §4.4, §12 |
| Bootstrap 5.3 (color modes, licencia) | https://getbootstrap.com/docs/5.3/customize/color-modes/ | §4.2 (descarte informado) |
| Bulma (v1, dark mode, licencia) | https://bulma.io/documentation/ | §4.2 (descarte informado) |
| Lucide (licencia ISC) | https://lucide.dev/license | §15 |
| Inter (repo, licencia SIL OFL 1.1, `tnum`) | https://github.com/rsms/inter · https://rsms.me/inter/ | §6 |
| IBM Plex (repo, SIL OFL 1.1) | https://github.com/IBM/plex | §6 |
| WCAG 2.2 | https://www.w3.org/TR/WCAG22/ | §5, §17 |
| Documento rector del proyecto | [`../planificacion.md`](../planificacion.md) | Métricas, formatos, invariantes |

## Anexo B. Verificación de contrastes (método)

Ratios calculados con la fórmula WCAG 2.x de luminancia relativa (sRGB): `L = 0.2126·R + 0.7152·G + 0.0722·B` sobre canales linealizados; `ratio = (L1 + 0.05) / (L2 + 0.05)`. Todos los pares de las tablas §5–§5.6 fueron calculados con un script Python local (2026-10-19); los valores citados son el resultado exacto del cálculo, redondeado a 2 decimales. En F6 se sugiere preservar el script como `scripts/check_contrast.py` para validar cualquier token nuevo.
