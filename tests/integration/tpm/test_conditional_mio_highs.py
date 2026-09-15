"""Consumer-owned Pyomo composition around an attached conditional pair."""

from __future__ import annotations

import math

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
    build_embedding_parity_evidence,
    compile_conditional_mio_pair,
    evaluate_conditional_mio_pair,
    initialize_conditional_mio_attachment,
    inspect_conditional_mio_attachment,
)
from open_energy_lab.tpm.query import evaluate_native_conditional_pair
from tests.integration.tpm.conditional_mio_test_support import (
    CONDITIONAL_MAX_PAIR_PATH,
    CONDITIONAL_MIO_ARTIFACT_PATH,
    CONDITIONAL_PWL_PAIR_PATH,
    load_conditional_mio_source,
)
from tests.unit.tpm.test_conditional_pair import _pair


def test_integer_gaussian_lookup_fixed_orders_and_complete_sum_witness(monkeypatch):
    import pyomo.environ as pyo
    from tests.unit.tpm.test_integer_lookup import compile_gaussian_lookup, lookup_caller, assign

    pair, _ = compile_gaussian_lookup(monkeypatch)
    for q in (40, 88, 112, 160):
        model, attachment = lookup_caller(pair)
        assign(model, q)
        model.q.fix()
        expected = initialize_conditional_mio_attachment(
            pair, attachment, declared_domain_assignments={'x': q})
        assert all(v.value is not None and math.isfinite(v.value)
                   for v in model.component_data_objects(pyo.Var))
        # Inspect the supplied complete witness before solving can repair it.
        for row in model.component_data_objects(pyo.Constraint, active=True):
            value = pyo.value(row.body)
            assert row.lower is None or value >= pyo.value(row.lower) - 1e-6
            assert row.upper is None or value <= pyo.value(row.upper) + 1e-6
        solver = pyo.SolverFactory('highs')
        solver.options['threads'] = 1
        result = solver.solve(model)
        assert result.solver.termination_condition == pyo.TerminationCondition.optimal
        assert pyo.value(attachment.numerator_root) == pytest.approx(expected.numerator_log, abs=1e-6)
        assert pyo.value(attachment.denominator_root) == pytest.approx(expected.denominator_log, abs=1e-6)
        assert pyo.value(attachment.conditional_log_risk) == pytest.approx(expected.conditional_log_risk, abs=1e-6)
        assert not tuple(model.component_objects(pyo.Objective))


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a mapping")
    return dict(value)


def _fixed_mixed_attachment(pair, assignments: dict[str, object], *, namespace: str):
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    model.activation = pyo.Var(domain=pyo.Binary)
    model.category = pyo.Set(
        initialize=("economy", "standard", "priority"), ordered=True
    )
    model.service_tier = pyo.Var(model.category, domain=pyo.Binary)
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(
            TPMContinuousDecisionMapping("x", model.x),
            TPMBinaryDecisionMapping("activation", model.activation),
            TPMCategoricalDecisionMapping(
                "service_tier",
                tuple(
                    (label, model.service_tier[label]) for label in model.category
                ),
            ),
        ),
        namespace=namespace,
    )
    model.x.fix(float(assignments["x"]))
    model.activation.fix(1 if assignments["activation"] == "on" else 0)
    for label in model.category:
        model.service_tier[label].fix(
            int(label == assignments["service_tier"])
        )
    return model, attachment


def _solve_and_inspect(model, attachment):
    import highspy
    import pyomo.environ as pyo

    solver = pyo.SolverFactory("highs")
    # HiGHS owns a process-global scheduler; use the repository's established
    # single-threaded CPU setting so later compatibility solves can request the
    # same setting in this pytest process.
    solver.options["threads"] = 1
    results = solver.solve(model)
    return inspect_conditional_mio_attachment(
        attachment,
        solver_metadata={
            "solver_name": "highs",
            "solver_version": highspy.Highs().version(),
            "status": str(results.solver.status),
            "termination_condition": str(results.solver.termination_condition),
        },
    )


