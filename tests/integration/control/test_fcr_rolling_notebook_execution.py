"""Optional execution contract for the Feature 015 source notebook."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


pytestmark = pytest.mark.notebook


NOTEBOOK_PATH = Path(
    "examples/fcr_rolling_backtest/fcr_rolling_backtest_walkthrough.ipynb"
)
FIGURE_EXPORT_DIR = Path("tmp/fcr-rolling-backtest-notebook/figures")
EXPECTED_DISPLAY_FINGERPRINT = (
    "81f26440de4c5053dffc85b56c2ecc1927701202b1e126276ba16249ff9cf8d1"
)


def _code_cell(nbformat, source: str, *, cell_id: str):
    cell = nbformat.v4.new_code_cell(source=source)
    cell["id"] = cell_id
    return cell


def _export_snapshot() -> dict[str, bytes]:
    if not FIGURE_EXPORT_DIR.exists():
        return {}
    return {
        str(path.relative_to(FIGURE_EXPORT_DIR)): path.read_bytes()
        for path in sorted(FIGURE_EXPORT_DIR.rglob("*"))
        if path.is_file()
    }


def _offline_guard(nbformat):
    return _code_cell(
        nbformat,
        """
import os
import socket
import urllib.request

def _forbidden_notebook_io(*_args, **_kwargs):
    raise AssertionError("offline rolling notebook attempted network access")

socket.create_connection = _forbidden_notebook_io
socket.socket.connect = _forbidden_notebook_io
urllib.request.urlopen = _forbidden_notebook_io
_real_getenv = os.getenv

def _guarded_notebook_getenv(key, default=None):
    if key in {
        "RTE_CLIENT_ID",
        "RTE_CLIENT_SECRET",
        "ENTSOE_API_TOKEN",
        "GRB_LICENSE_FILE",
        "GUROBI_HOME",
    }:
        raise AssertionError(f"offline rolling notebook read credential variable {key}")
    return _real_getenv(key, default)

os.getenv = _guarded_notebook_getenv
""".strip(),
        cell_id="test-offline-guard",
    )


def test_notebook_executes_default_study_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nbformat = pytest.importorskip("nbformat", reason="notebook group is optional")
    nbclient = pytest.importorskip("nbclient", reason="notebook group is optional")

    source_bytes = NOTEBOOK_PATH.read_bytes()
    notebook = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    working = copy.deepcopy(notebook)
    before_exports = _export_snapshot()

    for key in (
        "RTE_CLIENT_ID",
        "RTE_CLIENT_SECRET",
        "ENTSOE_API_TOKEN",
        "GRB_LICENSE_FILE",
        "GUROBI_HOME",
    ):
        monkeypatch.delenv(key, raising=False)

    assertions = _code_cell(
        nbformat,
        f"""
assert RUN_ALL_AUTHORED_PROFILES is False
assert RUN_NATIVE_REFERENCE_BENCHMARK is False
assert RUN_EXTERNAL_ACTIVATION_REPLAY is False
assert EXPORT_FIGURES is False
assert len(profile_table) == 5
assert budget_table.iloc[-1]["value"] == 2.75
assert selected_authored_profiles == (DEFAULT_PROFILE_ID,)
assert authored_result.completeness_status == "complete"
assert len(authored_result.records) == 4
assert set(authored_daily_table["lifecycle"]) == {{"finalized"}}
assert len(state_link_table) == 3
assert state_ledger_table["successor reconciliation residual (kWh)"].dropna().abs().max() <= 1e-9
assert all(
    value == 0.0
    for record in authored_result.records
    for value in (record.latest_revision.fcr_capacity_kw or ())
)
assert carry_policy_table["evidence fingerprint"].nunique() == 2
assert len(overlap_energy_table) == 40
assert len(overlap_fcr_table) == 10
assert causality_table.iloc[0]["unchanged"]
assert not causality_table.iloc[1]["unchanged"]
assert len(economics_table) == 4
assert len(lifecycle_table) == 4
assert set(lifecycle_table["lifecycle"]) == {{"initialization_only", "finalized", "unfinalized"}}
assert len(source_solve_table) == 20
assert set(source_solve_table["termination"]) == {{"OPTIMAL", "TIME_LIMIT"}}
assert len(failure_resume_table) == 5
assert len(failure_transition_table) == 2
assert not failure_transition_table["missing state invented"].any()
assert partial_result.completeness_status == "partial"
assert len(partial_result.records) == 2
assert resumed_result.semantic_fingerprint == authored_result.semantic_fingerprint
assert resume_identity_table["compatible"].all()
assert native_reference_benchmark["status"] == "not_requested"
assert external_activation_result["status"] == "not_requested"
assert exported_figure_paths == []
assert len(generated_figures) == 7
assert all(figure.axes for figure in generated_figures.values())
assert notebook_display_fingerprint == {EXPECTED_DISPLAY_FINGERPRINT!r}
""".strip(),
        cell_id="test-default-assertions",
    )
    working.cells.insert(0, _offline_guard(nbformat))
    working.cells.append(assertions)

    client = nbclient.NotebookClient(
        working,
        timeout=240,
        kernel_name="python3",
        allow_errors=False,
    )
    client.execute(cwd=str(Path.cwd()))

    assert NOTEBOOK_PATH.read_bytes() == source_bytes
    assert all(
        cell.get("execution_count") is None and cell.get("outputs", []) == []
        for cell in notebook.cells
        if cell.cell_type == "code"
    )
    assert _export_snapshot() == before_exports
