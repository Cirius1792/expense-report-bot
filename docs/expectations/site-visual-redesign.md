# Expectations: Site visual redesign (art direction, typography, CSS-art icons)

**Scope:** `site/**` only (HTML, `assets/style.css`, new `assets/icons.css`,
new `assets/fonts/**`). No `src/`, no Python, no workflow changes.
Supersedes the visual choices of `landing-site.md`; that file's content
checklist and link rules still bind.

## Goal

Replace the generic card-grid landing page with a deliberately art-directed
site: an editorial, engineering-ledger visual language derived from the
existing brand (teal `#2a927f` + charcoal `#464646` logo, flat geometric
shapes, ring motif).

## Art direction (single coherent direction, no mixed styles)

- **Language:** "technical editorial" — hairline rules as the primary
  structural device, mono uppercase section labels with indices (`01 — …`),
  asymmetrical two-column sections, restrained whitespace.
- **Type:** Fraunces (variable, display serif, `font-optical-sizing: auto`)
  for headings and the wordmark; IBM Plex Sans (variable) for body/UI; IBM Plex
  Mono for data, labels, commands, code. Self-hosted latin subsets in
  `site/assets/fonts/` under SIL OFL 1.1 (license text bundled as `OFL.txt`).
  No system-font-only fallback styling differences: each family declares a
  metric-compatible local fallback in its stack.
- **Palette:** warm bone paper `#faf8f4`, white panels, ink `#1b1f1e`,
  hairline `#e2ddd4`, teal accent `#2a927f` for graphics/large text,
  `#1c6b5c` for text and button fills (white-on-`#2a927f` fails AA at 3.81:1,
  white-on-`#1c6b5c` passes at 6.35:1), deep ink-teal `#17211f` for the one
  dark band.
- **Dark band:** exactly one (the data/privacy section) so contrast carries
  meaning rather than decoration.
- **No repeated card grid:** every section uses a distinct composition
  (editorial list, spec-sheet band, timeline, reference table, dark band with
  boundary diagram, multi-column footer).

## Icons

- Every glyph on the site is hand-built **CSS art**: flat filled geometric
  shapes drawn with `background`, `border`, `border-radius`, `clip-path`, and
  `box-shadow` on an element plus its two pseudo-elements. No icon font, no
  SVG file, no external image, no emoji.
- Icons live in `site/assets/icons.css`, drawn on a 24-unit square scaled by
  `font-size` (`.i { width: 1em; height: 1em }`), colored by `currentColor`,
  with knockout details in `var(--i-hole)` so each surface declares its own
  background color for holes.
- They visually match the logo: solid, geometric, slight corner radii.
- Decorative icons carry `aria-hidden="true"`; icons are never the only label
  for an interactive element.

## Required content (unchanged from `landing-site.md`)

Hero (logo, bot name, one-line pitch, `Self-host it` → `docs/deployment.html`,
`View source` → repo), the six features, the four use cases, the four-step
flow, the commands/buttons reference, the privacy points, and the footer
(MIT, repo, author).

## Behaviours that must NOT happen

- **No emoji anywhere in `site/**`** — not in markup, CSS `content`, or docs.
  Verified by codepoint scan.
- **No external subresources**: no `<img>`, `<script>`, `<link>`, or `@font-face`
  src that points off-site. The page must render completely with no network.
  External *hyperlinks* (`t.me`, `github.com`) remain allowed. This removes the
  two GitHub badge images the old hero carried.
- No invented product claims, fake testimonials, invented metrics, or fake
  screenshots. The hero chat is a representation of real bot messages and must
  copy the real field names, `YYYYMMDD-n` key shape, and real keyboard labels.
- No new JS; no animation beyond subtle CSS transitions that respect
  `prefers-reduced-motion: reduce`.
- No light text on `#2a927f`, no text below 4.5:1 contrast.
- No content regression: no env var name, path, command, or behaviour claim may
  change or disappear from the docs pages.

## Edge cases

- 390 px, 900 px, 1440 px widths: no horizontal overflow, no clipped text, no
  overlapping elements; the hero chat mock and the reference tables stay
  legible (tables scroll inside their own container rather than the page).
- Every icon must be recognizable at 20 px (inline in tables) and 32 px (cards).
- Long strings (`AUTHORIZED_USERS_CONFIG_PATH`, `20260710-3`) must not break
  the layout of the narrow columns.
