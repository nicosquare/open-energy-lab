"""Regression contracts for conditional-pair-v2 semantics and formulation."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from open_energy_lab.tpm.conditional import (
    CONDITIONAL_PAIR_COMPILER_VERSION,
    CONDITIONAL_PAIR_RECORD_KIND,
    CONDITIONAL_PAIR_SCHEMA_VERSION,
    TPMConditionalCircuit,
    TPMConditionalCircuitNode,
    TPMContinuousDecisionMapping,
    load_conditional_pair,
    publish_conditional_pair,
    resolve_conditional_attachment_formulation,
)
from open_energy_lab.tpm.conditional_mio import (
    attach_conditional_mio_pair,
    evaluate_conditional_mio_pair,
    initialize_conditional_mio_attachment,
    inspect_conditional_mio_attachment,
)
from open_energy_lab.tpm.piecewise import (
    CONDITIONAL_GUARD_POLICY_NAME,
    CONDITIONAL_GUARD_TRANSITION_WIDTH,
    PiecewiseBreakpointPolicy,
    build_logsumexp_piecewise_spec,
    evaluate_guarded_exponential,
    piecewise_linear_interpolate,
    resolve_guarded_exponential_spec,
)
from tests.unit.tpm.test_conditional_mio import _pair_with_circuits
from tests.unit.tpm.test_conditional_pair import _encoding, _pair


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LEGACY_PAIR_PATHS = (
    REPOSITORY_ROOT / "tests" / "fixtures" / "tpm" / "conditional_pair_max_v1.json",
    REPOSITORY_ROOT / "tests" / "fixtures" / "tpm" / "conditional_pair_pwl_v1.json",
)


def test_prevalidated_guard_evaluator_is_bitwise_equal_at_knots_and_interiors():
    import random
    from open_energy_lab.tpm.piecewise import _guarded_exponential_evaluator
    configuration=_encoding('piecewise').sum_configuration
    fast=_guarded_exponential_evaluator(configuration)
    points=configuration['exp_x_points'];rng=random.Random(0)
    values=[rng.uniform(points[0],points[-1]) for _ in range(1000)]
    for x in points:
        values.extend(v for v in (x,math.nextafter(x,-math.inf),math.nextafter(x,math.inf)) if points[0]<=v<=points[-1])
    for value in values:
        assert fast(value)==evaluate_guarded_exponential(value,configuration=configuration)
    for value in (float('nan'),float('inf'),points[0]-1,1):
        with pytest.raises(ValueError):fast(value)


def test_sparse_dcc_preserves_every_active_linear_row_without_unused_columns():
    import pyomo.environ as pyo
    from pyomo.repn import generate_standard_repn
    from open_energy_lab.tpm.mio import _sparse_dcc_piecewise

    points=[i/16 for i in range(17)]
    values=[math.sin(4*x) for x in points]
    m=pyo.ConcreteModel();m.x=pyo.Var(bounds=(0,1));m.y=pyo.Var(bounds=(-1,1))
    m.dense=pyo.Piecewise(m.y,m.x,pw_pts=points,f_rule=values,pw_repn='DCC',pw_constr_type='EQ')
    m.sparse=_sparse_dcc_piecewise(pyo,m.y,m.x,x_points=points,y_points=values)
    assert len(m.dense.DCC_lambda)==16*17
    assert len(m.sparse.DCC_lambda)==2*16
    def rows(block):
        result={}
        for row in block.component_data_objects(pyo.Constraint,active=True):
            rep=generate_standard_repn(row.body)
            normalize=lambda name:name.replace(block.name+'.','PWL.')
            result[normalize(row.name)]=(rep.constant,
                {normalize(v.name):c for v,c in zip(rep.linear_vars,rep.linear_coefs)},
                None if row.lower is None else pyo.value(row.lower),
                None if row.upper is None else pyo.value(row.upper))
        return result
    assert rows(m.dense)==rows(m.sparse)


def test_declared_wider_zero_tail_preserves_native_unit_coordinate_and_solver_parity(tmp_path):
    from dataclasses import replace
    import pyomo.environ as pyo
    from tests.unit.tpm.test_conditional_mio import _constant_curve

    base=_pair(encoding=_encoding('piecewise'))
    old=base.encoding.sum_configuration
    guard=resolve_guarded_exponential_spec(base_x_points=old['base_exp_x_points'],
        base_y_points=old['base_exp_y_points'],domain_floor=-5000.)
    configuration=dict(old,**guard);configuration['sum_big_m']=5000.
    encoding=replace(base.encoding,sum_configuration=configuration)
    numerator=TPMConditionalCircuit(root_id=2,nodes=(
        TPMConditionalCircuitNode.from_dict(dict(id=0,type='leaf_piecewise',feature_name='x',
            breakpoints=[0.,1.],log_values=[-1.,-1.])),
        TPMConditionalCircuitNode.from_dict(dict(id=1,type='leaf_piecewise',feature_name='x',
            breakpoints=[0.,1.],log_values=[-1000.,-1000.])),
        TPMConditionalCircuitNode.from_dict(dict(id=2,type='sum',children=[0,1],weights=[.5,.5])),
    ),metadata={'event_treatment':'fixed'})
    pair=replace(base,numerator=numerator,denominator=_constant_curve(0.,treatment='marginalized'),
        encoding=encoding,attachment_formulation=None,pair_id='')
    for x in [-500.,-20.,math.log(.001),-3.,-.1,0.]:
        assert evaluate_guarded_exponential(x,configuration=configuration)==evaluate_guarded_exponential(x,configuration=old)
    assert evaluate_guarded_exponential(-1000.,configuration=configuration)==0.
    coordinate=pair.attachment_formulation.numerator['guarded_input_coordinate']
    assert coordinate['native_scale']==coordinate['native_offset']==5000.
    publish_conditional_pair(pair,tmp_path/'pair.json')
    restored=load_conditional_pair(tmp_path/'pair.json');assert restored.pair_id==pair.pair_id
    m=pyo.ConcreteModel();m.x=pyo.Var(bounds=(40.,160.));m.x.fix(100.)
    a=attach_conditional_mio_pair(restored,m,mappings=(TPMContinuousDecisionMapping('x',m.x),),namespace='risk')
    direct=initialize_conditional_mio_attachment(restored,a,declared_domain_assignments={'x':100.})
    assert direct.conditional_log_risk==pytest.approx(-1.+math.log(.5))
    for row in m.component_data_objects(pyo.Constraint,active=True):
        value=pyo.value(row.body)
        assert row.lower is None or value>=pyo.value(row.lower)-1e-6
        assert row.upper is None or value<=pyo.value(row.upper)+1e-6
    m.objective=pyo.Objective(expr=a.conditional_log_risk)
    solver=pyo.SolverFactory('appsi_highs');solver.options['threads']=1
    result=solver.solve(m)
    assert result.solver.termination_condition==pyo.TerminationCondition.optimal
    assert pyo.value(a.conditional_log_risk)==pytest.approx(direct.conditional_log_risk,abs=1e-6)


@pytest.mark.parametrize("resolution", (5, 9, 17))
def test_guarded_exponential_resolves_plateau_transition_and_base_curve(
    resolution: int,
) -> None:
    policy = PiecewiseBreakpointPolicy(piecewise_breakpoint_count=resolution)
    base = build_logsumexp_piecewise_spec(max_terms=2, breakpoint_policy=policy)
    configuration = resolve_guarded_exponential_spec(
        base_x_points=base["exp_x_points"],
        base_y_points=base["exp_y_points"],
    )
    cutoff = math.log(1e-3)
    transition_end = cutoff + CONDITIONAL_GUARD_TRANSITION_WIDTH
    base_at_end = piecewise_linear_interpolate(
        transition_end,
        x_points=base["exp_x_points"],
        y_points=base["exp_y_points"],
    )

    assert configuration["guard_policy"] == CONDITIONAL_GUARD_POLICY_NAME
    assert configuration["guard_cutoff_log"] == cutoff
    assert configuration["guard_transition_width_log"] == 1e-3
    assert evaluate_guarded_exponential(-500.0, configuration=configuration) == 0.0
    assert evaluate_guarded_exponential(
        cutoff - 1e-9, configuration=configuration
    ) == 0.0
    assert evaluate_guarded_exponential(cutoff, configuration=configuration) == 0.0
    assert evaluate_guarded_exponential(
        cutoff + 0.5e-3, configuration=configuration
    ) == pytest.approx(0.5 * base_at_end)
    assert evaluate_guarded_exponential(
        transition_end, configuration=configuration
    ) == pytest.approx(base_at_end)
    for x_value, y_value in zip(
        base["exp_x_points"], base["exp_y_points"], strict=True
    ):
        if x_value >= transition_end:
            assert evaluate_guarded_exponential(
                x_value, configuration=configuration
            ) == pytest.approx(y_value)
    resolved_x = tuple(configuration["exp_x_points"])
    resolved_y = tuple(configuration["exp_y_points"])
    assert all(right > left for left, right in zip(resolved_x, resolved_x[1:]))
    assert all(right >= left for left, right in zip(resolved_y, resolved_y[1:]))


def test_pair_v2_identity_serialization_and_formulation_round_trip(tmp_path) -> None:
    pair = _pair(encoding=_encoding("piecewise"))
    output = tmp_path / "pair-v2.json"

    published = publish_conditional_pair(pair, output)
    loaded = load_conditional_pair(output)

    assert published.created and not published.reused
    assert loaded == pair
    assert loaded.record_kind == CONDITIONAL_PAIR_RECORD_KIND == "conditional-pair-v2"
    assert loaded.schema_version == CONDITIONAL_PAIR_SCHEMA_VERSION == "v2"
    assert loaded.compiler_version == CONDITIONAL_PAIR_COMPILER_VERSION == "conditional-mio-v2"
    assert loaded.attachment_formulation.to_dict() == pair.attachment_formulation.to_dict()
    assert "attachment_formulation" in loaded.identity_payload()


@pytest.mark.parametrize("legacy_path", LEGACY_PAIR_PATHS)
def test_every_v1_pair_is_rejected_with_recompile_guidance_without_model_mutation(
    legacy_path: Path,
) -> None:
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    before = tuple(model.component_map())
    with pytest.raises(ValueError, match="recompile the fitted artifact"):
        pair = load_conditional_pair(legacy_path)
        attach_conditional_mio_pair(
            pair,
            model,
            mappings=(TPMContinuousDecisionMapping("x", model.x),),
            namespace="legacy_pair",
        )
    assert tuple(model.component_map()) == before


def _all_node_type_circuits() -> tuple[TPMConditionalCircuit, TPMConditionalCircuit]:
    numerator = TPMConditionalCircuit(
        root_id=6,
        nodes=(
            TPMConditionalCircuitNode.from_dict({"id": 0, "type": "log_one"}),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 1,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 0.25, 0.5, 0.75, 1.0],
                    "log_values": [-4.0, -3.0, -2.0, -3.0, -4.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 2,
                    "type": "leaf_binary",
                    "feature_name": "violation",
                    "densities": [0.5, 0.5],
                    "fixed_value": 1,
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 3,
                    "type": "leaf_categorical",
                    "feature_name": "service",
                    "densities": [0.2, 0.3, 0.5],
                    "fixed_value": 2,
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {"id": 4, "type": "product", "children": [0, 1, 2, 3]}
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 5,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 0.5, 1.0],
                    "log_values": [-5.0, -2.5, -5.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 6,
                    "type": "sum",
                    "children": [4, 5],
                    "weights": [0.6, 0.4],
                }
            ),
        ),
        metadata={"event_treatment": "fixed"},
    )
    denominator = TPMConditionalCircuit(
        root_id=0,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [-1.0, -1.0],
                }
            ),
        ),
        metadata={"event_treatment": "marginalized"},
    )
    return numerator, denominator


def test_interval_propagation_covers_every_node_and_persists_sum_records() -> None:
    numerator, denominator = _all_node_type_circuits()
    formulation = resolve_conditional_attachment_formulation(
        encoding=_encoding("piecewise"),
        numerator=numerator,
        denominator=denominator,
    )
    payload = formulation.numerator
    node_bounds = {
        int(record["node_id"]): record for record in payload["node_output_bounds"]
    }
    representations = {
        int(record["node_id"]): record["representation"]
        for record in payload["leaf_piecewise_representations"]
    }
    sum_record = payload["sum_nodes"][0]

    assert set(node_bounds) == set(range(7))
    assert node_bounds[0] == {"node_id": 0, "lower": 0.0, "upper": 0.0}
    assert node_bounds[1]["lower"] <= -4.0 <= node_bounds[1]["upper"]
    assert node_bounds[2]["lower"] <= math.log(0.5) <= node_bounds[2]["upper"]
    assert node_bounds[3]["lower"] <= math.log(0.5) <= node_bounds[3]["upper"]
    assert representations == {1: "DLOG", 5: "DCC"}
    assert len(sum_record["term_bounds"]) == 2
    assert len(sum_record["relative_bounds"]) == 2
    assert len(sum_record["branch_big_m"]) == 2
    assert all(record["upper"] == 0.0 for record in sum_record["relative_bounds"])
    assert all(
        0.0 <= record["lower"] <= record["upper"] <= 1.0
        for record in sum_record["solver_input_bounds"]
    )
    assert all(record["value"] <= 100.0 for record in sum_record["branch_big_m"])
    assert sum_record["exponential_representation"] == "DCC"
    assert sum_record["logarithm_representation"] == "DCC"
    assert sum_record["total_bounds"]["lower"] >= 1.0
    assert payload["root_bounds"] == sum_record["output_bounds"]
    assert payload["guarded_input_coordinate"]["policy"] == "unit-affine-log-v1"
    assert payload["guarded_input_coordinate"]["solver_bounds"] == {
        "lower": 0.0,
        "upper": 1.0,
    }


def test_branch_specific_outward_big_m_above_cap_fails_before_attachment() -> None:
    numerator = TPMConditionalCircuit(
        root_id=2,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [0.0, 0.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 1,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [-101.0, -101.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 2,
                    "type": "sum",
                    "children": [0, 1],
                    "weights": [0.5, 0.5],
                }
            ),
        ),
        metadata={"event_treatment": "fixed"},
    )
    denominator = _all_node_type_circuits()[1]
    with pytest.raises(ValueError, match="exceeding configured cap"):
        resolve_conditional_attachment_formulation(
            encoding=_encoding("max"),
            numerator=numerator,
            denominator=denominator,
        )


def test_attachment_applies_finite_bounds_and_declared_dlog_dcc() -> None:
    import pyomo.environ as pyo

    numerator, denominator = _all_node_type_circuits()
    pair = _pair_with_circuits(
        mode="piecewise", numerator=numerator, denominator=denominator
    )
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="bounded_v2",
    )

    for subblock in (attachment.block.numerator, attachment.block.denominator):
        for variable in subblock.component_data_objects(pyo.Var, descend_into=True):
            assert variable.lb is not None and math.isfinite(variable.lb)
            assert variable.ub is not None and math.isfinite(variable.ub)
    component_names = tuple(
        component.name
        for component in attachment.block.numerator.component_objects(
            descend_into=True
        )
    )
    assert any("piecewise_leaf_1.DLOG" in name for name in component_names)
    assert any("piecewise_leaf_5.DCC" in name for name in component_names)
    assert any("sum_exp_piecewise_6_0.DCC" in name for name in component_names)
    assert any("sum_log_piecewise_6.DCC" in name for name in component_names)


@pytest.mark.parametrize("mode", ("max", "piecewise"))
def test_fixed_assignment_initializer_populates_unchanged_attachment(mode: str) -> None:
    import pyomo.environ as pyo

    numerator, denominator = _all_node_type_circuits()
    pair = _pair_with_circuits(
        mode=mode, numerator=numerator, denominator=denominator
    )
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0), initialize=100.0)
    model.caller_constraint = pyo.Constraint(expr=model.x >= 50.0)
    model.caller_objective = pyo.Objective(expr=model.x)
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace=f"initialized_{mode}",
    )
    caller_state = (model.x.value, model.x.fixed, model.x.bounds)

    direct = initialize_conditional_mio_attachment(
        pair,
        attachment,
        declared_domain_assignments={"x": 100.0},
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

    assert (model.x.value, model.x.fixed, model.x.bounds) == caller_state
    assert model.caller_constraint.active
    assert model.caller_objective.active
    assert diagnostics.numerator_log == pytest.approx(direct.numerator_log)
    assert diagnostics.denominator_log == pytest.approx(direct.denominator_log)
    assert diagnostics.conditional_log_risk == pytest.approx(
        direct.conditional_log_risk
    )
    assert diagnostics.maximum_constraint_residual <= 1e-12
    assert all(
        variable.value is not None
        for variable in attachment.block.component_data_objects(
            pyo.Var, active=True, descend_into=True
        )
    )


def test_guarded_pwl_input_equality_measures_residual_in_native_log_units() -> None:
    import pyomo.environ as pyo

    numerator, denominator = _all_node_type_circuits()
    pair = _pair_with_circuits(mode="piecewise", numerator=numerator, denominator=denominator)
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0), initialize=100.0)
    attachment = attach_conditional_mio_pair(
        pair, model, mappings=(TPMContinuousDecisionMapping("x", model.x),), namespace="native_residual"
    )
    initialize_conditional_mio_attachment(pair, attachment, declared_domain_assignments={"x": 100.0})
    variable = attachment.block.numerator.sum_exp_input_var_6[0]
    variable.set_value(variable.value + 3e-9, skip_validation=True)
    diagnostics = inspect_conditional_mio_attachment(
        attachment, solver_metadata=dict(solver_name="not-solved", solver_version="fixture",
                                         status="perturbed", termination_condition="not-solved")
    )
    # The coordinate is (relative_log + 500) / 500. A normalized residual
    # below a solver's 1e-8 tolerance still exceeds 1e-6 in native log units.
    assert diagnostics.maximum_constraint_residual == pytest.approx(1.5e-6, abs=1e-12)


def test_fixed_assignment_initializer_rejects_an_attachment_from_another_pair() -> None:
    import pyomo.environ as pyo

    numerator, denominator = _all_node_type_circuits()
    attached_pair = _pair_with_circuits(
        mode="max", numerator=numerator, denominator=denominator
    )
    other_pair = _pair_with_circuits(
        mode="piecewise", numerator=numerator, denominator=denominator
    )
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0), initialize=100.0)
    attachment = attach_conditional_mio_pair(
        attached_pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="attached_pair",
    )

    with pytest.raises(ValueError, match="does not belong"):
        initialize_conditional_mio_attachment(
            other_pair,
            attachment,
            declared_domain_assignments={"x": 100.0},
        )


def _guard_boundary_circuits(
    relative_value: float,
) -> tuple[TPMConditionalCircuit, TPMConditionalCircuit]:
    leading_child = -1.0 - math.log(0.5)
    numerator = TPMConditionalCircuit(
        root_id=2,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [leading_child, leading_child],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 1,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [
                        leading_child + relative_value,
                        leading_child + relative_value,
                    ],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 2,
                    "type": "sum",
                    "children": [0, 1],
                    "weights": [0.5, 0.5],
                }
            ),
        ),
        metadata={"event_treatment": "fixed"},
    )
    denominator = TPMConditionalCircuit(
        root_id=0,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 1.0],
                    "log_values": [0.0, 0.0],
                }
            ),
        ),
        metadata={"event_treatment": "marginalized"},
    )
    return numerator, denominator


@pytest.mark.parametrize(
    "relative_value",
    (
        math.log(1e-3) - 1.0,
        math.log(1e-3),
        math.log(1e-3) + 0.5e-3,
        math.log(1e-3) + 1e-3,
        math.log(1e-3) + 0.1,
    ),
)
def test_minimal_guarded_exponential_objective_free_highs_parity(
    relative_value: float,
) -> None:
    import highspy
    import pyomo.environ as pyo

    numerator, denominator = _guard_boundary_circuits(relative_value)
    pair = _pair_with_circuits(
        mode="piecewise", numerator=numerator, denominator=denominator
    )
    direct = evaluate_conditional_mio_pair(
        pair, declared_domain_assignments={"x": 100.0}
    )
    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(TPMContinuousDecisionMapping("x", model.x),),
        namespace="guard_boundary",
    )
    model.x.fix(100.0)
    solver = pyo.SolverFactory("highs")
    solver.options["threads"] = 1
    results = solver.solve(model)
    diagnostics = inspect_conditional_mio_attachment(
        attachment,
        solver_metadata={
            "solver_name": "highs",
            "solver_version": highspy.Highs().version(),
            "status": str(results.solver.status),
            "termination_condition": str(results.solver.termination_condition),
        },
    )

    assert not tuple(model.component_data_objects(pyo.Objective, active=True))
    assert diagnostics.numerator_log == pytest.approx(direct.numerator_log, abs=1e-6)
    assert diagnostics.denominator_log == pytest.approx(direct.denominator_log, abs=1e-6)
    assert diagnostics.conditional_log_risk == pytest.approx(
        direct.conditional_log_risk, abs=1e-6
    )
    assert diagnostics.maximum_constraint_residual <= 1e-6
