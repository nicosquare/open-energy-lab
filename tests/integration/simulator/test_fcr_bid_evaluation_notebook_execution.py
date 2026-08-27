"""Optional execution contracts for the Feature 012 source-only notebook."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest


NOTEBOOK_PATH = Path(
    "examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb"
)
EXTERNAL_ACTIVATION_PATH = Path(
    "artifacts/reference/robust_storage_bidding/regulation_signal.csv"
)
FIGURE_EXPORT_DIR = Path("tmp/fcr-bid-evaluation-notebook/figures")
EXPECTED_DISPLAY_FINGERPRINT = (
    "14ac81308ab6efbaa34140c296f6c651dc43262ce2cc5ba8d57985d3fb18eb96"
)
EXPECTED_EXTERNAL_TRACE_FINGERPRINT = (
    "f292f4990d99f6ca4aa7bb12c304b70751396e3c2005544577c58ceb153573f6"
)
EXPECTED_EXTERNAL_SETTLEMENT_FINGERPRINT = (
    "8e5382463fd8e9bd110214fa4cd87be7539ae0fab70eb4ead0bb2b55cbbf72ca"
)
EXPECTED_EXTERNAL_COMPARISON_FINGERPRINT = (
    "1e16c8f03f3c8c649ab1a435d8a14849f51b168b91fc7915df236c492a8b274e"
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
    raise AssertionError("offline notebook attempted network access")

socket.create_connection = _forbidden_notebook_io
socket.socket.connect = _forbidden_notebook_io
urllib.request.urlopen = _forbidden_notebook_io
_real_getenv = os.getenv

def _guarded_notebook_getenv(key, default=None):
    if key in {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}:
        raise AssertionError(f"offline notebook read credential variable {key}")
    return _real_getenv(key, default)

os.getenv = _guarded_notebook_getenv
""".strip(),
        cell_id="test-offline-guard",
    )


def test_notebook_executes_all_default_cells_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nbformat = pytest.importorskip("nbformat", reason="notebook group is optional")
    nbclient = pytest.importorskip("nbclient", reason="notebook group is optional")

    source_bytes = NOTEBOOK_PATH.read_bytes()
    notebook = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    working = copy.deepcopy(notebook)
    before_exports = _export_snapshot()

    for key in ("RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    assertions = _code_cell(
        nbformat,
        f"""
assert RUN_EXTERNAL_REFERENCE is False
assert EXPORT_FIGURES is False
assert authored_report.status == "settled"
assert invalid_report.status == "validation_failed"
assert len(schedule_table) == 5
assert len(physical_trace_table) == 8
assert len(physical_summary_table) >= 16
assert len(settlement_table) == 8
assert len(directional_energy_table) == 6
assert len(diagnostic_table) >= 1
assert len(producer_comparison_table) == 4
assert set(producer_comparison_table["producer_kind"]) == {{"manual", "heuristic", "robust", "tpm"}}
assert set(producer_comparison_table["status"]) == {{"settled"}}
assert producer_comparison_table["physical_fingerprint"].nunique() == 1
assert producer_comparison_table["settlement_fingerprint"].nunique() == 1
assert len(reference_provenance_table) >= 8
assert len(reference_mapping_table) >= 8
assert len(reference_field_table) == 24
assert len(precision_bound_table) == 9
assert len(generated_figures) == 5
assert all(figure.axes for figure in generated_figures.values())
assert external_reference_result["status"] == "not_requested"
assert notebook_display_fingerprint == {EXPECTED_DISPLAY_FINGERPRINT!r}
""".strip(),
        cell_id="test-default-assertions",
    )
    working.cells.insert(0, _offline_guard(nbformat))
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
    assert _export_snapshot() == before_exports


@pytest.mark.external_reference_data
def test_notebook_executes_explicit_2023_06_18_reference_case() -> None:
    if not EXTERNAL_ACTIVATION_PATH.is_file():
        pytest.skip(
            "external Feature 012 reference data is absent; place the digest-matched "
            "regulation_signal.csv at artifacts/reference/robust_storage_bidding/ "
            "as documented in specs/012-fcr-bid-evaluation-parity/quickstart.md"
        )

    nbformat = pytest.importorskip("nbformat", reason="notebook group is optional")
    nbclient = pytest.importorskip("nbclient", reason="notebook group is optional")

    source_bytes = NOTEBOOK_PATH.read_bytes()
    notebook = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    working = copy.deepcopy(notebook)
    activation_path = EXTERNAL_ACTIVATION_PATH.resolve()
    config = next(cell for cell in working.cells if cell.id == "offline-configuration")
    config.source = config.source.replace(
        "RUN_EXTERNAL_REFERENCE = False", "RUN_EXTERNAL_REFERENCE = True"
    )
    config.source = "\n".join(
        (
            f"EXTERNAL_REFERENCE_CSV = Path({str(activation_path)!r})"
            if line.startswith("EXTERNAL_REFERENCE_CSV = ")
            else line
        )
        for line in config.source.splitlines()
    )

    assertions = _code_cell(
        nbformat,
        f"""
assert external_reference_result["status"] == "source_precision_compatible"
assert external_reference_result["counts"] == {{"energy": 24, "fcr": 6, "checkpoint": 96, "activation": 8640}}
assert external_reference_result["mismatch_count"] == 0
assert len(external_reference_comparison_table) == len(external_comparison.fields)
assert {{"field_id", "status", "actual_value", "expected_value", "unit"}} <= set(external_reference_comparison_table.columns)
assert "mismatch" not in set(external_reference_comparison_table["status"])
assert external_reference_result["trace_fingerprint"] == {EXPECTED_EXTERNAL_TRACE_FINGERPRINT!r}
assert external_reference_result["settlement_fingerprint"] == {EXPECTED_EXTERNAL_SETTLEMENT_FINGERPRINT!r}
assert external_reference_result["comparison_fingerprint"] == {EXPECTED_EXTERNAL_COMPARISON_FINGERPRINT!r}
""".strip(),
        cell_id="test-external-assertions",
    )
    working.cells.insert(0, _offline_guard(nbformat))
    working.cells.append(assertions)

    client = nbclient.NotebookClient(
        working,
        timeout=180,
        kernel_name="python3",
        allow_errors=False,
    )
    client.execute(cwd=str(Path.cwd()))

    assert NOTEBOOK_PATH.read_bytes() == source_bytes
