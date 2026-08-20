/**
 * Optional visit statistics for adriacare.me.
 * Google Analytics 4 and Yandex Metrica load only after explicit accept.
 * Default is reject: no gtag.js, no Metrica tag, no GA/YM cookies.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "acr-stats-consent";
  var GA_ID = "G-2T17E8PYZK";
  var YM_ID = 111778025;
  var loaded = false;

  var COPY = {
    de: {
      aria: "Einwilligung zur Besuchsstatistik",
      text: "Optional zählen wir Seitenaufrufe mit Google Analytics 4 und Yandex Metrica — nur nach Ihrer Zustimmung. Keine Werbung, kein Session-Replay.",
      privacy: "Datenschutz",
      accept: "Statistik akzeptieren",
      decline: "Ablehnen"
    },
    en: {
      aria: "Consent for visit statistics",
      text: "We can count page views with Google Analytics 4 and Yandex Metrica — only if you accept. No advertising, no session replay.",
      privacy: "Privacy",
      accept: "Accept statistics",
      decline: "Decline"
    },
    fr: {
      aria: "Consentement pour les statistiques de visite",
      text: "Nous pouvons compter les pages vues avec Google Analytics 4 et Yandex Metrica — uniquement si vous acceptez. Pas de publicité, pas d’enregistrement de session.",
      privacy: "Confidentialité",
      accept: "Accepter les statistiques",
      decline: "Refuser"
    },
    es: {
      aria: "Consentimiento para estadísticas de visita",
      text: "Podemos contar las visitas con Google Analytics 4 y Yandex Metrica — solo si usted acepta. Sin publicidad ni grabación de sesión.",
      privacy: "Privacidad",
      accept: "Aceptar estadísticas",
      decline: "Rechazar"
    },
    sr: {
      aria: "Saglasnost za statistiku poseta",
      text: "Posete možemo brojati pomoću Google Analytics 4 i Yandex Metrica — samo ako prihvatite. Bez reklama i bez snimanja sesije.",
      privacy: "Zaštita podataka",
      accept: "Prihvati statistiku",
      decline: "Odbij"
    },
    ru: {
      aria: "Согласие на статистику посещений",
      text: "Мы можем считать просмотры страниц с помощью Google Analytics 4 и Yandex Metrica — только с вашего согласия. Без рекламы и без записи сеанса.",
      privacy: "Конфиденциальность",
      accept: "Принять статистику",
      decline: "Отклонить"
    }
  };

  function pageLang() {
    var lang = (document.documentElement.getAttribute("lang") || "de").toLowerCase();
    return COPY[lang] ? lang : "de";
  }

  function copy() {
    return COPY[pageLang()] || COPY.de;
  }

  function readChoice() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (err) {
      return null;
    }
  }

  function writeChoice(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (err) {
      /* private mode: keep this visit untracked unless already accepted in-memory */
    }
  }

  function privacyHref() {
    var lang = pageLang();
    var base = lang === "de" ? "/datenschutz.html" : "/" + lang + "/datenschutz.html";
    return base + "#statistik";
  }

  function loadGA4() {
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () {
      window.dataLayer.push(arguments);
    };
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_ID;
    document.head.appendChild(s);
    window.gtag("js", new Date());
    window.gtag("config", GA_ID, {
      anonymize_ip: true,
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }

  function loadMetrica() {
    window.ym = window.ym || function () {
      (window.ym.a = window.ym.a || []).push(arguments);
    };
    window.ym.l = 1 * new Date();
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://mc.yandex.ru/metrika/tag.js";
    document.head.appendChild(s);
    window.ym(YM_ID, "init", {
      clickmap: false,
      trackLinks: false,
      accurateTrackBounce: false,
      webvisor: false
    });
  }

  function loadAnalytics() {
    if (loaded) return;
    loaded = true;
    loadGA4();
    loadMetrica();
  }

  function injectStyles() {
    if (document.getElementById("acr-consent-css")) return;
    var style = document.createElement("style");
    style.id = "acr-consent-css";
    style.textContent =
      ".acr-consent{position:fixed;z-index:80;left:0;right:0;bottom:0;background:var(--surface,#fdfcf9);color:var(--ink,#1d2a30);border-top:1px solid var(--line,#d9d4c8);box-shadow:0 -8px 24px rgba(29,42,48,.08);padding:12px 20px;font:14.5px/1.45 \"Avenir Next\",\"Segoe UI\",-apple-system,\"Helvetica Neue\",sans-serif}" +
      ".acr-consent-inner{max-width:1060px;margin:0 auto;display:flex;gap:14px 20px;align-items:center;justify-content:space-between;flex-wrap:wrap}" +
      ".acr-consent p{margin:0;max-width:68ch}" +
      ".acr-consent a{color:var(--sea,#16566b)}" +
      ".acr-consent-actions{display:flex;gap:8px;flex-wrap:wrap}" +
      ".acr-consent button{font:inherit;font-size:13.5px;font-weight:600;border:0;padding:8px 14px;cursor:pointer}" +
      ".acr-consent .acr-accept{background:var(--sea,#16566b);color:var(--on-sea,#f2f6f7)}" +
      ".acr-consent .acr-decline{background:transparent;color:var(--ink,#1d2a30);border:1px solid var(--line,#d9d4c8)}" +
      "body.acr-consent-open{padding-bottom:96px}";
    document.head.appendChild(style);
  }

  function hideBar() {
    var bar = document.getElementById("acr-consent");
    if (bar) bar.remove();
    document.body.classList.remove("acr-consent-open");
  }

  function showBar() {
    if (document.getElementById("acr-consent")) return;
    injectStyles();
    var t = copy();
    var bar = document.createElement("div");
    bar.id = "acr-consent";
    bar.className = "acr-consent";
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-label", t.aria);
    bar.innerHTML =
      '<div class="acr-consent-inner">' +
        "<p>" + t.text + ' <a href="' + privacyHref() + '">' + t.privacy + "</a></p>" +
        '<div class="acr-consent-actions">' +
          '<button type="button" class="acr-accept">' + t.accept + "</button>" +
          '<button type="button" class="acr-decline">' + t.decline + "</button>" +
        "</div>" +
      "</div>";
    document.body.appendChild(bar);
    document.body.classList.add("acr-consent-open");
    bar.querySelector(".acr-accept").addEventListener("click", function () {
      writeChoice("accepted");
      hideBar();
      loadAnalytics();
    });
    bar.querySelector(".acr-decline").addEventListener("click", function () {
      writeChoice("declined");
      hideBar();
    });
  }

  function applyChoice() {
    var choice = readChoice();
    if (choice === "accepted") {
      loadAnalytics();
      hideBar();
      return;
    }
    if (choice === "declined") {
      hideBar();
      return;
    }
    showBar();
  }

  function maybeOpenFromHash() {
    if (location.hash === "#statistik") showBar();
  }

  function start() {
    applyChoice();
    maybeOpenFromHash();
    window.addEventListener("hashchange", maybeOpenFromHash);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
