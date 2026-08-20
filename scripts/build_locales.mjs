#!/usr/bin/env node
/**
 * Bake crawlable language copies for GitHub Pages.
 *
 * German markup in the repo-root HTML files is the source of truth.
 * Translations live in each page's `var I18N = { ... }` object.
 *
 * Writes:
 *   - updated German files (hreflang, URL switcher, no JS language swap)
 *   - /en /fr /es /sr /ru HTML with translations already in the markup
 *   - sitemap.xml with xhtml:hreflang alternates
 *
 * Usage: node scripts/build_locales.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SITE = "https://adriacare.me";
const LASTMOD = "2026-08-20";

const LANGS = ["de", "en", "fr", "es", "sr", "ru"];
const LOCALE_LANGS = LANGS.filter((l) => l !== "de");

const OG_LOCALE = {
  de: "de_DE",
  en: "en_GB",
  fr: "fr_FR",
  es: "es_ES",
  sr: "sr_RS",
  ru: "ru_RU",
};

const CONTENT_PAGES = [
  "index.html",
  "montenegro.html",
  "wellness.html",
  "excursions.html",
  "pilgrimage.html",
  "neighbors.html",
];

const LEGAL_PAGES = ["impressum.html", "datenschutz.html"];
const ALL_PAGES = [...CONTENT_PAGES, ...LEGAL_PAGES];

const PAGE_PATH = {
  "index.html": "/",
  "montenegro.html": "/montenegro.html",
  "wellness.html": "/wellness.html",
  "excursions.html": "/excursions.html",
  "pilgrimage.html": "/pilgrimage.html",
  "neighbors.html": "/neighbors.html",
  "impressum.html": "/impressum.html",
  "datenschutz.html": "/datenschutz.html",
};

const PAGE_PRIORITY = {
  "index.html": "1.0",
  "montenegro.html": "0.7",
  "wellness.html": "0.7",
  "excursions.html": "0.7",
  "pilgrimage.html": "0.7",
  "neighbors.html": "0.7",
  "impressum.html": "0.3",
  "datenschutz.html": "0.3",
};

const PAGE_CHANGEFREQ = {
  "impressum.html": "yearly",
  "datenschutz.html": "yearly",
};

/** Titles/descriptions follow the existing German meta, in the site's current wording. */
const PAGE_META = {
  "index.html": {
    de: {
      title: "Adria Care Residenz — saisonale Pflegeaufenthalte in Budva",
      desc: "Saisonale Pflegeaufenthalte in Budva: 4–12 Wochen für Gruppen aus europäischen Pflegeeinrichtungen, Pflegegrade 1–2, Betreuung in sechs Sprachen. Eröffnung 2027.",
    },
    en: {
      title: "Adria Care Residence — seasonal care stays in Budva",
      desc: "Seasonal care stays in Budva: 4–12 weeks for groups from European care homes, care levels 1–2, support in six languages. Opening 2027.",
    },
    fr: {
      title: "Adria Care Résidence — séjours de soins saisonniers à Budva",
      desc: "Séjours de soins saisonniers à Budva : 4 à 12 semaines pour des groupes d’établissements européens, niveaux de dépendance 1–2, accompagnement en six langues. Ouverture en 2027.",
    },
    es: {
      title: "Adria Care Residencia — estancias de cuidados estacionales en Budva",
      desc: "Estancias de cuidados estacionales en Budva: 4–12 semanas para grupos de centros europeos, grados 1–2, atención en seis idiomas. Apertura en 2027.",
    },
    sr: {
      title: "Adria Care Rezidencija — sezonski boravci sa negom u Budvi",
      desc: "Sezonski boravci sa negom u Budvi: 4–12 nedelja za grupe iz evropskih ustanova, stepeni nege 1–2, pratnja na šest jezika. Otvaranje 2027.",
    },
    ru: {
      title: "Adria Care Residenz — сезонные заезды с уходом в Будве",
      desc: "Сезонные заезды с уходом в Будве: 4–12 недель для групп из европейских учреждений, степени ухода 1–2, сопровождение на шести языках. Открытие — 2027.",
    },
  },
  "montenegro.html": {
    de: {
      title: "Montenegro: Klima und Wege — Adria Care Residenz",
      desc: "Montenegro als Standort der Adria Care Residenz: Klima und Temperaturen in Budva, ebene Spazierwege sowie begleitete Ausflüge an Küste, Seen und Berge.",
    },
    en: {
      title: "Montenegro: climate and routes — Adria Care Residenz",
      desc: "Montenegro as the location of Adria Care Residenz: climate and temperatures in Budva, level walking routes and accompanied excursions to the coast, lakes and mountains.",
    },
    fr: {
      title: "Monténégro : climat et itinéraires — Adria Care Residenz",
      desc: "Le Monténégro, lieu de l’Adria Care Residenz : climat et températures à Budva, promenades planes et excursions accompagnées vers la côte, les lacs et les montagnes.",
    },
    es: {
      title: "Montenegro: clima y rutas — Adria Care Residenz",
      desc: "Montenegro como ubicación de Adria Care Residenz: clima y temperaturas en Budva, paseos llanos y excursiones acompañadas a la costa, lagos y montañas.",
    },
    sr: {
      title: "Crna Gora: klima i staze — Adria Care Residenz",
      desc: "Crna Gora kao lokacija Adria Care Residenz: klima i temperature u Budvi, ravna šetališta i izleti uz pratnju do obale, jezera i planina.",
    },
    ru: {
      title: "Черногория: климат и маршруты — Adria Care Residenz",
      desc: "Черногория как место Adria Care Residenz: климат и температуры в Будве, ровные прогулочные маршруты и поездки с сопровождением к морю, озёрам и в горы.",
    },
  },
  "wellness.html": {
    de: {
      title: "Gesundheit und Bewegung — Adria Care Residenz",
      desc: "Gesundheit und Bewegung in Montenegro: Morgengymnastik, Gleichgewichtstraining, Thalasso und geprüfte Spazierwege — begleitet und an die Mobilität angepasst.",
    },
    en: {
      title: "Health and movement — Adria Care Residenz",
      desc: "Health and movement in Montenegro: morning exercise, balance training, thalasso and assessed walking routes — accompanied and adapted to mobility.",
    },
    fr: {
      title: "Santé et mouvement — Adria Care Residenz",
      desc: "Santé et mouvement au Monténégro : gymnastique matinale, travail de l’équilibre, thalasso et sentiers vérifiés — accompagnés et adaptés à la mobilité.",
    },
    es: {
      title: "Salud y movimiento — Adria Care Residenz",
      desc: "Salud y movimiento en Montenegro: gimnasia matinal, equilibrio, talasoterapia y senderos revisados — con acompañamiento y adaptados a la movilidad.",
    },
    sr: {
      title: "Zdravlje i kretanje — Adria Care Residenz",
      desc: "Zdravlje i kretanje u Crnoj Gori: jutarnja gimnastika, vežbe ravnoteže, talaso i proverene staze — uz pratnju i prilagođeno pokretljivosti.",
    },
    ru: {
      title: "Здоровье и движение — Adria Care Residenz",
      desc: "Здоровье и движение в Черногории: утренняя гимнастика, упражнения на равновесие, талассотерапия и проверенные маршруты — с сопровождением и с учётом подвижности.",
    },
  },
  "pilgrimage.html": {
    de: {
      title: "Begleitete Pilgerfahrten — Adria Care Residenz",
      desc: "Begleitete Pilgerfahrten ab Budva nach Ostrog, Cetinje, Reževići, Podmaine, Gospa od Škrpjela und Kotor — in ruhigem Tempo und mit geplanten Pausen.",
    },
    en: {
      title: "Accompanied pilgrimages — Adria Care Residenz",
      desc: "Accompanied pilgrimages from Budva to Ostrog, Cetinje, Reževići, Podmaine, Gospa od Škrpjela and Kotor — at a calm pace with planned rest stops.",
    },
    fr: {
      title: "Pèlerinages accompagnés — Adria Care Residenz",
      desc: "Pèlerinages accompagnés depuis Budva vers Ostrog, Cetinje, Reževići, Podmaine, Gospa od Škrpjela et Kotor — à un rythme calme, avec des pauses prévues.",
    },
    es: {
      title: "Peregrinaciones acompañadas — Adria Care Residenz",
      desc: "Peregrinaciones acompañadas desde Budva a Ostrog, Cetinje, Reževići, Podmaine, Gospa od Škrpjela y Kotor — a un ritmo tranquilo y con pausas previstas.",
    },
    sr: {
      title: "Hodočašća uz pratnju — Adria Care Residenz",
      desc: "Hodočašća uz pratnju iz Budve do Ostroga, Cetinja, Reževića, Podmaine, Gospe od Škrpjela i Kotora — mirnim tempom i sa planiranim pauzama.",
    },
    ru: {
      title: "Паломничества с сопровождением — Adria Care Residenz",
      desc: "Паломничества с сопровождением из Будвы в Острог, Цетине, Режевичи, Подмаине, Госпа-од-Шкрпьела и Котор — в спокойном темпе и с запланированными паузами.",
    },
  },
  "excursions.html": {
    de: {
      title: "Ausflüge in Montenegro — Adria Care Residenz",
      desc: "Acht begleitete Ausflugsrouten durch Montenegro: kurze Gehstrecken, geplante Pausen, lizenzierte Guides und klimatisierte Kleinbusse.",
    },
    en: {
      title: "Excursions in Montenegro — Adria Care Residenz",
      desc: "Eight accompanied excursion routes through Montenegro: short walking distances, planned rest stops, licensed guides and air-conditioned minibuses.",
    },
    fr: {
      title: "Excursions au Monténégro — Adria Care Residenz",
      desc: "Huit circuits accompagnés au Monténégro : peu de marche, pauses prévues, guides agréés et minibus climatisé.",
    },
    es: {
      title: "Excursiones en Montenegro — Adria Care Residenz",
      desc: "Ocho rutas de excursión acompañadas por Montenegro: trayectos a pie cortos, pausas previstas, guías con licencia y microbuses climatizados.",
    },
    sr: {
      title: "Izleti u Crnoj Gori — Adria Care Residenz",
      desc: "Osam izleta uz pratnju kroz Crnu Goru: kratke pešačke deonice, planirane pauze, licencirani vodiči i klimatizovani minibusi.",
    },
    ru: {
      title: "Экскурсии по Черногории — Adria Care Residenz",
      desc: "Восемь маршрутов с сопровождением по Черногории: короткие пешие участки, запланированные паузы, лицензированные гиды и микроавтобусы с кондиционером.",
    },
  },
  "neighbors.html": {
    de: {
      title: "Nachbarländer entdecken — Adria Care Residenz",
      desc: "Begleitete Reisen ab Budva nach Kroatien, Bosnien-Herzegowina, Albanien und Nordmazedonien — mit kurzen Gehstrecken, Pflegebegleitung und Hilfe an der Grenze.",
    },
    en: {
      title: "Neighbouring countries — Adria Care Residenz",
      desc: "Accompanied trips from Budva to Croatia, Bosnia and Herzegovina, Albania and North Macedonia — with short walking distances, care support and help at the border.",
    },
    fr: {
      title: "Pays voisins — Adria Care Residenz",
      desc: "Voyages accompagnés depuis Budva vers la Croatie, la Bosnie-Herzégovine, l’Albanie et la Macédoine du Nord — avec peu de marche, un accompagnement soignant et une aide à la frontière.",
    },
    es: {
      title: "Países vecinos — Adria Care Residenz",
      desc: "Viajes acompañados desde Budva a Croacia, Bosnia y Herzegovina, Albania y Macedonia del Norte — con trayectos a pie cortos, acompañamiento de cuidados y ayuda en la frontera.",
    },
    sr: {
      title: "Susjedne zemlje — Adria Care Residenz",
      desc: "Putovanja uz pratnju iz Budve u Hrvatsku, Bosnu i Hercegovinu, Albaniju i Severnu Makedoniju — sa kratkim pešačenjem, negom i pomoći na granici.",
    },
    ru: {
      title: "Соседние страны — Adria Care Residenz",
      desc: "Поездки с сопровождением из Будвы в Хорватию, Боснию и Герцеговину, Албанию и Северную Македонию — с короткими пешими участками, уходом и помощью на границе.",
    },
  },
  "impressum.html": {
    de: {
      title: "Impressum — Adria Care Residenz",
      desc: "Impressum der Adria Care Residenz: Betreiber MK REHAB DOO, Podgorica, Montenegro.",
    },
    en: {
      title: "Legal notice (German) — Adria Care Residenz",
      desc: "Legal notice of Adria Care Residenz: operator MK REHAB DOO, Podgorica, Montenegro. The legally binding text is in German.",
    },
    fr: {
      title: "Mentions légales (texte allemand) — Adria Care Residenz",
      desc: "Mentions légales de l’Adria Care Residenz : exploitant MK REHAB DOO, Podgorica, Monténégro. Le texte juridiquement contraignant est en allemand.",
    },
    es: {
      title: "Aviso legal (texto alemán) — Adria Care Residenz",
      desc: "Aviso legal de Adria Care Residenz: operador MK REHAB DOO, Podgorica, Montenegro. El texto jurídicamente vinculante está en alemán.",
    },
    sr: {
      title: "Impressum (nemački tekst) — Adria Care Residenz",
      desc: "Impressum Adria Care Residenz: operator MK REHAB DOO, Podgorica, Crna Gora. Pravno obavezujući tekst je na nemačkom.",
    },
    ru: {
      title: "Выходные данные (немецкий текст) — Adria Care Residenz",
      desc: "Выходные данные Adria Care Residenz: оператор MK REHAB DOO, Подгорица, Черногория. Юридически обязательный текст — на немецком языке.",
    },
  },
  "datenschutz.html": {
    de: {
      title: "Datenschutz — Adria Care Residenz",
      desc: "Datenschutzerklärung der Adria Care Residenz: Verantwortlicher MK REHAB DOO, optionale Besuchsstatistik nach Einwilligung, keine Marketing-Cookies.",
    },
    en: {
      title: "Privacy (German) — Adria Care Residenz",
      desc: "Privacy notice of Adria Care Residenz: controller MK REHAB DOO, optional visit statistics after consent, no marketing cookies. The legally binding text is in German.",
    },
    fr: {
      title: "Protection des données (texte allemand) — Adria Care Residenz",
      desc: "Déclaration de confidentialité de l’Adria Care Residenz : responsable MK REHAB DOO, statistiques de visite facultatives après consentement, pas de cookies marketing. Le texte juridiquement contraignant est en allemand.",
    },
    es: {
      title: "Protección de datos (texto alemán) — Adria Care Residenz",
      desc: "Aviso de privacidad de Adria Care Residenz: responsable MK REHAB DOO, estadísticas de visita opcionales tras el consentimiento, sin cookies de marketing. El texto jurídicamente vinculante está en alemán.",
    },
    sr: {
      title: "Zaštita podataka (nemački tekst) — Adria Care Residenz",
      desc: "Izjava o zaštiti podataka Adria Care Residenz: odgovorni MK REHAB DOO, opciona statistika poseta nakon saglasnosti, bez marketinških kolačića. Pravno obavezujući tekst je na nemačkom.",
    },
    ru: {
      title: "Защита данных (немецкий текст) — Adria Care Residenz",
      desc: "Уведомление о защите данных Adria Care Residenz: ответственный MK REHAB DOO, необязательная статистика посещений после согласия, без маркетинговых cookie. Юридически обязательный текст — на немецком языке.",
    },
  },
};

