"""Fail when a pull request changes shipped files without a greater version."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from scripts.version_gate import (
    LOCK_FILE,
    PROJECT_FILE,
    VersionCheckError,
    requires_version_bump,
    validate_version_change,
)


def _git(repository: Path, *arguments: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=repository, check=True, capture_output=True
        )
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode("utf-8", errors="replace").strip()
        raise VersionCheckError(
            f"git {' '.join(arguments)} failed: {details or 'unknown git error'}"
        ) from error
    return result.stdout


def _show(repository: Path, ref: str, path: str) -> str | None:
    """Content of ``path`` at ``ref``, or None when the file does not exist there."""
    try:
        return _git(repository, "show", f"{ref}:{path}").decode("utf-8")
    except VersionCheckError:
        return None


def validate_refs(base_ref: str, head_ref: str, *, repository: Path) -> None:
    raw = _git(
        repository,
        "diff",
        "--no-renames",
        "--name-only",
        "-z",
        f"{base_ref}...{head_ref}",
    )
    changed_paths = [path for path in raw.decode("utf-8").split("\0") if path]
    if not requires_version_bump(changed_paths):
        return

    head_project = _show(repository, head_ref, PROJECT_FILE)
    if head_project is None:
        raise VersionCheckError(f"pull request does not contain {PROJECT_FILE}")

    validate_version_change(
        changed_paths=changed_paths,
        base_project=_show(repository, base_ref, PROJECT_FILE) or '[project]\nversion = "0.0.0"\n',
        head_project=head_project,
        head_lock=_show(repository, head_ref, LOCK_FILE) or "",
    )


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that a shipped-file pull request increments the version."
    )
    parser.add_argument("base_ref", help="Git ref for the pull request base")
    parser.add_argument("head_ref", help="Git ref for the pull request head")
    parser.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Repository to inspect (default: current directory)",
    )
    parsed = parser.parse_args(arguments)

    try:
        validate_refs(parsed.base_ref, parsed.head_ref, repository=parsed.repository)
    except VersionCheckError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    print("Pull request version policy passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
