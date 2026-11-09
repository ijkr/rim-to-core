// Loads Google Analytics (via Tag Manager) only after a visitor accepts.
(function () {
  var KEY = "rtc-analytics-consent";
  var gtmId = document.currentScript.dataset.gtmId;
  var bar = document.getElementById("consent");
  var settings = document.getElementById("consent-settings");
  var loaded = false;

  function readChoice() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function saveChoice(value) {
    try { localStorage.setItem(KEY, value); } catch (e) { /* storage blocked */ }
  }

  function loadAnalytics() {
    if (loaded) return;
    loaded = true;
    window.dataLayer = window.dataLayer || [];
    function gtag() { window.dataLayer.push(arguments); }
    gtag("js", new Date());
    var script = document.createElement("script");
    script.async = true;
    script.src = "https://www.googletagmanager.com/gtm.js?id=" + gtmId;
    document.head.appendChild(script);
  }

  // GA sets its cookies on the parent domain, so clear them at each level.
  function clearAnalyticsCookies() {
    var parts = location.hostname.split(".");
    var domains = [""];
    for (var i = 0; i < parts.length - 1; i++) {
      domains.push("; domain=." + parts.slice(i).join("."));
    }
    document.cookie.split(";").forEach(function (cookie) {
      var name = cookie.split("=")[0].trim();
      if (name.indexOf("_ga") !== 0) return;
      domains.forEach(function (domain) {
        document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/" + domain;
      });
    });
  }

  document.getElementById("consent-accept").addEventListener("click", function () {
    saveChoice("granted");
    bar.hidden = true;
    loadAnalytics();
  });

  document.getElementById("consent-decline").addEventListener("click", function () {
    var wasLoaded = loaded;
    saveChoice("denied");
    bar.hidden = true;
    clearAnalyticsCookies();
    // A running tag can only be stopped by leaving the page.
    if (wasLoaded) location.reload();
  });

  settings.hidden = false;
  settings.addEventListener("click", function () { bar.hidden = false; });

  var choice = readChoice();
  if (choice === "granted") loadAnalytics();
  else if (choice !== "denied") bar.hidden = false;
})();
