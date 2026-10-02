"""Source contracts for the conditional-MIO composition walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/tpm_planning/conditional_mio_embedding_walkthrough.ipynb"
)
OWNERSHIP_DIAGRAM_PATH = Path(
    "examples/tpm_planning/conditional_mio_embedding_ownership.svg"
)


def _notebook() -> dict[str, object]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source() -> str:
    return "\n".join(
        "".join(cell.get("source", ())) for cell in _notebook()["cells"]
    )


def _code_source() -> str:
    return "\n".join(
        "".join(cell.get("source", ()))
        for cell in _notebook()["cells"]
        if cell["cell_type"] == "code"
    )


def test_notebook_explains_conditional_mathematics_and_ownership() -> None:
    source = _source()

    for required in (
        "Composable Conditional Risk in Caller-Owned Models",
        "continuous densities, not point probabilities",
        "explicit learned denominator",
        "$z_{\\mathrm{num}}(x)",
        "$z_{\\mathrm{den}}(x)",
        "$z_{\\mathrm{num}}(x)-z_{\\mathrm{den}}(x)$",
        "caller owns",
        "OEL owns",
        "objective",
        "deterministic constraints",
        "$\\alpha$",
        "chance constraint",
        "Embedding/solver parity",
        "Native/compiler fidelity",
        "What embedding means here",
        "conditional_mio_embedding_ownership.svg",
    ):
        assert required in source


def test_notebook_uses_public_fixture_backed_composition_for_all_mapping_forms() -> None:
    source = _source()
    code = _code_source()

    for required in (
        "tpm_artifact_conditional_mio_v3.json",
        "conditional_pair_max_v2.json",
        "conditional_pair_pwl_v2.json",
        "conditional_mio_evidence_v1.json",
        "TPMContinuousDecisionMapping",
        "TPMBinaryDecisionMapping",
        "TPMCategoricalDecisionMapping",
        "attach_conditional_mio_pair",
        "evaluate_conditional_mio_pair",
        "inspect_conditional_mio_attachment",
        "build_embedding_parity_evidence",
        "_attach_with_compact_piecewise_notices",
        "NEAR_EQUAL_SLOPE_NOTICE",
        "redirect_stdout",
        "near_equal_pwl_slope_notices",
        'pyo.SolverFactory("highs")',
        '"max"',
        '"piecewise"',
        "policy_model.caller_objective",
        "policy_model.caller_deterministic_constraint",
        "policy_model.caller_chance_constraint",
        "policy_unsolved",
        "conditional_demo_complete",
        "evidence_figure",
        "embedding_parity_absolute_tolerance",
        'set_yscale("log")',
    ):
        assert required in source

    tree = ast.parse(code)
    oel_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.split(".")[0] in {"open_energy_lab", "tpm"}
    ]
    assert oel_imports
    assert {node.module for node in oel_imports} == {"tpm"}


def test_notebook_remains_thin_without_fitting_compilation_or_enumeration() -> None:
    code = _code_source()
    lowered = code.casefold()

    for prohibited in (
        "fit_tpm",
        "fit_tpm_artifact",
        "compile_conditional_mio_pair",
        "compile_spflow_model_to_mio",
        "condition_compiled_spflow_mio",
        "publish_conditional",
        "stage_evidence",
        "stage_pairs",
        "regenerate",
        "itertools.product",
        "cartesian",
        "np.linspace",
        "numpy.linspace",
        "solver.solve(policy_model",
        "plt.savefig",
        "warning_tol",
    ):
        assert prohibited not in lowered


def test_notebook_code_compiles_and_source_is_output_free() -> None:
    notebook = _notebook()

    assert notebook["nbformat"] == 4
    for cell in notebook["cells"]:
        assert cell.get("id")
        if cell["cell_type"] != "code":
            continue
        ast.parse("".join(cell["source"]))
        assert cell.get("execution_count") is None
        assert cell.get("outputs", []) == []


def test_notebook_ownership_diagram_is_a_local_svg_asset() -> None:
    assert OWNERSHIP_DIAGRAM_PATH.is_file()
    source = OWNERSHIP_DIAGRAM_PATH.read_text(encoding="utf-8")
    assert source.startswith("<svg")
    assert "Caller owns" in source
    assert "OEL owns one namespaced attachment block" in source
