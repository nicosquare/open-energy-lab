"""Optional execution contract for the Feature 013 source notebook."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


NOTEBOOK_PATH = Path(
    "examples/robust_fcr_bidding/robust_fcr_bidding_walkthrough.ipynb"
)
FIGURE_EXPORT_DIR = Path("tmp/robust-fcr-bidding-notebook/figures")
EXPECTED_DISPLAY_FINGERPRINT = (
    "a8de959baccdeda692f29b6edfc6c1e164ae73070758b7c9d759931cc04e0ce4"
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
    raise AssertionError("offline robust-FCR notebook attempted network access")

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
        raise AssertionError(
            f"offline robust-FCR notebook read credential variable {key}"
        )
    return _real_getenv(key, default)

os.getenv = _guarded_notebook_getenv
""".strip(),
        cell_id="test-offline-guard",
    )


def test_notebook_executes_default_workflow_offline(
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
assert RUN_NATIVE_REFERENCE_BENCHMARK is False
assert RUN_OPTIONAL_GUROBI_EXACT is False
assert RUN_EXTERNAL_ACTIVATION_REPLAY is False
assert EXPORT_FIGURES is False
assert len(time_contract.planning_intervals) == 96
assert len(time_contract.energy_intervals) == 24
assert len(time_contract.fcr_intervals) == 6
assert horizon_budget.horizon_activation_budget_hours == 2.75
assert len(mapping_table) == 96
assert len(uncertainty_table) == 6
assert restriction_result.solver.solve_status == "optimal"
assert restriction_result.deployability_status == "eligible"
assert restriction_result.deployable_plan is not None
assert relaxation_result.solver.solve_status == "optimal"
assert relaxation_result.deployability_status == "not_applicable"
assert relaxation_result.deployable_plan is None
assert restriction_result.solver.objective_value_eur == 6.0
assert relaxation_result.solver.objective_value_eur == 6.0
assert bound_comparison.restriction_le_relaxation.satisfied
assert len(energy_schedule_table) == 24
assert len(fcr_schedule_table) == 6
assert set(energy_schedule_table["restriction baseline (kW, charge-positive)"]) == {{0.0}}
assert set(fcr_schedule_table["restriction symmetric FCR (kW)"]) == {{10.0}}
assert audit.passes_deployability_audit
assert max(audit.modeled_slacks.values()) == 0.0
assert audit_table["maximum positive violation"].max() == 0.0
assert len(headroom_table) == 96
assert len(stored_energy_envelope_table) == 96
assert stored_energy_envelope_table["lower horizon-budget envelope (kWh)"].min() == 22.5
assert stored_energy_envelope_table["upper horizon-budget envelope (kWh)"].max() == 77.5
assert len(objective_table) == 10
assert walkthrough_evaluation_report.status == "settled"
assert walkthrough_evaluation_request.plan is restriction_result.deployable_plan
assert len(replay_trace_table) == 96
assert physical_metrics["saturation_sample_count"] == 0
assert physical_metrics["absolute_tracking_error_kw_sum"] == 0.0
assert physical_metrics["stored_energy_kwh"] == {{
    "initial": 50.0,
    "minimum": 47.5,
    "maximum": 50.0,
    "terminal": 50.0,
}}
assert physical_metrics["throughput_kwh"] == 120.0
assert len(settlement_table) == 8
assert settlement_payload["total_profit_eur"] == 6.0
assert settlement_payload["reconciliation_error_eur"] == 0.0
assert len(fingerprint_table) == 12
assert len(reference_provenance_table) == 8
assert len(reference_precision_table) == 5
assert len(reference_decision_table) == 30
assert reference_fixture.precision_policy.decision_half_unit_kw == 0.0005
assert len(generated_figures) == 7
assert set(generated_figures) == {{
    "input_prices",
    "optimized_schedules",
    "robust_feasibility",
    "objective_evidence",
    "physical_replay",
    "realized_settlement",
    "reference_source_precision",
}}
assert all(figure.axes for figure in generated_figures.values())
assert native_reference_benchmark["status"] == "not_requested"
assert optional_exact_result["status"] == "not_requested"
assert external_activation_result["status"] == "not_requested"
assert exported_figure_paths == []
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
