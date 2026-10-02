"""Optional real-kernel execution contract for the U-Bounds walkthrough."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


pytestmark = pytest.mark.notebook


NOTEBOOK_PATH = Path(
    "examples/tpm_planning/declared_feature_domains_walkthrough.ipynb"
)


def _code_cell(nbformat, source: str, *, cell_id: str):
    cell = nbformat.v4.new_code_cell(source=source)
    cell["id"] = cell_id
    return cell


def test_notebook_executes_all_cells_offline_against_persisted_v3_evidence() -> None:
    nbformat = pytest.importorskip("nbformat", reason="notebook group is optional")
    nbclient = pytest.importorskip("nbclient", reason="notebook group is optional")

    source_bytes = NOTEBOOK_PATH.read_bytes()
    notebook = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    working = copy.deepcopy(notebook)
    guard = _code_cell(
        nbformat,
        """
import socket
import urllib.request

def _forbidden_notebook_io(*_args, **_kwargs):
    raise AssertionError("declared-domain notebook attempted network access")

socket.create_connection = _forbidden_notebook_io
socket.socket.connect = _forbidden_notebook_io
urllib.request.urlopen = _forbidden_notebook_io
""".strip(),
        cell_id="test-offline-guard",
    )
    assertions = _code_cell(
        nbformat,
        """
assert artifact.schema_version == "v3"
assert semantic_summary.loc["x", "mathematical meaning"] == "decision-domain: [40.0, 160.0]"
assert semantic_summary.loc["demand", "normalization"] == "identity"
assert (wide_x.training_support.minimum, wide_x.training_support.maximum) == (60.0, 140.0)
assert (narrow_x.training_support.minimum, narrow_x.training_support.maximum) == (80.0, 120.0)
assert normalization_comparison.iloc[:, 1].equals(normalization_comparison.iloc[:, 2])
assert not bool(relevant_cases.loc[1, "observed in training"])
assert len(native_query_table) == 3
assert set(native_query_table["source"]) == {"spflow_backend"}
assert rejected_native_query["reason"] == "decision_domain_violation"
assert compiled["schema_version"] == "v2"
assert compiled_validity["physical_interval"] == [60.0, 140.0]
assert compiled_validity["model_interval"] == [1.0 / 6.0, 5.0 / 6.0]
assert len(compiled_evaluation_table) == 3
assert len(compiled_rejections) == 2
assert str(inside_result.solver.termination_condition).lower() == "optimal"
assert abs(highs_link_evidence["derived model coordinate"] - 0.5) <= 1e-9
assert "infeasible" in str(outside_result.solver.termination_condition).lower()
""".strip(),
        cell_id="test-domain-assertions",
    )
    working.cells.insert(0, guard)
    working.cells.append(assertions)

    client = nbclient.NotebookClient(
        working,
        timeout=180,
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
