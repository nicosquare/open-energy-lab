"""Source-only contract for the Feature 013 bidding walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/robust_fcr_bidding/robust_fcr_bidding_walkthrough.ipynb"
)
EXPECTED_CELL_IDS = (
    "title-objective",
    "setup-evidence-limits",
    "offline-configuration",
    "imports-and-style",
    "ownership-and-equations",
    "build-authored-problem",
    "time-and-uncertainty-tables",
    "uncertainty-derivation",
    "plot-input-prices",
    "formulation-heading",
    "solve-formulations",
    "solver-and-bound-table",
    "schedule-and-audit-tables",
    "plot-optimized-schedules",
    "robust-feasibility-equations",
    "robust-feasibility-tables",
    "plot-robust-feasibility",
    "objective-heading",
    "objective-tables",
    "plot-objective-evidence",
    "feature-012-replay-heading",
    "build-feature-012-request",
    "evaluate-feature-012",
    "replay-tables",
    "plot-physical-replay",
    "settlement-heading",
    "settlement-table",
    "plot-realized-settlement",
    "fingerprint-heading",
    "fingerprint-table",
    "reference-fixture-heading",
    "load-reference-fixture",
    "reference-tables",
    "plot-reference-precision",
    "optional-reference-heading",
    "optional-reference-benchmark",
    "optional-gurobi-heading",
    "optional-gurobi-exact",
    "optional-external-heading",
    "optional-external-replay",
    "optional-figure-export",
    "display-fingerprint",
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


def test_notebook_covers_bidding_audit_replay_and_evidence_limits() -> None:
    markdown = _source(cell_type="markdown").lower()
    required = (
        "24-hour problem",
        "charge-positive",
        "restriction",
        "relaxation",
        "upper-bound formulation",
        "activation",
        "evaluation-only information",
        "two distinct uncertainty sets",
        "2.75",
        "power headroom",
        "stored-energy protection",
        "ex-ante optimization objective",
        "post-acceptance handoff",
        "feature 012",
        "ex-post settlement",
        "source-precision envelope",
        "0.0005",
        "not proof of identical unrounded decisions",
        "complete julia trace parity",
    )
    assert [term for term in required if term not in markdown] == []

    code = _source(cell_type="code")
    required_code = (
        "build_walkthrough_problem",
        "solve_robust_fcr_bid",
        "compare_robust_fcr_bounds",
        "solver_table",
        "energy_schedule_table",
        "fcr_schedule_table",
        "audit_table",
        "headroom_table",
        "stored_energy_envelope_table",
        "objective_table",
        "build_walkthrough_evaluation_request",
        "evaluate_fixed_fcr_bid",
        "replay_trace_table",
        "settlement_table",
        "fingerprint_table",
        "reference_decision_table",
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
        cell_source = "".join(cell["source"])
        tree = ast.parse(cell_source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {item.name.split(".", 1)[0] for item in node.names}
                assert roots.isdisjoint(forbidden_roots)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module.split(".", 1)[0] not in forbidden_roots
        assert "subprocess" not in cell_source


def test_research_paths_and_figure_export_are_explicit_and_disabled() -> None:
    config = _cell_source("offline-configuration")
    benchmark = _cell_source("optional-reference-benchmark")
    exact = _cell_source("optional-gurobi-exact")
    external = _cell_source("optional-external-replay")
    export = _cell_source("optional-figure-export")

    assert "RUN_NATIVE_REFERENCE_BENCHMARK = False" in config
    assert "RUN_OPTIONAL_GUROBI_EXACT = False" in config
    assert "RUN_EXTERNAL_ACTIVATION_REPLAY = False" in config
    assert "EXPORT_FIGURES = False" in config
    assert "artifacts/reference/robust_storage_bidding/regulation_signal.csv" in config
    assert 'Path("tmp/robust-fcr-bidding-notebook/figures")' in config
    assert "if RUN_NATIVE_REFERENCE_BENCHMARK:" in benchmark
    assert "compare_robust_fcr_reference" in benchmark
    assert "if RUN_OPTIONAL_GUROBI_EXACT:" in exact
    assert 'solver_name="gurobi"' in exact
    assert "if RUN_EXTERNAL_ACTIVATION_REPLAY:" in external
    assert "if not EXTERNAL_ACTIVATION_PATH.is_file():" in external
    assert "if EXPORT_FIGURES:" in export
    assert "mkdir" not in _source(cell_type="code").replace(export, "")


def test_notebook_setup_and_navigation_are_linked_from_review_docs() -> None:
    markdown = _source(cell_type="markdown").lower()
    assert "uv sync --group notebook" in markdown
    assert "uv run jupyter lab" in markdown
    assert "source notebook is committed with empty outputs" in markdown

    for path in (
        Path("examples/robust_fcr_bidding/README.md"),
        Path("README.md"),
        Path("docs/architecture/README.md"),
        Path("specs/013-reference-robust-fcr-bidding/quickstart.md"),
    ):
        content = path.read_text(encoding="utf-8")
        assert "robust_fcr_bidding_walkthrough.ipynb" in content, path