- The dark band and the paper sections must both give icons enough contrast.

## Verification (executed evidence required)

1. Emoji codepoint scan over `site/**` returns zero matches.
2. Internal link/asset check: every `href`/`src` resolves locally; every
   external URL is a hyperlink, not a subresource.
3. Contrast computation over the final palette: all text pairs >= 4.5:1, all
   graphical accents >= 3:1.
4. Headless Chrome screenshots at 1440/900/390 px of all four pages, plus an
   icon contact sheet on paper and on the dark band — inspected, iterated.
5. `uvx ruff format && uvx ruff check && uvx ty check && uv run pytest -o addopts=""`.

## Verification evidence (executed 2026-10-13)

All commands run from the repo root against the working tree of
`feature/landing-site`.

**1. Emoji codepoint scan over `site/**` (HTML + CSS, incl. CSS `content`)**

```
EMOJI SCAN: clean
```
(Scanned U+1F000–U+1FAFF, U+2600–U+27BF, U+2B00–U+2BFF, flags, U+FE0F, U+200D,
U+20E3, U+2190–U+21FF, and every codepoint > U+2FFF. Only `&copy;`, `&middot;`,
`&ndash;`, `&mdash;`, `&ldquo;`, `&rdquo;`, `&hellip;` remain.)

**2. Link, asset, and subresource check over `site/**`**

```
BROKEN LOCAL LINKS/ASSETS: none
BROKEN CSS URLS: none
EXTERNAL SUBRESOURCES (images/scripts/styles/fonts): none
EXTERNAL HYPERLINKS (allowed): 21
```

**3. Contrast, computed from the tokens shipped in `style.css`**

```
body text on paper        #3c4442 on #faf8f4   9.44:1  PASS
muted text on paper       #626a67 on #faf8f4   5.24:1  PASS
muted text on panel       #626a67 on #ffffff   5.56:1  PASS
muted text on tint        #626a67 on #f2eee7   4.81:1  PASS
headings on paper         #1b1f1e on #faf8f4  15.70:1  PASS
links/kicker on paper     #1c6b5c on #faf8f4   5.99:1  PASS
button label on fill      #ffffff on #1c6b5c   6.35:1  PASS
accent graphic on paper   #2a927f on #faf8f4   3.59:1  PASS (>=3:1)
body on dark              #e4ebe8 on #17211f  13.62:1  PASS
secondary on dark         #9fb2ad on #17211f   7.42:1  PASS
accent on dark            #7fcdb9 on #17211f   8.90:1  PASS (>=3:1)
code text on code-bg      #d7e3de on #1d2725  11.64:1  PASS
code comment on code-bg   #86968f on #1d2725   4.95:1  PASS
```
The `--muted` token was darkened from `#6b7370` (4.21:1 on `--tint`) to
`#626a67` to clear AA everywhere it is used.

**4. Overflow measurement (headless Chrome, iframe harness, 4 pages x 5 widths)**

```
{ "pageLevelOverflow": [], "checked": 20,
  "innerScrollers": ["div.table-scroll", "pre."], "allClear": true }
```
Widths: 390, 768, 900, 1280, 1440. Intentional inner scrollers are the reference
tables and code blocks. Two real defects were found and fixed this way: the docs
tables overflowed the page at 390 px (now wrapped in `.table-scroll`), and the
long inline `code` path `UNAUTHORIZED_LOG_PATH=/data/unauthorized.log` could not
wrap (`overflow-wrap: break-word`).

**5. Self-hosted fonts actually load from disk (no network)**

```
{"Fraunces loaded": true, "Fraunces italic loaded": true,
 "IBM Plex Sans loaded": true, "IBM Plex Mono loaded": true}
h1font: Fraunces, Georgia, "Times New Roman", serif | 62.4px | weight 600
```

**6. Glyph coverage of the shipped subsets** (fontTools cmap check against every
non-ASCII character the site renders)

```
Fraunces         missing: none
Fraunces italic  missing: none
IBM Plex Sans    missing: none
IBM Plex Mono    missing: none
```
The only uncovered character (`─`, U+2500) appears solely inside CSS comments.
Because the latin subsets do not carry `U+2264`, "PDF receipts (≤5 pages)" is
written as "up to 5 pages" — same fact, no fallback glyph.

