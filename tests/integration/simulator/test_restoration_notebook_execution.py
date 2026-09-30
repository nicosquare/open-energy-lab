"""Optional real-kernel execution contract for the offline walkthrough."""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest


pytestmark = pytest.mark.notebook


NOTEBOOK_PATH = Path(
    "examples/restoration_services/restoration_services_walkthrough.ipynb"
)
EXPECTED_RESULT_FINGERPRINT = (
    "abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f"
)
EXPECTED_DISPLAY_FINGERPRINT = (
    "88ab88e3859e4fe81555651468bcc9e4c474db43feee11ecd1eef6b18568e976"
)


def _code_cell(nbformat, source: str, *, cell_id: str):
    cell = nbformat.v4.new_code_cell(source=source)
    cell["id"] = cell_id
    return cell


def test_notebook_executes_all_offline_cells_with_network_and_credentials_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nbformat = pytest.importorskip("nbformat", reason="notebook group is optional")
    nbclient = pytest.importorskip("nbclient", reason="notebook group is optional")

    source_bytes = NOTEBOOK_PATH.read_bytes()
    notebook = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    working = copy.deepcopy(notebook)

    for key in ("RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    guard = _code_cell(
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
    assertions = _code_cell(
        nbformat,
        f"""
assert RUN_LIVE_QUERY is False
assert RUN_LIVE_ENTSOE_QUERY is False
assert EXPORT_FIGURES is False
assert result_set_fingerprint == {EXPECTED_RESULT_FINGERPRINT!r}
assert notebook_display_fingerprint == {EXPECTED_DISPLAY_FINGERPRINT!r}
assert set(product_cases) == {{"AFRR", "MFRR"}}
assert len(provenance_table) == 2
assert len(afrr_market_table) == 32
assert len(mfrr_market_table) >= 22
assert len(commitment_table) == 4
assert len(activation_table) == 5
assert len(physical_table) == 5
assert len(performance_table) >= 4
assert len(energy_table) == 2
assert len(settlement_table) == 2
assert len(reproducibility_table) >= 10
assert len(generated_figures) >= 7
assert all(figure.axes for figure in generated_figures.values())
assert live_rte_table.empty
assert live_replay_table.empty
assert live_settlement_table.empty
assert live_pipeline_result is None
assert live_entsoe_selection == "not requested; using declared zero day-ahead price"
""".strip(),
        cell_id="test-offline-assertions",
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
    assert not Path("tmp/restoration-services-notebook/figures").exists()