const LEGAL_UI = {
  en: {
    back: "← Home",
    home: "Home",
    eyebrow: "Legal",
    notice_impressum:
      "The legally binding operator information is the German text below. Adria Care Residenz is the public name of the project; the legal operator is MK REHAB DOO in Podgorica, Montenegro. There is no German GmbH and no phone number on this website.",
    notice_datenschutz:
      "The legally binding privacy notice is the German text below. The controller is MK REHAB DOO. After consent, the site may use Google Analytics 4 and Yandex Metrica to count visits. There are no marketing pixels or ad networks. There is no phone number on this website.",
  },
  fr: {
    back: "← Accueil",
    home: "Accueil",
    eyebrow: "Mentions légales",
    notice_impressum:
      "Les informations juridiquement contraignantes sur l’exploitant sont le texte allemand ci-dessous. Adria Care Residenz est le nom public du projet ; l’exploitant légal est MK REHAB DOO à Podgorica, Monténégro. Il n’existe pas de GmbH allemande et aucun numéro de téléphone n’est publié.",
    notice_datenschutz:
      "La déclaration de confidentialité juridiquement contraignante est le texte allemand ci-dessous. Le responsable est MK REHAB DOO. Après consentement, le site peut utiliser Google Analytics 4 et Yandex Metrica pour compter les visites. Il n’y a ni pixels marketing ni réseaux publicitaires. Aucun numéro de téléphone n’est publié.",
  },
  es: {
    back: "← Inicio",
    home: "Inicio",
    eyebrow: "Aviso legal",
    notice_impressum:
      "La información jurídicamente vinculante sobre el operador es el texto alemán siguiente. Adria Care Residenz es el nombre público del proyecto; el operador legal es MK REHAB DOO en Podgorica, Montenegro. No existe una GmbH alemana y no se publica ningún número de teléfono.",
    notice_datenschutz:
      "El aviso de privacidad jurídicamente vinculante es el texto alemán siguiente. El responsable es MK REHAB DOO. Tras el consentimiento, el sitio puede usar Google Analytics 4 y Yandex Metrica para contar visitas. No hay píxeles de marketing ni redes publicitarias. No se publica ningún número de teléfono.",
  },
  sr: {
    back: "← Početna",
    home: "Početna",
    eyebrow: "Pravne informacije",
    notice_impressum:
      "Pravno obavezujući podaci o operatoru su nemački tekst ispod. Adria Care Residenz je javni naziv projekta; pravni operator je MK REHAB DOO u Podgorici, Crna Gora. Ne postoji nemački GmbH i na sajtu nema broja telefona.",
    notice_datenschutz:
      "Pravno obavezujuća izjava o zaštiti podataka je nemački tekst ispod. Odgovorni je MK REHAB DOO. Nakon saglasnosti sajt može koristiti Google Analytics 4 i Yandex Metrica za brojanje poseta. Nema marketinških piksela ni reklamnih mreža. Broj telefona se ne objavljuje.",
  },
  ru: {
    back: "← Главная",
    home: "Главная",
    eyebrow: "Правовая информация",
    notice_impressum:
      "Юридически обязательные сведения об операторе — немецкий текст ниже. Adria Care Residenz — публичное название проекта; правовой оператор — MK REHAB DOO в Подгорице, Черногория. Немецкого GmbH нет, номер телефона на сайте не публикуется.",
    notice_datenschutz:
      "Юридически обязательное уведомление о защите данных — немецкий текст ниже. Ответственный — MK REHAB DOO. После согласия сайт может использовать Google Analytics 4 и Yandex Metrica для подсчёта визитов. Маркетинговых пикселей и рекламных сетей нет. Номер телефона на сайте не публикуется.",
  },
};

