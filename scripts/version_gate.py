"""Version bump policy for pull requests (standard library only).

Pure logic: no git, no filesystem, no environment access, so it is unit-tested
in memory and shared by the CLI entry point.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass

PROJECT_FILE = "pyproject.toml"
LOCK_FILE = "uv.lock"
PACKAGE_NAME = "expense-report-bot"

# Files whose change alters the shipped image or its metadata.
RELEVANT_FILES = frozenset(
    {
        "Dockerfile",
        "LICENSE",
        "docker-entrypoint.sh",
        "pyproject.toml",
        "uv.lock",
    }
)
# Directories copied into the image (see Dockerfile).
RELEVANT_DIRECTORIES = ("src/", "db/")

_SEMVER = re.compile(r"(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)")


class VersionCheckError(ValueError):
    """Raised when a pull request violates the version policy."""


@dataclass(frozen=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, raw: str, *, source: str) -> SemanticVersion:
        match = _SEMVER.fullmatch(raw)
        if match is None:
            raise VersionCheckError(f"{source} version {raw!r} must use MAJOR.MINOR.PATCH")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )


def requires_version_bump(changed_paths: Sequence[str]) -> bool:
    return any(
        path in RELEVANT_FILES or path.startswith(RELEVANT_DIRECTORIES) for path in changed_paths
    )


def read_project_version(content: str, *, source: str) -> str:
    try:
        version = tomllib.loads(content)["project"]["version"]
    except (tomllib.TOMLDecodeError, KeyError, TypeError) as error:
        raise VersionCheckError(f"{source} must define project.version") from error
    return str(version)


def read_lock_version(content: str) -> str:
    try:
        lock_data = tomllib.loads(content)
    except tomllib.TOMLDecodeError as error:
        raise VersionCheckError(f"{LOCK_FILE} is not valid TOML") from error

    packages = lock_data.get("package", [])
    if not isinstance(packages, list) or not all(isinstance(package, dict) for package in packages):
        raise VersionCheckError(f"{LOCK_FILE} package metadata must be a list of tables")

    for package in packages:
        if package.get("name") != PACKAGE_NAME:
            continue
        version = package.get("version")
        if not isinstance(version, str):
            raise VersionCheckError(f"{LOCK_FILE} {PACKAGE_NAME} package must define version")
        return version

    raise VersionCheckError(f"{LOCK_FILE} does not contain {PACKAGE_NAME} package metadata")


def validate_version_change(
    *,
    changed_paths: Sequence[str],
    base_project: str,
    head_project: str,
    head_lock: str,
) -> None:
    if not requires_version_bump(changed_paths):
        return

    base_version = read_project_version(base_project, source="base " + PROJECT_FILE)
    head_version = read_project_version(head_project, source="pull request " + PROJECT_FILE)
    if SemanticVersion.parse(
        head_version, source="pull request " + PROJECT_FILE
    ) <= SemanticVersion.parse(base_version, source="base " + PROJECT_FILE):
        raise VersionCheckError(
            f"pull request version {head_version} must be greater than {base_version}"
        )

    lock_version = read_lock_version(head_lock)
    if lock_version != head_version:
        raise VersionCheckError(
            f"{LOCK_FILE} version {lock_version} does not match {PROJECT_FILE} "
            f"version {head_version}"
        )
