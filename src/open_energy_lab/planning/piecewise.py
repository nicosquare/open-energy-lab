"""Import-light solver-facing piecewise planning assembly helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from tpm.piecewise import (
    PiecewiseApproximationMetadata,
    load_piecewise_metadata,
)
from tpm.domains import TPMCompiledValidityRecord
from tpm.mio import condition_compiled_spflow_mio

DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR = -500.0
CURRENT_SPFLOW_MIO_SCHEMA_VERSION = "v2"
LEGACY_SPFLOW_MIO_SCHEMA_VERSION = "v1"
CURRENT_SPFLOW_MIO_PAYLOAD_FORMAT = "open-energy-lab-spflow-mio"
CURRENT_SPFLOW_MIO_COMPILER_VERSION = "spflow-v1-mio-v2"
LEGACY_SPFLOW_MIO_COMPILER_VERSION = "spflow-v1-mio-v1"
CURRENT_SPFLOW_BACKEND_API_VERSION = "1.1.0"
CURRENT_SPFLOW_BREAKPOINT_COUNT = 5
CURRENT_SPFLOW_MIO_EPSILON = 1e-6
SUPPORTED_FIRST_RELEASE_DECISION_TYPES = ("battery", "solar")
SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES = (
    "continuous",
    "binary",
    "categorical",
    "mixed",
)


class PlanningMIOCompatibilityError(ValueError):
    """Raised when compiler output cannot be consumed by planning assembly."""


def validate_current_spflow_mio_payload(
    payload: Mapping[str, object],
    *,
    approximation_metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Validate the versioned current-SPFlow compiler contract for planning."""

    if not isinstance(payload, Mapping):
        raise PlanningMIOCompatibilityError("compiled MIO payload must be a mapping")
    compiled = {str(key): value for key, value in payload.items()}
    schema_version = compiled.get("schema_version")
    if schema_version not in {
        LEGACY_SPFLOW_MIO_SCHEMA_VERSION,
        CURRENT_SPFLOW_MIO_SCHEMA_VERSION,
    }:
        raise PlanningMIOCompatibilityError(
            "incompatible compiled MIO schema_version: expected 'v1' or 'v2', "
            f"found {schema_version!r}"
        )
    compiler_version = (
        LEGACY_SPFLOW_MIO_COMPILER_VERSION
        if schema_version == LEGACY_SPFLOW_MIO_SCHEMA_VERSION
        else CURRENT_SPFLOW_MIO_COMPILER_VERSION
    )
    expected_values = {
        "payload_format": CURRENT_SPFLOW_MIO_PAYLOAD_FORMAT,
        "compiler_version": compiler_version,
        "backend_compiler_version": compiler_version,
        "backend_generation": "current-spflow",
        "backend_api_version": CURRENT_SPFLOW_BACKEND_API_VERSION,
        "approximation_kind": "piecewise",
        "leaf_encoding_mode": "piecewise-log-density",
        "sum_encoding_mode": "weighted-logsumexp",
        "output_channels": 1,
        "num_repetitions": 1,
    }
    for field_name, expected in expected_values.items():
        actual = compiled.get(field_name)
        if actual != expected:
            raise PlanningMIOCompatibilityError(
                f"incompatible compiled MIO {field_name}: expected {expected!r}, "
                f"found {actual!r}"
            )

    breakpoint_policy = _required_mapping(
        compiled.get("breakpoint_policy"),
        field_name="compiled MIO breakpoint_policy",
    )
    if breakpoint_policy.get("breakpoint_count") != CURRENT_SPFLOW_BREAKPOINT_COUNT:
        raise PlanningMIOCompatibilityError(
            "incompatible compiled MIO breakpoint count: expected "
            f"{CURRENT_SPFLOW_BREAKPOINT_COUNT}, found "
            f"{breakpoint_policy.get('breakpoint_count')!r}"
        )
    if float(compiled.get("mio_epsilon", -1.0)) != CURRENT_SPFLOW_MIO_EPSILON:
        raise PlanningMIOCompatibilityError(
            "incompatible compiled MIO epsilon: expected "
            f"{CURRENT_SPFLOW_MIO_EPSILON}, found {compiled.get('mio_epsilon')!r}"
        )

    feature_schema = _required_mapping_sequence(
        compiled.get("feature_schema"),
        field_name="feature_schema",
    )
    nodes = _required_mapping_sequence(compiled.get("nodes"), field_name="nodes")
    node_ids = {int(node["id"]) for node in nodes}
    if len(node_ids) != len(nodes) or int(compiled.get("root_id", -1)) not in node_ids:
        raise PlanningMIOCompatibilityError(
            "compiled MIO nodes must use unique ids and contain root_id"
        )
    if schema_version == CURRENT_SPFLOW_MIO_SCHEMA_VERSION:
        validity_records = _required_mapping_sequence(
            compiled.get("compiled_validity"),
            field_name="compiled_validity",
        )
        try:
            loaded_validity = tuple(
                TPMCompiledValidityRecord.from_dict(record)
                for record in validity_records
            )
        except (TypeError, ValueError) as exc:
            raise PlanningMIOCompatibilityError(
                f"invalid compiled-v2 validity record: {exc}"
            ) from exc
        if any(
            record.payload_schema_version != CURRENT_SPFLOW_MIO_SCHEMA_VERSION
            or record.compiler_version != CURRENT_SPFLOW_MIO_COMPILER_VERSION
            for record in loaded_validity
        ):
            raise PlanningMIOCompatibilityError(
                "compiled-v2 validity records must match payload and compiler versions"
            )
        validity_by_index = {
            record.feature_index: record for record in loaded_validity
        }
        if len(validity_by_index) != len(loaded_validity):
            raise PlanningMIOCompatibilityError(
                "compiled-v2 validity feature indices must be unique"
            )
        continuous_curve_scopes: set[int] = set()
        for node in nodes:
            if node.get("type") != "normal":
                continue
            for curve in _required_mapping_sequence(
                node.get("curves"),
                field_name="normal.curves",
            ):
                feature_index = int(curve["scope"])
                continuous_curve_scopes.add(feature_index)
                if feature_index not in validity_by_index:
                    raise PlanningMIOCompatibilityError(
                        f"compiled-v2 normal scope {feature_index} lacks validity"
                    )
                record = validity_by_index[feature_index]
                if not 0 <= feature_index < len(feature_schema):
                    raise PlanningMIOCompatibilityError(
                        f"compiled-v2 validity scope {feature_index} is outside feature_schema"
                    )
                if str(feature_schema[feature_index].get("feature_name", "")) != (
                    record.feature_name
                ):
                    raise PlanningMIOCompatibilityError(
                        "compiled-v2 validity feature identity does not match feature_schema"
                    )
                if tuple(curve.get("breakpoints", ())) != record.model_breakpoints:
                    raise PlanningMIOCompatibilityError(
                        f"compiled-v2 model breakpoints for {record.feature_name!r} "
                        "do not match validity"
                    )
                if tuple(curve.get("physical_breakpoints", ())) != (
                    record.physical_breakpoints
                ):
                    raise PlanningMIOCompatibilityError(
                        f"compiled-v2 physical breakpoints for {record.feature_name!r} "
                        "do not match validity"
                    )
        if set(validity_by_index) != continuous_curve_scopes:
            raise PlanningMIOCompatibilityError(
                "compiled-v2 validity records must correspond exactly to retained "
                "continuous approximations"
            )
    elif "compiled_validity" in compiled:
        raise PlanningMIOCompatibilityError(
            "compiled-v1 payloads are normalized-only and must not claim physical validity"
        )

    if approximation_metadata is not None:
        metadata_compiler = approximation_metadata.get(
            "compiler_version",
            approximation_metadata.get("backend_compiler_version"),
        )
        if (
            metadata_compiler is not None
            and metadata_compiler != compiled["compiler_version"]
        ):
            raise PlanningMIOCompatibilityError(
                "artifact compiler metadata does not match the compiled MIO payload: "
                f"expected {metadata_compiler!r}, found {compiled['compiler_version']!r}"
            )
        metadata_epsilon = float(
            approximation_metadata.get("mio_epsilon", CURRENT_SPFLOW_MIO_EPSILON)
        )
        if metadata_epsilon != float(compiled["mio_epsilon"]):
            raise PlanningMIOCompatibilityError(
                "artifact MIO epsilon does not match the compiled payload"
            )

    return compiled


