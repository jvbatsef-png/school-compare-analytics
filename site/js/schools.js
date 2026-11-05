// School data, fetched once per page.
window.SCA = window.SCA || {};

(function () {
  var cache = null;
  SCA.loadSchools = function () {
    if (!cache) cache = fetch("data/schools.json").then(function (r) { return r.json(); });
    return cache;
  };
})();
