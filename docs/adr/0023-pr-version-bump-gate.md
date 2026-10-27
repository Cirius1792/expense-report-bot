# ADR 0023: Pull-Request Version Bump Gate

**Date:** 2026-10-27
**Status:** Accepted

## Context

Releases are tag-triggered, but nothing forced a pull request to raise
`[project].version`. `.github/workflows/release.yml` only validated that a pushed
tag matched whatever `pyproject.toml` said *after* the fact, via a `grep` read of
the version line.

Consequences:

1. `src/`, `db/`, `Dockerfile`, or `docker-entrypoint.sh` could change with the
   version untouched, so two different images could ship under the same version,
   and the release skill actively encouraged committing only `pyproject.toml`
   (leaving a stale `uv.lock`).
2. A release could be tagged from a commit whose `uv.lock` disagreed with
   `pyproject.toml`, producing an image whose installed metadata and workspace
   lockfile diverged.

## Decision

Add a **pull-request gate** that fails when a PR changes anything that ships in
the image without also raising `[project].version` to a strictly greater
`MAJOR.MINOR.PATCH`, and requires the PR head `uv.lock` entry for
`expense-report-bot` to record the same version as `pyproject.toml`.

- The gate is a `version-check` job in `.github/workflows/ci.yml` — **not** the
  reusable `tests.yml`, which `release.yml` also calls and which has no
  `pull_request` payload to diff.
- The policy lists the shipped paths: directory prefixes `src/`, `db/` and exact
  files `Dockerfile`, `docker-entrypoint.sh`, `LICENSE`, `pyproject.toml`, `uv.lock`.
- Implementation split: pure policy (`scripts/version_gate.py`) → git plumbing +
  CLI (`scripts/check_pr_version.py`) → workflow job (`.github/workflows/ci.yml`).
- Versions must be strict `MAJOR.MINOR.PATCH`; the PR head version must be
  strictly greater than the merge-base version, compared numerically per
  component. Lockfile version must equal the PR head `pyproject.toml` version.
- Diff via three-dot `base...head` with `--no-renames`; the gate runs with a
  read-only token and a full (`fetch-depth: 0`) checkout.

## Alternatives considered

- Reverse diff `head...base` — fails when `main` advances past the merge base.
- Two-dot `base..head` — wrongly counts commits merged into `main`.
- `paths:` filters on the workflow — a required check that never runs leaves the
  PR permanently "Expected — Waiting for status to be reported".
- A bot/action that auto-bumps — the increment choice (patch/minor/major) is a
  human/author judgement.
- Keeping the gate inside the reusable test workflow — breaks the release caller.

## Consequences

The gate adds a `version-check` job to `ci.yml`, a new ADR, an expectations file,
and release-workflow hardening; the release skill now bumps via `uv version --bump`
and commits both `pyproject.toml` and `uv.lock`.
