# Expectations: Site SEO and link previews

**Scope:** `site/**` only — `<head>` metadata in the four pages, `robots.txt`,
`sitemap.xml`, `assets/og-image.png`. No Python, no workflow changes.

## Canonical origin

The site is a GitHub **project** page (no `CNAME` in `site/`, and `pages.yml`
uses `actions/configure-pages`), so the real origin is:

    https://cirius1792.github.io/expense-report-bot/

**Rename applied 2026-10-13.** The owner renamed the repository from the typo'd
`expese-report-bot` to `expense-report-bot`; every canonical, `og:url`,
`og:image`, `twitter:image`, JSON-LD `url`, the sitemap, `robots.txt`, and the
Pages origin moved with it in the same change (54 replacements across
`README.md` and `site/**`). The old slug still 301-redirects.

**If a custom domain is ever adopted, this origin must change everywhere at
once** — a canonical pointing at the wrong origin is worse than none.

## What each page declares

- `<title>` — descriptive, brand plus search phrase, <= 60 chars
  (landing: "…self-hosted Telegram expense bot"; the `<h1>` stays the creative
  line — the title tag is metadata, the headline is design).
- `<meta name="description">` — unique per page, 108-189 chars.
- `<meta name="robots" content="index, follow, max-image-preview:large">`.
- `<link rel="canonical">` — absolute; docs index canonicalises to `/docs/`
  because Pages serves the same content at `/docs/` and `/docs/index.html`.
- Open Graph (`og:type/url/title/description/image/*`) and
  `twitter:card=summary_large_image` with title, description, image, image alt.
- `og:image` is `assets/og-image.png`, 1200x630, composed from the site's own
  stylesheet rather than a stock or hand-drawn image.
- JSON-LD: `SoftwareApplication` on the landing page (`name`, `description`,
  `url`, `applicationCategory`, `operatingSystem`, `codeRepository`,
  `isAccessibleForFree`, `license`, `author`); `BreadcrumbList` on the docs pages.
- `<link rel="preload" as="font" type="font/woff2" crossorigin>` for the two
  fonts used above the fold (Fraunces roman, IBM Plex Sans), so the webfont
  arrives with the CSS instead of after it.

## Indexability

- `site/sitemap.xml` — the four canonical URLs with `lastmod`, well-formed XML.
- `site/robots.txt` — `Allow: /` plus the `Sitemap:` line.
- **Known limitation:** crawlers read `robots.txt` only from the *origin* root.
  On a project page the origin belongs to `github.io`, so this file is inert
  until a custom domain exists. The sitemap is still the submission mechanism —
  submit it directly in Search Console against a **path property**
  (`/expese-report-bot/`).

## Behaviours that must NOT happen

- No invented structured data: no `offers`, `aggregateRating`, `review`, or
  rating values, no fake prices, no org the project does not have. `isAccessibleForFree`
  is used because that is simply true.
- No canonical/`og:url` on any origin other than the one documented above.
- No external subresources introduced by the metadata work (`og:image` is a
  meta value, not a fetched page resource).
- No keyword stuffing or hidden text; titles/descriptions stay readable English.
- Metadata must not drift from page content (title/description/JSON-LD are
  generated from the page's own title and description strings).

## Verification (executed)

Metadata presence, uniqueness, and JSON validity:
```
canonical per page ......... 1 each, absolute, consistent with sitemap
JSON-LD .................... 4 blocks parse; no null values; SoftwareApplication
                             has all required-ish properties; BreadcrumbList
                             positions are 1..n
sitemap.xml ................ well-formed XML (xml.etree), 4 <loc> entries
robots.txt / sitemap / og-image reachable over HTTP ... 200
preload deduplication ...... exactly 5 font requests per page, each font fetched once
```

Core Web Vitals, headless Chrome over CDP with `Network.emulateNetworkConditions`
(Slow 4G: 1.6 Mbps down, 150 ms latency) + 4x CPU throttling + cache disabled,
localhost origin (so these are indicative, not field data):

```
landing        LCP 1012 ms   CLS 0.0003   FCP 1012 ms   load 835 ms   8 req   269 KB
docs/config    LCP  972 ms   CLS 0.0265   FCP  972 ms   load 826 ms   7 req   189 KB
```
Both well inside "good" thresholds (LCP < 2.5 s, CLS < 0.1).

Regression guards re-run after the metadata work: emoji scan clean, no broken
local refs, no external subresources, no page-level overflow at 390-1440 px,
all four scrollers still keyboard-reachable, and
`uvx ruff check` / `uvx ty check` / `uv run pytest` still pass.