const LANG_CSS = `  .lang { display: flex; gap: 2px; border: 1px solid var(--line); }
  .lang a {
    font: inherit; font-size: 12.5px; font-weight: 600; letter-spacing: 0.05em;
    background: transparent; color: var(--ink-soft); text-decoration: none;
    padding: 6px 9px; display: inline-block;
  }
  .lang a[aria-current="page"] { background: var(--sea); color: var(--on-sea); }
  .lang a:focus-visible { outline: 2px solid var(--gold); outline-offset: -2px; }
  .head-right { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
  .legal-note {
    margin-top: 20px; max-width: 62ch; font-size: 16px; line-height: 1.55;
    color: var(--ink); background: var(--surface);
    border: 1px solid var(--line); border-left: 3px solid var(--gold);
    padding: 14px 16px;
  }
`;

function pageHref(lang, file) {
  const suffix = PAGE_PATH[file];
  if (lang === "de") return suffix;
  return suffix === "/" ? `/${lang}/` : `/${lang}${suffix}`;
}

function pageUrl(lang, file) {
  return SITE + pageHref(lang, file);
}

function escAttr(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function extractI18N(html) {
  const start = html.indexOf("var I18N = {");
  if (start < 0) return null;
  const brace = html.indexOf("{", start);
  let depth = 0;
  let inStr = null;
  let esc = false;
  for (let i = brace; i < html.length; i++) {
    const c = html[i];
    if (inStr) {
      if (esc) {
        esc = false;
        continue;
      }
      if (c === "\\") {
        esc = true;
        continue;
      }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      inStr = c;
      continue;
    }
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) {
        const obj = html.slice(brace, i + 1);
        return Function(`"use strict"; return (${obj});`)();
      }
    }
  }
  throw new Error("Unbalanced I18N object");
}

