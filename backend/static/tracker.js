/* Realtime Traffic Tracker — embeddable snippet.
 *
 * A client pastes ONE tag on their site:
 *
 *   <script defer src="https://YOUR-POC-HOST/tracker.js"
 *           data-site="my-site" data-ga4="G-XXXXXXXXXX"></script>
 *
 * What it does:
 *   1. Sends a tiny pageview beacon to this backend's /api/track
 *      (feeds the local demo pipeline).
 *   2. If data-ga4 is present, also loads real gtag so the same pageview
 *      lands in your GA4 property — which the backend reads back via the
 *      GA4 Realtime Data API. Remove the beacon in a pure-GA4 deployment.
 */
(function () {
  var script = document.currentScript;
  if (!script) return;
  var origin = new URL(script.src).origin; // backend origin, derived from this file's own URL
  var site = script.getAttribute("data-site") || location.hostname;
  var ga4 = script.getAttribute("data-ga4");

  var vid;
  try {
    vid = sessionStorage.getItem("poc_vid");
    if (!vid) {
      vid = window.crypto && crypto.randomUUID
        ? crypto.randomUUID()
        : Date.now() + "-" + Math.random().toString(36).slice(2);
      sessionStorage.setItem("poc_vid", vid);
    }
  } catch (e) {
    vid = "anon-" + Math.random().toString(36).slice(2);
  }

  if (ga4) {
    var g = document.createElement("script");
    g.async = true;
    g.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(ga4);
    document.head.appendChild(g);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag("js", new Date());
    gtag("config", ga4);
  }

  var payload = JSON.stringify({
    site: site,
    path: location.pathname,
    visitor_id: vid,
    referrer: document.referrer || null
  });
  // A plain string body ships as text/plain — a CORS "simple request" — so the
  // beacon works cross-origin without a preflight.
  var sent = false;
  if (navigator.sendBeacon) {
    sent = navigator.sendBeacon(origin + "/api/track", payload);
  }
  if (!sent) {
    fetch(origin + "/api/track", { method: "POST", body: payload, keepalive: true })
      .catch(function () {});
  }
})();
