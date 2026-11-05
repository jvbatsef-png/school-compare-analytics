// A/B assignment: drawn once per browser, kept in localStorage under sca_variant.
window.SCA = window.SCA || {};

(function () {
  var KEY = "sca_variant";
  var memory = null; // used when storage is blocked, so the page keeps one variant

  SCA.getVariant = function () {
    if (memory) return memory;
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) { /* storage blocked */ }
    if (stored === "A" || stored === "B") return (memory = stored);
    memory = Math.random() < 0.5 ? "A" : "B";
    try { localStorage.setItem(KEY, memory); } catch (e) { /* keep in memory only */ }
    return memory;
  };
})();
