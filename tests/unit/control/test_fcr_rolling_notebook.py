"""Source-only contract for the Feature 015 rolling walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/fcr_rolling_backtest/fcr_rolling_backtest_walkthrough.ipynb"
)
EXPECTED_CELL_IDS = (
    "title-objective",
    "setup-evidence-limits",
    "offline-configuration",
    "imports-and-style",
    "ownership-equations",
    "build-profile-manifests",
    "profile-semantics-table",
    "authored-study-heading",
    "run-authored-study",
    "authored-result-tables",
    "plot-authored-schedules",
    "state-ledger-heading",
    "state-ledger-table",
    "plot-state-ledger",
    "state-carry-equation",
    "state-carry-policy-demo",
    "plot-state-carry",
    "overlap-heading",
    "load-reference-fixture",
    "reference-provenance-tables",
    "build-overlap-table",
    "plot-overlap-horizon",
    "causality-heading",
    "causality-check",
    "economics-heading",
    "economics-tables",
    "plot-economics",
    "lifecycle-heading",
    "lifecycle-table",
    "plot-lifecycle",
    "source-evidence-heading",
    "source-evidence-tables",
    "plot-source-evidence",
    "failure-resume-heading",
    "failure-resume-table",
    "optional-benchmark-heading",
    "optional-native-benchmark",
    "optional-external-heading",
    "optional-external-activation",
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


def test_notebook_covers_rolling_semantics_equations_and_evidence_limits() -> None:
    markdown = _source(cell_type="markdown").lower()
    required = (
        "feature 013 bid optimization",
        "feature 012 physical replay and settlement",
        "feature 015 rolling orchestration",
        "five pinned non-intraday profiles",
        "midnight state carry-over",
        "08:00 overlapping horizon",
        "causal information boundaries",
        "charge-positive",
        "source-compatible rounding",
        "native full precision",
        "half-open observed interval",
        "ex-ante optimization",
        "ex-post economics",
        "blocked_by_predecessor",
        "source-precision envelope",
        "time_limit",
        "not proven optimality",
        "no cell downloads data",
        "table a1 parity",
    )
    assert [term for term in required if term not in markdown] == []

    equations = (
        "\\gamma=n\\gamma'",
        "e^{\\mathrm{init}}_{d+1}",
        "q_3(e)",
        "x_{0:16}=x^{\\mathrm{accepted}}_{0:16}",
        "a|_{[t_0,t_c)}=a'|_{[t_0,t_c)}",
        "z^{\\mathrm{bid}}_d",
        "\\pi^{\\mathrm{realized}}_d",
    )
    assert [equation for equation in equations if equation not in markdown] == []

    code = _source(cell_type="code")
    required_code = (
        "profile_table",
        "authored_daily_table",
        "state_link_table",
        "state_ledger_table",
        "carry_policy_table",
        "overlap_energy_table",
        "overlap_fcr_table",
        "causality_table",
        "economics_table",
        "lifecycle_table",
        "source_solve_table",
        "failure_resume_table",
        "failure_transition_table",
        "partial_result",
        "resumed_result",
        "notebook_display_fingerprint",
        "generated_figures",
    )
    assert [term for term in required_code if term not in code] == []


def test_notebook_uses_supported_offline_source_boundaries() -> None:
    forbidden_roots = {
        "baselines",
        "gurobi",
        "gurobipy",
        "julia",
        "legacy",
        "pyomo",
        "solvers",
        "subprocess",
        "tests",
    }
    for cell in _notebook()["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"])
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {item.name.split(".", 1)[0] for item in node.names}
                assert roots.isdisjoint(forbidden_roots)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module.split(".", 1)[0] not in forbidden_roots
        assert "requests." not in source
        assert "urllib." not in source
        assert "socket." not in source
        assert "os.getenv" not in source
        assert "os.environ" not in source


def test_optional_research_and_export_paths_are_explicit_and_disabled() -> None:
    config = _cell_source("offline-configuration")
    benchmark = _cell_source("optional-native-benchmark")
    external = _cell_source("optional-external-activation")
    export = _cell_source("optional-figure-export")

    assert "RUN_ALL_AUTHORED_PROFILES = False" in config
    assert "RUN_NATIVE_REFERENCE_BENCHMARK = False" in config
    assert "RUN_EXTERNAL_ACTIVATION_REPLAY = False" in config
    assert "EXPORT_FIGURES = False" in config
    assert (
        'Path("artifacts/reference/robust_storage_bidding/regulation_signal.csv")'
        in config
    )
    assert 'Path("tmp/fcr-rolling-backtest-notebook/figures")' in config
    assert "if RUN_NATIVE_REFERENCE_BENCHMARK:" in benchmark
    assert "run_bounded_reference_benchmark" in benchmark
    assert "if RUN_EXTERNAL_ACTIVATION_REPLAY:" in external
    assert "expected_digest" in external and "expected_bytes" in external
    assert "if EXPORT_FIGURES:" in export
    assert "mkdir" not in _source(cell_type="code").replace(export, "")


def test_figures_use_explicit_units_or_categorical_axes() -> None:
    code = _source(cell_type="code")
    expected_figures = {
        "authored_energy_fcr_schedules",
        "midnight_state_ledger",
        "state_carry_precision",
        "rolling_0800_overlap",
        "optimization_and_realized_economics",
        "rolling_0800_lifecycle",
        "source_termination_evidence",
    }
    for figure_name in expected_figures:
        assert f'generated_figures["{figure_name}"]' in code
    for label in (
        "Energy baseline (kW)",
        "Symmetric FCR capacity (kW)",
        "Stored energy (kWh)",
        "Value (EUR)",
        "Record lifecycle category",
        "categorical, not a numeric score",
    ):
        assert label in code
    assert "normalized_deviation" not in code


def test_notebook_setup_and_navigation_are_linked_from_review_docs() -> None:
    markdown = _source(cell_type="markdown").lower()
    assert "uv sync --group notebook" in markdown
    assert "uv run jupyter lab" in markdown
    assert "empty outputs" in markdown

    for path in (
        Path("examples/fcr_rolling_backtest/README.md"),
        Path("README.md"),
        Path("docs/architecture/README.md"),
        Path("specs/015-fcr-rolling-backtest-parity/quickstart.md"),
    ):
        content = path.read_text(encoding="utf-8")
        assert "fcr_rolling_backtest_walkthrough.ipynb" in content, path
