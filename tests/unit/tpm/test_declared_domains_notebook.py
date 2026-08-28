"""Source contracts for the thin declared-feature-domains walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/tpm_planning/declared_feature_domains_walkthrough.ipynb"
)


def _notebook() -> dict[str, object]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source() -> str:
    return "\n".join(
        "".join(cell.get("source", ())) for cell in _notebook()["cells"]
    )


def test_notebook_demonstrates_each_declared_domain_layer_and_reuses_fixture() -> None:
    source = _source()

    for required in (
        "mathematical decision domain",
        "training support",
        "normalization",
        "compiler approximation domain",
        "tpm_artifact_domains_v3.json",
        "normalize_training_data",
        "query_tpm_artifact",
        "TPMApproximationDomain",
        "compile_spflow_model_to_mio",
        "evaluate_compiled_spflow_probability",
        "build_compiled_spflow_decision_link_model",
        'pyo.SolverFactory("highs")',
    ):
        assert required in source

    assert "fit_tpm_artifact" not in source
    assert "run_declared_domains_pipeline.py" in source


def test_notebook_covers_accepted_and_rejected_relevant_cases() -> None:
    source = _source()

    for required in (
        "observed [60, 140]",
        "observed [80, 120]",
        "unbounded demand probe",
        "declared but unobserved category",
        "lower endpoint outside training support",
        "upper endpoint outside training support",
        "decision_domain_violation",
        "compiled_rejections",
        "outside compiler validity",
        "outside termination",
        "Knapsack",
        "Newsvendor",
    ):
        assert required in source


def test_notebook_code_compiles_and_is_committed_without_execution_state() -> None:
    notebook = _notebook()

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        ast.parse("".join(cell["source"]))
        assert cell.get("execution_count") is None
        assert cell.get("outputs", []) == []


def test_notebook_is_documented_as_offline_and_thin() -> None:
    source = _source().lower()
    readme = Path("examples/tpm_planning/README.md").read_text(encoding="utf-8")
    migration = Path("docs/migration/declared-feature-domains.md").read_text(
        encoding="utf-8"
    )
    quickstart = Path(
        "specs/014-declared-feature-domains/quickstart.md"
    ).read_text(encoding="utf-8")

    for required in (
        "offline and cpu-only",
        "reloads the reviewed, digest-checked v3 fixture instead of refitting",
        "not as a benchmark chance-constraint result",
        "capacity is a coupled model constraint, not a coordinate bound",
    ):
        assert required in source
    assert "declared_feature_domains_walkthrough.ipynb" in readme
    assert "declared_feature_domains_walkthrough.ipynb" in migration
    assert "optional post-feature documentation extension" in readme.lower()
    assert "optional post-feature documentation extension" in migration.lower()
    assert "## Optional post-feature notebook validation" in quickstart
    assert "--ignore=tests/unit/tpm/test_declared_domains_notebook.py" in quickstart
    assert (
        "--ignore=tests/integration/tpm/test_declared_domains_notebook_execution.py"
        in quickstart
    )
