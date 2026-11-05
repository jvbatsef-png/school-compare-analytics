// The only site code that writes events to the dataLayer (contract: tracking/events.yaml).
window.SCA = window.SCA || {};

SCA.track = function (event, params) {
  var push = { event: event };
  if (event !== "consent_update") push.experiment_variant = SCA.getVariant();
  Object.keys(params || {}).forEach(function (key) {
    var value = params[key];
    if (value !== undefined && value !== null && value !== "") push[key] = value;
  });
  window.dataLayer.push(push);
};
