// The only site code that writes events to the dataLayer (contract: tracking/events.yaml).
window.SCA = window.SCA || {};

SCA.track = function (event, params) {
  var push = { event: event };
  if (event !== "consent_update") push.experiment_variant = SCA.getVariant();
  // Empty fields are pushed as undefined, not left out: GTM's data model keeps keys from earlier
  // pushes, so a missing key would resend the previous search's value. GA4 drops undefined params.
  Object.keys(params || {}).forEach(function (key) {
    var value = params[key];
    push[key] = value === null || value === "" ? undefined : value;
  });
  window.dataLayer.push(push);
};
