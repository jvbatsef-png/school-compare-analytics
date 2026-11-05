// Index page: search form and result cards.
window.SCA = window.SCA || {};

(function () {
  var FIELDS = ["q", "level", "location"];
  var LEVELS = { elementary: "Elementary", middle: "Middle school", high: "High school" };
  var TYPES = { public: "Public", private: "Private", charter: "Charter" };
  var shown = [];

  function readForm() {
    var values = {};
    FIELDS.forEach(function (f) { values[f] = document.getElementById(f).value.trim(); });
    return values;
  }

  function filter(schools, v) {
    var q = v.q.toLowerCase(), loc = v.location.toLowerCase();
    return schools.filter(function (s) {
      return (!q || s.name.toLowerCase().indexOf(q) !== -1) &&
        (!v.level || s.level === v.level) &&
        (!loc || (s.city + ", " + s.state).toLowerCase().indexOf(loc) !== -1);
    }).sort(function (a, b) { return b.rating - a.rating || (a.id < b.id ? -1 : 1); });
  }

  function card(s) {
    var li = document.createElement("li");
    li.className = "card";
    li.dataset.schoolId = s.id;
    var link = document.createElement("a");
    link.href = "school.html?id=" + s.id + "&src=results";
    link.textContent = s.name;
    var title = document.createElement("h3");
    title.appendChild(link);
    var meta = document.createElement("p");
    meta.className = "meta";
    meta.textContent = s.city + ", " + s.state + " · " + LEVELS[s.level] + " · " + TYPES[s.type];
    var rating = document.createElement("p");
    rating.className = "rating";
    rating.textContent = "Rating " + s.rating + "/10";
    li.append(title, meta, rating);
    if (SCA.getVariant() === "B") {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn compare-btn";
      btn.textContent = "Compare";
      li.appendChild(btn);
    }
    return li;
  }

  function render(list) {
    shown = list;
    var results = document.getElementById("results");
    results.replaceChildren.apply(results, list.map(card));
    document.getElementById("results-count").textContent = list.length + (list.length === 1 ? " school" : " schools");
    document.getElementById("results-count").hidden = list.length === 0;
    document.getElementById("no-results").hidden = list.length !== 0;
  }

  SCA.shownSchools = function () { return shown; };

  function onSubmit(e) {
    e.preventDefault();
    var v = readForm();
    SCA.loadSchools().then(function (schools) {
      var list = filter(schools, v);
      render(list);
      SCA.track("search", { search_term: v.q, school_level: v.level, location: v.location });
      SCA.track("view_search_results", { search_term: v.q, results_count: list.length });
      var params = new URLSearchParams();
      FIELDS.forEach(function (f) { if (v[f]) params.set(f, v[f]); });
      var query = params.toString();
      history.replaceState(null, "", location.pathname + (query ? "?" + query : ""));
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.getElementById("search-form").addEventListener("submit", onSubmit);
    var params = new URLSearchParams(location.search);
    var restore = FIELDS.some(function (f) { return params.has(f); });
    if (!restore) return;
    FIELDS.forEach(function (f) { document.getElementById(f).value = params.get(f) || ""; });
    var v = readForm();
    SCA.loadSchools().then(function (schools) { render(filter(schools, v)); });
  });
})();
