"""Serialized-SPN chance models: build, solve, and extract a Pyomo design."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from importlib import import_module
from itertools import product as cartesian_product
from typing import Any

from .._graph import memoized_acyclic
from ..domains import (
    TPMCompiledValidityRecord,
)
from ..features import TPMFeatureSpec, load_feature_schema
from ..piecewise import build_histogram_piecewise_points
from ..piecewise import interpolate_within_breakpoints
from ._common import (
    SPNSolverDependencyUnavailableError,
    _float_sequence,
    _mapping,
    _sequence,
    _sequence_of_mappings,
)
from .encode import (
    _add_decision_variable,
    _decision_decoder,
    _decode_decision_value,
)


_SUM_BIG_M = 100.0


def build_spn_chance_model(
    backend: Any,
    *,
    problem_id: str,
    spn_payload: Mapping[str, object],
    cost_terms: Mapping[str, float],
    option_costs: Mapping[str, Mapping[object, float]] | None = None,
    chance_limit_epsilon: float,
    numeric_tolerance: float,
    piecewise_terms: object,
) -> object:
    """Build one direct-design SPN chance-constrained Pyomo model."""

    conditional_models = _mapping(spn_payload.get("conditional_models"), field_name="conditional_models")
    numerator_model = _mapping(conditional_models.get("numerator_model"), field_name="conditional_models.numerator_model")
    denominator_model = _mapping(
        conditional_models.get("denominator_model"),
        field_name="conditional_models.denominator_model",
    )
    feature_schema = load_feature_schema(
        _sequence_of_mappings(
            spn_payload.get("feature_schema"),
            field_name="feature_schema",
        ),
        schema_version=str(spn_payload.get("fitted_artifact_schema_version", "v2")),
    )
    feature_by_name = {spec.feature_name: spec for spec in feature_schema}
    compiled_validity_by_name: dict[str, TPMCompiledValidityRecord] = {}
    for raw_validity in _sequence_of_mappings(
        spn_payload.get("compiled_validity", ()),
        field_name="compiled_validity",
    ):
        validity = TPMCompiledValidityRecord.from_dict(raw_validity)
        if validity.feature_name in compiled_validity_by_name:
            raise ValueError("compiled validity feature names must be unique")
        compiled_validity_by_name[validity.feature_name] = validity
    decision_features = tuple(
        str(name)
        for name in _string_sequence(
            spn_payload.get("decision_features"),
            field_name="decision_features",
        )
    )
    sum_encoding_mode = str(
        spn_payload.get("sum_encoding_mode", getattr(piecewise_terms, "sum_encoding_mode", "piecewise"))
    )
    if sum_encoding_mode not in {"max", "piecewise"}:
        raise ValueError("sum_encoding_mode must be 'max' or 'piecewise'")

    model = backend.ConcreteModel(name=f"{problem_id}-spn-mio")
    model.decision_features = backend.Set(initialize=decision_features, ordered=True)
    model._tpm_feature_by_name = feature_by_name
    model._tpm_decision_variables = {}
    model._tpm_decision_decoders = {}

    total_cost = 0.0
    resolved_option_costs = dict(option_costs or {})
    for feature_name in decision_features:
        if feature_name not in feature_by_name:
            raise ValueError(f"decision feature {feature_name!r} not present in feature_schema")
        feature_spec = feature_by_name[feature_name]
        per_option_costs = resolved_option_costs.get(feature_name)
        if per_option_costs is None and feature_name not in cost_terms:
            raise ValueError(f"missing cost definition for {feature_name!r}")
        coefficient = (
            1.0 if per_option_costs is not None else float(cost_terms[feature_name])
        )
        decision_payload = _add_decision_variable(
            backend,
            model,
            feature_spec=feature_spec,
            feature_name=feature_name,
            option_costs=per_option_costs,
            compiled_validity=compiled_validity_by_name.get(feature_name),
        )
        model._tpm_decision_variables[feature_name] = decision_payload
        model._tpm_decision_decoders[feature_name] = _decision_decoder(feature_spec)
        total_cost += coefficient * decision_payload["cost_expression"]

    if _supports_exact_categorical_lookup(
        decision_features=decision_features,
        feature_by_name=feature_by_name,
        numerator_model=numerator_model,
        denominator_model=denominator_model,
    ):
        return _build_exact_categorical_lookup_model(
            backend,
            model,
            decision_features=decision_features,
            feature_by_name=feature_by_name,
            decision_variables=model._tpm_decision_variables,
            numerator_model=numerator_model,
            denominator_model=denominator_model,
            total_cost=total_cost,
            chance_limit_epsilon=float(chance_limit_epsilon),
            sum_encoding_mode=sum_encoding_mode,
        )

    numerator_block = backend.Block()
    denominator_block = backend.Block()
    model.add_component("numerator_spn", numerator_block)
    model.add_component("denominator_spn", denominator_block)

    numerator_root = _encode_serialized_spn(
        backend,
        numerator_block,
        model=model,
        spn_model=numerator_model,
        feature_by_name=feature_by_name,
        decision_variables=model._tpm_decision_variables,
        sum_encoding_mode=sum_encoding_mode,
        piecewise_terms=piecewise_terms,
    )
    denominator_root = _encode_serialized_spn(
        backend,
        denominator_block,
        model=model,
        spn_model=denominator_model,
        feature_by_name=feature_by_name,
        decision_variables=model._tpm_decision_variables,
        sum_encoding_mode=sum_encoding_mode,
        piecewise_terms=piecewise_terms,
    )

    chance_limit_log = math.log(max(float(chance_limit_epsilon), float(numeric_tolerance)))
    model.chance_constraint = backend.Constraint(
        expr=numerator_root - denominator_root <= chance_limit_log
    )
    model.total_cost = backend.Objective(expr=total_cost, sense=backend.minimize)
    model._tpm_risk_log_numerator = numerator_root
    model._tpm_risk_log_denominator = denominator_root
    model._tpm_chance_limit_epsilon = float(chance_limit_epsilon)
    model._tpm_sum_encoding_mode = sum_encoding_mode
    return model


def _supports_exact_categorical_lookup(
    *,
    decision_features: Sequence[str],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    numerator_model: Mapping[str, object],
    denominator_model: Mapping[str, object],
) -> bool:
    if not decision_features or any(
        feature_by_name[feature_name].feature_type != "categorical"
        for feature_name in decision_features
    ):
        return False
    decision_names = set(decision_features)
    for spn_model in (numerator_model, denominator_model):
        for node in _sequence_of_mappings(
            spn_model.get("nodes"),
            field_name="spn_model.nodes",
        ):
            node_type = str(node.get("type", ""))
            if node_type not in {
                "leaf_binary",
                "leaf_categorical",
                "product",
                "sum",
            }:
                return False
            if node_type.startswith("leaf_") and "fixed_value" not in node:
                if str(node.get("feature_name", "")) not in decision_names:
                    return False
    return True


def _build_exact_categorical_lookup_model(
    backend: Any,
    model: object,
    *,
    decision_features: Sequence[str],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
    numerator_model: Mapping[str, object],
    denominator_model: Mapping[str, object],
    total_cost: object,
    chance_limit_epsilon: float,
    sum_encoding_mode: str,
) -> object:
    """Encode exact compiled-SPN risks over a finite categorical design grid."""

    category_domains = tuple(
        tuple(decision_variables[feature_name]["category_values"])
        for feature_name in decision_features
    )
    combinations = tuple(cartesian_product(*category_domains))
    risks: list[float] = []
    for combination in combinations:
        assignments = dict(zip(decision_features, combination, strict=True))
        numerator_log = _evaluate_serialized_categorical_spn(
            numerator_model,
            assignments=assignments,
            feature_by_name=feature_by_name,
        )
        denominator_log = _evaluate_serialized_categorical_spn(
            denominator_model,
            assignments=assignments,
            feature_by_name=feature_by_name,
        )
        risks.append(math.exp(min(0.0, numerator_log - denominator_log)))

    combination_ids = tuple(range(len(combinations)))
    model.categorical_combination_ids = backend.Set(
        initialize=combination_ids,
        ordered=True,
    )
    model.categorical_combination_selected = backend.Var(
        model.categorical_combination_ids,
        domain=backend.Binary,
    )
    model.categorical_combination_one_hot = backend.Constraint(
        expr=sum(
            model.categorical_combination_selected[combination_id]
            for combination_id in combination_ids
        )
        == 1
    )

    for feature_index, feature_name in enumerate(decision_features):
        decision_var = decision_variables[feature_name]["normalized_var"]
        for category_index in range(len(category_domains[feature_index])):
            matching_combinations = tuple(
                combination_id
                for combination_id, combination in enumerate(combinations)
                if combination[feature_index]
                == category_domains[feature_index][category_index]
            )
            model.add_component(
                f"categorical_combination_link_{feature_name}_{category_index}",
                backend.Constraint(
                    expr=decision_var[category_index]
                    == sum(
                        model.categorical_combination_selected[combination_id]
                        for combination_id in matching_combinations
                    )
                ),
            )

    risk_expression = sum(
        risks[combination_id]
        * model.categorical_combination_selected[combination_id]
        for combination_id in combination_ids
    )
    model.chance_constraint = backend.Constraint(
        expr=risk_expression <= chance_limit_epsilon
    )
    model.total_cost = backend.Objective(expr=total_cost, sense=backend.minimize)
    model._tpm_risk_probability = risk_expression
    model._tpm_risk_by_combination = tuple(risks)
    model._tpm_categorical_combinations = combinations
    model._tpm_chance_limit_epsilon = chance_limit_epsilon
    model._tpm_sum_encoding_mode = sum_encoding_mode
    model._tpm_risk_encoding_strategy = "exact-categorical-lookup"
    return model


def _evaluate_serialized_categorical_spn(
    spn_model: Mapping[str, object],
    *,
    assignments: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
) -> float:
    """Evaluate one conditioned compiled graph at categorical assignments."""

    nodes = _sequence_of_mappings(
        spn_model.get("nodes"),
        field_name="spn_model.nodes",
    )
    node_by_id = {int(node["id"]): node for node in nodes}
    if len(node_by_id) != len(nodes):
        raise ValueError("serialized categorical SPN nodes must use unique ids")

    def evaluate_node(node_id: int) -> float:
        node = node_by_id[node_id]
        node_type = str(node.get("type", ""))
        if node_type in {"leaf_binary", "leaf_categorical"}:
            densities = _float_sequence(node.get("densities"))
            if "fixed_value" in node:
                value_index = int(float(node["fixed_value"]))
            else:
                feature_name = str(node.get("feature_name", ""))
                if feature_name not in assignments or feature_name not in feature_by_name:
                    raise ValueError(
                        f"categorical SPN leaf requires assignment for {feature_name!r}"
                    )
                feature_spec = feature_by_name[feature_name]
                category_values = tuple(
                    feature_spec.ordering or feature_spec.discrete_values
                )
                value_index = category_values.index(assignments[feature_name])
            if not 0 <= value_index < len(densities):
                raise ValueError("categorical SPN leaf value index is outside densities")
            value = math.log(max(densities[value_index], 1e-12))
        elif node_type == "product":
            value = math.fsum(
                evaluate(int(child_id)) for child_id in node.get("children", ())
            )
        elif node_type == "sum":
            child_ids = tuple(int(child_id) for child_id in node.get("children", ()))
            weights = _float_sequence(node.get("weights"))
            if not child_ids or len(child_ids) != len(weights):
                raise ValueError("categorical SPN sum children and weights must align")
            weighted_terms = tuple(
                evaluate(child_id) + math.log(max(weight, 1e-12))
                for child_id, weight in zip(child_ids, weights, strict=True)
            )
            maximum = max(weighted_terms)
            value = maximum + math.log(
                math.fsum(math.exp(term - maximum) for term in weighted_terms)
            )
        else:
            raise ValueError(
                f"unsupported exact categorical SPN node type {node_type!r}"
            )
        return value

    evaluate = memoized_acyclic(
        evaluate_node,
        cycle_message="serialized categorical SPN nodes must be acyclic",
        nodes=node_by_id,
        missing_message="serialized categorical SPN node {node_id} does not exist",
    )
    return evaluate(int(spn_model["root_id"]))


def extract_spn_solution(
    model: object,
    *,
    backend: Any,
    numeric_tolerance: float,
) -> dict[str, object]:
    """Decode one solved direct-design SPN model into a stable summary payload."""

    value_function = getattr(backend, "value", None)
    if not callable(value_function):
        raise TypeError("backend must expose value() to decode a solved SPN model")

    decision_variables = getattr(model, "_tpm_decision_variables")
    feature_by_name = getattr(model, "_tpm_feature_by_name")
    selected_design: dict[str, object] = {}
    for feature_name, decision_payload in decision_variables.items():
        feature_spec = feature_by_name[feature_name]
        selected_design[feature_name] = _decode_decision_value(
            feature_spec,
            decision_payload=decision_payload,
            value_function=value_function,
            numeric_tolerance=numeric_tolerance,
        )

    objective_value = float(value_function(model.total_cost))
    risk_probability = getattr(model, "_tpm_risk_probability", None)
    result = {
        "selected_design": selected_design,
        "objective_value": objective_value,
    }
    if risk_probability is not None:
        estimated_risk = float(value_function(risk_probability))
        result.update(
            {
                "estimated_event_probability": estimated_risk,
                "estimated_shortfall_risk": estimated_risk,
                "risk_encoding_strategy": "exact-categorical-lookup",
            }
        )
        return result

    numerator_log = float(value_function(model._tpm_risk_log_numerator))
    denominator_log = float(value_function(model._tpm_risk_log_denominator))
    estimated_risk = math.exp(min(0.0, numerator_log - denominator_log))
    result.update(
        {
            "estimated_event_probability": estimated_risk,
            "estimated_shortfall_risk": estimated_risk,
            "numerator_log_likelihood": numerator_log,
            "denominator_log_likelihood": denominator_log,
            "risk_encoding_strategy": "piecewise-spn",
        }
    )
    return result


def infer_max_sum_terms(spn_payload: Mapping[str, object]) -> int:
    """Infer the largest sum-node arity across one serialized conditional SPN payload."""

    conditional_models = _mapping(
        spn_payload.get("conditional_models"),
        field_name="conditional_models",
    )
    max_terms = 2
    for model_name in ("numerator_model", "denominator_model"):
        model_payload = _mapping(
            conditional_models.get(model_name),
            field_name=f"conditional_models.{model_name}",
        )
        nodes = _sequence_of_mappings(model_payload.get("nodes"), field_name=f"{model_name}.nodes")
        for node in nodes:
            if str(node.get("type", "")) != "sum":
                continue
            child_count = len(_sequence(node.get("children"), field_name=f"{model_name}.children"))
            if child_count > max_terms:
                max_terms = child_count
    return max_terms


def _encode_serialized_spn(
    backend: Any,
    block: object,
    *,
    model: object,
    spn_model: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
    sum_encoding_mode: str,
    piecewise_terms: object,
) -> object:
    nodes = _sequence_of_mappings(spn_model.get("nodes"), field_name="spn_model.nodes")
    root_id = int(spn_model["root_id"])
    node_ids = tuple(int(node["id"]) for node in nodes)
    block.NODE_IDS = backend.Set(initialize=node_ids, ordered=True)
    block.node_out = backend.Var(block.NODE_IDS, within=backend.Reals)
    node_by_id = {int(node["id"]): node for node in nodes}

    for node in nodes:
        node_id = int(node["id"])
        node_type = str(node["type"])
        if node_type == "leaf_histogram":
            _encode_histogram_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
                piecewise_terms=piecewise_terms,
            )
            continue
        if node_type == "leaf_piecewise":
            _encode_piecewise_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
            )
            continue
        if node_type == "leaf_binary":
            _encode_binary_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
            )
            continue
        if node_type == "leaf_categorical":
            _encode_categorical_leaf(
                backend,
                block,
                node_id=node_id,
                node=node,
                feature_by_name=feature_by_name,
                decision_variables=decision_variables,
            )
            continue
        if node_type == "product":
            child_ids = tuple(int(value) for value in node["children"])
            block.add_component(
                f"product_{node_id}",
                backend.Constraint(
                    expr=block.node_out[node_id]
                    == sum(block.node_out[child_id] for child_id in child_ids)
                ),
            )
            continue
        if node_type == "sum":
            _encode_sum_node(
                backend,
                block,
                node_id=node_id,
                node=node,
                sum_encoding_mode=sum_encoding_mode,
                piecewise_terms=piecewise_terms,
            )
            continue
        raise ValueError(f"unsupported serialized SPN node type {node_type!r}")

    if root_id not in node_by_id:
        raise ValueError(f"root_id {root_id!r} is not present in serialized SPN nodes")
    return block.node_out[root_id]


def _encode_histogram_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
    piecewise_terms: object,
) -> None:
    feature_name = str(node["feature_name"])
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        fixed_value = float(node["fixed_value"])
        log_density = _histogram_log_density(
            breaks=_float_sequence(node["breaks"]),
            densities=_float_sequence(node["densities"]),
            value=fixed_value,
        )
        block.add_component(
            f"hist_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == log_density),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "continuous":
        raise ValueError(f"histogram leaf {node_id} requires a continuous decision variable")

    in_var = decision_payload["normalized_var"]
    log_densities = tuple(math.log(max(value, 1e-12)) for value in _float_sequence(node["densities"]))
    pw_x, pw_y = build_histogram_piecewise_points(
        _float_sequence(node["breaks"]),
        log_densities,
    )
    pw_constraint = backend.Piecewise(
        block.node_out[node_id],
        in_var,
        pw_pts=list(pw_x),
        pw_constr_type="EQ",
        pw_repn="DCC",
        f_rule=list(pw_y),
    )
    block.add_component(f"hist_leaf_piecewise_{node_id}", pw_constraint)


def _encode_piecewise_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
) -> None:
    feature_name = str(node["feature_name"])
    breakpoints = _float_sequence(node["breakpoints"])
    log_values = _float_sequence(node["log_values"])
    if len(breakpoints) != len(log_values) or len(breakpoints) < 2:
        raise ValueError(
            f"piecewise leaf {node_id} breakpoints and log_values must align"
        )
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        if "fixed_value" not in node:
            raise ValueError(
                f"piecewise leaf {node_id} requires a decision variable or fixed_value"
            )
        fixed_value = float(node["fixed_value"])
        fixed_log_value = interpolate_within_breakpoints(
            fixed_value,
            x_values=breakpoints,
            y_values=log_values,
        )
        block.add_component(
            f"piecewise_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == fixed_log_value),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "continuous":
        raise ValueError(
            f"piecewise leaf {node_id} requires a continuous decision variable"
        )
    block.add_component(
        f"piecewise_leaf_{node_id}",
        backend.Piecewise(
            block.node_out[node_id],
            decision_payload["normalized_var"],
            pw_pts=list(breakpoints),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(log_values),
        ),
    )


def _encode_binary_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
) -> None:
    feature_name = str(node["feature_name"])
    densities = tuple(math.log(max(value, 1e-12)) for value in _float_sequence(node["densities"]))
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        fixed_value = int(float(node["fixed_value"]))
        block.add_component(
            f"binary_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == densities[fixed_value]),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "binary":
        raise ValueError(f"binary leaf {node_id} requires a binary decision variable")
    in_var = decision_payload["normalized_var"]
    block.add_component(
        f"binary_leaf_{node_id}",
        backend.Constraint(
            expr=block.node_out[node_id]
            == (1.0 - in_var) * densities[0] + in_var * densities[1]
        ),
    )


def _encode_categorical_leaf(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    feature_by_name: Mapping[str, TPMFeatureSpec],
    decision_variables: Mapping[str, Mapping[str, object]],
) -> None:
    feature_name = str(node["feature_name"])
    densities = tuple(math.log(max(value, 1e-12)) for value in _float_sequence(node["densities"]))
    if feature_name not in feature_by_name or feature_name not in decision_variables:
        fixed_value = int(float(node["fixed_value"]))
        block.add_component(
            f"categorical_leaf_fixed_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == densities[fixed_value]),
        )
        return

    decision_payload = decision_variables[feature_name]
    if str(decision_payload["kind"]) != "categorical":
        raise ValueError(f"categorical leaf {node_id} requires a categorical decision variable")
    in_var = decision_payload["normalized_var"]
    block.add_component(
        f"categorical_leaf_{node_id}",
        backend.Constraint(
            expr=block.node_out[node_id]
            == sum(in_var[index] * densities[index] for index in range(len(densities)))
        ),
    )


def _encode_sum_node(
    backend: Any,
    block: object,
    *,
    node_id: int,
    node: Mapping[str, object],
    sum_encoding_mode: str,
    piecewise_terms: object,
) -> None:
    child_ids = tuple(int(value) for value in node["children"])
    weights = tuple(float(value) for value in node["weights"])
    weighted_terms = [block.node_out[child_id] + math.log(max(weight, 1e-12)) for child_id, weight in zip(child_ids, weights, strict=True)]

    slack_index = backend.Set(initialize=tuple(range(len(child_ids))), ordered=True)
    block.add_component(f"sum_choice_index_{node_id}", slack_index)
    active = backend.Var(slack_index, domain=backend.Binary)
    block.add_component(f"sum_choice_var_{node_id}", active)
    block.add_component(
        f"sum_choice_one_hot_{node_id}",
        backend.Constraint(expr=sum(active[index] for index in slack_index) == 1),
    )
    max_value = backend.Var(within=backend.Reals)
    block.add_component(f"sum_max_var_{node_id}", max_value)
    block.add_component(
        f"sum_max_lb_{node_id}",
        backend.Constraint(
            slack_index,
            rule=lambda _b, index: max_value >= weighted_terms[index],
        ),
    )
    block.add_component(
        f"sum_max_ub_{node_id}",
        backend.Constraint(
            slack_index,
            rule=lambda _b, index: max_value
            <= weighted_terms[index] + _SUM_BIG_M * (1 - active[index]),
        ),
    )

    if sum_encoding_mode == "max":
        block.add_component(
            f"sum_max_output_{node_id}",
            backend.Constraint(expr=block.node_out[node_id] == max_value),
        )
        return

    sub_index = backend.Set(initialize=tuple(range(len(child_ids))), ordered=True)
    block.add_component(f"sum_sub_index_{node_id}", sub_index)
    sub_var = backend.Var(sub_index, bounds=(piecewise_terms.exp_curve.domain_lower_bound, 0.0))
    block.add_component(f"sum_sub_var_{node_id}", sub_var)
    exp_var = backend.Var(sub_index, bounds=(0.0, 1.0))
    block.add_component(f"sum_exp_var_{node_id}", exp_var)
    block.add_component(
        f"sum_sub_constraint_{node_id}",
        backend.Constraint(
            sub_index,
            rule=lambda _b, index: sub_var[index] == weighted_terms[index] - max_value,
        ),
    )
    for index in range(len(child_ids)):
        piecewise = backend.Piecewise(
            exp_var[index],
            sub_var[index],
            pw_pts=list(piecewise_terms.exp_curve.x_points),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(piecewise_terms.exp_curve.y_points),
            unbounded_domain_var=True,
        )
        block.add_component(f"sum_exp_piecewise_{node_id}_{index}", piecewise)

    sum_var = backend.Var(
        bounds=(
            piecewise_terms.log_curve.domain_lower_bound,
            piecewise_terms.log_curve.domain_upper_bound,
        )
    )
    block.add_component(f"sum_exp_total_{node_id}", sum_var)
    block.add_component(
        f"sum_exp_total_constraint_{node_id}",
        backend.Constraint(expr=sum_var == sum(exp_var[index] for index in sub_index)),
    )
    log_var = backend.Var(
        bounds=(
            min(piecewise_terms.log_curve.y_points),
            max(piecewise_terms.log_curve.y_points),
        )
    )
    block.add_component(f"sum_log_var_{node_id}", log_var)
    block.add_component(
        f"sum_log_piecewise_{node_id}",
        backend.Piecewise(
            log_var,
            sum_var,
            pw_pts=list(piecewise_terms.log_curve.x_points),
            pw_constr_type="EQ",
            pw_repn="DCC",
            f_rule=list(piecewise_terms.log_curve.y_points),
        ),
    )
    block.add_component(
        f"sum_output_{node_id}",
        backend.Constraint(expr=block.node_out[node_id] == max_value + log_var),
    )


def _histogram_log_density(*, breaks: Sequence[float], densities: Sequence[float], value: float) -> float:
    for density, upper_bound in zip(
        [densities[0], *densities, densities[-1]],
        [*breaks, math.inf],
        strict=True,
    ):
        if upper_bound > value:
            return math.log(max(density, 1e-12))
    return math.log(max(densities[-1], 1e-12))


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")
    return tuple(str(item) for item in value)


def require_pyomo_backend() -> Any:
    """Import Pyomo only when the generic TPM solve path is invoked."""

    try:
        return import_module("pyomo.environ")
    except ImportError as exc:  # pragma: no cover - depends on installation state
        raise SPNSolverDependencyUnavailableError(
            "Pyomo-backed SPN chance solving requires the project 'pyomo' dependency."
        ) from exc


