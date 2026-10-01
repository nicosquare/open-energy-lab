"""Optional execution contract for the Feature 013 source notebook."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


pytestmark = pytest.mark.notebook


NOTEBOOK_PATH = Path(
    "examples/robust_fcr_bidding/robust_fcr_bidding_walkthrough.ipynb"
)
FIGURE_EXPORT_DIR = Path("tmp/robust-fcr-bidding-notebook/figures")
EXPECTED_DISPLAY_FINGERPRINT = (
    "7f6c1ae687495655b63c309b17741af753fd7bb6419c0bcdc25532b26efbaec0"
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
assert RUN_OPTIONAL_GUROBI_REFERENCE_BENCHMARK is False
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
assert abs(restriction_result.solver.objective_value_eur - 4.254545454545456) < 1e-12
assert abs(relaxation_result.solver.objective_value_eur - 4.254545454545454) < 1e-12
assert bound_comparison.restriction_le_relaxation.satisfied
assert len(energy_schedule_table) == 24
assert len(fcr_schedule_table) == 6
assert energy_schedule_table["restriction baseline (kW, charge-positive)"].tolist() == [
    -10.0, 10.0, 10.0, 0.0, -10.0, -10.0, 0.0, 0.0,
    3.636363636, 6.363636364, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
]
assert fcr_schedule_table["restriction symmetric FCR (kW)"].tolist() == [
    0.0, 0.0, 3.636363636, 3.636363636, 3.636363636, 3.636363636,
]
assert audit.passes_deployability_audit
assert max(audit.modeled_slacks.values()) == 0.0
assert audit_table["maximum positive violation"].max() < 1e-9
assert len(headroom_table) == 96
assert len(reserve_attribution_table) == 6
assert reserve_attribution_table["pointwise power-only capacity (kW)"].tolist()[:2] == [0.0, 0.0]
assert reserve_attribution_table["pointwise power-only capacity (kW)"].tolist()[3:] == [10.0, 10.0, 10.0]
assert abs(robust_energy_capacity_kw - 3.6363636363636362) < 1e-12
assert len(objective_table) == 10
assert walkthrough_evaluation_report.status == "settled"
assert walkthrough_evaluation_request.plan is restriction_result.deployable_plan
assert set(walkthrough_evaluation_reports) == {{"nominal", "upward pulses", "downward pulses"}}
assert all(report.status == "settled" for report in walkthrough_evaluation_reports.values())
assert all(
    request.plan is restriction_result.deployable_plan
    for request in walkthrough_evaluation_requests.values()
)
assert len(replay_trace_table) == 288
assert activation_stress_table["absolute activated hours"].tolist() == [0.0, 2.0, 2.0]
assert physical_metrics["saturation_sample_count"] == 0
assert physical_metrics["absolute_tracking_error_kw_sum"] == 0.0
assert physical_metrics["stored_energy_kwh"]["initial"] == 10.0
assert physical_metrics["stored_energy_kwh"]["minimum"] == 0.0
assert physical_metrics["stored_energy_kwh"]["maximum"] == 20.0
assert abs(physical_metrics["stored_energy_kwh"]["terminal"] - 2.727272728) < 1e-9
assert abs(physical_metrics["throughput_kwh"] - 65.454545454) < 1e-9
assert set(physical_summary_table["saturation samples"]) == {{0}}
assert set(physical_summary_table["tracking-error sum (kW-samples)"]) == {{0.0}}
assert len(settlement_table) == 24
assert abs(settlement_payload["total_profit_eur"] - 4.690909090720001) < 1e-12
assert settlement_payload["reconciliation_error_eur"] < 1e-12
assert economics_separation_table["Feature 012 realized profit (EUR)"].tolist()[0] < economics_separation_table["Feature 012 realized profit (EUR)"].tolist()[1]
assert economics_separation_table["Feature 012 realized profit (EUR)"].tolist()[2] < economics_separation_table["Feature 012 realized profit (EUR)"].tolist()[0]
assert len(fingerprint_table) == 20
assert len(reference_provenance_table) == 8
assert len(reference_precision_table) == 5
assert len(reference_decision_table) == 30
assert len(reference_precision_resolution_table) == 2
assert reference_fixture.precision_policy.decision_half_unit_kw == 0.0005
assert len(generated_figures) == 6
assert set(generated_figures) == {{
    "input_prices",
    "joint_bid_and_headroom",
    "reserve_constraint_attribution",
    "ex_ante_objective_components",
    "post_acceptance_stress_replay",
    "realized_economics_by_scenario",
}}
assert all(figure.axes for figure in generated_figures.values())
assert native_reference_benchmark["status"] == "not_requested"
assert gurobi_reference_benchmark["status"] == "not_requested"
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
