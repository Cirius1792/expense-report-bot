# Expectations: Version Bump Gate

**Scope:** Pull-request version-bump gate (`scripts/version_gate.py`,
`scripts/check_pr_version.py`, `version-check` job in `.github/workflows/ci.yml`)
and release tag validation (`.github/workflows/release.yml`). No behaviour change
to the bot itself.

Consumes ADR 0023.

## Happy path

- A PR that changes any shipped path (`src/**`, `db/**`, `Dockerfile`,
  `docker-entrypoint.sh`, `LICENSE`, `pyproject.toml`, `uv.lock`) with a strictly
  greater `[project].version` and an `uv.lock` recording the same version → the
  `version-check` job is green and prints exactly `Pull request version policy passed.`
- A bumped-and-synced PR (`uv version --bump patch|minor|major`, both files
  committed) passes.

## Edge cases

- Docs/test/CI/skill-only PRs pass without a bump.
- A rename that moves source out of `src/`/`db/` is still gated
  (`--no-renames`).
- A PR opened before `main` advanced only counts its own changes
  (`base...head` three-dot diff).
- A base commit that predates `pyproject.toml` is treated as version `0.0.0`.
- A PR head that deletes `pyproject.toml` fails with a clear message.

## Behaviors that must NOT happen

- The gate must not run `uv sync` / install the project / touch the lockfile.
- No `pull_request_target` trigger.
- The gate must not write, commit, comment, or label anything.
- No gate in the reusable `tests.yml` or `release.yml`.
- No version bump required for `tests/`, `features/`, `docs/`, `.github/`,
  `.agents/`, `scripts/`, `README.md`, `AGENTS.md`, `CONTEXT.md`, or the compose file.

## Evidence mapping

- Pytest: `tests/migrations/test_version_gate.py` (D4) proves unit policy + CLI behaviour.
- Pytest: `tests/migrations/test_version_bump_workflow.py` (D5) proves workflow/policy drift guards.
- Real PR run remains the final end-to-end proof (post-merge maintainer step, ADR 0023 §8).

## Evidence log — executed

RED (D4, implementation absent):

```
uv run pytest tests/migrations/test_version_gate.py -q
# ModuleNotFoundError: No module named 'scripts.version_gate'
# 1 error in 0.06s
```

GREEN (D1 + D2 added):

```
uv run pytest tests/migrations/test_version_gate.py -q
# 27 passed in 0.23s
```

RED (D5, before touching ci.yml):

```
uv run pytest tests/migrations/test_version_bump_workflow.py -q
# 2 failed, 2 passed in 0.02s
```

GREEN (D3 added):

```
uv run pytest tests/migrations/test_version_gate.py tests/migrations/test_version_bump_workflow.py tests/migrations/test_ci_workflows.py -q
# 44 passed in 0.21s
```

Full suite and static checks after implementation:

```
uvx ruff format --check   # 163 files already formatted
uvx ruff check            # All checks passed!
uvx ty check              # All checks passed!
uv run pytest -o addopts="" -q
# 430 passed in 47.06s
```

Local gate transcripts (§6.1, on throwaway demo branches):

- FAIL: shipped change without bump → `::error::pull request version 0.8.0 must be greater than 0.8.0`, exit 1
- PASS: bumped-and-synced (`uv version --bump patch` + commit both files) → `Pull request version policy passed.`, exit 0
- STALE LOCK: bump without lockfile update → `::error::uv.lock version 0.8.0 does not match pyproject.toml version 0.8.1`, exit 1
- Local `act` run (real Docker runner): `act pull_request --job version-check --env-file /dev/null --action-cache-path /tmp/act-cache`
  - `[CI/version-check] ⭐ Run Set up job` ✅
  - `[CI/version-check] ⭐ Run Main Checkout pull request` ✅
  - `[CI/version-check] ⭐ Run Main Set up uv` ✅ (uv 0.13.6)
  - `[CI/version-check] ⭐ Run Main Check pull request version` → `Pull request version policy passed.` ✅
  - `[CI/version-check] 🏁 Job succeeded`
