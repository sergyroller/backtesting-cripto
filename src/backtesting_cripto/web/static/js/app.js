/* ==========================================================================
 * app.js — helpers de UI: tramos semanales, atajos de rango, pestañas,
 * acordeón de filas en móvil y toasts. Sin framework.
 * ========================================================================== */

(function () {
  "use strict";

  /* --- Parámetros de la simulación: JSON oculto sincronizado --- */
  function syncParams(form) {
    var hidden = form.querySelector("[data-params-json]");
    if (!hidden) {
      return;
    }
    var threshold = form.querySelector("[name='daily_below_threshold']");
    var amount = form.querySelector("[name='daily_amount_eur']");
    var bands = [];
    form.querySelectorAll("[data-band-row]").forEach(function (row) {
      var min = row.querySelector("[data-band-min]");
      var max = row.querySelector("[data-band-max]");
      var bandAmount = row.querySelector("[data-band-amount]");
      if (!min || !max || !bandAmount) {
        return;
      }
      bands.push({
        min_value: parseInt(min.value, 10),
        max_value: parseInt(max.value, 10),
        amount_eur: bandAmount.value,
      });
    });
    hidden.value = JSON.stringify({
      daily_below_threshold: threshold ? parseInt(threshold.value, 10) : 10,
      daily_amount_eur: amount ? amount.value : "0",
      weekly_bands: bands,
    });
  }

  function addBandRow(form, template, band) {
    var list = form.querySelector("[data-band-list]");
    if (!list) {
      return;
    }
    var fragment = template.content.cloneNode(true);
    var row = fragment.querySelector("[data-band-row]");
    if (band && row) {
      row.querySelector("[data-band-min]").value = band.min_value;
      row.querySelector("[data-band-max]").value = band.max_value;
      row.querySelector("[data-band-amount]").value = band.amount_eur;
    }
    list.appendChild(fragment);
    syncParams(form);
  }

  function initBands(form) {
    var template = document.getElementById("band-row-template");
    var list = form.querySelector("[data-band-list]");
    if (!template || !list) {
      return;
    }
    form.querySelectorAll("[data-band-add]").forEach(function (button) {
      button.addEventListener("click", function () {
        addBandRow(form, template, null);
      });
    });
    list.addEventListener("click", function (event) {
      var remove = event.target.closest("[data-band-remove]");
      if (remove) {
        var row = remove.closest("[data-band-row]");
        if (row && list.querySelectorAll("[data-band-row]").length > 1) {
          row.remove();
          syncParams(form);
        }
      }
    });
    form.addEventListener("input", function () {
      syncParams(form);
    });
    syncParams(form);
  }

  /* --- Atajos de rango 1A / 3A / 5A / Todo --- */
  function initRangeShortcuts(form) {
    var endInput = form.querySelector("[data-range-end]");
    var startInput = form.querySelector("[data-range-start]");
    if (!endInput || !startInput) {
      return;
    }
    form.querySelectorAll("[data-range-years]").forEach(function (button) {
      button.addEventListener("click", function () {
        var years = parseInt(button.dataset.rangeYears, 10);
        var end = new Date(endInput.value + "T00:00:00Z");
        if (isNaN(end.getTime())) {
          return;
        }
        var start = new Date(Date.UTC(end.getUTCFullYear() - years, end.getUTCMonth(), end.getUTCDate()));
        var min = startInput.getAttribute("min");
        if (min && start.toISOString().slice(0, 10) < min) {
          start = new Date(min + "T00:00:00Z");
        }
        startInput.value = start.toISOString().slice(0, 10);
        startInput.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
  }

  /* --- Pestañas Resumen / Operaciones / Supuestos --- */
  function initTabs() {
    document.querySelectorAll("[data-tabs]").forEach(function (group) {
      var tabs = group.querySelectorAll("[data-tab]");
      var panels = group.querySelectorAll("[data-tab-panel]");
      tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
          tabs.forEach(function (other) {
            other.setAttribute("aria-selected", String(other === tab));
          });
          panels.forEach(function (panel) {
            panel.hidden = panel.dataset.tabPanel !== tab.dataset.tab;
          });
          if (window.Plotly) {
            panels.forEach(function (panel) {
              panel.querySelectorAll("[data-chart]").forEach(function (el) {
                if (el.data) {
                  Plotly.Plots.resize(el);
                }
              });
            });
          }
        });
      });
    });
  }

  /* --- Acordeón de filas en móvil (tabla de operaciones) --- */
  function initRowDetails() {
    document.querySelectorAll("[data-row-toggle]").forEach(function (button) {
      button.addEventListener("click", function () {
        var target = document.getElementById(button.getAttribute("aria-controls") || "");
        if (!target) {
          return;
        }
        var expanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!expanded));
        target.hidden = expanded;
      });
    });
  }

  /* --- Toasts: auto-dismiss a los 6 s, pausa al enfocar --- */
  function initToasts() {
    document.querySelectorAll("[data-toast]").forEach(function (toast) {
      var timer = setTimeout(function () {
        toast.remove();
      }, 6000);
      toast.addEventListener("mouseenter", function () {
        clearTimeout(timer);
      });
      toast.addEventListener("focusin", function () {
        clearTimeout(timer);
      });
    });
  }

  /* --- aria-busy en el botón de envío durante peticiones HTMX (§13.12) --- */
  document.body.addEventListener("htmx:beforeRequest", function (evt) {
    var elt = evt.detail && evt.detail.elt;
    var button = elt && elt.querySelector ? elt.querySelector("button[type='submit']") : null;
    if (button) {
      button.setAttribute("aria-busy", "true");
    }
  });
  document.body.addEventListener("htmx:afterRequest", function (evt) {
    var elt = evt.detail && evt.detail.elt;
    var button = elt && elt.querySelector ? elt.querySelector("button[type='submit']") : null;
    if (button) {
      button.removeAttribute("aria-busy");
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form[data-simulation-form]").forEach(function (form) {
      initBands(form);
      initRangeShortcuts(form);
    });
    initTabs();
    initRowDetails();
    initToasts();
  });

  document.body.addEventListener("htmx:load", function (evt) {
    var root = evt.detail && evt.detail.elt ? evt.detail.elt : document;
    root.querySelectorAll("form[data-simulation-form]").forEach(function (form) {
      initBands(form);
      initRangeShortcuts(form);
    });
    initTabs();
    initRowDetails();
    initToasts();
  });
})();
