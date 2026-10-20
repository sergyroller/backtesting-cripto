/* ==========================================================================
 * plotly-theme.js — REFERENCIA del sistema de diseño
 * (docs/design/DESIGN_SYSTEM.md, §12). Especificación para F6: copiar a
 * web/static/js/charts.js al implementar.
 *
 * Principio: una sola fuente de verdad (tokens.css). Este módulo LEE las
 * custom properties con getComputedStyle y construye el layout base de
 * Plotly. Los DATOS y los valores formateados llegan del servidor
 * (customdata); JS no formatea cifras.
 * ========================================================================== */

/* Lee un token CSS (--color-*) del elemento raíz. */
function cssToken(name) {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

/* Layout base compartido por TODOS los gráficos (§12.2).
 * `isMobile` ajusta márgenes y leyenda (§12.6). */
function baseLayout(isMobile) {
  return {
    font: {
      family: cssToken("--font-sans"),
      size: 12,
      color: cssToken("--color-text-2"),
    },
    paper_bgcolor: "rgba(0,0,0,0)", // hereda la superficie de .c-card
    plot_bgcolor: "rgba(0,0,0,0)",
    margin: isMobile
      ? { l: 48, r: 8, t: 8, b: 56 }
      : { l: 56, r: 16, t: 8, b: 40 },
    // Formato español: decimal ",", miles espacio fino U+202F.
    // Fallback verificado en F6 (§12.2): ",." si U+202F falla.
    separators: ",\u202F",
    hovermode: "x unified",
    hoverlabel: {
      bgcolor: cssToken("--color-tooltip-bg"),
      bordercolor: cssToken("--color-border-subtle"),
      font: {
        family: cssToken("--font-sans"),
        size: 13,
        color: cssToken("--color-tooltip-text"),
      },
    },
    xaxis: {
      showline: false,
      showgrid: false,
      ticks: "outside",
      tickfont: { size: 12 },
    },
    yaxis: {
      showline: false,
      showgrid: true,
      gridcolor: cssToken("--color-chart-grid"),
      ticks: "outside",
      tickfont: { size: 12 },
      zeroline: false,
    },
    legend: {
      orientation: "h",
      y: -0.18,
      font: { size: 12 },
    },
    showlegend: true,
  };
}

/* Config compartida (§12.2). */
function baseConfig(isMobile) {
  return {
    responsive: true,
    displaylogo: false,
    displayModeBar: isMobile ? false : "hover",
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
    scrollZoom: false, // solo true en G1/G2 de escritorio (§12.6)
  };
}

/* Colores de series por rol semántico (§12.3–§12.4). */
function seriesColors() {
  return {
    invested: cssToken("--color-text-2"), // capital invertido (neutro)
    portfolio: cssToken("--color-brand"), // valor de cartera (teal)
    buys: cssToken("--color-brand"),      // marcadores de compra (teal)
    fng: cssToken("--color-fng"),         // índice Fear & Greed (violeta)
    drawdown: cssToken("--color-negative"),
  };
}

/* Aplica los colores del tema vigente a cada traza según su `meta.role`. */
function applyTraceColors(traces) {
  var palette = seriesColors();
  return (traces || []).map(function (trace) {
    var role = trace.meta && trace.meta.role;
    var color = role && palette[role] ? palette[role] : palette.portfolio;
    var copy = Object.assign({}, trace);
    if (copy.line) {
      copy.line = Object.assign({}, copy.line, { color: color });
    }
    if (copy.marker) {
      copy.marker = Object.assign({}, copy.marker, { color: color });
    }
    return copy;
  });
}

/* Registro de gráficos vivos para re-tematizar y redimensionar (§12.7). */
window.__btCharts = window.__btCharts || [];

function registerChart(divId) {
  if (!window.__btCharts.includes(divId)) window.__btCharts.push(divId);
}

/* Fusión profunda del layout base con el layout específico de cada gráfico.
 * Object.assign superficial perdería xaxis/yaxis (gridcolor, ticks, rangos y
 * ticktext en español) al sobreescribir el objeto entero (§12.7). */
function mergeLayout(base, override) {
  var over = override || {};
  var merged = Object.assign({}, base, over);
  merged.xaxis = Object.assign({}, base.xaxis || {}, over.xaxis || {});
  merged.yaxis = Object.assign({}, base.yaxis || {}, over.yaxis || {});
  merged.margin = Object.assign({}, base.margin || {}, over.margin || {});
  merged.font = Object.assign({}, base.font || {}, over.font || {});
  merged.legend = Object.assign({}, base.legend || {}, over.legend || {});
  merged.hoverlabel = Object.assign({}, base.hoverlabel || {}, over.hoverlabel || {});
  return merged;
}

/* Inicializa todos los div[data-chart] presentes en `root` leyendo su
 * <script type="application/json" data-chart-for="<id>"> asociado. */
function initChartsIn(root) {
  var scope = root || document;
  var isMobile = window.matchMedia("(max-width: 639px)").matches;
  var nodes = scope.querySelectorAll("[data-chart]");
  nodes.forEach(function (el) {
    if (!el.id) return;
    var dataScript = document.querySelector(
      'script[type="application/json"][data-chart-for="' + el.id + '"]'
    );
    if (dataScript && !el.dataset.chartInitialized) {
      var spec = JSON.parse(dataScript.textContent || "{}");
      var traces = applyTraceColors(spec.traces || []);
      var layout = mergeLayout(baseLayout(isMobile), spec.layout || {});
      var config = Object.assign({}, baseConfig(isMobile), spec.config || {});
      Plotly.newPlot(el, traces, layout, config);
      el.dataset.chartInitialized = "true";
      // Se guarda el layout propio para que el cambio de tema no lo borre.
      el.__btSpecLayout = spec.layout || {};
      registerChart(el.id);
    } else if (el.dataset.chartInitialized) {
      Plotly.Plots.resize(el);
    }
  });
}

/* Ante `bt:theme-changed`: actualiza layout (relayout) y colores de series
 * dependientes del tema (restyle sobre line.color / marker.color) (§12.7). */
document.addEventListener("bt:theme-changed", function () {
  var isMobile = window.matchMedia("(max-width: 639px)").matches;
  var palette = seriesColors();
  window.__btCharts.forEach(function (id) {
    var el = document.getElementById(id);
    if (!el || !el.data) return;
    // Se fusiona con el layout propio del gráfico para no perder títulos,
    // rangos ni los ticktext en español generados por el servidor.
    Plotly.relayout(el, mergeLayout(baseLayout(isMobile), el.__btSpecLayout));
    el.data.forEach(function (trace, idx) {
      var role = trace.meta && trace.meta.role;
      var color = role && palette[role] ? palette[role] : null;
      if (!color) return;
      var update = {};
      if (trace.line) update["line.color"] = color;
      if (trace.marker) update["marker.color"] = color;
      if (Object.keys(update).length > 0) {
        Plotly.restyle(el, update, [idx]);
      }
    });
  });
});

/* Inicialización en carga inicial y tras cualquier swap HTMX (`htmx:load`). */
document.addEventListener("DOMContentLoaded", function () {
  initChartsIn(document);
});

document.body.addEventListener("htmx:load", function (evt) {
  initChartsIn(evt.detail && evt.detail.elt ? evt.detail.elt : document);
});

/* Redimensionar los gráficos vivos cuando cambia el tamaño de su
 * contenedor (necesario tras swaps HTMX que cambian el layout; §12.6). */
if (typeof ResizeObserver !== "undefined") {
  var chartResizeObserver = new ResizeObserver(function (entries) {
    entries.forEach(function (entry) {
      var el = entry.target;
      if (el.id && el.data && window.__btCharts.indexOf(el.id) !== -1) {
        Plotly.Plots.resize(el);
      }
    });
  });

  var observeCharts = function (root) {
    var scope = root || document;
    scope.querySelectorAll("[data-chart]").forEach(function (el) {
      chartResizeObserver.observe(el);
    });
  };

  document.addEventListener("DOMContentLoaded", function () {
    observeCharts(document);
  });
  document.body.addEventListener("htmx:load", function (evt) {
    observeCharts(evt.detail && evt.detail.elt ? evt.detail.elt : document);
  });
}