def _max_compilation_request(artifact_path, source: dict[str, object]):
    compilation = _mapping(
        source["conditional_compilation"], field_name="conditional_compilation"
    )
    policies = _mapping(
        compilation["sum_policies"], field_name="sum_policies"
    )
    selected = _mapping(policies["max"], field_name="sum_policies.max")
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
        encoding=TPMConditionalEncodingPolicy(
            mode=str(selected["mode"]),
            approximation_label=str(selected["approximation_label"]),
            certification_label=str(selected["certification_label"]),
            leaf_configuration=_mapping(
                compilation["leaf_policy"], field_name="leaf_policy"
            ),
            sum_configuration={
                name: value
                for name, value in selected.items()
                if name
                not in {"mode", "approximation_label", "certification_label"}
            },
        ),
        numerical_policy=TPMConditionalNumericalPolicy(
            tolerances=_mapping(
                compilation["numerical_policy"], field_name="numerical_policy"
            )
        ),
    )


def test_consumer_owns_objective_deterministic_policy_and_chance_threshold() -> None:
    import pyomo.environ as pyo

    pair = _pair()
    model = pyo.ConcreteModel()
    model.quantity = pyo.Var(domain=pyo.NonNegativeReals, bounds=(40.0, 160.0))
    model.reserve = pyo.Var(domain=pyo.NonNegativeReals, initialize=0.0)
    model.reserve.fix(0.0)
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(
            TPMContinuousDecisionMapping(
                "x", model.quantity + model.reserve
            ),
        ),
        namespace="oel_conditional_risk",
    )

    model.alpha = pyo.Param(initialize=0.2)
    model.storage_limit = pyo.Constraint(expr=model.quantity <= 150.0)
    model.risk_limit = pyo.Constraint(
        expr=attachment.conditional_log_risk <= math.log(pyo.value(model.alpha))
    )
    model.cost = pyo.Objective(expr=3.0 * model.quantity + model.reserve)

    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    model.quantity.set_value(100.0)
    link = attachment.decision_links["x"]
    link.model_coordinate.set_value(0.5)
    attachment.numerator_root.set_value(direct.numerator_log)
    attachment.denominator_root.set_value(direct.denominator_log)

    assert math.isfinite(pyo.value(model.cost.expr))
    assert pyo.value(attachment.conditional_log_risk) == pytest.approx(
        direct.conditional_log_risk
    )
    assert math.isfinite(pyo.value(model.risk_limit.body))
    assert not model.quantity.fixed
    assert model.quantity.domain is pyo.NonNegativeReals
    assert model.storage_limit.parent_block() is model
    assert model.risk_limit.parent_block() is model
    assert model.cost.parent_block() is model
    assert not tuple(
        attachment.block.component_objects(pyo.Objective, descend_into=True)
    )
    assert not hasattr(attachment.block, "alpha")
    assert not hasattr(attachment.block, "risk_limit")
    assert not hasattr(attachment.block, "storage_limit")


@pytest.mark.parametrize(
    ("mode", "pair_path"),
    (("max", CONDITIONAL_MAX_PAIR_PATH), ("pwl", CONDITIONAL_PWL_PAIR_PATH)),
)
def test_objective_free_highs_matches_direct_pair_at_predeclared_cases(
    mode: str,
    pair_path,
) -> None:
    import pyomo.environ as pyo

    pair_before = pair_path.read_bytes()
    pair = load_conditional_pair(pair_path)
    source = load_conditional_mio_source()
    case_results = {}

    for raw_case in source["representative_assignments"]:
        case = _mapping(raw_case, field_name="representative_assignment")
        assignments = _mapping(case["values"], field_name="values")
        direct = evaluate_conditional_mio_pair(
            pair, declared_domain_assignments=assignments
        )
        model, attachment = _fixed_mixed_attachment(
            pair,
            assignments,
            namespace=f"{mode}_{case['case_name'].replace('-', '_')}",
        )
        diagnostics = _solve_and_inspect(model, attachment)
        case_results[str(case["case_name"])] = (direct, diagnostics)

        for name, subblock in (
            ("numerator", attachment.block.numerator),
            ("denominator", attachment.block.denominator),
        ):
            formulation = getattr(pair.attachment_formulation, name)
            for bound in formulation["node_output_bounds"]:
                value = pyo.value(subblock.node_out[int(bound["node_id"])])
                assert (
                    float(bound["lower"]) - 1e-12
                    <= value
                    <= float(bound["upper"]) + 1e-12
                )

        assert not tuple(
            attachment.block.component_objects(
                pyo.Objective,
                descend_into=True,
            )
        )

    evidence = build_embedding_parity_evidence(
        pair,
        case_results=case_results,
        provenance={"purpose": "required fixed-assignment integration parity"},
    )
    assert evidence.accepted is True
    assert len(evidence.cases) == 3
    assert all(case["accepted"] is True for case in evidence.cases)
    assert all(
        case["attached"]["maximum_constraint_residual"] <= 1e-6
        for case in evidence.cases
    )
    assert pair_path.read_bytes() == pair_before


