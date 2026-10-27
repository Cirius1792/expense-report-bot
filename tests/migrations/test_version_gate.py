"""Unit and CLI coverage for the pull-request version bump gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.version_gate import (
    VersionCheckError,
    requires_version_bump,
    validate_version_change,
)

REPO_ROOT = Path(__file__).parents[2]


def _project(version: str) -> str:
    return f'[project]\nname = "expense-report-bot"\nversion = "{version}"\n'


def _lock(version: str) -> str:
    return f'version = 1\n\n[[package]]\nname = "expense-report-bot"\nversion = "{version}"\n'


def _validate(changed_paths: list[str], base: str = "0.8.0", head: str = "0.8.1") -> None:
    validate_version_change(
        changed_paths=changed_paths,
        base_project=_project(base),
        head_project=_project(head),
        head_lock=_lock(head),
    )


@pytest.mark.parametrize(
    "path",
    [
        "src/expense_report/domain/models.py",
        "db/changelog/db.changelog.xml",
        "Dockerfile",
        "docker-entrypoint.sh",
        "pyproject.toml",
        "uv.lock",
    ],
)
def test_shipped_paths_require_a_greater_version(path: str) -> None:
    with pytest.raises(VersionCheckError, match="must be greater than 0.8.0"):
        _validate([path], head="0.8.0")


@pytest.mark.parametrize(
    "path",
    [
        "docs/expectations/expense-query-policy.md",
        "tests/domain/test_models.py",
        "features/delete.feature",
        ".github/workflows/ci.yml",
        "README.md",
        "AGENTS.md",
    ],
)
def test_repository_only_paths_do_not_require_a_bump(path: str) -> None:
    assert requires_version_bump([path]) is False
    _validate([path], base="0.8.0", head="0.8.0")


@pytest.mark.parametrize("head", ["0.8.1", "0.9.0", "1.0.0"])
def test_a_greater_synced_version_is_accepted(head: str) -> None:
    _validate(["src/expense_report/domain/models.py"], head=head)


@pytest.mark.parametrize("head", ["0.8.0", "0.7.9"])
def test_equal_or_lower_versions_are_rejected(head: str) -> None:
    with pytest.raises(VersionCheckError, match="must be greater than 0.8.0"):
        _validate(["src/expense_report/domain/models.py"], head=head)


@pytest.mark.parametrize("head", ["0.9", "v1.0.0", "1.0.0-rc.1", "01.0.0"])
def test_non_semantic_versions_are_rejected(head: str) -> None:
    with pytest.raises(VersionCheckError, match="MAJOR.MINOR.PATCH"):
        _validate(["src/expense_report/domain/models.py"], head=head)


def test_stale_lockfile_is_rejected() -> None:
    with pytest.raises(VersionCheckError, match="uv.lock version 0.8.0"):
        validate_version_change(
            changed_paths=["src/expense_report/domain/models.py"],
            base_project=_project("0.8.0"),
            head_project=_project("0.8.1"),
            head_lock=_lock("0.8.0"),
        )


def test_lockfile_without_the_project_entry_is_rejected() -> None:
    with pytest.raises(VersionCheckError, match="does not contain expense-report-bot"):
        validate_version_change(
            changed_paths=["src/expense_report/domain/models.py"],
            base_project=_project("0.8.0"),
            head_project=_project("0.8.1"),
            head_lock='version = 1\n\n[[package]]\nname = "other"\nversion = "1.0.0"\n',
        )


def test_missing_project_version_is_rejected() -> None:
    with pytest.raises(VersionCheckError, match="must define project.version"):
        validate_version_change(
            changed_paths=["src/expense_report/domain/models.py"],
            base_project=_project("0.8.0"),
            head_project='[project]\nname = "expense-report-bot"\n',
            head_lock=_lock("0.8.1"),
        )


def _git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments], cwd=repository, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", ".")
    _git(repository, "commit", "-m", message)
    return _git(repository, "rev-parse", "HEAD")


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "config", "user.name", "Test User")
    _git(repository, "config", "user.email", "test@example.com")
    (repository / "src" / "expense_report").mkdir(parents=True)
    (repository / "src" / "expense_report" / "models.py").write_text(
        "VALUE = 1\n", encoding="utf-8"
    )
    (repository / "pyproject.toml").write_text(_project("0.8.0"), encoding="utf-8")
    (repository / "uv.lock").write_text(_lock("0.8.0"), encoding="utf-8")
    return repository


def _run_gate(repository: Path, base_ref: str, head_ref: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.check_pr_version",
            "--repository",
            str(repository),
            base_ref,
            head_ref,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_rejects_source_change_without_a_bump(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    base_sha = _commit(repository, "base")
    (repository / "src" / "expense_report" / "models.py").write_text(
        "VALUE = 2\n", encoding="utf-8"
    )
    head_sha = _commit(repository, "source change")

    result = _run_gate(repository, base_sha, head_sha)

    assert result.returncode == 1
    assert "must be greater than 0.8.0" in result.stderr


def test_cli_accepts_documentation_only_change(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    base_sha = _commit(repository, "base")
    (repository / "README.md").write_text("docs\n", encoding="utf-8")
    head_sha = _commit(repository, "docs only")

    result = _run_gate(repository, base_sha, head_sha)

    assert result.returncode == 0
    assert "policy passed" in result.stdout


def test_cli_rejects_moving_source_out_of_the_shipped_tree(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _git(repository, "config", "diff.renames", "true")
    base_sha = _commit(repository, "base")
    (repository / "docs").mkdir()
    _git(repository, "mv", "src/expense_report/models.py", "docs/models.py")
    head_sha = _commit(repository, "move source into docs")

    result = _run_gate(repository, base_sha, head_sha)

    assert result.returncode == 1
    assert "must be greater than 0.8.0" in result.stderr
