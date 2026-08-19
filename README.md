# Adria Care Residenz

B2B landing page for a seasonal care residency in Budva, Montenegro — partner to European nursing homes.

Hosted on GitHub Pages, custom domain: [adriacare.me](https://adriacare.me).

## Language URLs (for Google hreflang)

German is the default. Other languages are **real HTML documents** on their own paths — not a JavaScript-only swap. Googlebot can read the translated text without clicking a language button.

| Language | Home | Example inner page |
| --- | --- | --- |
| German (default, `x-default`) | `/` | `/montenegro.html` |
| English | `/en/` | `/en/montenegro.html` |
| French | `/fr/` | `/fr/montenegro.html` |
| Spanish | `/es/` | `/es/montenegro.html` |
| Serbian | `/sr/` | `/sr/montenegro.html` |
| Russian | `/ru/` | `/ru/montenegro.html` |

Every language version of a page has:

- `html lang` for that language
- `link rel="canonical"` to itself
- reciprocal `link rel="alternate" hreflang` for `de`, `en`, `fr`, `es`, `sr`, `ru`, and `x-default` (German root)
- matching Open Graph `og:locale`

The language switcher is a set of links to those URLs (same visual style as before).

Impressum and Datenschutz stay legally German. Locale copies add a short labelled note and keep the German legal body (`lang="de"`). They do not invent a German GmbH, a phone number, or extra legal facts.

`sitemap.xml` lists all language URLs with `xhtml:hreflang` alternates. `robots.txt` allows crawling of the locale folders.

## Editing copy

1. Edit the German HTML at the repo root (markup is the German source of truth).
2. Edit the `var I18N = { ... }` dictionaries in the same files for `en`, `fr`, `es`, `sr`, `ru`.
3. Rebuild the locale folders:

```bash
node scripts/build_locales.mjs
python3 scripts/check_locales.py
```

Do not enable outreach automation from this public site.

- `docs-kommerzielles-angebot.md` — commercial offer (German, not public)
- `docs-semantik-core.md` — semantic / SEO notes