def build_current_spflow_planning_payload(
    compiled_payload: Mapping[str, object],
    *,
    approximation_metadata: Mapping[str, object],
    decision_features: Sequence[str],
    event_target_name: str,
    chance_limit_epsilon: float,
    shortfall_threshold: float,
    payload_locator: str | None,
) -> dict[str, object]:
    """Adapt solver-neutral compiler output into the planning chance handoff."""

    compiled = validate_current_spflow_mio_payload(
        compiled_payload,
        approximation_metadata=approximation_metadata,
    )
    normalized_decisions = tuple(str(name) for name in decision_features)
    feature_schema = _required_mapping_sequence(
        compiled["feature_schema"],
        field_name="feature_schema",
    )
    feature_by_name = {
        str(spec.get("feature_name", "")): spec for spec in feature_schema
    }
    feature_names = set(feature_by_name)
    missing_features = [
        name for name in (*normalized_decisions, str(event_target_name))
        if name not in feature_names
    ]
    if missing_features:
        raise PlanningMIOCompatibilityError(
            "compiled MIO feature_schema is missing planning features: "
            + ", ".join(missing_features)
        )
    event_spec = feature_by_name[str(event_target_name)]
    event_values = tuple(
        event_spec.get("ordering") or event_spec.get("discrete_values") or ()
    )
    if event_spec.get("feature_type") != "binary" or event_values != (0.0, 1.0):
        raise PlanningMIOCompatibilityError(
            "compiled MIO event target must be binary with ordering (0.0, 1.0)"
        )

    return {
        "source": "current-spflow-mio-compiler",
        "payload_locator": payload_locator,
        "decision_features": list(normalized_decisions),
        "chance_limit_epsilon": float(chance_limit_epsilon),
        "target_threshold": float(shortfall_threshold),
        "shortfall_threshold": float(shortfall_threshold),
        "event_target_name": str(event_target_name),
        "feature_schema": [dict(spec) for spec in feature_schema],
        "fitted_artifact_schema_version": (
            "v3" if compiled["schema_version"] == "v2" else "v2"
        ),
        "compiled_validity": list(compiled.get("compiled_validity", ())),
        "sum_encoding_mode": "piecewise",
        "compiler_version": compiled["compiler_version"],
        "compiler_schema_version": compiled["schema_version"],
        "compiled_mio": compiled,
        "conditional_models": {
            "numerator_model": _condition_compiled_mio(
                compiled,
                decision_features=normalized_decisions,
                event_target_name=str(event_target_name),
                include_event=True,
            ),
            "denominator_model": _condition_compiled_mio(
                compiled,
                decision_features=normalized_decisions,
                event_target_name=str(event_target_name),
                include_event=False,
            ),
        },
    }


