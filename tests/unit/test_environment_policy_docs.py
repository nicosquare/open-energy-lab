"""Documentation contract tests for foundation environment policy."""

from __future__ import annotations

from pathlib import Path


ENVIRONMENT_YML = Path("environment.yml")
PYPROJECT_TOML = Path("pyproject.toml")
ENVIRONMENT_POLICY_DOC = Path("docs/migration/environment-assumptions.md")


def _read_text(path: Path) -> str:
    assert path.is_file(), f"{path} must exist"
    return path.read_text(encoding="utf-8")


def test_environment_files_define_conda_base_and_uv_python_workflow() -> None:
    environment_yml = _read_text(ENVIRONMENT_YML).lower()
    pyproject_toml = _read_text(PYPROJECT_TOML).lower()

    assert "name: open-energy-lab" in environment_yml
    assert "conda-forge" in environment_yml
    assert "python=3.11" in environment_yml
    assert "uv" in environment_yml
    assert '"pvlib"' in pyproject_toml
    assert '"timezonefinder"' in pyproject_toml
    assert '"pandas"' in pyproject_toml
    assert "[dependency-groups]" in pyproject_toml
    assert "pytest" in pyproject_toml


def test_environment_policy_doc_describes_conda_base_and_uv_package_manager() -> None:
    policy_text = _read_text(ENVIRONMENT_POLICY_DOC).lower()

    required_terms = [
        "conda",
        "base environment",
        "uv",
        "python package manager",
    ]
    missing_terms = [term for term in required_terms if term not in policy_text]

    assert missing_terms == []
