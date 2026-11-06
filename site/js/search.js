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
    var q = v.q.toLowerCase();
    return schools.filter(function (s) {
      return (!q || s.name.toLowerCase().indexOf(q) !== -1) &&
        (!v.level || s.level === v.level) &&
        (!v.location || s.city + ", " + s.state === v.location);
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
      btn.addEventListener("click", function () { toggleCompare(s); });
      li.appendChild(btn);
    }
    return li;
  }

  // Compare tray (variant B): ids in the order added, max 3.
  var MAX_TRAY = 3;
  var tray = [];
  var tableOpen = false;
  var byId = {};

  function toggleCompare(s) {
    var at = tray.indexOf(s.id);
    document.getElementById("compare-full").hidden = true;
    if (at !== -1) {
      tray.splice(at, 1);
    } else if (tray.length >= MAX_TRAY) {
      document.getElementById("compare-full").hidden = false;
      return;
    } else {
      tray.push(s.id);
      byId[s.id] = s;
      SCA.track("compare_add", {
        school_id: s.id, list_position: shown.indexOf(s) + 1, compare_count: tray.length
      });
    }
    renderTray();
  }

  function renderTray() {
    document.querySelectorAll("#results .card").forEach(function (el) {
      var btn = el.querySelector(".compare-btn");
      if (!btn) return;
      var added = tray.indexOf(el.dataset.schoolId) !== -1;
      btn.textContent = added ? "Added ✓" : "Compare";
      btn.setAttribute("aria-pressed", added ? "true" : "false");
    });
    var list = document.getElementById("compare-list");
    list.replaceChildren.apply(list, tray.map(function (id) {
      var li = document.createElement("li");
      li.dataset.schoolId = id;
      li.textContent = byId[id].name;
      return li;
    }));
    document.getElementById("compare-tray").hidden = tray.length === 0;
    document.getElementById("compare-open").disabled = tray.length < 2;
    if (tableOpen && tray.length < 2) closeTable();
    else if (tableOpen) renderTable();
  }

  function renderTable() {
    var rows = [
      ["Location", function (s) { return s.city + ", " + s.state; }],
      ["Level", function (s) { return LEVELS[s.level]; }],
      ["Type", function (s) { return TYPES[s.type]; }],
      ["Rating", function (s) { return s.rating + "/10"; }],
      ["Students", function (s) { return s.students.toLocaleString("en-US"); }],
      ["Tuition", function (s) { return s.tuition ? "$" + s.tuition.toLocaleString("en-US") + "/yr" : "Free"; }]
    ];
    var schools = tray.map(function (id) { return byId[id]; });
    var head = document.createElement("tr");
    head.appendChild(document.createElement("td"));
    schools.forEach(function (s) {
      var th = document.createElement("th");
      th.scope = "col";
      th.dataset.schoolId = s.id;
      var link = document.createElement("a");
      link.href = "school.html?id=" + s.id + "&src=compare";
      link.textContent = s.name;
      th.appendChild(link);
      head.appendChild(th);
    });
    var body = rows.map(function (row) {
      var tr = document.createElement("tr");
      var th = document.createElement("th");
      th.scope = "row";
      th.textContent = row[0];
      tr.appendChild(th);
      schools.forEach(function (s) {
        var td = document.createElement("td");
        td.textContent = row[1](s);
        tr.appendChild(td);
      });
      return tr;
    });
    var table = document.querySelector("#compare-table table");
    table.replaceChildren.apply(table, [head].concat(body));
  }

  function openTable() {
    if (tableOpen) return; // one compare_view per opening
    tableOpen = true;
    renderTable();
    document.getElementById("compare-table").hidden = false;
    document.getElementById("compare-table").scrollIntoView({ block: "start" });
    SCA.track("compare_view", { compare_count: tray.length, school_ids: tray.join(",") });
  }

  function closeTable() {
    tableOpen = false;
    document.getElementById("compare-table").hidden = true;
  }

  function render(list) {
    shown = list;
    var results = document.getElementById("results");
    results.replaceChildren.apply(results, list.map(card));
    document.getElementById("results-count").textContent = list.length + (list.length === 1 ? " school" : " schools");
    document.getElementById("results-count").hidden = list.length === 0;
    document.getElementById("no-results").hidden = list.length !== 0;
    renderTray();
  }

  // Location is a closed list of "City, ST" values, so GA4 gets one clean value per city.
  function buildLocations(schools) {
    var seen = {};
    schools.forEach(function (s) { seen[s.city + ", " + s.state] = true; });
    var select = document.getElementById("location");
    Object.keys(seen).sort().forEach(function (loc) {
      var opt = document.createElement("option");
      opt.value = loc;
      opt.textContent = loc;
      select.appendChild(opt);
    });
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
    document.getElementById("compare-open").addEventListener("click", openTable);
    document.getElementById("compare-close").addEventListener("click", closeTable);
    SCA.loadSchools().then(function (schools) {
      buildLocations(schools);
      // Restore runs after the options exist, so a saved location can be selected.
      var params = new URLSearchParams(location.search);
      var restore = FIELDS.some(function (f) { return params.has(f); });
      if (!restore) return;
      FIELDS.forEach(function (f) { document.getElementById(f).value = params.get(f) || ""; });
      var select = document.getElementById("location");
      if (select.selectedIndex === -1) select.selectedIndex = 0; // unknown value: Any location
      render(filter(schools, readForm()));
    });
  });
})();
