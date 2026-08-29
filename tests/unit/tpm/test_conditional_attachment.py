"""Contracts for attaching conditional circuits to caller-owned Pyomo models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import math

import pytest

import open_energy_lab.tpm.conditional_mio as conditional_mio_module
from open_energy_lab.tpm.artifact import load_tpm_artifact
from open_energy_lab.tpm.conditional import (
    TPMBinaryDecisionMapping,
    TPMCategoricalDecisionMapping,
    TPMConditionalPair,
    TPMContinuousDecisionMapping,
)
from open_energy_lab.tpm.conditional_mio import (
    attach_conditional_mio_pair,
    compile_conditional_mio_pair,
)
from open_energy_lab.tpm.mio import SPNSolverDependencyUnavailableError
from tests.unit.tpm.test_conditional_pair import _pair


def _mixed_pair(monkeypatch: pytest.MonkeyPatch):
    from tests.unit.tpm.test_conditional_mio import (
        TPM_FIXTURE_DIRECTORY,
        _compilation_request,
        _install_compiler_stubs,
    )

    artifact = load_tpm_artifact(
        TPM_FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
    )
    _install_compiler_stubs(monkeypatch, artifact)
    return compile_conditional_mio_pair(_compilation_request())


def _component_names(model) -> tuple[str, ...]:
    return tuple(model.component_map())


def _component_snapshot(model) -> tuple[tuple[str, int, str], ...]:
    return tuple(
        (name, id(component), component.ctype.__name__)
        for name, component in model.component_map().items()
    )


def test_scalar_continuous_attachment_reuses_caller_variable_and_returns_roots() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))

    attachment = attach_conditional_mio_pair(
        _pair(),
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="conditional_risk",
    )

    assert model.conditional_risk is attachment.block
    assert attachment.namespace == "conditional_risk"
    assert attachment.pair_id == _pair().pair_id
    assert attachment.numerator_root.parent_block() is attachment.block.numerator
    assert attachment.denominator_root.parent_block() is attachment.block.denominator
    assert attachment.conditional_log_risk.parent_block() is attachment.block
    assert attachment.decision_links["x"].physical_expression is model.x
    assert model.x.parent_block() is model
    assert not tuple(model.component_objects(pyo.Objective))
    assert not hasattr(attachment.block, "alpha")
    assert not hasattr(attachment.block, "chance_constraint")
    assert not hasattr(attachment.block, "conditional_probability")
    with pytest.raises(FrozenInstanceError):
        attachment.namespace = "changed"
    with pytest.raises(TypeError):
        attachment.decision_links["other"] = object()


def test_multivariable_affine_mapping_accepts_fixed_continuous_vars_and_parameters() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.base = pyo.Var(domain=pyo.Reals)
    model.reserve = pyo.Var(domain=pyo.NonNegativeReals)
    model.reserve.fix(5.0)
    model.scale = pyo.Param(initialize=2.0)
    expression = model.base + model.scale * model.reserve + 40.0

    attachment = attach_conditional_mio_pair(
        _pair(),
        model,
        mappings=(TPMContinuousDecisionMapping("x", expression),),
        namespace="affine_risk",
    )

    link = attachment.decision_links["x"]
    assert link.physical_expression is expression
    assert set(variable.name for variable in link.caller_variables) == {
        "base",
        "reserve",
    }
    assert model.reserve.fixed
    assert pyo.value(model.scale) == 2.0


def test_continuous_link_uses_persisted_normalization_and_closed_boundaries() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(domain=pyo.Reals)
    attachment = attach_conditional_mio_pair(
        _pair(),
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="bounded_risk",
    )
    link = attachment.decision_links["x"]

    for physical, coordinate in ((40.0, 0.0), (100.0, 0.5), (160.0, 1.0)):
        model.x.set_value(physical)
        link.model_coordinate.set_value(coordinate)
        assert pyo.value(link.coordinate_link.body) == pytest.approx(0.0)
        assert pyo.value(link.physical_lower.body) >= pyo.value(
            link.physical_lower.lower
        )
        assert pyo.value(link.physical_upper.body) <= pyo.value(
            link.physical_upper.upper
        )
    assert link.approximation_domain["physical_interval"] == (40.0, 160.0)
    assert link.normalization["kind"] == "min-max"


@pytest.mark.parametrize("mode", ["max", "piecewise"])
def test_attachment_encodes_the_pair_selected_sum_semantics(mode: str) -> None:
    import pyomo.environ as pyo

    from tests.unit.tpm.test_conditional_mio import (
        _pair_with_circuits,
        _sum_circuits,
    )

    numerator, denominator = _sum_circuits()
    pair = _pair_with_circuits(
        mode=mode, numerator=numerator, denominator=denominator
    )
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))

    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace=f"{mode}_risk",
    )

    if mode == "max":
        assert hasattr(attachment.block.numerator, "sum_max_output_6")
        assert not hasattr(attachment.block.numerator, "sum_log_piecewise_6")
    else:
        assert hasattr(attachment.block.numerator, "sum_log_piecewise_6")
        assert not hasattr(attachment.block.numerator, "sum_max_output_6")


def test_mapping_sequence_requires_exact_coverage_before_mutation() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var()
    before = _component_names(model)

    with pytest.raises(ValueError, match="missing"):
        attach_conditional_mio_pair(
            _pair(), model, mappings=(), namespace="missing_risk"
        )
    with pytest.raises(ValueError, match="duplicate"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(
                TPMContinuousDecisionMapping("x", model.x),
                TPMContinuousDecisionMapping("x", model.x),
            ),
            namespace="duplicate_risk",
        )
    with pytest.raises(ValueError, match="unknown|extra"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("other", model.x),),
            namespace="extra_risk",
        )

    assert _component_names(model) == before


def test_same_pair_attaches_under_two_isolated_namespaces() -> None:
    import pyomo.environ as pyo

    pair = _pair()
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    first = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="first_risk",
    )
    first_snapshot = _component_snapshot(model)
    second = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="second_risk",
    )

    assert first.block is model.first_risk
    assert second.block is model.second_risk
    assert first.block is not second.block
    assert first.decision_links["x"].physical_expression is model.x
    assert second.decision_links["x"].physical_expression is model.x
    assert _component_snapshot(model)[: len(first_snapshot)] == first_snapshot
    assert first.pair_id == second.pair_id == pair.pair_id


def test_duplicate_and_unrelated_namespace_collisions_preserve_existing_components() -> None:
    import pyomo.environ as pyo

    pair = _pair()
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    model.unrelated = pyo.Block(concrete=True)
    unrelated = model.unrelated
    before = _component_snapshot(model)

    with pytest.raises(ValueError, match="occupied"):
        attach_conditional_mio_pair(
            pair,
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="unrelated",
        )
    assert _component_snapshot(model) == before
    assert model.unrelated is unrelated

    first = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="conditional_risk",
    )
    after_first = _component_snapshot(model)
    with pytest.raises(ValueError, match="occupied"):
        attach_conditional_mio_pair(
            pair,
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="conditional_risk",
        )
    assert _component_snapshot(model) == after_first
    assert model.conditional_risk is first.block
    assert model.unrelated is unrelated


def test_invalid_pair_identity_and_domain_fail_before_model_mutation() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    before = _component_snapshot(model)

    with pytest.raises(TypeError, match="TPMConditionalPair"):
        attach_conditional_mio_pair(
            object(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="wrong_type",
        )

    bad_identity = _pair()
    object.__setattr__(bad_identity, "pair_id", "0" * 64)
    with pytest.raises(ValueError, match="pair_id|identity"):
        attach_conditional_mio_pair(
            bad_identity,
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="bad_identity",
        )

    bad_domain_payload = _pair().to_dict()
    bad_domain_payload["pair_id"] = ""
    bad_domain_payload["validity"][0]["approximation_domain"][
        "physical_interval"
    ] = [160.0, 40.0]
    bad_domain = TPMConditionalPair.from_dict(bad_domain_payload)
    with pytest.raises(ValueError, match="approximation|interval|pair_id"):
        attach_conditional_mio_pair(
            bad_domain,
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="bad_domain",
        )

    assert _component_snapshot(model) == before


def test_detached_block_construction_failure_leaves_caller_model_exactly_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0), initialize=100.0)
    model.caller_constraint = pyo.Constraint(expr=model.x >= 50.0)
    before = _component_snapshot(model)
    original_domain = model.x.domain
    original_fixed = model.x.fixed

    def fail_encoding(*_args, **_kwargs):
        raise RuntimeError("injected detached-build failure")

    monkeypatch.setattr(
        conditional_mio_module,
        "encode_conditioned_spflow_circuit",
        fail_encoding,
    )
    with pytest.raises(RuntimeError, match="detached-build"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="failed_risk",
        )

    assert _component_snapshot(model) == before
    assert model.x.domain is original_domain
    assert model.x.fixed is original_fixed
    assert not hasattr(model, "failed_risk")


@pytest.mark.parametrize("failure_mode", ["before-registration", "after-registration"])
def test_final_component_add_failure_rolls_back_only_the_new_block(
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    model.caller_owned = pyo.Block(concrete=True)
    caller_owned = model.caller_owned
    before = _component_snapshot(model)
    model_type = type(model)
    real_add_component = model_type.add_component

    def failing_add_component(instance, name, component):
        if instance is model and name == "failed_risk":
            if failure_mode == "after-registration":
                real_add_component(instance, name, component)
            raise RuntimeError(f"injected {failure_mode} add failure")
        return real_add_component(instance, name, component)

    monkeypatch.setattr(model_type, "add_component", failing_add_component)
    with pytest.raises(RuntimeError, match=failure_mode):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="failed_risk",
        )

    assert _component_snapshot(model) == before
    assert model.caller_owned is caller_owned
    assert model.component("failed_risk") is None


def test_final_add_collision_does_not_delete_concurrently_added_caller_component(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    model_type = type(model)
    real_add_component = model_type.add_component
    concurrent = pyo.Block(concrete=True)

    def competing_add_component(instance, name, component):
        if instance is model and name == "contended_risk":
            real_add_component(instance, name, concurrent)
            raise RuntimeError("injected concurrent namespace collision")
        return real_add_component(instance, name, component)

    monkeypatch.setattr(model_type, "add_component", competing_add_component)
    with pytest.raises(RuntimeError, match="concurrent namespace"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="contended_risk",
        )

    assert model.contended_risk is concurrent
    assert tuple(model.component_map()).count("contended_risk") == 1


def test_constant_only_and_non_scalar_continuous_mappings_fail_before_mutation() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.coordinates = pyo.Set(initialize=(0, 1))
    model.x = pyo.Var(model.coordinates)
    before = _component_names(model)

    with pytest.raises(ValueError, match="at least one.*variable|constant"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", 100.0),),
            namespace="constant_risk",
        )
    with pytest.raises(TypeError, match="scalar"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="indexed_risk",
        )

    assert _component_names(model) == before


@pytest.mark.parametrize("variable_kind", ["integer", "binary"])
def test_integer_or_binary_variables_hidden_in_affine_expressions_are_rejected(
    variable_kind: str,
) -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    domain = pyo.Integers if variable_kind == "integer" else pyo.Binary
    model.discrete = pyo.Var(domain=domain)
    model.continuous = pyo.Var(domain=pyo.Reals)
    expression = model.continuous + model.discrete
    before = _component_names(model)

    with pytest.raises(ValueError, match="continuous|integer|binary"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", expression),),
            namespace=f"{variable_kind}_risk",
        )

    assert _component_names(model) == before


def test_fixed_variable_nonlinearity_is_detected_without_unfixing() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.fixed_x = pyo.Var(domain=pyo.Reals, initialize=2.0)
    model.y = pyo.Var(domain=pyo.Reals)
    model.fixed_x.fix()
    expression = model.fixed_x * model.y
    before = _component_names(model)

    with pytest.raises(ValueError, match="structurally affine|nonlinear"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", expression),),
            namespace="nonlinear_risk",
        )

    assert model.fixed_x.fixed
    assert _component_names(model) == before


def test_uninitialized_parameter_and_nonfinite_coefficient_are_rejected() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(domain=pyo.Reals)
    model.uninitialized = pyo.Param(mutable=True)
    before = _component_names(model)

    with pytest.raises(ValueError, match="parameter|finite|initialized"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(
                TPMContinuousDecisionMapping(
                    "x", model.uninitialized * model.x
                ),
            ),
            namespace="parameter_risk",
        )
    with pytest.raises(ValueError, match="finite"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(
                TPMContinuousDecisionMapping("x", math.inf * model.x),
            ),
            namespace="nonfinite_risk",
        )

    assert _component_names(model) == before


def test_foreign_model_variables_and_invalid_namespaces_are_rejected_atomically() -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(domain=pyo.Reals)
    other = pyo.ConcreteModel()
    other.y = pyo.Var(domain=pyo.Reals)
    before = _component_names(model)

    with pytest.raises(ValueError, match="caller.*model|foreign"):
        attach_conditional_mio_pair(
            _pair(),
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x + other.y),),
            namespace="foreign_risk",
        )
    for namespace in ("", "risk.block", "risk block", "1risk"):
        with pytest.raises(ValueError, match="namespace"):
            attach_conditional_mio_pair(
                _pair(),
                model,
                mappings=(TPMContinuousDecisionMapping("x", model.x),),
                namespace=namespace,
            )

    assert _component_names(model) == before


def test_attachment_reports_missing_pyomo_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_backend():
        raise SPNSolverDependencyUnavailableError(
            "locked Pyomo dependency is absent"
        )

    monkeypatch.setattr(
        conditional_mio_module, "require_pyomo_backend", missing_backend
    )

    with pytest.raises(
        SPNSolverDependencyUnavailableError, match="Pyomo dependency is absent"
    ):
        attach_conditional_mio_pair(
            _pair(),
            object(),
            mappings=(TPMContinuousDecisionMapping("x", object()),),
            namespace="risk",
        )


def test_mixed_binary_and_ordered_categorical_mappings_remain_caller_owned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyomo.environ as pyo

    pair = _mixed_pair(monkeypatch)
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    model.activation = pyo.Var(domain=pyo.Binary)
    model.categories = pyo.Set(initialize=("economy", "standard", "priority"))
    model.service = pyo.Var(model.categories, domain=pyo.Binary)
    model.caller_coupling = pyo.Constraint(
        expr=model.activation + model.service["priority"] <= 1
    )

    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(
            TPMContinuousDecisionMapping("x", model.x),
            TPMBinaryDecisionMapping("activation", model.activation),
            TPMCategoricalDecisionMapping(
                "service_tier",
                (
                    ("economy", model.service["economy"]),
                    ("standard", model.service["standard"]),
                    ("priority", model.service["priority"]),
                ),
            ),
        ),
        namespace="mixed_risk",
    )

    binary_link = attachment.decision_links["activation"]
    category_link = attachment.decision_links["service_tier"]
    assert binary_link.caller_variable is model.activation
    assert binary_link.declared_ordering == ("off", "on")
    assert category_link.declared_ordering == (
        "economy",
        "standard",
        "priority",
    )
    assert tuple(value for _, value in category_link.ordered_indicators) == tuple(
        model.service[label]
        for label in ("economy", "standard", "priority")
    )
    assert category_link.exactly_one.parent_block() is attachment.block
    assert model.caller_coupling.parent_block() is model
    assert model.activation.parent_block() is model
    assert all(
        value.parent_component() is model.service for value in model.service.values()
    )
    names = tuple(
        component.name
        for component in attachment.block.component_objects(descend_into=True)
    )
    assert not any("combination" in name or "lookup" in name for name in names)


@pytest.mark.parametrize(
    ("category_entries", "match"),
    [
        (("economy", "standard"), "category|coverage|ordering"),
        (("standard", "economy", "priority"), "ordering"),
        (("economy", "standard", "priority", "extra"), "categor|coverage"),
    ],
)
def test_categorical_mapping_rejects_missing_reordered_or_extra_labels(
    monkeypatch: pytest.MonkeyPatch,
    category_entries: tuple[str, ...],
    match: str,
) -> None:
    import pyomo.environ as pyo

    pair = _mixed_pair(monkeypatch)
    model = pyo.ConcreteModel()
    model.x = pyo.Var()
    model.activation = pyo.Var(domain=pyo.Binary)
    model.indicator_index = pyo.Set(
        initialize=("economy", "standard", "priority", "extra")
    )
    model.indicator = pyo.Var(model.indicator_index, domain=pyo.Binary)
    before = _component_names(model)
    mapping = TPMCategoricalDecisionMapping(
        "service_tier",
        tuple((label, model.indicator[label]) for label in category_entries),
    )

    with pytest.raises(ValueError, match=match):
        attach_conditional_mio_pair(
            pair,
            model,
            mappings=(
                TPMContinuousDecisionMapping("x", model.x),
                TPMBinaryDecisionMapping("activation", model.activation),
                mapping,
            ),
            namespace="invalid_category_risk",
        )

    assert _component_names(model) == before


def test_discrete_mapping_rejects_duplicate_nonbinary_and_foreign_indicators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pyomo.environ as pyo

    pair = _mixed_pair(monkeypatch)
    model = pyo.ConcreteModel()
    model.x = pyo.Var()
    model.activation = pyo.Var(domain=pyo.Binary)
    model.first = pyo.Var(domain=pyo.Binary)
    model.second = pyo.Var(domain=pyo.Binary)
    model.continuous = pyo.Var(domain=pyo.UnitInterval)
    foreign = pyo.ConcreteModel()
    foreign.indicator = pyo.Var(domain=pyo.Binary)
    before = _component_names(model)

    invalid_categories = (
        (
            ("economy", model.first),
            ("standard", model.first),
            ("priority", model.second),
        ),
        (
            ("economy", model.first),
            ("standard", model.continuous),
            ("priority", model.second),
        ),
        (
            ("economy", model.first),
            ("standard", foreign.indicator),
            ("priority", model.second),
        ),
    )
    for index, entries in enumerate(invalid_categories):
        with pytest.raises((TypeError, ValueError), match="distinct|binary|foreign|model"):
            attach_conditional_mio_pair(
                pair,
                model,
                mappings=(
                    TPMContinuousDecisionMapping("x", model.x),
                    TPMBinaryDecisionMapping("activation", model.activation),
                    TPMCategoricalDecisionMapping("service_tier", entries),
                ),
                namespace=f"invalid_discrete_risk_{index}",
            )

    with pytest.raises(ValueError, match="binary"):
        attach_conditional_mio_pair(
            pair,
            model,
            mappings=(
                TPMContinuousDecisionMapping("x", model.x),
                TPMBinaryDecisionMapping("activation", model.continuous),
                TPMCategoricalDecisionMapping(
                    "service_tier",
                    (
                        ("economy", model.first),
                        ("standard", model.second),
                        ("priority", model.activation),
                    ),
                ),
            ),
            namespace="invalid_binary_risk",
        )

    assert _component_names(model) == before
