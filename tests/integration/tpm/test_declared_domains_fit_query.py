"""Real current-SPFlow evidence for declared-domain fitting and native queries."""

from __future__ import annotations

from pathlib import Path

import pytest

from tpm.artifact import load_tpm_artifact
from tpm.domains import TPMFeatureDomain
from tpm.fit import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    fit_tpm_artifact_from_rows,
)
from tpm.query import TPMQueryRequest, query_tpm_artifact
from tests.integration.tpm.declared_domains_test_support import (
    load_declared_domains_fixture,
    physical_training_rows,
)


def _feature_domains(payload: dict[str, object]) -> dict[str, TPMFeatureDomain]:
    declarations = payload["feature_declarations"]
    assert isinstance(declarations, dict)
    return {
        feature_name: TPMFeatureDomain.from_dict(
            {"feature_name": feature_name, **declaration}
        )
        for feature_name, declaration in declarations.items()
    }


def _fit_real_declared_artifact(
    output_path: Path,
    *,
    rows: tuple[dict[str, object], ...],
    artifact_id: str,
):
    payload = load_declared_domains_fixture()
    fit_case = payload["fit_case"]
    assert isinstance(fit_case, dict)
    return fit_tpm_artifact_from_rows(
        rows,
        build_request=TPMArtifactBuildRequest(
            artifact_id=artifact_id,
            dataset_reference=str(fit_case["dataset_reference"]),
            decision_features=tuple(fit_case["decision_features"]),
            target_name=str(fit_case["target_name"]),
            event_target_name=str(fit_case["event_target_name"]),
            target_threshold=float(fit_case["target_threshold"]),
            feature_domains=_feature_domains(payload),
            provenance={
                "declared_domain_fixture": (
                    "tests/fixtures/tpm/declared_feature_domains_v1.json"
                ),
            },
        ),
        output_path=output_path,
        fit_config=TPMFitConfig(
            training_random_seed=int(fit_case["training_random_seed"]),
        ),
    )


@pytest.fixture(scope="module")
def fitted_declared_artifacts(tmp_path_factory):
    payload = load_declared_domains_fixture()
    first_rows = physical_training_rows(payload)
    second_rows = tuple(
        {
            **row,
            "x": 80.0 + (float(row["x"]) - 60.0) / 2.0,
        }
        for row in first_rows
    )
    output_directory = tmp_path_factory.mktemp("declared-domains-fit-query")
    first = _fit_real_declared_artifact(
        output_directory / "first.json",
        rows=first_rows,
        artifact_id="declared-domains-first",
    )
    second = _fit_real_declared_artifact(
        output_directory / "second.json",
        rows=second_rows,
        artifact_id="declared-domains-second",
    )
    return (
        load_tpm_artifact(first.source_path),
        load_tpm_artifact(second.source_path),
    )


def test_real_declared_fits_keep_coordinates_stable_across_training_supports(
    fitted_declared_artifacts,
) -> None:
    first, second = fitted_declared_artifacts
    first_specs = {spec.feature_name: spec for spec in first.feature_specs}
    second_specs = {spec.feature_name: spec for spec in second.feature_specs}

    assert first.schema_version == second.schema_version == "v3"
    assert first_specs["x"].normalize_value(100.0) == pytest.approx(0.5)
    assert second_specs["x"].normalize_value(100.0) == pytest.approx(0.5)
    assert (
        first_specs["x"].training_support.minimum,
        first_specs["x"].training_support.maximum,
    ) == (60.0, 140.0)
    assert (
        second_specs["x"].training_support.minimum,
        second_specs["x"].training_support.maximum,
    ) == (80.0, 120.0)
    assert first_specs["demand"].mathematical_domain.shape == "unbounded"
    assert first_specs["demand"].normalization.kind == "identity"
    assert first_specs["demand"].normalize_value(250.0) == pytest.approx(250.0)


@pytest.mark.parametrize("x_value", [40.0, 160.0])
def test_real_native_query_accepts_declared_decision_values_outside_training_support(
    fitted_declared_artifacts,
    x_value: float,
) -> None:
    first, _ = fitted_declared_artifacts

    result = query_tpm_artifact(
        first,
        TPMQueryRequest(
            decision_assignments={
                "x": x_value,
                "activation": "off",
                "service_tier": "economy",
            },
        ),
    )

    assert result["source"] == "spflow_backend"
    assert 0.0 <= result["conditional_probability"] <= 1.0


def test_real_native_query_leaves_unobserved_declared_category_probability_to_backend(
    fitted_declared_artifacts,
) -> None:
    first, _ = fitted_declared_artifacts
    service_tier = {
        spec.feature_name: spec for spec in first.feature_specs
    }["service_tier"]

    assert "priority" not in service_tier.training_support.observed_values
    assert "priority" in service_tier.mathematical_domain.values
    result = query_tpm_artifact(
        first,
        TPMQueryRequest(
            decision_assignments={
                "x": 100.0,
                "activation": "on",
                "service_tier": "priority",
            },
        ),
    )

    assert result["source"] == "spflow_backend"
    assert 0.0 <= result["conditional_probability"] <= 1.0
