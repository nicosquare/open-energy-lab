"""Real SPFlow backend coverage when the legacy-compatible backend is installed."""

from __future__ import annotations

import pyomo.environ as pyo
import pytest

from open_energy_lab.tpm import (
    SPNSolveConfig,
    TPMArtifactBuildRequest,
    TPMQueryRequest,
    detect_spflow_backend_capabilities,
    fit_tpm_artifact_from_rows,
    query_tpm_artifact,
    solve_spn_chance_model_from_artifact,
)


def _legacy_backend_available() -> bool:
    return bool(detect_spflow_backend_capabilities()["supports_real_spn_training"])


def _gurobi_available() -> bool:
    try:
        solver = pyo.SolverFactory("gurobi")
    except Exception:
        return False
    available = getattr(solver, "available", None)
    if not callable(available):
        return True
    try:
        return bool(available(exception_flag=False))
    except TypeError:
        return bool(available())


@pytest.mark.xfail(
    strict=True,
    reason="v1 serialized spn_mip payload path is broken since 3a5307e; retired in consolidation step B3 (docs/dev/consolidation.md)",
)
@pytest.mark.skipif(not _legacy_backend_available(), reason="legacy-compatible SPFlow backend unavailable")
@pytest.mark.skipif(not _gurobi_available(), reason="gurobi solver unavailable")
def test_real_spflow_backend_supports_fit_query_and_direct_mio_solve(tmp_path) -> None:
    artifact_path = tmp_path / "real-spflow-artifact.json"

    fit_tpm_artifact_from_rows(
        (
            {
                "generator_size_kw": 2.0,
                "tariff_plan": "flat",
                "ambient_band": "low",
                "loss_ratio": 0.01,
            },
            {
                "generator_size_kw": 6.0,
                "tariff_plan": "peak",
                "ambient_band": "high",
                "loss_ratio": 0.12,
            },
            {
                "generator_size_kw": 4.0,
                "tariff_plan": "flat",
                "ambient_band": "high",
                "loss_ratio": 0.02,
            },
            {
                "generator_size_kw": 8.0,
                "tariff_plan": "peak",
                "ambient_band": "high",
                "loss_ratio": 0.20,
            },
        ),
        output_path=artifact_path,
        build_request=TPMArtifactBuildRequest(
            artifact_id="real-spflow-artifact",
            dataset_reference="real-spflow-dataset",
            decision_features=("generator_size_kw", "tariff_plan"),
            target_name="loss_ratio",
            event_target_name="loss_event",
            target_threshold=0.05,
        ),
    )

    query_result = query_tpm_artifact(
        artifact_path,
        TPMQueryRequest(
            decision_assignments={
                "generator_size_kw": 2.0,
                "tariff_plan": "flat",
            },
            marginalized_features=("ambient_band",),
            output_mode="conditional_probability",
            target_name="loss_ratio",
        ),
    )
    solve_summary = solve_spn_chance_model_from_artifact(
        artifact=artifact_path,
        problem_id="real-spflow-generic-problem",
        decision_features=("generator_size_kw", "tariff_plan"),
        cost_terms={
            "generator_size_kw": 100.0,
            "tariff_plan": 0.0,
        },
        chance_limit_epsilon=0.5,
        solve_config=SPNSolveConfig(solver_name="gurobi"),
    )

    assert query_result["source"] == "spflow_backend"
    assert 0.0 <= query_result["value"] <= 1.0
    assert solve_summary.status == "optimal"
    assert solve_summary.estimated_event_probability is not None
    assert solve_summary.estimated_event_probability <= 0.5 + 1e-9
    assert solve_summary.estimated_shortfall_risk == pytest.approx(
        solve_summary.estimated_event_probability
    )
