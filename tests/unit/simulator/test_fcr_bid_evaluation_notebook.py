"""Source-only contract for the Feature 012 evaluation walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/fcr_bid_evaluation/fcr_bid_evaluation_walkthrough.ipynb"
)
EXPECTED_CELL_IDS = (
    "title-objective",
    "terminology-evidence-limits",
    "offline-configuration-guide",
    "offline-configuration",
    "authored-plan-heading",
    "build-authored-evaluation",
    "schedule-tables",
    "plot-schedules",
    "physical-replay-heading",
    "physical-trace-table",
    "plot-power-trace",
    "plot-energy-soc",
    "settlement-heading",
    "settlement-tables",
    "plot-settlement",
    "invalid-headroom-heading",
    "invalid-headroom-diagnostics",
    "producer-neutral-heading",
    "producer-neutral-comparison",
    "golden-reference-heading",
    "load-golden-reference",
    "reference-inspection-tables",
    "plot-reference-evidence",
    "display-fingerprint",
    "optional-reference-heading",
    "optional-reference-replay",
    "plot-external-reference-parity",
    "optional-figure-export",
    "conclusions-and-limits",
)


def _notebook() -> dict[str, object]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source(*, cell_type: str | None = None) -> str:
    cells = _notebook()["cells"]
    assert isinstance(cells, list)
    return "\n".join(
        "".join(cell.get("source", ()))
        for cell in cells
        if cell_type is None or cell.get("cell_type") == cell_type
    )


def _cell_source(cell_id: str) -> str:
    cells = _notebook()["cells"]
    assert isinstance(cells, list)
    matches = [cell for cell in cells if cell.get("id") == cell_id]
    assert len(matches) == 1
    return "".join(matches[0].get("source", ()))


def test_notebook_is_valid_v4_source_only_python_with_stable_cell_ids() -> None:
    notebook = _notebook()
    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] >= 5
    cells = notebook["cells"]
    assert isinstance(cells, list)
    assert tuple(cell["id"] for cell in cells) == EXPECTED_CELL_IDS
    assert len(set(EXPECTED_CELL_IDS)) == len(EXPECTED_CELL_IDS)

    for cell in cells:
        assert set(cell) >= {"cell_type", "id", "metadata", "source"}
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs", []) == []
            ast.parse("".join(cell["source"]))


def test_notebook_covers_evaluator_physics_settlement_and_evidence_limits() -> None:
    markdown = _source(cell_type="markdown").lower()
    required = (
        "common fixed-plan evaluator",
        "charge-positive",
        "positive activation requests upward discharge",
        "requested power",
        "delivered power",
        "stored energy",
        "state of charge",
        "directional fcr energy",
        "throughput",
        "component reconciliation",
        "validation_failed",
        "producer-neutral",
        "golden reference fixture",
        "24 hourly energy decisions",
        "six four-hour fcr decisions",
        "source_precision_compatible",
        "unavailable",
        "bounded reference-result parity",
        "no complete ten-second julia trace parity",
    )
    assert [term for term in required if term not in markdown] == []

    code = _source(cell_type="code")
    required_code = (
        "build_manual_request",
        "evaluate_fixed_fcr_bid",
        "physical_trace_table",
        "physical_summary_table",
        "settlement_table",
        "diagnostic_table",
        "producer_comparison_table",
        "reference_provenance_table",
        "reference_mapping_table",
        "reference_field_table",
        "precision_bound_table",
        "notebook_display_fingerprint",
        "generated_figures",
    )
    assert [term for term in required_code if term not in code] == []


def test_notebook_uses_only_supported_source_boundaries() -> None:
    forbidden_roots = {
        "baselines",
        "gurobi",
        "gurobipy",
        "julia",
        "legacy",
        "pyomo",
        "solvers",
        "tests",
    }
    for cell in _notebook()["cells"]:
        if cell["cell_type"] != "code":
            continue
        tree = ast.parse("".join(cell["source"]))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {item.name.split(".", 1)[0] for item in node.names}
                assert roots.isdisjoint(forbidden_roots)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module.split(".", 1)[0] not in forbidden_roots
        assert "subprocess" not in "".join(cell["source"])


def test_external_replay_and_figure_export_are_explicit_and_disabled() -> None:
    config = _cell_source("offline-configuration")
    external = _cell_source("optional-reference-replay")
    parity_plot = _cell_source("plot-external-reference-parity")
    export = _cell_source("optional-figure-export")

    assert "RUN_EXTERNAL_REFERENCE = False" in config
    assert "EXPORT_FIGURES = False" in config
    assert (
        'Path("artifacts/reference/robust_storage_bidding/regulation_signal.csv")'
        in config
    )
    assert 'Path("tmp/fcr-bid-evaluation-notebook/figures")' in config
    assert "if RUN_EXTERNAL_REFERENCE:" in external
    assert "build_reference_request" in external
    assert "compare_reference_evaluation" in external
    assert "external_comparison.fields" in external
    assert 'external_comparison_payload["field_results"]' not in external
    assert 'parity_units = ("EUR", "kWh", "kW")' in parity_plot
    assert 'row["expected_interval"]' in parity_plot
    assert 'row["actual_interval"]' in parity_plot
    assert "[categorical_y, categorical_y]" in parity_plot
    assert 'external_reference_parity_plot_table["normalized_deviation"]' in parity_plot
    assert "deviation_axis.axvspan(-1.0, 1.0" in parity_plot
    assert 'generated_figures["external_reference_parity"]' in parity_plot
    assert "if RUN_EXTERNAL_REFERENCE:" in parity_plot
    assert "if EXPORT_FIGURES:" in export
    assert "mkdir" not in _source(cell_type="code").replace(export, "")


def test_notebook_setup_and_navigation_are_linked_from_review_docs() -> None:
    markdown = _source(cell_type="markdown").lower()
    assert "uv sync --group notebook" in markdown
    assert "uv run jupyter lab" in markdown
    assert "source notebook is committed with empty outputs" in markdown

    for path in (
        Path("examples/fcr_bid_evaluation/README.md"),
        Path("README.md"),
        Path("docs/architecture/README.md"),
        Path("specs/012-fcr-bid-evaluation-parity/quickstart.md"),
    ):
        content = path.read_text(encoding="utf-8")
        assert "fcr_bid_evaluation_walkthrough.ipynb" in content, path