function findClose(html, afterOpen, tag) {
  const openRe = new RegExp(`<${tag}(?:\\s|/?>)`, "i");
  const closeRe = new RegExp(`</${tag}>`, "i");
  let depth = 1;
  let i = afterOpen;
  while (i < html.length && depth > 0) {
    const rest = html.slice(i);
    const nextOpen = rest.search(openRe);
    const nextClose = rest.search(closeRe);
    if (nextClose < 0) throw new Error(`No closing </${tag}>`);
    if (nextOpen >= 0 && nextOpen < nextClose) {
      depth++;
      i += nextOpen + 1;
    } else {
      depth--;
      if (depth === 0) return i + nextClose;
      i += nextClose + 2;
    }
  }
  throw new Error(`Unclosed <${tag}>`);
}

function applyDict(html, dict) {
  const matches = [];
  const re = /<([a-zA-Z][\w-]*)([^>]*\sdata-i18n=["']([^"']+)["'][^>]*)>/g;
  let m;
  while ((m = re.exec(html))) {
    const tag = m[1];
    const key = m[3];
    if (dict[key] == null) continue;
    const afterOpen = m.index + m[0].length;
    const closeIdx = findClose(html, afterOpen, tag);
    matches.push({ afterOpen, closeIdx, value: dict[key] });
  }
  let out = html;
  for (const item of matches.reverse()) {
    out = out.slice(0, item.afterOpen) + item.value + out.slice(item.closeIdx);
  }

  out = out.replace(
    /<([a-zA-Z][\w-]*)([^>]*\sdata-i18n-ph=["']([^"']+)["'][^>]*)>/g,
    (full, _tag, _attrs, key) => {
      if (dict[key] == null) return full;
      const escaped = escAttr(dict[key]);
      if (/\splaceholder=/.test(full)) {
        return full.replace(/\splaceholder="[^"]*"/, ` placeholder="${escaped}"`);
      }
      return full.replace(/>$/, ` placeholder="${escaped}">`);
    }
  );
  return out;
}