def _condition_compiled_mio(
    compiled: Mapping[str, object],
    *,
    decision_features: tuple[str, ...],
    event_target_name: str,
    include_event: bool,
) -> dict[str, object]:
    try:
        return condition_compiled_spflow_mio(
            compiled,
            decision_features=decision_features,
            event_target_name=event_target_name,
            event_value_index=1 if include_event else None,
            compatibility_mode="planning-v1",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanningMIOCompatibilityError(str(exc)) from exc


def _required_mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise PlanningMIOCompatibilityError(f"{field_name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _required_mapping_sequence(
    value: object,
    *,
    field_name: str,
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise PlanningMIOCompatibilityError(f"{field_name} must be a sequence")
    normalized = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise PlanningMIOCompatibilityError(
                f"{field_name}[{index}] must be a mapping"
            )
        normalized.append({str(key): nested for key, nested in item.items()})
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class PiecewiseCurveSpec:
    """One solver-ready piecewise curve specification."""

    x_points: tuple[float, ...]
    y_points: tuple[float, ...]
    domain_lower_bound: float
    domain_upper_bound: float
    unbounded_domain_var: bool = False

    def __post_init__(self) -> None:
        x_points = tuple(float(point) for point in self.x_points)
        y_points = tuple(float(point) for point in self.y_points)
        if len(x_points) != len(y_points):
            raise ValueError("piecewise curve x_points and y_points must align")
        if len(x_points) < 2:
            raise ValueError("piecewise curve specs require at least two points")
        if any(
            right < left for left, right in zip(x_points, x_points[1:], strict=False)
        ):
            raise ValueError("piecewise curve x_points must be non-decreasing")
        if x_points[-1] <= x_points[0]:
            raise ValueError("piecewise curve x_points must span a positive domain")
        object.__setattr__(self, "x_points", x_points)
        object.__setattr__(self, "y_points", y_points)

        domain_lower_bound = float(self.domain_lower_bound)
        domain_upper_bound = float(self.domain_upper_bound)
        if domain_lower_bound > domain_upper_bound:
            raise ValueError("piecewise curve domain bounds must be ordered")
        object.__setattr__(self, "domain_lower_bound", domain_lower_bound)
        object.__setattr__(self, "domain_upper_bound", domain_upper_bound)


@dataclass(frozen=True, slots=True)
class PiecewisePlanningTerms:
    """Deterministic planning-facing view of canonical TPM piecewise metadata."""

    decision_features: tuple[str, ...]
    decision_feature_types: Mapping[str, str]
    approximation_kind: str
    leaf_encoding_mode: str
    sum_encoding_mode: str
    breakpoint_policy: Mapping[str, object]
    exp_breakpoints: tuple[float, ...]
    exp_values: tuple[float, ...]
    log_breakpoints: tuple[float, ...]
    log_values: tuple[float, ...]
    exp_curve: PiecewiseCurveSpec
    log_curve: PiecewiseCurveSpec
    max_terms: int
    mio_epsilon: float
    fit_numeric_tolerance: float
    query_numeric_tolerance: float
    legacy_reference_paths: tuple[str, ...]


def build_piecewise_planning_terms(
    approximation_metadata: Mapping[str, object] | PiecewiseApproximationMetadata,
    *,
    max_terms: int = 2,
    decision_features: tuple[str, ...] = (),
    decision_feature_types: Mapping[str, str] | None = None,
) -> PiecewisePlanningTerms:
    """Resolve deterministic solver-facing approximation terms from TPM metadata."""

    resolved_metadata = load_piecewise_metadata(approximation_metadata)
    max_terms = int(max_terms)
    if max_terms < 1:
        raise ValueError("max_terms must be at least 1")
    normalized_decision_features, normalized_decision_feature_types = (
        validate_first_release_decision_features(
            decision_features,
            decision_feature_types=decision_feature_types,
        )
    )

    breakpoint_policy = resolved_metadata.breakpoint_policy
    exp_breakpoints = breakpoint_policy.exp_breakpoints()
    exp_values = breakpoint_policy.exp_values()
    log_breakpoints = breakpoint_policy.log_breakpoints(max_terms=max_terms)
    log_values = breakpoint_policy.log_values(max_terms=max_terms)
    return PiecewisePlanningTerms(
        decision_features=normalized_decision_features,
        decision_feature_types=normalized_decision_feature_types,
        approximation_kind=resolved_metadata.approximation_kind,
        leaf_encoding_mode=resolved_metadata.leaf_encoding_mode,
        sum_encoding_mode=resolved_metadata.sum_encoding_mode,
        breakpoint_policy=breakpoint_policy.to_dict(),
        exp_breakpoints=exp_breakpoints,
        exp_values=exp_values,
        log_breakpoints=log_breakpoints,
        log_values=log_values,
        exp_curve=build_exponential_piecewise_curve(
            resolved_metadata,
            domain_floor=DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR,
        ),
        log_curve=build_logarithm_piecewise_curve(
            resolved_metadata,
            max_terms=max_terms,
        ),
        max_terms=max_terms,
        mio_epsilon=resolved_metadata.mio_epsilon,
        fit_numeric_tolerance=resolved_metadata.fit_numeric_tolerance,
        query_numeric_tolerance=resolved_metadata.query_numeric_tolerance,
        legacy_reference_paths=resolved_metadata.legacy_reference_paths,
    )


def validate_first_release_decision_features(
    decision_features: tuple[str, ...] | list[str],
    *,
    decision_feature_types: Mapping[str, str] | None = None,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Normalize and validate the first-release planning decision-variable set."""

    normalized_decision_features = tuple(str(feature_name) for feature_name in decision_features)
    if any(not feature_name for feature_name in normalized_decision_features):
        raise ValueError("decision_features must contain non-empty names")
    if len(set(normalized_decision_features)) != len(normalized_decision_features):
        raise ValueError("decision_features must be unique")
    for feature_name in normalized_decision_features:
        if any(
            feature_name == decision_scope or feature_name.startswith(f"{decision_scope}_")
            for decision_scope in SUPPORTED_FIRST_RELEASE_DECISION_TYPES
        ):
            continue
        raise ValueError(
            f"{feature_name!r} is outside the first-release planning scope; "
            "expected battery/solar decision features"
        )

    normalized_decision_feature_types: dict[str, str] = {}
    if decision_feature_types is not None:
        normalized_decision_feature_types = {
            str(feature_name): str(feature_type)
            for feature_name, feature_type in decision_feature_types.items()
        }
        if set(normalized_decision_feature_types) != set(normalized_decision_features):
            raise ValueError(
                "decision_feature_types must define exactly one type for each "
                "decision feature"
            )
        for feature_name, feature_type in normalized_decision_feature_types.items():
            if feature_type not in SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES:
                raise ValueError(
                    f"{feature_name} uses unsupported decision_variable_type "
                    f"{feature_type!r}; expected one of "
                    f"{SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES!r}"
                )

    return normalized_decision_features, normalized_decision_feature_types


def build_exponential_piecewise_curve(
    approximation_metadata: Mapping[str, object] | PiecewiseApproximationMetadata,
    *,
    domain_floor: float = DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR,
) -> PiecewiseCurveSpec:
    """Build the canonical solver-ready `exp(x)` piecewise curve."""

    resolved_metadata = load_piecewise_metadata(approximation_metadata)
    exp_breakpoints = resolved_metadata.breakpoint_policy.exp_breakpoints()
    exp_values = resolved_metadata.breakpoint_policy.exp_values()
    domain_floor = float(domain_floor)
    if domain_floor >= exp_breakpoints[0]:
        raise ValueError(
            "domain_floor must stay below the first exponential breakpoint"
        )
    return PiecewiseCurveSpec(
        x_points=(domain_floor, exp_breakpoints[0], *exp_breakpoints),
        y_points=(0.0, 0.0, *exp_values),
        domain_lower_bound=domain_floor,
        domain_upper_bound=0.0,
        unbounded_domain_var=True,
    )


def build_logarithm_piecewise_curve(
    approximation_metadata: Mapping[str, object] | PiecewiseApproximationMetadata,
    *,
    max_terms: int,
) -> PiecewiseCurveSpec:
    """Build the canonical solver-ready `log(x)` piecewise curve."""

    resolved_metadata = load_piecewise_metadata(approximation_metadata)
    max_terms = int(max_terms)
    if max_terms < 1:
        raise ValueError("max_terms must be at least 1")
    log_breakpoints = resolved_metadata.breakpoint_policy.log_breakpoints(
        max_terms=max_terms
    )
    return PiecewiseCurveSpec(
        x_points=log_breakpoints,
        y_points=resolved_metadata.breakpoint_policy.log_values(max_terms=max_terms),
        domain_lower_bound=log_breakpoints[0],
        domain_upper_bound=log_breakpoints[-1],
    )


__all__ = [
    "DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR",
    "PiecewiseCurveSpec",
    "PiecewisePlanningTerms",
    "SUPPORTED_FIRST_RELEASE_DECISION_TYPES",
    "SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES",
    "build_exponential_piecewise_curve",
    "build_logarithm_piecewise_curve",
    "build_piecewise_planning_terms",
    "validate_first_release_decision_features",
]
