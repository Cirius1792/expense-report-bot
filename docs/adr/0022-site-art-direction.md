# ADR 0022: Site Art Direction — Technical Editorial, Self-Hosted Type, CSS-Art Icons

**Date:** 2026-10-13
**Status:** Accepted

## Context

The `site/` folder (GitHub Pages, `feature/landing-site`) carried a competent but
generic landing page: system fonts only, a repeated three-column card grid for
every section, emoji as icons, and two GitHub badge images loaded from
github.com — which contradicted the folder's own rule that the site must render
fully offline from local files (see `docs/expectations/landing-site.md`).

Two constraints shape any fix:

1. The site is a **static folder with no build step** — no bundler, no npm, no
   JS pipeline. Anything added must be a plain file that Pages can serve.
2. The site must render **offline, with no external subresources** (the rule the
   badge images broke).

## Decision

**Art direction — "technical editorial."** Hairline rules are the primary
structural device; mono uppercase labels carry metadata and section indices
(`01 — What it does`); sections alternate between asymmetric two-column layouts,
a bordered spec band, a timeline, a reference table, one dark band, and a
three-column footer. No section repeats another's composition, and no repeated
card grid is used anywhere.

**Typography — three roles, self-hosted.** Fraunces (variable, `opsz`/`wght`)
for display and the wordmark, IBM Plex Sans (variable) for text, IBM Plex Mono
for data, labels, and commands. Latin subsets are committed to
`site/assets/fonts/` (≈225 KB total, woff2) with the SIL OFL 1.1 license text in
`fonts/OFL.txt`, so the typography survives offline and no CDN is involved. A
real italic Fraunces cut is used rather than a synthetic slant.

**Palette — extending the logo, not replacing it.** Warm bone paper `#faf8f4`,
white panels, ink `#1b1f1e`, hairline `#e5e0d7`, the logo teal `#2a927f` for
graphics and large type only, and `#1c6b5c` as its text/button counterpart
(white on `#2a927f` measures 3.81:1 and fails AA; on `#1c6b5c` it measures
6.35:1). One dark ink-teal band `#17211f` carries the data-ownership section, so
contrast carries meaning rather than decoration.

**Icons — hand-built CSS art.** `site/assets/icons.css` draws 18 glyphs from an
element plus its two pseudo-elements, on a fixed 1em box so percentages always
mean "of the 24-unit icon square" (resizing the element itself silently rescales
its pseudo-elements — the trap that shaped this rule). Colour comes from
`currentColor`; knockouts paint `var(--i-hole, transparent)`, which each surface
sets to its own background, so one icon works on paper, on white, and on the
dark band. No emoji, no icon font, no SVG, no image file.

**Product representation.** The hero shows a Telegram chat reconstructed from the
real messages in `adapters/inbound/telegram_bot.py` (field names, the
`YYYYMMDD-n` key from ADR 0016, the real reply-keyboard labels, the inline delete
button). The reply-keyboard button glyphs are drawn with the CSS icons instead
of the bot's emoji, since the page forbids emoji.

**Badges removed.** The two GitHub badge images are gone; the hero carries a
factual mono line instead. This is what makes "no external subresources" true
rather than aspirational.

## Considered alternatives

- **Icon library or SVG sprite.** Rejected: an added dependency and external
  files for 18 glyphs that fit in one committed stylesheet, and the brief asked
  for CSS art.
- **System font stack with tuned typography.** Rejected: no identity, and the
  page is mostly text — the type is the design.
- **Google Fonts `<link>`.** Rejected: breaks the offline/no-subresource rule.
- **Keeping the badge images.** Rejected: they were the only external
  subresources, and the brief calls out unnecessary badges.
- **A second stylesheet for icons.** Kept as its own file after all: the icon set
  is a self-contained drawing system with its own coordinate convention, and it
  keeps `style.css` about layout.

## Consequences

- New files to maintain: `site/assets/icons.css`, `site/assets/fonts/*`.
  `pages.yml` publishes `site/` wholesale, so no workflow change was needed.
- The site is now genuinely offline-clean and emoji-free; both are machine-checked
  in `docs/expectations/site-visual-redesign.md`.
- Reference tables and code blocks scroll inside their own container below
  640 px, verified by measurement rather than by eye.
- Docs pages inherit the same nav, tabs, tables, and footer; content and facts
  are unchanged (env vars, paths, commands, failure behaviors).

## Post-audit revisions (same day)

An independent audit reproduced the verification and found one factual error and
several quality gaps; all were fixed in the same branch. The two that change the
design record:

- **The hero chat must be faithful, not merely plausible.** It quoted the bot
  asking for a field (`category`) that `_missing_fields` can never request, and
  it showed a photo message as a document card with a filename. Both are now
  modelled on what the bot and Telegram actually do — the constraint is accuracy
  over convenience when representing the product.
- **A scrolling region is only acceptable if it is discoverable and reachable.**
  Horizontal scrollers now carry `tabindex="0"`, `role="region"`, an
  `aria-label`, and scrolling shadows, and the forced minimum width was narrowed
  to the single table that needs it. Where a table can wrap instead of scroll, it
  wraps.