**7. Repo quality gate**

```
$ uvx ruff format    -> 154 files left unchanged
$ uvx ruff check     -> All checks passed!
$ uvx ty check       -> All checks passed!
$ uv run pytest                    -> 390 passed, 8 deselected in 13.73s
$ uv run pytest -o addopts=""      -> 398 passed in 49.73s
```

**8. Screenshots inspected** (headless Chrome, iterated between passes): landing
page and all three docs pages at 1440 px; landing page at 900 px and 390 px;
icon contact sheet at 20/24/32/48 px on paper, white, and the dark band.

## Independent audit round (2026-10-13)

An independent reviewer (`site-auditor` subagent, separate model, fresh context)
re-audited the claims by reproducing every check, including rendered-page
equality with the network disabled and CDP viewport measurements. Report:
`/tmp/site-audit.md`. Claims 1-5 and 7 reproduced; one factual error and several
quality gaps were found. Everything below was fixed in this branch.

### Fixed

- **D1 (accuracy, should-fix)** — the step-03 chat quote asked for
  "amount, category". `_missing_fields` (`telegram_bot.py:909`) can only emit
  `amount, currency, merchant, date`, and `domain/models.py` marks category
  optional ("does not affect completeness"), so the bot can never ask for it.
  The quote now reads `amount, currency`.
- **D2 (accessibility, should-fix)** — the four `.table-scroll` regions and the
  five `<pre>` blocks scroll horizontally on narrow screens but were not
  keyboard-reachable (WCAG 2.1.1). All nine now carry `tabindex="0"`,
  `role="region"`, and a descriptive `aria-label`; verified by focusing each
  scroller in CDP and asserting `document.activeElement`.
- **D3 (affordance, should-fix)** — scrolling regions gave no sign that content
  was off-screen. They now draw scrolling shadows (background-attachment
  local/scroll) that appear only when there is more content, and the forced
  `min-width` is scoped to the one table that genuinely needs it (the four-column
  environment-variable table). The startup-failure and commands tables now wrap
  instead of scrolling.
- **D4 (accuracy)** — `LOG_LEVEL` is read by `main.py:48` but was missing from a
  table that claims to be complete. Row added.
- **D5 (weight)** — `site/assets/logo.png` was a 1024px, 874 KB file displayed at
  26-30px. Replaced with `logo-96.png` (10 KB) and `logo-192.png` (28 KB) for the
  favicon; the original is deleted. Site assets: 1310 KB -> 303 KB.
- **D6 (typography)** — micro-copy inside the chat mock sat at 10.6-10.9 px; the
  floor is now 11.5 px. Icons remain verified at 20 px and legible at 15 px.
- **D7 (accuracy)** — "Example: local (non-Docker) run" was wrong: the bot
  migrates through the Liquibase wrapper, which runs the official Docker image
  (`liquibase_migration.py` -> `scripts/liquibase` -> `docker run`). Retitled
  "run from a source checkout" and it now exports the wrapper onto `PATH` and
  states that Docker is required for migrations.
- **D9 (fidelity)** — the mock keyboard is 3-then-2 as in Telegram at every
  width (it previously collapsed to 2 columns on phones), and the outgoing
  message is a photo bubble showing the image rather than a filename, since
  Telegram does not display filenames for photos.

### Deliberately not changed

- **A 4-column reference table still scrolls at 390 px.** `TELEGRAM_BOT_TOKEN` …
  `AUTHORIZED_USERS_CONFIG_PATH` plus three more columns cannot fit 335 px of
  content width without either wrapping identifiers mid-name or collapsing to a
  stacked layout that would drop the table semantics for assistive tech.
  Scrolling *with* a visible affordance and keyboard access is the trade-off.
- **No `LICENSE` file exists in the repo** although the README, the site footer,
  and `pyproject.toml` all say MIT. Adding a top-level `LICENSE` is a repo-wide
  change outside this work's `site/**` scope — flagged for the owner to decide.
  *Resolved 2026-10-13 at the owner's request:* `LICENSE` (MIT, "Copyright (c)
  2026 Ciro Lucio Tecce") now exists at the repo root and `pyproject.toml`
  declares it as `license = "MIT"` + `license-files = ["LICENSE"]`; `uv build`
  emits `License-Expression: MIT` and ships the file in the wheel.