function convertImgPaths(html) {
  return html.replace(/\bsrc=(["'])img\//g, "src=$1/img/");
}

const CONSENT_SCRIPT = '<script src="/js/consent-analytics.js" defer></script>';

function ensureConsentScript(html) {
  if (html.includes("consent-analytics.js")) return html;
  return html.replace(/\s*<\/body>/, `\n${CONSENT_SCRIPT}\n</body>`);
}

const LANG_LINK_CSS = `  .lang a {
    font: inherit; font-size: 12.5px; font-weight: 600; letter-spacing: 0.05em;
    background: transparent; color: var(--ink-soft); text-decoration: none;
    padding: 6px 9px; display: inline-block;
  }`;

function convertLangCss(html) {
  let out = html.replace(/\.lang button/g, ".lang a");
  out = out.replace(/\.lang a\[aria-pressed="true"\]/g, '.lang a[aria-current="page"]');
  if (/[ \t]*\.lang a \{[^}]*\}/.test(out)) {
    out = out.replace(/[ \t]*\.lang a \{[^}]*\}/, LANG_LINK_CSS);
  }
  return out;
}

function hreflangBlock(file) {
  const lines = LANGS.map(
    (lang) => `<link rel="alternate" hreflang="${lang}" href="${pageUrl(lang, file)}">`
  );
  lines.push(`<link rel="alternate" hreflang="x-default" href="${pageUrl("de", file)}">`);
  return lines.join("\n");
}

function upsertHreflang(html, file) {
  let out = html.replace(/\n?<link rel="alternate" hreflang="[^"]+" href="[^"]+">/g, "");
  if (/<link rel="canonical" href="[^"]+">/.test(out)) {
    return out.replace(/<link rel="canonical" href="[^"]+">/, (m) => `${m}\n${hreflangBlock(file)}`);
  }
  return out.replace("</head>", `${hreflangBlock(file)}\n</head>`);
}

