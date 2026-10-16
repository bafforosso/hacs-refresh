"""Validate integration, project, and optional release-tag versions."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("custom_components/hacs_refresh/manifest.json")
PROJECT_PATH = Path("pyproject.toml")

# SemVer: MAJOR.MINOR.PATCH, optional prerelease and build metadata.
_VERSION_PATTERN = re.compile(
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)\."
    r"(?:0|[1-9]\d*)"
    r"(?:"
    # Home Assistant / PEP 440 prerelease suffixes: 1.0.0a0, 1.0.0b0, 1.0.0rc0
    r"(?:a|b|rc)(?:0|[1-9]\d*)"
    r"|"
    # SemVer prerelease identifiers
    r"-(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*"
    r")?"
    # Optional SemVer build metadata
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)


class VersionCheckError(ValueError):
    """Raised when version declarations or the release tag are invalid."""


def _read_version(root: Path, relative_path: Path, key: str) -> str:
    """Read and validate a version declaration."""
    path = root / relative_path

    try:
        with path.open("rb") as file:
            if relative_path.suffix == ".json":
                data: Any = json.load(file)
            else:
                data = tomllib.load(file)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
    ) as err:
        raise VersionCheckError(f"Cannot read {relative_path}: {err}") from err

    value: Any = data
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise VersionCheckError(
                f"Missing version declaration '{key}' in {relative_path}"
            )
        value = value[part]

    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
        raise VersionCheckError(
            f"Invalid version in {relative_path} ({key}): {value!r}; "
            "expected MAJOR.MINOR.PATCH with an optional supported "
            "prerelease suffix or build metadata"
        )

    return value


def validate_versions(root: Path, tag: str | None = None) -> None:
    """Validate the declarations and, optionally, a v-prefixed release tag."""
    manifest_version = _read_version(root, MANIFEST_PATH, "version")
    project_version = _read_version(root, PROJECT_PATH, "project.version")

    if manifest_version != project_version:
        raise VersionCheckError(
            f"Version mismatch: {MANIFEST_PATH} declares {manifest_version}, "
            f"but {PROJECT_PATH} declares {project_version}"
        )

    if tag is None:
        return

    if not tag.startswith("v"):
        raise VersionCheckError(
            f"Invalid release tag {tag!r}: expected a 'v' prefix (for example, v1.2.2)"
        )

    tag_version = tag[1:]
    if not _VERSION_PATTERN.fullmatch(tag_version):
        raise VersionCheckError(
            f"Invalid release tag {tag!r}: expected 'v' followed by "
            "MAJOR.MINOR.PATCH with an optional supported prerelease "
            "suffix or build metadata"
        )

    if tag_version != manifest_version:
        raise VersionCheckError(
            f"Release tag {tag!r} does not match the declared version "
            f"{manifest_version}"
        )


def main() -> int:
    """Run the version consistency check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        help="Release tag to validate (must use the v prefix)",
    )
    args = parser.parse_args()

    try:
        validate_versions(PROJECT_ROOT, args.tag)
    except VersionCheckError as err:
        print(f"Version check failed: {err}", file=sys.stderr)
        return 1

    if args.tag is None:
        print("Version declarations are consistent.")
    else:
        print(f"Version declarations match release tag {args.tag!r}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
