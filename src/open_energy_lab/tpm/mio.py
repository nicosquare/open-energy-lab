"""Pyomo-facing SPN-to-MIO encoding helpers for serialized TPM payloads."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from .artifact import TPMArtifact, load_tpm_artifact
from .features import TPMFeatureSpec, load_feature_schema
from .optional_spflow import build_spn_mip_payload
from .piecewise import build_histogram_piecewise_points
from .piecewise import load_piecewise_metadata


_SUM_BIG_M = 100.0
_DEFAULT_EXP_DOMAIN_FLOOR = -500.0


@dataclass(frozen=True, slots=True)
class SPNPiecewiseCurveSpec:
    x_points: tuple[float, ...]
    y_points: tuple[float, ...]
    domain_lower_bound: float
    domain_upper_bound: float
    unbounded_domain_var: bool = False


@dataclass(frozen=True, slots=True)
class SPNModelingTerms:
    approximation_kind: str
    leaf_encoding_mode: str
    sum_encoding_mode: str
    exp_curve: SPNPiecewiseCurveSpec
    log_curve: SPNPiecewiseCurveSpec
    max_terms: int
    mio_epsilon: float
    fit_numeric_tolerance: float
    query_numeric_tolerance: float


class SPNSolverDependencyUnavailableError(ImportError):
    """Raised when solving one SPN chance model requires Pyomo but it is unavailable."""


class SPNSolverUnavailableError(RuntimeError):
    """Raised when one requested solver cannot be used for SPN chance solving."""


@dataclass(frozen=True, slots=True)
class SPNSolveConfig:
    solver_name: str = "gurobi"
    numeric_tolerance: float = 1e-9
    time_limit_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class SPNSolveSummary:
    problem_id: str
    status: str
    selected_design: Mapping[str, object]
    objective_value: float | None
    estimated_event_probability: float | None
    estimated_shortfall_risk: float | None
    chance_limit_epsilon: float
    solver_metadata: Mapping[str, object]


def build_spn_chance_model(
    backend: Any,
    *,
    problem_id: str,
    spn_payload: Mapping[str, object],
    cost_terms: Mapping[str, float],
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
        )
    )
    feature_by_name = {spec.feature_name: spec for spec in feature_schema}
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
    model._open_energy_lab_feature_by_name = feature_by_name
    model._open_energy_lab_decision_variables = {}
    model._open_energy_lab_decision_decoders = {}

    total_cost = 0.0
    for feature_name in decision_features:
        if feature_name not in feature_by_name:
            raise ValueError(f"decision feature {feature_name!r} not present in feature_schema")
        feature_spec = feature_by_name[feature_name]
        coefficient = float(cost_terms[feature_name])
        decision_payload = _add_decision_variable(
            backend,
            model,
            feature_spec=feature_spec,
            feature_name=feature_name,
        )
        model._open_energy_lab_decision_variables[feature_name] = decision_payload
        model._open_energy_lab_decision_decoders[feature_name] = _decision_decoder(feature_spec)
        total_cost += coefficient * decision_payload["cost_expression"]

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
        decision_variables=model._open_energy_lab_decision_variables,
        sum_encoding_mode=sum_encoding_mode,
        piecewise_terms=piecewise_terms,
    )
    denominator_root = _encode_serialized_spn(
        backend,
        denominator_block,
        model=model,
        spn_model=denominator_model,
        feature_by_name=feature_by_name,
        decision_variables=model._open_energy_lab_decision_variables,
        sum_encoding_mode=sum_encoding_mode,
        piecewise_terms=piecewise_terms,
    )

    chance_limit_log = math.log(max(float(chance_limit_epsilon), float(numeric_tolerance)))
    model.chance_constraint = backend.Constraint(
        expr=numerator_root - denominator_root <= chance_limit_log
    )
    model.total_cost = backend.Objective(expr=total_cost, sense=backend.minimize)
    model._open_energy_lab_risk_log_numerator = numerator_root
    model._open_energy_lab_risk_log_denominator = denominator_root
    model._open_energy_lab_chance_limit_epsilon = float(chance_limit_epsilon)
    model._open_energy_lab_sum_encoding_mode = sum_encoding_mode
    return model


def build_spn_chance_model_from_artifact(
    backend: Any,
    *,
    artifact: TPMArtifact | str | Path | Mapping[str, object],
    problem_id: str,
    decision_features: Sequence[str],
    cost_terms: Mapping[str, float],
    chance_limit_epsilon: float,
    target_threshold: float | None = None,
    numeric_tolerance: float = 1e-9,
    piecewise_terms: object | None = None,
) -> object:
    """Build one generic SPN chance-constrained model directly from a TPM artifact."""

    resolved_artifact = _load_artifact(artifact)
    resolved_decision_features = tuple(str(name) for name in decision_features)
    if target_threshold is None:
        resolved_target_threshold = float(
            resolved_artifact.target_definition.get("threshold_default", 0.0)
        )
    else:
        resolved_target_threshold = float(target_threshold)

    spn_payload = build_spn_mip_payload(
        resolved_artifact,
        decision_features=resolved_decision_features,
        chance_limit_epsilon=float(chance_limit_epsilon),
        target_threshold=resolved_target_threshold,
    )
    if spn_payload is None:
        raise ValueError(
            "TPM artifact does not expose a serialized SPN MIO payload for direct chance-model assembly"
        )

    resolved_piecewise_terms = (
        piecewise_terms
        if piecewise_terms is not None
        else build_spn_modeling_terms(
            resolved_artifact.approximation_metadata,
            max_terms=infer_max_sum_terms(spn_payload),
        )
    )
    return build_spn_chance_model(
        backend,
        problem_id=problem_id,
        spn_payload=spn_payload,
        cost_terms=cost_terms,
        chance_limit_epsilon=float(chance_limit_epsilon),
        numeric_tolerance=float(numeric_tolerance),
        piecewise_terms=resolved_piecewise_terms,
    )


def solve_spn_chance_model(
    model: object,
    *,
    backend: Any | None = None,
    solve_config: SPNSolveConfig | None = None,
) -> SPNSolveSummary:
    """Solve one already-built SPN chance model with Pyomo and decode the result."""

    resolved_backend = backend if backend is not None else require_pyomo_backend()
    resolved_config = solve_config or SPNSolveConfig()
    solver_factory = getattr(resolved_backend, "SolverFactory", None)
    if solver_factory is None:
        raise SPNSolverUnavailableError(
            "pyomo backend does not expose SolverFactory for SPN chance solving"
        )

    try:
        solver = solver_factory(resolved_config.solver_name)
    except Exception as exc:  # pragma: no cover - backend specific
        raise SPNSolverUnavailableError(str(exc)) from exc
    if not _solver_is_available(solver):
        raise SPNSolverUnavailableError(
            f"solver {resolved_config.solver_name!r} is unavailable"
        )

    _apply_time_limit_if_supported(
        solver,
        time_limit_seconds=resolved_config.time_limit_seconds,
    )
    results = solver.solve(model, tee=False)
    diagnostics = _solver_result_metadata(results)
    if _solver_result_reports_infeasible(results):
        return SPNSolveSummary(
            problem_id=str(getattr(model, "name", "spn-mio-problem")),
            status="infeasible",
            selected_design={},
            objective_value=None,
            estimated_event_probability=None,
            estimated_shortfall_risk=None,
            chance_limit_epsilon=float(getattr(model, "_open_energy_lab_chance_limit_epsilon")),
            solver_metadata={
                "requested_solver_name": resolved_config.solver_name,
                "backend_module": getattr(resolved_backend, "__name__", resolved_backend.__class__.__name__),
                "backend_version": getattr(resolved_backend, "__version__", "unknown"),
                "status": "infeasible",
                "solve_execution_mode": "native-pyomo-solver",
                **diagnostics,
            },
        )

    solution = extract_spn_solution(
        model,
        backend=resolved_backend,
        numeric_tolerance=resolved_config.numeric_tolerance,
    )
    return SPNSolveSummary(
        problem_id=str(getattr(model, "name", "spn-mio-problem")),
        status="optimal",
        selected_design=_mapping(solution.get("selected_design"), field_name="selected_design"),
        objective_value=float(solution["objective_value"]),
        estimated_event_probability=float(solution["estimated_event_probability"]),
        estimated_shortfall_risk=float(solution["estimated_shortfall_risk"]),
        chance_limit_epsilon=float(getattr(model, "_open_energy_lab_chance_limit_epsilon")),
        solver_metadata={
            "requested_solver_name": resolved_config.solver_name,
            "backend_module": getattr(resolved_backend, "__name__", resolved_backend.__class__.__name__),
            "backend_version": getattr(resolved_backend, "__version__", "unknown"),
            "status": "optimal",
            "solve_execution_mode": "native-pyomo-solver",
            **diagnostics,
        },
    )


def solve_spn_chance_model_from_artifact(
    *,
    artifact: TPMArtifact | str | Path | Mapping[str, object],
    problem_id: str,
    decision_features: Sequence[str],
    cost_terms: Mapping[str, float],
    chance_limit_epsilon: float,
    target_threshold: float | None = None,
    numeric_tolerance: float = 1e-9,
    piecewise_terms: object | None = None,
    backend: Any | None = None,
    solve_config: SPNSolveConfig | None = None,
) -> SPNSolveSummary:
    """Build and solve one generic SPN chance-constrained model from a TPM artifact."""

    resolved_backend = backend if backend is not None else require_pyomo_backend()
    model = build_spn_chance_model_from_artifact(
        resolved_backend,
        artifact=artifact,
        problem_id=problem_id,
        decision_features=decision_features,
        cost_terms=cost_terms,
        chance_limit_epsilon=chance_limit_epsilon,
        target_threshold=target_threshold,
        numeric_tolerance=numeric_tolerance,
        piecewise_terms=piecewise_terms,
    )
    return solve_spn_chance_model(
        model,
        backend=resolved_backend,
        solve_config=solve_config,
    )


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

    decision_variables = getattr(model, "_open_energy_lab_decision_variables")
    feature_by_name = getattr(model, "_open_energy_lab_feature_by_name")
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
    numerator_log = float(value_function(model._open_energy_lab_risk_log_numerator))
    denominator_log = float(value_function(model._open_energy_lab_risk_log_denominator))
    estimated_risk = math.exp(min(0.0, numerator_log - denominator_log))
    return {
        "selected_design": selected_design,
        "objective_value": objective_value,
        "estimated_event_probability": estimated_risk,
        "estimated_shortfall_risk": estimated_risk,
        "numerator_log_likelihood": numerator_log,
        "denominator_log_likelihood": denominator_log,
    }


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


def build_spn_modeling_terms(
    approximation_metadata: Mapping[str, object],
    *,
    max_terms: int,
) -> SPNModelingTerms:
    """Build generic SPN modeling terms without planning-specific decision-scope validation."""

    resolved_metadata = load_piecewise_metadata(approximation_metadata)
    normalized_max_terms = int(max_terms)
    if normalized_max_terms < 1:
        raise ValueError("max_terms must be at least 1")
    breakpoint_policy = resolved_metadata.breakpoint_policy
    exp_breakpoints = breakpoint_policy.exp_breakpoints()
    exp_values = breakpoint_policy.exp_values()
    log_breakpoints = breakpoint_policy.log_breakpoints(max_terms=normalized_max_terms)
    log_values = breakpoint_policy.log_values(max_terms=normalized_max_terms)
    return SPNModelingTerms(
        approximation_kind=resolved_metadata.approximation_kind,
        leaf_encoding_mode=resolved_metadata.leaf_encoding_mode,
        sum_encoding_mode=resolved_metadata.sum_encoding_mode,
        exp_curve=SPNPiecewiseCurveSpec(
            x_points=(_DEFAULT_EXP_DOMAIN_FLOOR, exp_breakpoints[0], *exp_breakpoints),
            y_points=(0.0, 0.0, *exp_values),
            domain_lower_bound=_DEFAULT_EXP_DOMAIN_FLOOR,
            domain_upper_bound=0.0,
            unbounded_domain_var=True,
        ),
        log_curve=SPNPiecewiseCurveSpec(
            x_points=log_breakpoints,
            y_points=log_values,
            domain_lower_bound=log_breakpoints[0],
            domain_upper_bound=log_breakpoints[-1],
        ),
        max_terms=normalized_max_terms,
        mio_epsilon=resolved_metadata.mio_epsilon,
        fit_numeric_tolerance=resolved_metadata.fit_numeric_tolerance,
        query_numeric_tolerance=resolved_metadata.query_numeric_tolerance,
    )


def _add_decision_variable(
    backend: Any,
    model: object,
    *,
    feature_spec: TPMFeatureSpec,
    feature_name: str,
) -> dict[str, object]:
    if feature_spec.feature_type == "continuous":
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
        if discrete_values != (0.0, 1.0):
            raise ValueError(
                f"binary decision feature {feature_name!r} must use ordering (0.0, 1.0)"
            )
        return {
            "kind": "binary",
            "normalized_var": var,
            "cost_expression": var,
        }

    if feature_spec.feature_type == "categorical":
        categories = tuple(feature_spec.ordering or feature_spec.discrete_values)
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
            "cost_expression": 0.0,
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
        normalized_value = float(value_function(decision_payload["normalized_var"]))
        lower, upper = feature_spec.bounds or (0.0, 1.0)
        return lower + normalized_value * (upper - lower)

    if kind == "binary":
        normalized_value = float(value_function(decision_payload["normalized_var"]))
        return 1.0 if normalized_value >= 1.0 - numeric_tolerance else 0.0

    if kind == "categorical":
        category_values = tuple(decision_payload["category_values"])
        var = decision_payload["normalized_var"]
        best_index = max(
            range(len(category_values)),
            key=lambda index: float(value_function(var[index])),
        )
        return category_values[best_index]

    raise ValueError(f"unsupported decision payload kind {kind!r}")


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
        pw_repn="SOS2",
        f_rule=list(pw_y),
    )
    block.add_component(f"hist_leaf_piecewise_{node_id}", pw_constraint)


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
            rule=lambda _b, index: max_value <= weighted_terms[index] + _SUM_BIG_M * (1 - active[index]),
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
            pw_repn="SOS2",
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
            pw_repn="SOS2",
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


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): inner_value for key, inner_value in value.items()}


def _sequence(value: object, *, field_name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence")
    return tuple(value)


def _sequence_of_mappings(value: object, *, field_name: str) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of mappings")
    result: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} must contain only mappings")
        result.append(item)
    return tuple(result)


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")
    return tuple(str(item) for item in value)


def _float_sequence(value: object) -> tuple[float, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("expected a numeric sequence")
    return tuple(float(item) for item in value)


def _load_artifact(
    artifact: TPMArtifact | str | Path | Mapping[str, object],
) -> TPMArtifact:
    if isinstance(artifact, TPMArtifact):
        return artifact
    return load_tpm_artifact(artifact)


def require_pyomo_backend() -> Any:
    """Import Pyomo only when the generic TPM solve path is invoked."""

    try:
        return import_module("pyomo.environ")
    except ImportError as exc:  # pragma: no cover - depends on optional install state
        raise SPNSolverDependencyUnavailableError(
            "Pyomo-backed SPN chance solving requires the optional 'pyomo' dependency."
        ) from exc


def _solver_is_available(solver: object) -> bool:
    available = getattr(solver, "available", None)
    if not callable(available):
        return True
    try:
        return bool(available(exception_flag=False))
    except TypeError:
        return bool(available())


def _apply_time_limit_if_supported(solver: object, *, time_limit_seconds: float | None) -> None:
    if time_limit_seconds is None or not hasattr(solver, "options"):
        return
    options = getattr(solver, "options")
    if not isinstance(options, dict):
        return
    options.setdefault("timelimit", float(time_limit_seconds))


def _solver_result_reports_infeasible(results: object) -> bool:
    diagnostics = _solver_result_metadata(results)
    termination_condition = str(diagnostics.get("termination_condition", "")).lower()
    return "infeasible" in termination_condition


def _solver_result_metadata(results: object) -> dict[str, object]:
    solver_block = getattr(results, "solver", None)
    diagnostics: dict[str, object] = {}
    if solver_block is not None:
        status = getattr(solver_block, "status", None)
        termination_condition = getattr(solver_block, "termination_condition", None)
        if status is not None:
            diagnostics["solver_status"] = str(status)
        if termination_condition is not None:
            diagnostics["termination_condition"] = str(termination_condition)
    return diagnostics


__all__ = [
    "SPNModelingTerms",
    "SPNPiecewiseCurveSpec",
    "SPNSolveConfig",
    "SPNSolveSummary",
    "SPNSolverDependencyUnavailableError",
    "SPNSolverUnavailableError",
    "build_spn_chance_model_from_artifact",
    "build_spn_modeling_terms",
    "build_spn_chance_model",
    "extract_spn_solution",
    "infer_max_sum_terms",
    "require_pyomo_backend",
    "solve_spn_chance_model",
    "solve_spn_chance_model_from_artifact",
]
