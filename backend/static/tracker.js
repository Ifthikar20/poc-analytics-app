/* Realtime Traffic Tracker — embeddable snippet (hardened).
 *
 * Development embed:
 *
 *   <script defer src="https://YOUR-POC-HOST/tracker.js"
 *           data-site="my-site" data-ga4="G-XXXXXXXXXX"></script>
 *
 * Production embed — pin the versioned URL and its SRI hash so a compromised
 * host cannot silently swap the script (compute the hash with:
 * `openssl dgst -sha384 -binary backend/static/tracker.js | openssl base64 -A`):
 *
 *   <script defer src="https://YOUR-POC-HOST/tracker.v1.js"
 *           integrity="sha384-…" crossorigin="anonymous"
 *           data-site="my-site" data-ga4="G-XXXXXXXXXX"></script>
 *
 * Safety properties:
 *   - The whole script runs inside try/catch — it can never break the host page.
 *   - Runs once, in the top frame only, and never counts prerendered pages.
 *   - Beacons over HTTPS only (localhost excepted, for development).
 *   - Honors Do Not Track and Global Privacy Control: sends nothing at all.
 *   - data-ga4 must match ^G-[A-Z0-9]{4,20}$ or gtag is not injected.
 *   - Sends the referrer's ORIGIN only, never the full previous URL.
 *   - No cookies; the visitor id is a per-tab random UUID in sessionStorage.
 */
(function () {
  "use strict";
  try {
    if (window.__pocTrackerRan) return; // pasted twice — run once
    window.__pocTrackerRan = true;

    if (window.top !== window.self) return; // top frame only, no iframe counts

    var nav = navigator;
    if (nav.doNotTrack === "1" || window.doNotTrack === "1" || nav.globalPrivacyControl) {
      return; // the visitor opted out — send nothing, load nothing
    }

    var script = document.currentScript;
    if (!script || !script.src) return;
    var srcUrl = new URL(script.src);
    var origin = srcUrl.origin;
    var isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(srcUrl.hostname);
    if (srcUrl.protocol !== "https:" && !isLocal) return; // never beacon in cleartext

    var site = (script.getAttribute("data-site") || location.hostname).slice(0, 64);
    var ga4 = script.getAttribute("data-ga4");
    if (ga4 && !/^G-[A-Z0-9]{4,20}$/.test(ga4)) ga4 = null; // strict format or nothing

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

    var referrerOrigin = null;
    try {
      if (document.referrer) referrerOrigin = new URL(document.referrer).origin;
    } catch (e) { /* opaque or malformed referrer — drop it */ }

    var send = function () {
      var payload = JSON.stringify({
        site: site,
        path: location.pathname.slice(0, 200),
        visitor_id: vid,
        referrer: referrerOrigin
      });
      // A plain string body ships as text/plain — a CORS "simple request" — so
      // the beacon works cross-origin without a preflight.
      var sent = false;
      if (nav.sendBeacon) {
        sent = nav.sendBeacon(origin + "/api/track", payload);
      }
      if (!sent) {
        fetch(origin + "/api/track", { method: "POST", body: payload, keepalive: true })
          .catch(function () {});
      }
    };

    if (document.prerendering) {
      // A prerendered page may never be shown — count it only on activation.
      document.addEventListener("prerenderingchange", send, { once: true });
    } else {
      send();
    }
  } catch (e) {
    /* an analytics script must never break the page hosting it */
  }
})();
