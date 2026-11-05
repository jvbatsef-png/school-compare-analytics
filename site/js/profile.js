// School page: profile and "Request info" form. Typed values never reach the dataLayer.
window.SCA = window.SCA || {};

(function () {
  var LEVELS = { elementary: "Elementary", middle: "Middle school", high: "High school" };
  var TYPES = { public: "Public", private: "Private", charter: "Charter" };
  var EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  var SOURCES = ["results", "compare"];

  function text(id, value) { document.getElementById(id).textContent = value; }

  function fillYears() {
    var select = document.getElementById("start-year");
    var year = new Date().getFullYear();
    for (var y = year; y <= year + 2; y++) select.add(new Option(String(y), String(y)));
  }

  function showProfile(s) {
    document.title = s.name + " — School Compare";
    text("school-name", s.name);
    text("school-location", s.city + ", " + s.state);
    text("school-level", LEVELS[s.level]);
    text("school-type", TYPES[s.type]);
    text("school-rating", s.rating + "/10");
    text("school-students", s.students.toLocaleString("en-US"));
    text("school-tuition", s.tuition ? "$" + s.tuition.toLocaleString("en-US") + "/yr" : "Free");
    document.getElementById("profile").hidden = false;
  }

  function wireForm(s, source) {
    var form = document.getElementById("lead-form");
    var submit = document.getElementById("lead-submit");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (submit.disabled) return;
      var email = document.getElementById("email").value.trim();
      if (!EMAIL.test(email)) {
        document.getElementById("email-error").hidden = false;
        return;
      }
      document.getElementById("email-error").hidden = true;
      submit.disabled = true;
      var complete = document.getElementById("grade").value !== "" &&
        document.getElementById("start-year").value !== "" &&
        document.getElementById("message").value.trim() !== "";
      setTimeout(function () { // simulated network delay
        form.hidden = true;
        document.getElementById("lead-sent").hidden = false;
        SCA.track("generate_lead", {
          school_id: s.id, source: source, form_complete: complete, lead_type: "info_request"
        });
      }, 300);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var params = new URLSearchParams(location.search);
    var id = params.get("id");
    var source = SOURCES.indexOf(params.get("src")) !== -1 ? params.get("src") : "direct";
    fillYears();
    SCA.loadSchools().then(function (schools) {
      var school = schools.filter(function (s) { return s.id === id; })[0];
      if (!school) {
        document.getElementById("not-found").hidden = false;
        return;
      }
      showProfile(school);
      wireForm(school, source);
      SCA.track("school_profile_view", { school_id: school.id, source: source });
    });
  });
})();
