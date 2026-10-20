/* ==========================================================================
 * theme.js — preferencia de tema claro / oscuro / sistema (§8)
 * Persistencia en localStorage["theme-preference"], sin cookies: el tema
 * se resuelve íntegramente en cliente y el servidor nunca lo conoce.
 * ========================================================================== */

(function () {
  "use strict";

  var STORAGE_KEY = "theme-preference";
  var VALID = ["light", "dark", "system"];

  function systemPrefersDark() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function effectiveTheme(preference) {
    if (preference === "light" || preference === "dark") {
      return preference;
    }
    return systemPrefersDark() ? "dark" : "light";
  }

  function getThemePreference() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (VALID.indexOf(stored) !== -1) {
        return stored;
      }
    } catch (error) {
      /* almacenamiento no disponible (modo privado): sistema */
    }
    return "system";
  }

  function applyTheme(preference) {
    document.documentElement.dataset.theme = effectiveTheme(preference);
    document.documentElement.dataset.themePreference = preference;
  }

  function syncControls(preference) {
    document.querySelectorAll("[data-theme-option]").forEach(function (button) {
      button.setAttribute("aria-checked", String(button.dataset.themeOption === preference));
    });
  }

  function announce(preference) {
    document.dispatchEvent(
      new CustomEvent("bt:theme-changed", { detail: { preference: preference } })
    );
  }

  function setThemePreference(preference) {
    if (VALID.indexOf(preference) === -1) {
      return;
    }
    try {
      localStorage.setItem(STORAGE_KEY, preference);
    } catch (error) {
      /* sin persistencia: el tema dura lo que dura la sesión */
    }
    applyTheme(preference);
    syncControls(preference);
    announce(preference);
  }

  window.getThemePreference = getThemePreference;
  window.setThemePreference = setThemePreference;

  document.addEventListener("DOMContentLoaded", function () {
    var preference = getThemePreference();
    applyTheme(preference);
    syncControls(preference);

    document.querySelectorAll("[data-theme-option]").forEach(function (button) {
      button.addEventListener("click", function () {
        setThemePreference(button.dataset.themeOption);
      });
    });

    // En modo "sistema", seguir los cambios del SO en vivo (§8.1).
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
      if (getThemePreference() === "system") {
        applyTheme("system");
        announce("system");
      }
    });
  });
})();
