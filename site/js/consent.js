// Cookie banner and Consent Mode v2 updates. The default and any saved choice are set inline in <head>.
window.SCA = window.SCA || {};

(function () {
  var KEY = "sca_consent";

  function update(state) {
    gtag("consent", "update", {
      analytics_storage: state, ad_storage: state, ad_user_data: state, ad_personalization: state
    });
  }

  function banner() { return document.getElementById("consent-banner"); }

  SCA.consent = {
    save: function (state) {
      update(state);
      try { localStorage.setItem(KEY, state); } catch (e) { /* storage blocked: the choice lasts for this page only */ }
      banner().hidden = true;
      SCA.track("consent_update", { analytics_storage: state, ad_storage: state });
    }
  };

  document.addEventListener("DOMContentLoaded", function () {
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) { /* storage blocked */ }
    if (stored === "granted" || stored === "denied") return; // re-applied inline in <head>
    banner().hidden = false;
    document.getElementById("consent-accept").addEventListener("click", function () { SCA.consent.save("granted"); });
    document.getElementById("consent-reject").addEventListener("click", function () { SCA.consent.save("denied"); });
  });
})();