function setHtmlLang(html, lang) {
  return html.replace(/<html\s+lang="[^"]*">/, `<html lang="${lang}">`);
}

function setCanonicalAndSocial(html, lang, file) {
  const url = pageUrl(lang, file);
  const meta = PAGE_META[file][lang];
  const locale = OG_LOCALE[lang];
  const alts = LANGS.filter((l) => l !== lang)
    .map((l) => `<meta property="og:locale:alternate" content="${OG_LOCALE[l]}">`)
    .join("\n");

  let out = html;
  out = out.replace(/<title>[^<]*<\/title>/, `<title>${escAttr(meta.title)}</title>`);
  out = out.replace(
    /<meta name="description" content="[^"]*">/,
    `<meta name="description" content="${escAttr(meta.desc)}">`
  );
  out = out.replace(/<link rel="canonical" href="[^"]+">/, `<link rel="canonical" href="${url}">`);
  out = out.replace(
    /<meta property="og:title" content="[^"]*">/,
    `<meta property="og:title" content="${escAttr(meta.title)}">`
  );
  out = out.replace(
    /<meta property="og:description" content="[^"]*">/,
    `<meta property="og:description" content="${escAttr(meta.desc)}">`
  );
  out = out.replace(/<meta property="og:url" content="[^"]*">/, `<meta property="og:url" content="${url}">`);
  out = out.replace(
    /<meta property="og:locale" content="[^"]*">/,
    `<meta property="og:locale" content="${locale}">`
  );
  if (/<meta property="og:locale:alternate"/.test(out)) {
    out = out.replace(
      /(?:<meta property="og:locale:alternate" content="[^"]*">\n?)+/,
      `${alts}\n`
    );
  } else {
    out = out.replace(
      /<meta property="og:locale" content="[^"]*">/,
      (m) => `${m}\n${alts}`
    );
  }
  out = out.replace(
    /<meta name="twitter:title" content="[^"]*">/,
    `<meta name="twitter:title" content="${escAttr(meta.title)}">`
  );
  out = out.replace(
    /<meta name="twitter:description" content="[^"]*">/,
    `<meta name="twitter:description" content="${escAttr(meta.desc)}">`
  );
  return out;
}

function buildSwitcher(lang, file) {
  const items = LANGS.map((l) => {
    const current = l === lang ? ' aria-current="page"' : "";
    return `        <a href="${pageHref(l, file)}" hreflang="${l}" lang="${l}"${current}>${l.toUpperCase()}</a>`;
  }).join("\n");
  return `<nav class="lang" aria-label="Sprache / Language">\n${items}\n      </nav>`;
}

function setSwitcher(html, lang, file) {
  const nav = buildSwitcher(lang, file);
  if (/<nav class="lang"[\s\S]*?<\/nav>/.test(html)) {
    return html.replace(/\s*<nav class="lang"[\s\S]*?<\/nav>/, `\n      ${nav}`);
  }
  if (/<a class="backlink"/.test(html)) {
    return html.replace(
      /(<header class="site">\s*<a class="brand"[^>]*>[\s\S]*?<\/a>\s*)(<a class="backlink"[^>]*>[\s\S]*?<\/a>)\s*<\/header>/,
      `$1<div class="head-right">\n      $2\n${nav}\n    </div>\n  </header>`
    );
  }
  return html;
}

function disableClientI18N(html) {
  return html
    .replace(
      /\n  \/\* Capture German[\s\S]*?if \(saved && I18N\[saved\] && saved !== 'de'\) setLang\(saved\);\n/,
      "\n"
    )
    .replace(
      /\n  var DE = \{\};[\s\S]*?if \(saved && I18N\[saved\] && saved !== 'de'\) setLang\(saved\);\n/,
      "\n"
    );
}