def test_fixed_mixed_assignment_initializer_is_a_complete_constraint_witness() -> None:
    pair = load_conditional_pair(CONDITIONAL_PWL_PAIR_PATH)
    source = load_conditional_mio_source()
    raw_case = source["representative_assignments"][1]
    case = _mapping(raw_case, field_name="representative_assignment")
    assignments = _mapping(case["values"], field_name="values")
    model, attachment = _fixed_mixed_attachment(
        pair, assignments, namespace="initialized_mixed_assignment"
    )
    fixed_states = {
        variable.name: variable.fixed
        for variable in (
            model.x,
            model.activation,
            *tuple(model.service_tier.values()),
        )
    }

    direct = initialize_conditional_mio_attachment(
        pair,
        attachment,
        declared_domain_assignments=assignments,
    )
    diagnostics = inspect_conditional_mio_attachment(
        attachment,
        solver_metadata={
            "solver_name": "not-solved",
            "solver_version": "not-solved",
            "status": "initialized",
            "termination_condition": "not-solved",
        },
    )

    assert {
        variable.name: variable.fixed
        for variable in (
            model.x,
            model.activation,
            *tuple(model.service_tier.values()),
        )
    } == fixed_states
    assert diagnostics.numerator_log == pytest.approx(direct.numerator_log)
    assert diagnostics.denominator_log == pytest.approx(direct.denominator_log)
    assert diagnostics.conditional_log_risk == pytest.approx(
        direct.conditional_log_risk
    )
    assert diagnostics.maximum_constraint_residual <= 1e-12


def test_uninterrupted_real_fit_to_highs_path_uses_the_same_persisted_pair(
    tmp_path,
) -> None:
    from tests.integration.tpm.test_conditional_mio_current_spflow import (
        _fit_real_artifact,
    )

    source = load_conditional_mio_source()
    artifact_path = tmp_path / "artifact.json"
    fitted = _fit_real_artifact(artifact_path)
    artifact = load_tpm_artifact(fitted.source_path)
    compiled = compile_conditional_mio_pair(
        _max_compilation_request(artifact_path, source)
    )
    pair_path = tmp_path / "pair-max.json"
    publication = publish_conditional_pair(compiled, pair_path)
    assert publication.created and not publication.reused
    pair = load_conditional_pair(pair_path)
    pair_before = pair_path.read_bytes()
    raw_case = source["representative_assignments"][1]
    case = _mapping(raw_case, field_name="representative_assignment")
    assignments = _mapping(case["values"], field_name="values")

    native = evaluate_native_conditional_pair(
        artifact,
        pair,
        declared_domain_assignments=assignments,
    )
    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments=assignments
    )
    model, attachment = _fixed_mixed_attachment(
        pair, assignments, namespace="uninterrupted_real_backend"
    )
    diagnostics = _solve_and_inspect(model, attachment)
    parity = build_embedding_parity_evidence(
        pair,
        case_results={str(case["case_name"]): (direct, diagnostics)},
        provenance={"path": "fit-persist-reload-native-compile-direct-attach-highs"},
    )

    assert artifact.execution_mode == "production"
    assert pair.source.sidecar_sha256 == artifact.payload_hash
    assert native.backend_generation == "current-spflow"
    assert parity.accepted is True
    assert pair_path.read_bytes() == pair_before


