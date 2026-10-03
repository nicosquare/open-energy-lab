"""Encode conditioned MIO circuits and decision links as Pyomo constraints."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from ..domains import (
    TPMCompiledValidityRecord,
)
from ..features import TPMFeatureSpec, load_feature_schema
from ..piecewise import guarded_exponential_points
from ..piecewise import interpolate_within_breakpoints
from ._common import (
    _SPFLOW_MIO_COMPILER_VERSION,
    _SPFLOW_MIO_SCHEMA_VERSION,
    _float_sequence,
    _mapping,
    _sequence_of_mappings,
)
from .evaluate import _load_compiled_validity


def build_compiled_spflow_decision_link_model(
    backend: Any,
    *,
    compiled_payload: Mapping[str, object],
    decision_features: Sequence[str],
) -> object:
    """Build a constant-objective Pyomo model exposing compiled-v2 decision links."""

    compiled = _mapping(compiled_payload, field_name="compiled_payload")
    if compiled.get("schema_version") != _SPFLOW_MIO_SCHEMA_VERSION:
        raise ValueError("physical decision linking requires a compiled-v2 payload")
    if compiled.get("compiler_version") != _SPFLOW_MIO_COMPILER_VERSION:
        raise ValueError("physical decision linking requires the current compiled-v2 compiler")
    schema = load_feature_schema(
        _sequence_of_mappings(compiled.get("feature_schema"), field_name="feature_schema"),
        schema_version="v3",
    )
    feature_by_name = {spec.feature_name: spec for spec in schema}
    validity_by_index = _load_compiled_validity(compiled)
    validity_by_name = {
        record.feature_name: record for record in validity_by_index.values()
    }
    normalized_decisions = tuple(str(name) for name in decision_features)
    if not normalized_decisions or len(set(normalized_decisions)) != len(
        normalized_decisions
    ):
        raise ValueError("decision_features must be non-empty and unique")

    model = backend.ConcreteModel(name="compiled-spflow-decision-links")
    model._tpm_decision_variables = {}
    model._tpm_decision_decoders = {}
    for feature_name in normalized_decisions:
        if feature_name not in feature_by_name:
            raise ValueError(f"unknown compiled decision feature {feature_name!r}")
        feature_spec = feature_by_name[feature_name]
        if feature_spec.feature_role != "decision" or not feature_spec.modifiable:
            raise ValueError(
                f"compiled feature {feature_name!r} is not a modifiable decision"
            )
        validity = validity_by_name.get(feature_name)
        if feature_spec.feature_type == "continuous" and validity is None:
            raise ValueError(
                f"continuous decision {feature_name!r} lacks compiled-v2 validity"
            )
        decision_payload = _add_decision_variable(
            backend,
            model,
            feature_spec=feature_spec,
            feature_name=feature_name,
            compiled_validity=validity,
        )
        model._tpm_decision_variables[feature_name] = decision_payload
        model._tpm_decision_decoders[feature_name] = _decision_decoder(
            feature_spec
        )
    model.constant_objective = backend.Objective(expr=0.0)
    return model


def _add_decision_variable(
    backend: Any,
    model: object,
    *,
    feature_spec: TPMFeatureSpec,
    feature_name: str,
    option_costs: Mapping[object, float] | None = None,
    compiled_validity: TPMCompiledValidityRecord | None = None,
) -> dict[str, object]:
    if feature_spec.feature_type == "continuous":
        if compiled_validity is not None:
            physical_var = backend.Var(
                bounds=(
                    compiled_validity.physical_lower,
                    compiled_validity.physical_upper,
                )
            )
            model_var = backend.Var(
                bounds=(compiled_validity.model_lower, compiled_validity.model_upper)
            )
            model.add_component(f"decision_{feature_name}_physical", physical_var)
            model.add_component(
                f"decision_{feature_name}_model_coordinate",
                model_var,
            )
            model.add_component(
                f"decision_{feature_name}_physical_validity_lower",
                backend.Constraint(
                    expr=physical_var >= compiled_validity.physical_lower
                ),
            )
            model.add_component(
                f"decision_{feature_name}_physical_validity_upper",
                backend.Constraint(
                    expr=physical_var <= compiled_validity.physical_upper
                ),
            )
            model.add_component(
                f"decision_{feature_name}_model_validity_lower",
                backend.Constraint(expr=model_var >= compiled_validity.model_lower),
            )
            model.add_component(
                f"decision_{feature_name}_model_validity_upper",
                backend.Constraint(expr=model_var <= compiled_validity.model_upper),
            )
            normalization = compiled_validity.normalization
            if normalization.kind == "min-max":
                link_expression = model_var == (
                    physical_var - normalization.lower
                ) / (normalization.upper - normalization.lower)
            elif normalization.kind == "identity":
                link_expression = model_var == physical_var
            else:
                raise ValueError(
                    f"continuous decision {feature_name!r} uses unsupported compiled "
                    f"normalization {normalization.kind!r}"
                )
            link = backend.Constraint(expr=link_expression)
            model.add_component(f"decision_{feature_name}_coordinate_link", link)
            return {
                "kind": "continuous",
                "physical_var": physical_var,
                "model_coordinate_var": model_var,
                "normalized_var": model_var,
                "coordinate_link": link,
                "cost_expression": physical_var,
                "compiled_validity": compiled_validity,
            }
        var = backend.Var(bounds=(0.0, 1.0))
        model.add_component(f"decision_{feature_name}", var)
        lower, upper = feature_spec.bounds or (0.0, 1.0)
        cost_expression = lower + var * (upper - lower)
        return {
            "kind": "continuous",
            "normalized_var": var,
            "cost_expression": cost_expression,
        }

    if feature_spec.feature_type == "binary":
        var = backend.Var(domain=backend.Binary)
        model.add_component(f"decision_{feature_name}", var)
        discrete_values = tuple(feature_spec.ordering or feature_spec.discrete_values)
        if len(discrete_values) != 2:
            raise ValueError(
                f"binary decision feature {feature_name!r} must declare two ordered labels"
            )
        return {
            "kind": "binary",
            "normalized_var": var,
            "category_values": discrete_values,
            "cost_expression": var,
        }

    if feature_spec.feature_type == "categorical":
        categories = tuple(feature_spec.ordering or feature_spec.discrete_values)
        if option_costs is not None and set(option_costs) != set(categories):
            raise ValueError(
                f"option_costs for {feature_name!r} must exactly match {categories!r}"
            )
        index_set = backend.Set(initialize=tuple(range(len(categories))), ordered=True)
        model.add_component(f"decision_{feature_name}_set", index_set)
        var = backend.Var(index_set, domain=backend.Binary)
        model.add_component(f"decision_{feature_name}", var)
        model.add_component(
            f"decision_{feature_name}_one_hot",
            backend.Constraint(expr=sum(var[index] for index in index_set) == 1),
        )
        return {
            "kind": "categorical",
            "normalized_var": var,
            "category_values": categories,
            "cost_expression": (
                sum(float(option_costs[category]) * var[index]
                    for index, category in enumerate(categories))
                if option_costs is not None
                else 0.0
            ),
        }

    raise ValueError(
        f"SPN MIO builder does not yet support decision feature_type {feature_spec.feature_type!r}"
    )


def _decision_decoder(feature_spec: TPMFeatureSpec) -> object:
    return feature_spec


def _decode_decision_value(
    feature_spec: TPMFeatureSpec,
    *,
    decision_payload: Mapping[str, object],
    value_function: Any,
    numeric_tolerance: float,
) -> object:
    kind = str(decision_payload["kind"])
    if kind == "continuous":
        if "physical_var" in decision_payload:
            return float(value_function(decision_payload["physical_var"]))
        normalized_value = float(value_function(decision_payload["normalized_var"]))
        lower, upper = feature_spec.bounds or (0.0, 1.0)
        return lower + normalized_value * (upper - lower)

    if kind == "binary":
        normalized_value = float(value_function(decision_payload["normalized_var"]))
        labels = tuple(decision_payload.get("category_values", (0.0, 1.0)))
        return (
            labels[1]
            if normalized_value >= 1.0 - numeric_tolerance
            else labels[0]
        )

    if kind == "categorical":
        category_values = tuple(decision_payload["category_values"])
        var = decision_payload["normalized_var"]
        best_index = max(
            range(len(category_values)),
            key=lambda index: float(value_function(var[index])),
        )
        return category_values[best_index]

    raise ValueError(f"unsupported decision payload kind {kind!r}")


def encode_conditioned_spflow_circuit(
    backend: Any,
    block: object,
    *,
    circuit: Mapping[str, object],
    decision_variables: Mapping[str, Mapping[str, object]],
    encoding: Mapping[str, object],
    formulation: Mapping[str, object],
) -> Mapping[str, object]:
    """Encode one conditioned circuit against shared caller-supplied coordinates."""

    nodes = _sequence_of_mappings(
        circuit.get("nodes"), field_name="conditioned circuit nodes"
    )
    root_id = int(circuit["root_id"])
    node_ids = tuple(int(node["id"]) for node in nodes)
    if len(set(node_ids)) != len(node_ids) or root_id not in set(node_ids):
        raise ValueError("conditioned circuit node ids must be unique and contain root_id")
    encoding_mode = str(encoding.get("mode", ""))
    if encoding_mode not in {"max", "piecewise"}:
        raise ValueError("conditioned circuit encoding mode must be max or piecewise")
    leaf_configuration = _mapping(
        encoding.get("leaf_configuration"),
        field_name="conditional leaf_configuration",
    )
    sum_configuration = _mapping(
        encoding.get("sum_configuration"),
        field_name="conditional sum_configuration",
    )
    probability_floor = float(leaf_configuration["discrete_probability_floor"])
    if not math.isfinite(probability_floor) or probability_floor <= 0.0:
        raise ValueError("conditional discrete probability floor must be positive and finite")

    formulation_payload = _mapping(
        formulation, field_name="conditional attachment formulation"
    )
    node_bound_records = _sequence_of_mappings(
        formulation_payload.get("node_output_bounds"),
        field_name="conditional node output bounds",
    )
    node_bounds = {
        int(record["node_id"]): (
            float(record["lower"]),
            float(record["upper"]),
        )
        for record in node_bound_records
    }
    if set(node_bounds) != set(node_ids) or any(
        not math.isfinite(value) or node_bounds[node_id][0] > node_bounds[node_id][1]
        for node_id in node_ids
        for value in node_bounds[node_id]
    ):
        raise ValueError("conditional attachment node bounds are incomplete or invalid")
    leaf_representation_records = _sequence_of_mappings(
        formulation_payload.get("leaf_piecewise_representations", ()),
        field_name="conditional leaf Piecewise representations",
    )
    leaf_representations = {
        int(record["node_id"]): str(record["representation"])
        for record in leaf_representation_records
    }
    sum_records = _sequence_of_mappings(
        formulation_payload.get("sum_nodes", ()),
        field_name="conditional Sum formulation records",
    )
    sum_formulations = {int(record["node_id"]): record for record in sum_records}
    guarded_input_coordinate = formulation_payload.get("guarded_input_coordinate")

    block.NODE_IDS = backend.Set(initialize=node_ids, ordered=True)
    block.node_out = backend.Var(
        block.NODE_IDS,
        within=backend.Reals,
        bounds=lambda _block, node_id: node_bounds[int(node_id)],
    )
    node_by_id = {int(node["id"]): node for node in nodes}
    for node_id in node_ids:
        node = node_by_id[node_id]
        node_type = str(node["type"])
        if node_type == "log_one":
            block.add_component(
                f"log_one_{node_id}",
                backend.Constraint(expr=block.node_out[node_id] == 0.0),
            )
            continue
        if node_type == "leaf_piecewise":
            _encode_conditioned_piecewise_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                decision_variables=decision_variables,
                representation=leaf_representations.get(node_id),
            )
            continue
        if node_type in {"leaf_binary", "leaf_categorical"}:
            densities = _float_sequence(node["densities"])
            log_densities = tuple(
                math.log(max(value, probability_floor)) for value in densities
            )
            if "fixed_value" in node:
                index = int(node["fixed_value"])
                if not 0 <= index < len(densities):
                    raise ValueError(
                        f"conditioned discrete leaf {node_id} fixed index is invalid"
                    )
                block.add_component(
                    f"discrete_leaf_fixed_{node_id}",
                    backend.Constraint(
                        expr=block.node_out[node_id] == log_densities[index]
                    ),
                )
                continue
            feature_name = str(node["feature_name"])
            if feature_name not in decision_variables:
                raise ValueError(
                    f"conditioned discrete leaf {node_id} has no decision mapping"
                )
            payload = decision_variables[feature_name]
            kind = str(payload.get("kind"))
            if node_type == "leaf_binary" and kind == "binary":
                variable = payload["normalized_var"]
                block.add_component(
                    f"binary_leaf_{node_id}",
                    backend.Constraint(
                        expr=block.node_out[node_id]
                        == (1.0 - variable) * log_densities[0]
                        + variable * log_densities[1]
                    ),
                )
                continue
            if node_type == "leaf_categorical" and kind == "categorical":
                indicators = tuple(payload["normalized_var"])
                if len(indicators) != len(log_densities):
                    raise ValueError(
                        f"categorical leaf {node_id} indicator count differs from densities"
                    )
                block.add_component(
                    f"categorical_leaf_{node_id}",
                    backend.Constraint(
                        expr=block.node_out[node_id]
                        == sum(
                            indicator * log_density
                            for indicator, log_density in zip(
                                indicators, log_densities, strict=True
                            )
                        )
                    ),
                )
                continue
            raise ValueError(
                f"conditioned discrete leaf {node_id} mapping kind {kind!r} is invalid"
            )
        if node_type == "product":
            child_ids = tuple(int(value) for value in node.get("children", ()))
            block.add_component(
                f"product_{node_id}",
                backend.Constraint(
                    expr=block.node_out[node_id]
                    == sum(block.node_out[child_id] for child_id in child_ids)
                ),
            )
            continue
        if node_type == "sum":
            _encode_conditioned_sum_node(
                backend,
                block,
                node_id=node_id,
                node=node,
                mode=encoding_mode,
                sum_configuration=sum_configuration,
                formulation=sum_formulations.get(node_id),
                guarded_input_coordinate=guarded_input_coordinate,
            )
            continue
        raise ValueError(f"unsupported conditioned circuit node type {node_type!r}")

    constraint_names = tuple(
        component.getname(fully_qualified=False)
        for component in block.component_objects(
            backend.Constraint, active=True, descend_into=True
        )
    )
    return {
        "root": block.node_out[root_id],
        "node_output": block.node_out,
        "constraint_component_names": constraint_names,
    }


def _encode_conditioned_piecewise_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    decision_variables: Mapping[str, Mapping[str, object]],
    representation: str | None,
) -> None:
    feature_name = str(node["feature_name"])
    breakpoints = _float_sequence(node["breakpoints"])
    log_values = _float_sequence(node["log_values"])
    if len(breakpoints) < 2 or len(breakpoints) != len(log_values):
        raise ValueError(
            f"conditioned piecewise leaf {node_id} points must align"
        )
    if feature_name in decision_variables:
        payload = decision_variables[feature_name]
        if str(payload.get("kind")) == "integer_lookup":
            indicators = tuple(payload['indicators'])
            if (representation != 'integer-lookup'
                    or tuple(breakpoints) != tuple(payload['grid_coordinates'])
                    or len(indicators) != len(log_values)):
                raise ValueError('integer lookup leaf differs from the persisted shared grid')
            block.add_component(
                f'integer_leaf_{node_id}',
                backend.Constraint(expr=block.node_out[node_id]
                    == sum(value * z for value, z in zip(log_values, indicators, strict=True))),
            )
            return
        if str(payload.get("kind")) != "continuous":
            raise ValueError(
                f"conditioned piecewise leaf {node_id} requires a continuous mapping"
            )
        expected_representation = "DLOG" if len(breakpoints) - 1 == 4 else "DCC"
        if representation != expected_representation:
            raise ValueError(
                f"conditioned piecewise leaf {node_id} representation must be "
                f"{expected_representation}"
            )
        piecewise = backend.Piecewise(
            block.node_out[node_id],
            payload["normalized_var"],
            pw_pts=list(breakpoints),
            pw_constr_type="EQ",
            pw_repn=representation,
            f_rule=list(log_values),
        )
        block.add_component(f"piecewise_leaf_{node_id}", piecewise)
        _bound_piecewise_auxiliaries(backend, piecewise)
        return
    if "fixed_value" not in node:
        raise ValueError(
            f"conditioned piecewise leaf {node_id} has no decision mapping"
        )
    fixed_log_value = interpolate_within_breakpoints(
        float(node["fixed_value"]),
        x_values=breakpoints,
        y_values=log_values,
    )
    block.add_component(
        f"piecewise_leaf_fixed_{node_id}",
        backend.Constraint(expr=block.node_out[node_id] == fixed_log_value),
    )


def _sparse_dcc_piecewise(backend, output, input_value, *, x_points, y_points):
    """Exact DCC interpolation with only the two vertices used by each segment.

    Pyomo's generic DCC builder declares a dense segment-by-vertex product;
    only adjacent vertices occur in its equations. Preserve the same active
    equations and component names without allocating the unused columns.
    """
    if len(x_points) != len(y_points) or len(x_points) < 2:
        raise ValueError('DCC interpolation points must align')
    if any(not math.isfinite(float(v)) for v in (*x_points, *y_points)):
        raise ValueError('DCC interpolation points must be finite')
    if any(b <= a for a, b in zip(x_points, x_points[1:])):
        raise ValueError('DCC input points must increase strictly')
    block = backend.Block(concrete=True)
    segments = tuple(range(1, len(x_points)))
    vertices = tuple((p, v) for p in segments for v in (p, p + 1))
    block.DCC_lambda = backend.Var(vertices, domain=backend.NonNegativeReals, bounds=(0, 1))
    block.DCC_bin_y = backend.Var(segments, domain=backend.Binary)
    block.DCC_constraint1 = backend.Constraint(expr=input_value == sum(
        x_points[v - 1] * block.DCC_lambda[p, v] for p, v in vertices))
    block.DCC_constraint2 = backend.Constraint(expr=output == sum(
        y_points[v - 1] * block.DCC_lambda[p, v] for p, v in vertices))
    block.DCC_constraint3 = backend.Constraint(segments, rule=lambda _, p:
        block.DCC_bin_y[p] == block.DCC_lambda[p, p] + block.DCC_lambda[p, p + 1])
    block.DCC_constraint4 = backend.Constraint(expr=sum(block.DCC_bin_y[p] for p in segments) == 1)
    return block


def _encode_conditioned_sum_node(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    mode: str,
    sum_configuration: Mapping[str, object],
    formulation: Mapping[str, object] | None,
    guarded_input_coordinate: object,
) -> None:
    child_ids = tuple(int(value) for value in node["children"])
    weights = _float_sequence(node["weights"])
    if not child_ids or len(child_ids) != len(weights):
        raise ValueError(f"conditioned Sum {node_id} children and weights must align")
    if any(not math.isfinite(weight) or weight <= 0.0 for weight in weights):
        raise ValueError(f"conditioned Sum {node_id} weights must be positive and finite")
    weighted_terms = tuple(
        block.node_out[child_id] + math.log(weight)
        for child_id, weight in zip(child_ids, weights, strict=True)
    )
    if not isinstance(formulation, Mapping):
        raise ValueError(f"conditioned Sum {node_id} lacks persisted formulation")
    term_records = _sequence_of_mappings(
        formulation.get("term_bounds"),
        field_name=f"conditioned Sum {node_id} term bounds",
    )
    relative_records = _sequence_of_mappings(
        formulation.get("relative_bounds"),
        field_name=f"conditioned Sum {node_id} relative bounds",
    )
    big_m_records = _sequence_of_mappings(
        formulation.get("branch_big_m"),
        field_name=f"conditioned Sum {node_id} branch big-M",
    )
    if not (
        len(term_records) == len(relative_records) == len(big_m_records) == len(child_ids)
    ):
        raise ValueError(f"conditioned Sum {node_id} formulation branches must align")
    maximum_bounds = _formulation_interval(
        formulation.get("maximum_bounds"),
        field_name=f"conditioned Sum {node_id} maximum bounds",
    )
    relative_bounds = tuple(
        _formulation_interval(
            record,
            field_name=f"conditioned Sum {node_id} relative branch {index}",
        )
        for index, record in enumerate(relative_records)
    )
    branch_big_m = tuple(float(record["value"]) for record in big_m_records)
    if any(not math.isfinite(value) or value < 0.0 for value in branch_big_m):
        raise ValueError(f"conditioned Sum {node_id} branch big-M values are invalid")
    indices = tuple(range(len(child_ids)))
    choice_index = backend.Set(initialize=indices, ordered=True)
    block.add_component(f"sum_choice_index_{node_id}", choice_index)
    active = backend.Var(choice_index, domain=backend.Binary)
    block.add_component(f"sum_choice_var_{node_id}", active)
    block.add_component(
        f"sum_choice_one_hot_{node_id}",
        backend.Constraint(expr=sum(active[index] for index in indices) == 1),
    )
    maximum = backend.Var(within=backend.Reals, bounds=maximum_bounds)
    block.add_component(f"sum_max_var_{node_id}", maximum)
    block.add_component(
        f"sum_max_lb_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: maximum >= weighted_terms[index],
        ),
    )
    block.add_component(
        f"sum_max_ub_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: maximum
            <= weighted_terms[index] + branch_big_m[index] * (1 - active[index]),
        ),
    )
    if mode == "max":
        block.add_component(
            f"sum_max_output_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == maximum),
        )
        return

    exp_x, exp_y = guarded_exponential_points(sum_configuration)
    coordinate = _mapping(
        guarded_input_coordinate,
        field_name=f"conditioned Sum {node_id} guarded input coordinate",
    )
    if coordinate.get("policy") != "unit-affine-log-v1":
        raise ValueError(
            f"conditioned Sum {node_id} guarded input coordinate policy is unsupported"
        )
    native_offset = float(coordinate.get("native_offset"))
    native_scale = float(coordinate.get("native_scale"))
    if native_offset != -exp_x[0] or native_scale != native_offset or native_scale <= 0.0:
        raise ValueError(
            f"conditioned Sum {node_id} guarded input coordinate must match its declared domain"
        )
    solver_x = _float_sequence(coordinate.get("solver_breakpoints"))
    expected_solver_x = tuple(
        (value + native_offset) / native_scale for value in exp_x
    )
    if solver_x != expected_solver_x or solver_x[0] != 0.0 or solver_x[-1] != 1.0:
        raise ValueError(
            f"conditioned Sum {node_id} guarded solver breakpoints are inconsistent"
        )
    log_x = _float_sequence(sum_configuration["log_x_points"])
    log_y = _float_sequence(sum_configuration["log_y_points"])
    exponential_records = _sequence_of_mappings(
        formulation.get("exponential_bounds"),
        field_name=f"conditioned Sum {node_id} exponential bounds",
    )
    exponential_bounds = tuple(
        _formulation_interval(
            record,
            field_name=f"conditioned Sum {node_id} exponential branch {index}",
        )
        for index, record in enumerate(exponential_records)
    )
    solver_input_records = _sequence_of_mappings(
        formulation.get("solver_input_bounds"),
        field_name=f"conditioned Sum {node_id} solver input bounds",
    )
    solver_input_bounds = tuple(
        _formulation_interval(
            record,
            field_name=f"conditioned Sum {node_id} solver input branch {index}",
        )
        for index, record in enumerate(solver_input_records)
    )
    if not (
        len(exponential_bounds) == len(solver_input_bounds) == len(indices)
    ):
        raise ValueError(
            f"conditioned Sum {node_id} exponential and solver input bounds must align"
        )
    if formulation.get("exponential_representation") != "DCC":
        raise ValueError(f"conditioned Sum {node_id} exponential representation must be DCC")
    if formulation.get("logarithm_representation") != "DCC":
        raise ValueError(f"conditioned Sum {node_id} logarithm representation must be DCC")
    relative = backend.Var(
        choice_index, bounds=lambda _block, index: relative_bounds[index]
    )
    block.add_component(f"sum_relative_var_{node_id}", relative)
    exponentials = backend.Var(
        choice_index, bounds=lambda _block, index: exponential_bounds[index]
    )
    block.add_component(f"sum_exp_var_{node_id}", exponentials)
    solver_input = backend.Var(
        choice_index, bounds=lambda _block, index: solver_input_bounds[index]
    )
    block.add_component(f"sum_exp_input_var_{node_id}", solver_input)
    block.add_component(
        f"sum_relative_constraint_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: relative[index]
            == weighted_terms[index] - maximum,
        ),
    )
    block.add_component(
        f"sum_exp_input_constraint_{node_id}",
        backend.Constraint(
            choice_index,
            rule=lambda _block, index: native_scale * solver_input[index]
            == relative[index] + native_offset,
        ),
    )
    for index in indices:
        piecewise = _sparse_dcc_piecewise(
            backend,
            exponentials[index],
            solver_input[index],
            x_points=solver_x,
            y_points=exp_y,
        )
        block.add_component(f"sum_exp_piecewise_{node_id}_{index}", piecewise)
        # Keep the bounded unit coordinate, but enforce its interpolation
        # equality in native log units. Otherwise a 1e-8 solver residual in
        # this coordinate is amplified by native_scale in native log units.
        # Replace the active row rather than adding a redundant equality;
        # DCC variables, breakpoints and initialization remain unchanged.
        input_row = piecewise.DCC_constraint1
        piecewise.add_component(
            "native_input_constraint",
            backend.Constraint(expr=native_scale * input_row.body == 0),
        )
        input_row.deactivate()
        _bound_piecewise_auxiliaries(backend, piecewise)
    total_bounds = _formulation_interval(
        formulation.get("total_bounds"),
        field_name=f"conditioned Sum {node_id} total bounds",
    )
    total = backend.Var(bounds=total_bounds)
    block.add_component(f"sum_exp_total_{node_id}", total)
    block.add_component(
        f"sum_exp_total_constraint_{node_id}",
        backend.Constraint(
            expr=total == sum(exponentials[index] for index in indices)
        ),
    )
    logarithm_bounds = _formulation_interval(
        formulation.get("logarithm_bounds"),
        field_name=f"conditioned Sum {node_id} logarithm bounds",
    )
    logarithm = backend.Var(bounds=logarithm_bounds)
    block.add_component(f"sum_log_var_{node_id}", logarithm)
    log_piecewise = _sparse_dcc_piecewise(
        backend,
        logarithm,
        total,
        x_points=log_x,
        y_points=log_y,
    )
    block.add_component(f"sum_log_piecewise_{node_id}", log_piecewise)
    _bound_piecewise_auxiliaries(backend, log_piecewise)
    block.add_component(
        f"sum_output_{node_id}",
        backend.Constraint(expr=block.node_out[node_id] == maximum + logarithm),
    )


def _formulation_interval(
    value: object,
    *,
    field_name: str,
) -> tuple[float, float]:
    payload = _mapping(value, field_name=field_name)
    if not {"lower", "upper"}.issubset(payload):
        raise ValueError(f"{field_name} must contain lower and upper")
    lower = float(payload["lower"])
    upper = float(payload["upper"])
    if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
        raise ValueError(f"{field_name} must be a finite ordered interval")
    return lower, upper


def _bound_piecewise_auxiliaries(backend: Any, piecewise: object) -> None:
    """Apply explicit unit bounds to representation-owned convex weights."""

    for variable in piecewise.component_data_objects(
        backend.Var, active=True, descend_into=True
    ):
        if variable.lb is None:
            variable.setlb(0.0)
        if variable.ub is None:
            variable.setub(1.0)
