"""CI selects tests by marker, and CI and pyproject agree on the opt-in groups.

Replaces the per-job file-list pins (consolidation A4c). Test selection lives in
pyproject.toml markers; the workflow only chooses which marker groups run where.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
PYTEST_CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["pytest"]["ini_options"]

OPT_IN = {"licensed_gurobi", "live_entsoe", "live_rte", "reference_benchmark", "external_reference_data"}
OWN_JOB = {"slow", "notebook"}


def _run_steps(job: str) -> list[str]:
    return [step["run"] for step in WORKFLOW["jobs"][job]["steps"] if "run" in step]


def _pytest_command(job: str) -> str:
    commands = [run for run in _run_steps(job) if "pytest" in run]
    assert len(commands) == 1, commands
    return commands[0]


def _registered_markers() -> set[str]:
    return {entry.split(":", 1)[0] for entry in PYTEST_CONFIG["markers"]}


def _deselected(expression: str) -> set[str]:
    return set(re.findall(r"not (\w+)", expression))


def test_ci_has_one_job_per_marker_group() -> None:
    assert set(WORKFLOW["jobs"]) == {"tests", "slow", "notebooks"}
    assert WORKFLOW["jobs"]["tests"]["strategy"]["matrix"]["python-version"] == [
        "3.11", "3.12", "3.13", "3.14",
    ]


def test_no_ci_job_selects_tests_by_path() -> None:
    for job in WORKFLOW["jobs"]:
        command = _pytest_command(job)
        assert "tests/" not in command and "--ignore" not in command, (job, command)


def test_routine_job_runs_plain_pytest_and_pyproject_deselects_every_other_group() -> None:
    assert _pytest_command("tests").split() == ["uv", "run", "--locked", "--no-sync", "pytest"]
    assert PYTEST_CONFIG["testpaths"] == ["tests"]
    addopts = PYTEST_CONFIG["addopts"]
    assert "--strict-markers" in addopts
    assert _deselected(addopts) == OPT_IN | OWN_JOB
    assert OPT_IN | OWN_JOB <= _registered_markers()


def test_slow_and_notebook_jobs_select_their_group_and_exclude_opt_in_checks() -> None:
    assert _deselected(WORKFLOW["env"]["OPT_IN"]) == OPT_IN
    assert 'pytest -m "slow and ${OPT_IN}"' in _pytest_command("slow")
    assert 'pytest -m "notebook and ${OPT_IN}"' in _pytest_command("notebooks")
    assert any("--group notebook" in run for run in _run_steps("notebooks"))
    assert "--offline" in _pytest_command("notebooks")


def test_every_job_verifies_the_required_backends() -> None:
    for job in WORKFLOW["jobs"]:
        assert any("tools/verify_backends.py" in run for run in _run_steps(job)), job
