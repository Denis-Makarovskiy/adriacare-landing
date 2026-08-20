#!/usr/bin/env python3
"""Assert crawlable locale copies, reciprocal hreflang, and partner-safe copy."""

from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://adriacare.me"
LANGS = ("de", "en", "fr", "es", "sr", "ru")
PAGES = (
    "index.html",
    "montenegro.html",
    "wellness.html",
    "excursions.html",
    "pilgrimage.html",
    "neighbors.html",
    "impressum.html",
    "datenschutz.html",
)

EN_H1 = "Your residents spend winter on the Adriatic, with their usual care in place."
DE_H1 = "Ihre Bewohner verbringen den Winter an der Adria — mit der vertrauten Versorgung."


def href(lang: str, page: str) -> str:
    suffix = "/" if page == "index.html" else f"/{page}"
    if lang == "de":
        return suffix
    return f"/{lang}/" if page == "index.html" else f"/{lang}{suffix}"


def url(lang: str, page: str) -> str:
    return SITE + href(lang, page)


def read(lang: str, page: str) -> str:
    if lang == "de":
        return (ROOT / page).read_text(encoding="utf-8")
    return (ROOT / lang / page).read_text(encoding="utf-8")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    errors: list[str] = []

    def check(cond: bool, msg: str) -> None:
        if not cond:
            errors.append(msg)

    en_index = read("en", "index.html")
    check(EN_H1 in en_index, "en/index.html must contain the English h1 in raw HTML")
    check(DE_H1 not in en_index, "en/index.html must not keep the German h1")
    check("var I18N" not in en_index, "locale landing must not depend on an I18N swap script")
    check('<html lang="en">' in en_index, "en/index.html must set html lang=en")
    check(
        'class="photo hero-photo"' in read("de", "index.html"),
        "German homepage must keep the unblurred hero-photo",
    )
    check('"url":"https://adriacare.me/en/"' in en_index, "EN Organization JSON-LD must use the English URL")
    check("Seasonal care stays in Budva" in en_index, "EN Organization JSON-LD must be English")
    check('"inLanguage":"en"' in en_index, "EN FAQPage must set inLanguage=en")

    fr_index = read("fr", "index.html")
    check("L’hiver sur l’Adriatique" in fr_index, "fr/index.html must contain the French h1 in raw HTML")
    check('"url":"https://adriacare.me/fr/"' in fr_index, "FR Organization JSON-LD must use the French URL")
    check("Séjours de soins saisonniers" in fr_index, "FR Organization JSON-LD must be French")

    for page in PAGES:
        for lang in LANGS:
            html = read(lang, page)
            check(f'<html lang="{lang}">' in html, f"{lang}/{page}: html lang")
            check(
                f'<link rel="canonical" href="{url(lang, page)}">' in html,
                f"{lang}/{page}: canonical to self ({url(lang, page)})",
            )
            for alt in LANGS:
                needle = f'<link rel="alternate" hreflang="{alt}" href="{url(alt, page)}">'
                check(needle in html, f"{lang}/{page}: missing hreflang {alt}")
            xdef = f'<link rel="alternate" hreflang="x-default" href="{url("de", page)}">'
            check(xdef in html, f"{lang}/{page}: missing hreflang x-default")
            check("<nav class=\"lang\"" in html, f"{lang}/{page}: language switcher")
            check("data-lang=" not in html, f"{lang}/{page}: switcher should be links, not JS buttons")
            check(
                f'href="{href(lang, page)}"' in html and 'aria-current="page"' in html,
                f"{lang}/{page}: current language link",
            )
            check("noindex" not in html.lower(), f"{lang}/{page}: must not be noindex")
            og = {
                "de": "de_DE",
                "en": "en_GB",
                "fr": "fr_FR",
                "es": "es_ES",
                "sr": "sr_RS",
                "ru": "ru_RU",
            }[lang]
            check(
                f'<meta property="og:locale" content="{og}">' in html,
                f"{lang}/{page}: og:locale {og}",
            )
            check(
                'src="/js/consent-analytics.js"' in html,
                f"{lang}/{page}: consent-gated analytics script",
            )
            check("goatcounter" not in html.lower(), f"{lang}/{page}: do not add GoatCounter")
            check(
                not re.search(
                    r'<script[^>]+src="https?://(www\.googletagmanager\.com|mc\.yandex\.(ru|com))',
                    html,
                    re.I,
                ),
                f"{lang}/{page}: must not load GA/YM before consent",
            )
            if page == "index.html":
                hero_idx = html.find('class="photo hero-photo"')
                h1_idx = html.find("<h1", html.find('id="top"'))
                check(
                    hero_idx != -1 and "hero-terrace.webp" in html[hero_idx : hero_idx + 200],
                    f"{lang}/{page}: unblurred hero-photo (hero-terrace.webp)",
                )
                check(
                    hero_idx != -1 and h1_idx != -1 and hero_idx < h1_idx,
                    f"{lang}/{page}: hero-photo must appear before the h1, not only as a blurred gallery tile",
                )

    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    check('xmlns:xhtml="http://www.w3.org/1999/xhtml"' in sitemap, "sitemap xhtml namespace")
    for page in PAGES:
        for lang in LANGS:
            check(f"<loc>{url(lang, page)}</loc>" in sitemap, f"sitemap loc {url(lang, page)}")
            check(
                f'hreflang="{lang}" href="{url(lang, page)}"' in sitemap,
                f"sitemap hreflang {lang} for {page}",
            )
        check(
            f'hreflang="x-default" href="{url("de", page)}"' in sitemap,
            f"sitemap x-default for {page}",
        )

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    check("Allow: /" in robots, "robots.txt must allow /")
    check("Sitemap: https://adriacare.me/sitemap.xml" in robots, "robots.txt sitemap")
    check(not re.search(r"disallow:\s*/(en|fr|es|sr|ru)", robots, re.I), "robots.txt must not block locales")
    check("noindex" not in robots.lower(), "robots.txt must not noindex")

    banned_phone = re.compile(r"(\+382|\+49|\btel:|Telefonnummer\s+\+)", re.I)
    banned_price = re.compile(r"(€\s?\d|\d[\d.]*\s?€|EUR\s?\d|1[.,]890)")
    for page in PAGES:
        for lang in LANGS:
            html = read(lang, page)
            check(not banned_phone.search(html), f"{lang}/{page}: phone number leaked")
            check(not banned_price.search(html), f"{lang}/{page}: public euro price leaked")
            if "Vladislav" in html:
                check("Geschäftsführer" not in html, f"{lang}/{page}: Vladislav must not be Geschäftsführer")
            check("GmbH" not in html or "keine deutsche GmbH" in html.lower() or "no german gmbh" in html.lower() or "pas de gmbh" in html.lower() or "no existe una gmbh" in html.lower() or "ne postoji nemački gmbh" in html.lower() or "немецкого gmbh нет" in html.lower() or "keine deutsche GmbH" in html, f"{lang}/{page}: do not invent a German GmbH")

    de_imp = read("de", "impressum.html")
    check("MK REHAB DOO" in de_imp, "Impressum must name MK REHAB DOO")
    check("Denis Makarovskiy" in de_imp, "Impressum must name Denis Makarovskiy")
    check("Kooperationsmanagement" in de_imp, "Vladislav remains Kooperationsmanagement")
    check("2027" in de_imp and "noch nicht in Betrieb" in de_imp, "Impressum must say 2027 / not operating")

    en_imp = read("en", "impressum.html")
    check("MK REHAB DOO" in en_imp, "EN Impressum keeps MK REHAB DOO")
    check("The legally binding operator information" in en_imp, "EN Impressum labels the German legal text")
    check("lang=\"de\"" in en_imp, "EN Impressum marks German legal body")

    js = (ROOT / "js" / "consent-analytics.js").read_text(encoding="utf-8")
    check("G-2T17E8PYZK" in js, "consent script must use the real GA4 ID")
    check("111778025" in js, "consent script must use the real Yandex Metrica ID")
    check("localStorage" in js, "consent script must persist the choice")
    check("webvisor: false" in js, "Yandex Webvisor must stay off")
    check("clickmap: false" in js, "Yandex clickmap must stay off")
    check("accurateTrackBounce: false" in js, "Yandex accurateTrackBounce must stay off")
    check("goatcounter" not in js.lower(), "do not add GoatCounter")
    check("googletagmanager.com/gtag/js" in js, "GA4 must load via gtag.js after consent")

    de_ds = read("de", "datenschutz.html")
    check("Google Analytics 4" in de_ds, "Datenschutz must name Google Analytics 4")
    check("Yandex Metrica" in de_ds, "Datenschutz must name Yandex Metrica")
    check("Google Ireland" in de_ds, "Datenschutz must name Google Ireland")
    check("Google LLC" in de_ds, "Datenschutz must name Google LLC")
    check("Yandex" in de_ds, "Datenschutz must name Yandex as processor")
    check("kein Cookie-Banner" not in de_ds, "Datenschutz must not claim there is no cookie banner")
    check("keine Analyse-Tracker" not in de_ds, "Datenschutz must not claim there are no analysis trackers")
    check("Marketing-Pixel" in de_ds, "Datenschutz should say there are no marketing pixels")
    check("Telefonnummer wird auf dieser Website nicht" in de_ds, "Datenschutz must still say there is no phone number")
    check("G-2T17E8PYZK" in de_ds, "Datenschutz should name the GA4 measurement ID")
    check("111778025" in de_ds, "Datenschutz should name the Yandex counter ID")

    en_ds = read("en", "datenschutz.html")
    check("Google Analytics 4" in en_ds, "EN Datenschutz note must mention GA4")
    check("Yandex Metrica" in en_ds, "EN Datenschutz note must mention Yandex Metrica")
    check("there is no cookie banner" not in en_ds.lower(), "EN Datenschutz must not claim there is no cookie banner")
    check("no marketing pixels" in en_ds.lower() or "no marketing pixel" in en_ds.lower(), "EN Datenschutz note: no marketing pixels")

    if errors:
        print("\n".join(f"FAIL: {e}" for e in errors), file=sys.stderr)
        print(f"{len(errors)} check(s) failed", file=sys.stderr)
        sys.exit(1)
    print("Locale / hreflang checks passed.")


if __name__ == "__main__":
    main()
