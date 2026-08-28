"""Uninterrupted current-SPFlow evidence for conditional pair compilation."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.conditional import (
    TPMBinaryDecisionMapping,
    TPMCategoricalDecisionMapping,
    TPMConditionalCompilationRequest,
    TPMConditionalEncodingPolicy,
    TPMConditionalNumericalPolicy,
    TPMContinuousDecisionMapping,
    load_conditional_pair,
    publish_conditional_pair,
)
from open_energy_lab.tpm.conditional_mio import (
    attach_conditional_mio_pair,
    compile_conditional_mio_pair,
    evaluate_conditional_mio_pair,
)
from open_energy_lab.tpm.domains import TPMFeatureDomain
from open_energy_lab.tpm.fit import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    fit_tpm_artifact_from_rows,
)
from open_energy_lab.tpm.piecewise import (
    PiecewiseBreakpointPolicy,
    build_logsumexp_piecewise_spec,
)
from open_energy_lab.tpm.query import evaluate_native_conditional_pair
from tests.integration.tpm.conditional_mio_test_support import (
    CONDITIONAL_MIO_SOURCE_PATH,
    file_sha256,
    load_conditional_mio_source,
    physical_training_rows,
)


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a mapping")
    return dict(value)


def _feature_domains(source: dict[str, object]) -> dict[str, TPMFeatureDomain]:
    declarations = _mapping(
        source["feature_declarations"], field_name="feature_declarations"
    )
    return {
        name: TPMFeatureDomain.from_dict(
            {
                "feature_name": name,
                **_mapping(declaration, field_name=name),
            }
        )
        for raw_name, declaration in declarations.items()
        for name in (str(raw_name),)
    }


def _fit_real_artifact(output_path: Path):
    source = load_conditional_mio_source()
    fit_case = _mapping(source["fit_case"], field_name="fit_case")
    return fit_tpm_artifact_from_rows(
        physical_training_rows(source),
        build_request=TPMArtifactBuildRequest(
            artifact_id=str(fit_case["artifact_id"]),
            dataset_reference=str(fit_case["dataset_reference"]),
            decision_features=tuple(str(name) for name in fit_case["decision_features"]),
            target_name=str(fit_case["target_name"]),
            event_target_name=str(fit_case["event_target_name"]),
            feature_domains=_feature_domains(source),
            provenance={
                "source_fixture": str(CONDITIONAL_MIO_SOURCE_PATH),
                "source_fixture_sha256": file_sha256(CONDITIONAL_MIO_SOURCE_PATH),
                "retry_policy": "none",
            },
        ),
        output_path=output_path,
        fit_config=TPMFitConfig(
            training_random_seed=int(fit_case["training_random_seed"]),
            spn_payload_format="spflow-model-sidecar",
            learn_mspn_kwargs=_mapping(
                fit_case["learn_spn_options"], field_name="learn_spn_options"
            ),
            notes=("conditional-mio-embedding-v1", "offline-cpu-current-spflow"),
        ),
    )


def _encoding(source: dict[str, object], *, mode: str) -> TPMConditionalEncodingPolicy:
    compilation = _mapping(
        source["conditional_compilation"], field_name="conditional_compilation"
    )
    leaf = _mapping(compilation["leaf_policy"], field_name="leaf_policy")
    policies = _mapping(compilation["sum_policies"], field_name="sum_policies")
    selected = _mapping(policies[mode], field_name=f"sum_policies.{mode}")
    sum_configuration = {
        key: value
        for key, value in selected.items()
        if key not in {"mode", "approximation_label", "certification_label"}
    }
    if mode == "pwl":
        breakpoint_policy = PiecewiseBreakpointPolicy.from_dict(
            _mapping(selected["breakpoint_policy"], field_name="breakpoint_policy")
        )
        curves = build_logsumexp_piecewise_spec(
            max_terms=len(physical_training_rows(source)),
            breakpoint_policy=breakpoint_policy,
        )
        exp_floor = float(selected["exp_domain_floor"])
        exp_x = tuple(float(value) for value in curves["exp_x_points"])
        exp_y = tuple(float(value) for value in curves["exp_y_points"])
        sum_configuration.update(curves)
        if exp_floor < exp_x[0]:
            sum_configuration["exp_x_points"] = (exp_floor, *exp_x)
            sum_configuration["exp_y_points"] = (0.0, *exp_y)
        sum_configuration.pop("breakpoint_policy", None)
        normalized_mode = "piecewise"
    else:
        normalized_mode = "max"
    return TPMConditionalEncodingPolicy(
        mode=normalized_mode,
        approximation_label=str(selected["approximation_label"]),
        certification_label=str(selected["certification_label"]),
        leaf_configuration=leaf,
        sum_configuration=sum_configuration,
    )


def _request(
    artifact_path: Path,
    source: dict[str, object],
    *,
    mode: str,
) -> TPMConditionalCompilationRequest:
    compilation = _mapping(
        source["conditional_compilation"], field_name="conditional_compilation"
    )
    return TPMConditionalCompilationRequest(
        source_artifact=str(artifact_path),
        event_target=str(compilation["event_target"]),
        event_value=compilation["event_value"],
        retained_decisions=tuple(
            str(name) for name in compilation["retained_decisions"]
        ),
        approximation_domains=tuple(
            _mapping(value, field_name="approximation_domain")
            for value in compilation["approximation_domains"]
        ),
        encoding=_encoding(source, mode=mode),
        numerical_policy=TPMConditionalNumericalPolicy(
            tolerances=_mapping(
                compilation["numerical_policy"], field_name="numerical_policy"
            )
        ),
    )


@pytest.fixture(scope="module")
def real_conditional_campaign(tmp_path_factory):
    output_directory = tmp_path_factory.mktemp("conditional-mio-current-spflow")
    artifact_path = output_directory / "artifact.json"
    fitted = _fit_real_artifact(artifact_path)
    artifact = load_tpm_artifact(fitted.source_path)
    source = load_conditional_mio_source()
    pairs = {}
    for mode in ("max", "pwl"):
        pair = compile_conditional_mio_pair(
            _request(artifact_path, source, mode=mode)
        )
        pair_path = output_directory / f"pair-{mode}.json"
        publication = publish_conditional_pair(pair, pair_path)
        assert publication.created and not publication.reused
        pairs[mode] = load_conditional_pair(pair_path)
    return artifact, source, pairs


def test_real_current_spflow_pair_has_explicit_learned_denominator_and_sum_nodes(
    real_conditional_campaign,
) -> None:
    artifact, _, pairs = real_conditional_campaign

    assert artifact.schema_version == "v3"
    assert artifact.spn_payload_format == "spflow-model-sidecar"
    for pair in pairs.values():
        assert pair.source.artifact_id == artifact.artifact_id
        assert pair.source.model_digest == pair.numerator.metadata["source_model"][
            "model_digest"
        ]
        assert pair.source.model_digest == pair.denominator.metadata["source_model"][
            "model_digest"
        ]
        assert pair.denominator.metadata["event_treatment"] == "marginalized"
        assert any(node.node_type == "sum" for node in pair.numerator.nodes)
        assert any(node.node_type == "sum" for node in pair.denominator.nodes)


def test_real_current_spflow_max_and_pwl_pairs_evaluate_selected_semantics(
    real_conditional_campaign,
) -> None:
    artifact, source, pairs = real_conditional_campaign
    cases = source["representative_assignments"]
    assert isinstance(cases, list)

    for pair in pairs.values():
        for raw_case in cases:
            case = _mapping(raw_case, field_name="representative_assignment")
            assignments = _mapping(case["values"], field_name="values")
            direct = evaluate_conditional_mio_pair(
                pair, declared_domain_assignments=assignments
            )
            native = evaluate_native_conditional_pair(
                artifact,
                pair,
                declared_domain_assignments=assignments,
            )
            assert all(
                math.isfinite(value)
                for value in (
                    direct.numerator_log,
                    direct.denominator_log,
                    direct.conditional_log_risk,
                    native.numerator_log,
                    native.denominator_log,
                    native.conditional_log_risk,
                )
            )
            assert direct.conditional_probability >= 0.0
            assert native.conditional_probability >= 0.0


def test_real_native_denominator_retains_nonuniform_learned_decision_density(
    real_conditional_campaign,
) -> None:
    artifact, _, pairs = real_conditional_campaign
    pair = pairs["max"]

    lower = evaluate_native_conditional_pair(
        artifact,
        pair,
        declared_domain_assignments={
            "x": 50.0,
            "activation": "off",
            "service_tier": "economy",
        },
    )
    upper = evaluate_native_conditional_pair(
        artifact,
        pair,
        declared_domain_assignments={
            "x": 150.0,
            "activation": "off",
            "service_tier": "economy",
        },
    )

    assert lower.denominator_log != pytest.approx(upper.denominator_log)


def test_real_mixed_pair_attaches_representative_binary_and_categories_without_grid(
    real_conditional_campaign,
) -> None:
    import pyomo.environ as pyo

    _, source, pairs = real_conditional_campaign
    pair = pairs["max"]
    cases = source["representative_assignments"]
    assert isinstance(cases, list)
    seen_binary = set()
    seen_categories = set()

    for raw_case in cases:
        case = _mapping(raw_case, field_name="representative_assignment")
        values = _mapping(case["values"], field_name="values")
        model = pyo.ConcreteModel()
        model.x = pyo.Var(bounds=(40.0, 160.0))
        model.activation = pyo.Var(domain=pyo.Binary)
        model.category_index = pyo.Set(
            initialize=("economy", "standard", "priority")
        )
        model.service = pyo.Var(model.category_index, domain=pyo.Binary)
        attachment = attach_conditional_mio_pair(
            pair,
            model,
            mappings=(
                TPMContinuousDecisionMapping("x", model.x),
                TPMBinaryDecisionMapping("activation", model.activation),
                TPMCategoricalDecisionMapping(
                    "service_tier",
                    tuple(
                        (label, model.service[label])
                        for label in ("economy", "standard", "priority")
                    ),
                ),
            ),
            namespace="mixed_conditional_risk",
        )
        model.x.set_value(float(values["x"]))
        activation_index = 1 if values["activation"] == "on" else 0
        model.activation.set_value(activation_index)
        for label in ("economy", "standard", "priority"):
            model.service[label].set_value(int(label == values["service_tier"]))
        seen_binary.add(values["activation"])
        seen_categories.add(values["service_tier"])

        assert attachment.numerator_root.parent_block() is attachment.block.numerator
        assert attachment.denominator_root.parent_block() is attachment.block.denominator
        assert pyo.value(
            attachment.decision_links["service_tier"].exactly_one.body
        ) == pytest.approx(1.0)
        serialized_names = " ".join(
            component.name
            for component in attachment.block.component_objects(descend_into=True)
        ).casefold()
        assert "cartesian" not in serialized_names
        assert "combination" not in serialized_names
        assert "lookup" not in serialized_names

    assert seen_binary == {"off", "on"}
    assert seen_categories == {"economy", "standard", "priority"}
