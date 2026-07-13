"""Import-light solver-facing piecewise planning assembly helpers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from open_energy_lab.tpm.piecewise import (
    PiecewiseApproximationMetadata,
    load_piecewise_metadata,
)

DEFAULT_EXP_PIECEWISE_DOMAIN_FLOOR = -500.0
SUPPORTED_FIRST_RELEASE_DECISION_TYPES = ("battery", "solar")
SUPPORTED_FIRST_RELEASE_DECISION_VARIABLE_TYPES = (
    "continuous",
    "binary",
    "categorical",
    "mixed",
)


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
