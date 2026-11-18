/* TicketPilot landing page: theme toggle + subtle scroll reveal.
   Theme choice persists in localStorage; reduced-motion safe. */
(function () {
  "use strict";

  function applyTheme(name) {
    document.documentElement.dataset.theme = name;
    var light = document.getElementById("theme-light");
    var dark = document.getElementById("theme-dark");
    if (light && dark) {
      light.setAttribute("aria-pressed", String(name === "light"));
      dark.setAttribute("aria-pressed", String(name === "dark"));
    }
    try {
      localStorage.setItem("ticketpilot-theme", name);
    } catch (e) { /* storage blocked: page still works */ }
  }

  function initToggle() {
    var light = document.getElementById("theme-light");
    var dark = document.getElementById("theme-dark");
    if (!light || !dark) return;
    light.addEventListener("click", function () { applyTheme("light"); });
    dark.addEventListener("click", function () { applyTheme("dark"); });
    applyTheme(document.documentElement.dataset.theme || "light");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initToggle);
  } else {
    initToggle();
  }

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var items = document.querySelectorAll(".reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    items.forEach(function (el) { el.classList.add("visible"); });
    return;
  }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });
  items.forEach(function (el) { observer.observe(el); });
})();
