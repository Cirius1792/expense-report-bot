---
name: release
description: Tag-triggered release pipeline for spencer-bot. Bumps version in pyproject.toml, pushes tag, and the release.yml workflow builds + pushes the Docker image to ghcr.io. Use when the user wants to create a new release.
---

# Release Workflow for spencer-bot

Releases are tag-triggered. Push a semver tag (`vX.Y.Z`) and the pipeline builds the Docker image, pushes it to `ghcr.io/<owner>/spencer-bot`, and creates a GitHub Release.

## Release Process

### 1. Determine the new version

Use [Semantic Versioning](https://semver.org/):

- **Major (X.0.0):** breaking changes to the bot's behavior or API
- **Minor (X.Y.0):** new features, backward-compatible
- **Patch (X.Y.Z):** bug fixes, no new behavior

### 2. Update pyproject.toml

```bash
# 2. Bump the version (rewrites pyproject.toml AND uv.lock)
uv version --bump patch    # or: minor / major
```

### 3. Commit the version bump

```bash
# 3. Commit both files — the gate and the release validation both require them
git add pyproject.toml uv.lock
git commit -m "chore: bump version to $(uv version --short)"
```

### 4. Create and push the tag

The tag MUST match the version exactly (with `v` prefix):

```bash
git tag v1.2.3
git push origin main
git push origin v1.2.3
```

### 5. What happens automatically

The `release.yml` workflow runs on the tag push:

1. **validate-version** — confirms the tag matches `pyproject.toml` version
2. **tests** — runs `pytest` + `behave` (full test suite)
3. **build-push** — builds Docker image, pushes to `ghcr.io/<owner>/spencer-bot` with tags:
   - `1.2.3` (full version)
   - `1.2` (minor)
   - `latest` (moving tag for latest stable)
4. **github-release** — creates a GitHub Release with auto-generated release notes

### Important notes

- **Pre-release versions** (`v1.2.3-beta.1`, `v1.2.3-rc.1`) work but do NOT get `latest` or `major.minor` Docker tags — only the full version tag
- **Version 0.x.y** follows semver 0.x rules: `0.1.0` → tags `0.1.0`, `0.1`, `latest`
- **Mismatched tag/version** — the `validate-version` job fails fast if the tag doesn't match `pyproject.toml`
- **Version bump lockfile sync** — a version bump that changes only `pyproject.toml` fails `version-check` because `uv.lock` must record the same version
- **CI must be green first** — the `tests` job runs the full suite; if it fails, the image is never built
- **No rollback built-in** — to roll back, re-tag an earlier commit and push