function stripI18NKeepForm(html) {
  return html.replace(/<script>([\s\S]*?)<\/script>/g, (full, body) => {
    if (!body.includes("var I18N")) return full;
    const marker = "document.getElementById('lead-form')";
    const idx = body.indexOf(marker);
    if (idx >= 0) {
      return `<script>\n  ${body.slice(idx).trim()}\n</script>`;
    }
    return "";
  });
}

function stripHtml(value) {
  return String(value)
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}

function rewriteJsonLd(html, lang, dict, file) {
  if (file !== "index.html" || !dict) return html;
  const meta = PAGE_META[file][lang];
  const faqKeys = ["1", "2", "3", "4", "5", "6"];
  const entities = faqKeys.map((n) => ({
    "@type": "Question",
    name: stripHtml(dict[`q${n}`]),
    acceptedAnswer: { "@type": "Answer", text: stripHtml(dict[`a${n}`]) },
  }));
  const faq = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    inLanguage: lang,
    mainEntity: entities,
  };
  const org = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Adria Care Residenz",
    legalName: 'DRUŠTVO SA OGRANIČENOM ODGOVORNOŠĆU "MK REHAB" PODGORICA',
    alternateName: "MK REHAB DOO",
    url: pageUrl(lang, file),
    email: "partners@adriacare.me",
    logo: `${SITE}/img/mne-hero.webp`,
    description: meta.desc,
    address: {
      "@type": "PostalAddress",
      streetAddress: "Vojina Katnića C-14/19",
      addressLocality: "Podgorica",
      addressCountry: "ME",
    },
    areaServed: ["DE", "AT", "CH", "FR", "ES"],
  };
  let out = html.replace(
    /<script type="application\/ld\+json">\{"@context":\s*"https:\/\/schema\.org",\s*"@type":\s*"Organization"[\s\S]*?<\/script>/,
    `<script type="application/ld+json">${JSON.stringify(org)}</script>`
  );
  out = out.replace(
    /<script type="application\/ld\+json">\{"@context":\s*"https:\/\/schema\.org",\s*"@type":\s*"FAQPage"[\s\S]*?<\/script>/,
    `<script type="application/ld+json">${JSON.stringify(faq)}</script>`
  );
  return out;
}

function updateDatenschutzLanguageParagraph(html) {
  const oldPara =
    "<p>Wenn Sie auf der Startseite eine Sprache wählen, kann Ihr Browser diese Auswahl lokal speichern (localStorage, Schlüssel <code>acr-lang</code>). Diese Speicherung bleibt auf Ihrem Gerät und wird nicht an uns übermittelt.</p>";
  const nextPara =
    "<p>Die Website veröffentlicht sprachliche Fassungen unter eigenen Adressen (zum Beispiel <code>/en/</code> für Englisch). Die Sprachwahl erfolgt über diese Adressen. Es wird kein Cookie und kein localStorage-Eintrag für die Sprache gesetzt.</p>";
  if (html.includes(oldPara)) return html.replace(oldPara, nextPara);
  return html;
}

function ensureLegalCss(html) {
  if (html.includes(".lang a {") || html.includes(".legal-note")) {
    if (html.includes(".lang a {")) return html;
  }
  if (html.includes(".lang {")) return html;
  return html.replace("</style>", `${LANG_CSS}</style>`);
}

function localizeLegalChrome(html, lang, file) {
  const ui = LEGAL_UI[lang];
  if (!ui) return html;
  const notice = file === "impressum.html" ? ui.notice_impressum : ui.notice_datenschutz;
  let out = html;
  out = out.replace(
    /<a class="backlink" href="index\.html">[^<]*<\/a>/,
    `<a class="backlink" href="index.html">${escAttr(ui.back)}</a>`
  );
  out = out.replace(
    /<p class="eyebrow">Rechtliches<\/p>/,
    `<p class="eyebrow">${escAttr(ui.eyebrow)}</p>`
  );
  if (!out.includes("class=\"legal-note\"")) {
    out = out.replace(
      /(<p class="lede">[\s\S]*?<\/p>)/,
      `$1\n    <p class="legal-note">${escAttr(notice)}</p>`
    );
  }
  out = out.replace(/<section>/g, '<section lang="de">');
  out = out.replace(/<p class="lede"(?: lang="de")?>/, '<p class="lede" lang="de">');
  out = out.replace(
    /<a href="index\.html">Startseite<\/a>/,
    `<a href="index.html">${escAttr(ui.home)}</a>`
  );
  return out;
}

function writeSitemap() {
  const urls = [];
  for (const file of ALL_PAGES) {
    for (const lang of LANGS) {
      const loc = pageUrl(lang, file);
      const alternates = [
        ...LANGS.map(
          (l) =>
            `    <xhtml:link rel="alternate" hreflang="${l}" href="${pageUrl(l, file)}"/>`
        ),
        `    <xhtml:link rel="alternate" hreflang="x-default" href="${pageUrl("de", file)}"/>`,
      ].join("\n");
      const changefreq = PAGE_CHANGEFREQ[file] || "monthly";
      const priority = PAGE_PRIORITY[file];
      urls.push(
        `  <url>\n    <loc>${loc}</loc>\n    <lastmod>${LASTMOD}</lastmod>\n    <changefreq>${changefreq}</changefreq>\n    <priority>${priority}</priority>\n${alternates}\n  </url>`
      );
    }
  }
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls.join("\n")}
</urlset>
`;
  fs.writeFileSync(path.join(ROOT, "sitemap.xml"), xml);
}

function collectDeDict(html) {
  const dict = {};
  const re = /<([a-zA-Z][\w-]*)([^>]*\sdata-i18n=["']([^"']+)["'][^>]*)>/g;
  let m;
  while ((m = re.exec(html))) {
    const tag = m[1];
    const key = m[3];
    const afterOpen = m.index + m[0].length;
    const closeIdx = findClose(html, afterOpen, tag);
    dict[key] = html.slice(afterOpen, closeIdx);
  }
  const ph = /<([a-zA-Z][\w-]*)([^>]*\sdata-i18n-ph=["']([^"']+)["'][^>]*)>/g;
  while ((m = ph.exec(html))) {
    const key = m[3];
    const open = m[0];
    const pm = open.match(/\splaceholder="([^"]*)"/);
    if (pm) dict[key] = pm[1];
  }
  return dict;
}

function processContentPage(file) {
  const srcPath = path.join(ROOT, file);
  const original = fs.readFileSync(srcPath, "utf8");
  const i18n = extractI18N(original);
  if (!i18n) throw new Error(`${file}: missing I18N dictionary`);

  i18n.de = collectDeDict(original);

  let base = original;
  base = convertImgPaths(base);
  base = convertLangCss(base);
  base = upsertHreflang(base, file);

  let de = base;
  de = setHtmlLang(de, "de");
  de = setCanonicalAndSocial(de, "de", file);
  de = setSwitcher(de, "de", file);
  de = disableClientI18N(de);
  de = rewriteJsonLd(de, "de", i18n.de, file);
  de = ensureConsentScript(de);
  fs.writeFileSync(srcPath, de);

  for (const lang of LOCALE_LANGS) {
    const dict = i18n[lang];
    if (!dict) throw new Error(`${file}: missing I18N.${lang}`);
    let loc = applyDict(base, dict);
    loc = setHtmlLang(loc, lang);
    loc = setCanonicalAndSocial(loc, lang, file);
    loc = setSwitcher(loc, lang, file);
    loc = rewriteJsonLd(loc, lang, dict, file);
    loc = stripI18NKeepForm(loc);
    loc = ensureConsentScript(loc);
    const destDir = path.join(ROOT, lang);
    fs.mkdirSync(destDir, { recursive: true });
    fs.writeFileSync(path.join(destDir, file), loc);
  }
}

function processLegalPage(file) {
  const srcPath = path.join(ROOT, file);
  let original = fs.readFileSync(srcPath, "utf8");
  original = updateDatenschutzLanguageParagraph(original);

  let de = original;
  de = convertImgPaths(de);
  de = ensureLegalCss(de);
  de = upsertHreflang(de, file);
  de = setHtmlLang(de, "de");
  de = setCanonicalAndSocial(de, "de", file);
  de = setSwitcher(de, "de", file);
  de = ensureConsentScript(de);
  fs.writeFileSync(srcPath, de);

  for (const lang of LOCALE_LANGS) {
    let loc = de;
    loc = setHtmlLang(loc, lang);
    loc = upsertHreflang(loc, file);
    loc = setCanonicalAndSocial(loc, lang, file);
    loc = setSwitcher(loc, lang, file);
    loc = localizeLegalChrome(loc, lang, file);
    loc = ensureConsentScript(loc);
    fs.writeFileSync(path.join(ROOT, lang, file), loc);
  }
}

function main() {
  for (const file of CONTENT_PAGES) processContentPage(file);
  for (const file of LEGAL_PAGES) processLegalPage(file);
  writeSitemap();

  const robots = fs.readFileSync(path.join(ROOT, "robots.txt"), "utf8");
  if (/noindex|disallow:\s*\/(en|fr|es|sr|ru)/i.test(robots)) {
    throw new Error("robots.txt must allow locale folders");
  }
  if (!robots.includes("Allow: /") || !robots.includes("Sitemap: https://adriacare.me/sitemap.xml")) {
    throw new Error("robots.txt must allow crawling and point to the sitemap");
  }

  console.log("Built locale copies for", LOCALE_LANGS.join(", "));
  console.log("Updated German sources, sitemap.xml");
}

main();
