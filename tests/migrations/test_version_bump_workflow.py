"""Guard rails for the pull-request version bump gate (ADR 0023)."""

from __future__ import annotations

from pathlib import Path

from scripts.version_gate import requires_version_bump

REPO_ROOT = Path(__file__).parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GATE_COMMAND = 'uv run --no-project python -m scripts.check_pr_version "$BASE_SHA" "$HEAD_SHA"'


def _read(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_ci_runs_the_gate_on_pull_requests_against_event_shas() -> None:
    ci = _read("ci.yml")
    assert "version-check:" in ci
    assert "if: github.event_name == 'pull_request'" in ci
    assert "fetch-depth: 0" in ci
    assert "BASE_SHA: ${{ github.event.pull_request.base.sha }}" in ci
    assert "HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in ci
    assert GATE_COMMAND in ci


def test_gate_job_is_read_only() -> None:
    """The gate runs on fork code: it must never receive a write token."""
    job = _read("ci.yml").split("version-check:", 1)[1].split("generate-badge:", 1)[0]
    assert "contents: read" in job
    assert "contents: write" not in job


def test_gate_does_not_live_in_the_reusable_test_workflow() -> None:
    """release.yml calls tests.yml and has no pull_request payload to diff."""
    assert "check_pr_version" not in _read("tests.yml")
    assert "check_pr_version" not in _read("release.yml")


def test_policy_covers_every_path_the_image_ships() -> None:
    """A path copied into the image must be release-relevant, or it escapes the gate."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    shipped = [
        argument
        for line in dockerfile.splitlines()
        if line.startswith("COPY ") and "--from=" not in line
        for argument in line.split()[1:-1]
        if argument != "."
    ]
    assert shipped, "Dockerfile ships no explicit paths — check the parser"
    uncovered = [path for path in shipped if not requires_version_bump([path])]
    assert uncovered == []
