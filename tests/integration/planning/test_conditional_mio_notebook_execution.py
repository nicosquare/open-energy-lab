"""Required offline headless execution for the conditional-MIO notebook."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys

import pytest


pytestmark = pytest.mark.notebook


NOTEBOOK_PATH = Path(
    "examples/tpm_planning/conditional_mio_embedding_walkthrough.ipynb"
)
FIXTURE_PATHS = (
    Path("tests/fixtures/tpm/conditional_mio_embedding_v1.json"),
    Path("tests/fixtures/tpm/tpm_artifact_conditional_mio_v3.json"),
    Path(
        "tests/fixtures/tpm/sidecars/"
        "tpm_artifact_conditional_mio_v3.spn_payload.pkl"
    ),
    Path("tests/fixtures/tpm/conditional_pair_max_v2.json"),
    Path("tests/fixtures/tpm/conditional_pair_pwl_v2.json"),
    Path("tests/fixtures/tpm/conditional_mio_evidence_v1.json"),
)


def _code_cell(nbformat, source: str, *, cell_id: str):
    cell = nbformat.v4.new_code_cell(source=source)
    cell["id"] = cell_id
    return cell


def _local_kernel(tmp_path: Path) -> tuple[str, Path]:
    kernel_name = "oel-conditional-mio-local"
    kernel_directory = tmp_path / "kernels" / kernel_name
    kernel_directory.mkdir(parents=True)
    (kernel_directory / "kernel.json").write_text(
        json.dumps(
            {
                "argv": [
                    sys.executable,
                    "-m",
                    "ipykernel_launcher",
                    "-f",
                    "{connection_file}",
                ],
                "display_name": "OEL conditional MIO test kernel",
                "language": "python",
            }
        ),
        encoding="utf-8",
    )
    return kernel_name, tmp_path


def test_conditional_mio_notebook_executes_offline_without_mutating_evidence(
    tmp_path: Path,
) -> None:
    import nbclient
    import nbformat

    source_bytes = NOTEBOOK_PATH.read_bytes()
    fixture_bytes = {path: path.read_bytes() for path in FIXTURE_PATHS}
    notebook = nbformat.reads(source_bytes.decode("utf-8"), as_version=4)
    working = copy.deepcopy(notebook)
    working.cells.insert(
        0,
        _code_cell(
            nbformat,
            """
import socket
import urllib.request

def _forbidden_notebook_network(*_args, **_kwargs):
    raise AssertionError("conditional-MIO notebook attempted network access")

socket.create_connection = _forbidden_notebook_network
socket.socket.connect = _forbidden_notebook_network
urllib.request.urlopen = _forbidden_notebook_network
""".strip(),
            cell_id="test-offline-network-guard",
        ),
    )
    working.cells.append(
        _code_cell(
            nbformat,
            """
assert artifact.schema_version == "v3"
assert max_pair.encoding.mode == "max"
assert pwl_pair.encoding.mode == "piecewise"
assert max_parity.accepted
assert pwl_parity.accepted
assert len(loaded_parity_records) == 2
assert len(loaded_fidelity_records) == 2
assert all(record.accepted for record in loaded_parity_records)
assert all("accepted" not in record.to_dict() for record in loaded_fidelity_records)
assert len(evidence_figure.axes) == 2
assert evidence_figure.axes[0].get_yscale() == "log"
assert len(evidence_figure.axes[1].patches) == 6
assert policy_unsolved
assert piecewise_notice_count > 0
assert policy_attachment.block is policy_model.policy_risk
assert policy_model.component("caller_objective") is not None
assert policy_model.component("caller_deterministic_constraint") is not None
assert policy_model.component("caller_chance_constraint") is not None
assert conditional_demo_complete
""".strip(),
            cell_id="test-semantic-result-markers",
        )
    )

    kernel_name, jupyter_path = _local_kernel(tmp_path)
    previous_jupyter_path = os.environ.get("JUPYTER_PATH")
    os.environ["JUPYTER_PATH"] = str(jupyter_path)
    try:
        client = nbclient.NotebookClient(
            working,
            timeout=180,
            kernel_name=kernel_name,
            allow_errors=False,
        )
        client.execute(cwd=str(Path.cwd()))
    finally:
        if previous_jupyter_path is None:
            os.environ.pop("JUPYTER_PATH", None)
        else:
            os.environ["JUPYTER_PATH"] = previous_jupyter_path

    assert NOTEBOOK_PATH.read_bytes() == source_bytes
    assert {path: path.read_bytes() for path in FIXTURE_PATHS} == fixture_bytes
    assert all(
        cell.get("execution_count") is None and cell.get("outputs", []) == []
        for cell in notebook.cells
        if cell.cell_type == "code"
    )