def test_exported_native_mixture_compiles_and_attaches_to_integer_orders(tmp_path):
    """Real scalar export, persisted compiler input and objective-free HiGHS solve."""
    import json
    from dataclasses import replace

    import pyomo.environ as pyo
    from open_energy_lab.tpm.artifact import TPMArtifact, write_tpm_model_sidecar
    from open_energy_lab.tpm.native import TPMNativeMixtureConfig, _build_mixture, export_native_mixture_scalar
    from tests.unit.tpm.test_conditional_mio import _compilation_request, _encoding, TPM_FIXTURE_DIRECTORY

    template = load_tpm_artifact(TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json")
    names = ("x", "demand", "demand_above_100")
    schema = tuple(next(spec for spec in template.feature_schema if spec["feature_name"] == name)
                   for name in names)
    config = TPMNativeMixtureConfig(
        components=2, gaussian_indices=(0, 1), bernoulli_indices=(2,), target_index=2,
        conditioning_indices=(0,), gaussian_floors=(0.01, 0.01), coordinate_id="scalar-attachment-fixture",
    )
    native = _build_mixture(config, means=[[0.2, 80], [0.7, 110]], scales=[[0.3, 15], [0.4, 20]],
                            probabilities=[[0.2], [0.6]], weights=[0.4, 0.6], device="cpu")
    scalar = export_native_mixture_scalar(native)
    sidecar, digest = write_tpm_model_sidecar(tmp_path / "model.pkl", {
        "payload_kind": "current-spflow-model-sidecar", "backend_generation": "current-spflow",
        "artifact_schema_version": "v3",
        "backend_api_version": "1.1.0", "query_strategy": "spflow", "model": scalar,
        "column_order": list(names), "feature_schema": list(schema),
    })
    artifact = TPMArtifact(
        artifact_id="tiny-exported-native-mixture", schema_version="v3",
        dataset_reference="synthetic-library-fixture", feature_schema=schema,
        target_definition=dict(template.target_definition),
        fit_configuration={"backend_name": "spflow", "training_random_seed": 0,
                           "input_column_order": list(names), "input_row_count": 0},
        backend_generation="current-spflow", backend_api_version="1.1.0",
        spn_payload={"locator": sidecar.name, "serialization": "spflow-model-sidecar", "backend": "spflow"},
        spn_payload_format="spflow-model-sidecar", payload_hash=digest,
        query_configuration={"supported_output_modes": ["conditional_probability"],
                             "required_decision_features": ["x"]},
        approximation_metadata=dict(template.approximation_metadata),
    )
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact.to_dict()))
    encoding = _encoding("piecewise")
    encoding = replace(encoding, leaf_configuration={**dict(encoding.leaf_configuration),
                       "breakpoint_count": 5, "relative_breakpoints": [0, 0.25, 0.5, 0.75, 1]})
    request = replace(_compilation_request(retained_decisions=("x",), encoding=encoding),
                      source_artifact=str(path))
    pair = compile_conditional_mio_pair(request)
    assert pair.marginalized_features == ("demand",)
    cases = {}
    for quantity in (40, 100, 160):
        model = pyo.ConcreteModel()
        model.q = pyo.Var(domain=pyo.Integers, bounds=(40, 160))
        model.q.fix(quantity)
        attachment = attach_conditional_mio_pair(
            pair, model, mappings=(TPMContinuousDecisionMapping("x", model.q),), namespace="risk",
        )
        assert attachment.decision_links["x"].physical_expression is model.q
        assert model.q.is_integer()
        assert not tuple(model.component_objects(pyo.Objective))
        direct = evaluate_conditional_mio_pair(pair, declared_domain_assignments={"x": quantity})
        inspected = _solve_and_inspect(model, attachment)
        cases[str(quantity)] = (direct, inspected)
    evidence = build_embedding_parity_evidence(pair, case_results=cases,
                                             provenance={"purpose": "scalar export integer regression"})
    assert evidence.accepted
