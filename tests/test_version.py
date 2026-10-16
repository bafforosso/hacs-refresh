"""Tests for version consistency validation."""

import json
import sys
from pathlib import Path

import pytest

import scripts.check_version as version_check
from scripts.check_version import VersionCheckError, main, validate_versions


def create_project(
    tmp_path: Path,
    manifest_version: str = "1.2.2",
    project_version: str = "1.2.2",
) -> Path:
    """Create a minimal project layout for version validation."""
    manifest_path = tmp_path / "custom_components/hacs_refresh/manifest.json"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps({"version": manifest_version}),
        encoding="utf-8",
    )

    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "hacs-refresh"\nversion = "{project_version}"\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.mark.parametrize(
    "version",
    [
        "1.0.0a0",
        "1.0.0b0",
        "1.0.0b1",
        "1.0.0rc0",
        "1.2.2",
        "1.3.0-rc.1",
    ],
)
def test_accepts_valid_versions(tmp_path: Path, version: str) -> None:
    """Valid versions and their matching release tags are accepted."""
    create_project(
        tmp_path,
        manifest_version=version,
        project_version=version,
    )

    validate_versions(tmp_path)
    validate_versions(tmp_path, tag=f"v{version}")


def test_manifest_project_mismatch_fails(tmp_path: Path) -> None:
    """Different manifest and project versions fail."""
    root = create_project(
        tmp_path,
        manifest_version="1.2.2",
        project_version="1.2.3",
    )

    with pytest.raises(VersionCheckError, match="Version mismatch"):
        validate_versions(root)


@pytest.mark.parametrize(
    ("version", "tag"),
    [
        ("1.2.2", "v1.2.3"),
        ("1.2.2", "v1.2.2-rc.1"),
    ],
)
def test_release_tag_mismatch_fails(
    tmp_path: Path,
    version: str,
    tag: str,
) -> None:
    """A release tag that differs from the declarations fails."""
    root = create_project(
        tmp_path,
        manifest_version=version,
        project_version=version,
    )

    with pytest.raises(VersionCheckError, match="does not match"):
        validate_versions(root, tag)


@pytest.mark.parametrize(
    ("manifest_version", "project_version"),
    [
        ("", "1.2.2"),
        ("1.2", "1.2"),
        ("v1.2.2", "v1.2.2"),
        ("01.2.2", "01.2.2"),
        ("1.2.2-beta.", "1.2.2-beta."),
    ],
)
def test_invalid_declared_version_fails(
    tmp_path: Path,
    manifest_version: str,
    project_version: str,
) -> None:
    """Malformed declared versions fail."""
    root = create_project(
        tmp_path,
        manifest_version=manifest_version,
        project_version=project_version,
    )

    with pytest.raises(VersionCheckError, match="Invalid version"):
        validate_versions(root)


@pytest.mark.parametrize(
    "tag",
    [
        "1.2.2",
        "V1.2.2",
        "v",
        "v01.2.2",
        "v1.2",
        "v1.2.2-beta.",
    ],
)
def test_invalid_release_tag_fails(tmp_path: Path, tag: str) -> None:
    """Malformed release tags or missing v prefixes fail."""
    root = create_project(tmp_path)

    with pytest.raises(VersionCheckError, match="Invalid release tag"):
        validate_versions(root, tag)


def test_missing_manifest_version_fails(tmp_path: Path) -> None:
    """A missing manifest version fails with an actionable error."""
    root = create_project(tmp_path)
    manifest_path = root / "custom_components/hacs_refresh/manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    with pytest.raises(VersionCheckError, match="Missing version declaration"):
        validate_versions(root)


def test_missing_project_version_fails(tmp_path: Path) -> None:
    """A missing project version fails with an actionable error."""
    root = create_project(tmp_path)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "hacs-refresh"\n',
        encoding="utf-8",
    )

    with pytest.raises(VersionCheckError, match="Missing version declaration"):
        validate_versions(root)


def test_malformed_manifest_json_fails(tmp_path: Path) -> None:
    """Malformed manifest JSON produces a version-check error."""
    root = create_project(tmp_path)
    manifest_path = root / "custom_components/hacs_refresh/manifest.json"
    manifest_path.write_text('{"version": ', encoding="utf-8")

    with pytest.raises(VersionCheckError, match="Cannot read"):
        validate_versions(root)


def test_malformed_project_toml_fails(tmp_path: Path) -> None:
    """Malformed project TOML produces a version-check error."""
    root = create_project(tmp_path)
    project_path = root / "pyproject.toml"
    project_path.write_text("[project\n", encoding="utf-8")

    with pytest.raises(VersionCheckError, match="Cannot read"):
        validate_versions(root)


@pytest.mark.parametrize(
    "relative_path",
    [
        Path("custom_components/hacs_refresh/manifest.json"),
        Path("pyproject.toml"),
    ],
    ids=["manifest", "project-metadata"],
)
def test_missing_metadata_file_fails(
    tmp_path: Path,
    relative_path: Path,
) -> None:
    """Missing metadata files produce a version-check error."""
    root = create_project(tmp_path)
    (root / relative_path).unlink()

    with pytest.raises(VersionCheckError, match="Cannot read"):
        validate_versions(root)


@pytest.mark.parametrize(
    ("arguments", "expected_output"),
    [
        (
            [],
            "Version declarations are consistent.",
        ),
        (
            ["--tag", "v1.2.2"],
            "Version declarations match release tag 'v1.2.2'.",
        ),
    ],
    ids=["without-release-tag", "with-release-tag"],
)
def test_main_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    expected_output: str,
) -> None:
    """The CLI reports success for consistent versions."""
    create_project(tmp_path)
    monkeypatch.setattr(version_check, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_version.py", *arguments])

    assert main() == 0
    assert capsys.readouterr().out.strip() == expected_output


def test_main_returns_failure_for_mismatched_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI reports validation errors and returns a failure status."""
    create_project(
        tmp_path,
        manifest_version="1.2.2",
        project_version="1.2.3",
    )
    monkeypatch.setattr(version_check, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_version.py"])

    assert main() == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Version check failed: Version mismatch" in captured.err
