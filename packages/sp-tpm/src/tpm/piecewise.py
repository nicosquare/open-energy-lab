"""Canonical TPM piecewise-approximation metadata and encoding helpers."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

DEFAULT_APPROXIMATION_KIND = "piecewise"
DEFAULT_LEAF_ENCODING_MODE = "histogram"
DEFAULT_SUM_ENCODING_MODE = "piecewise"
SUPPORTED_SUM_ENCODING_MODES = ("max", "piecewise")
DEFAULT_BREAKPOINT_POLICY_NAME = "legacy-logspace-v1"
DEFAULT_PIECEWISE_BREAKPOINT_COUNT = 5
DEFAULT_EXP_PROBABILITY_FLOOR = 1e-3
DEFAULT_MIO_EPSILON = 1e-6
DEFAULT_QUERY_NUMERIC_TOLERANCE = 1e-9
DEFAULT_EXP_BREAKPOINT_START = 0.3
CONDITIONAL_GUARD_POLICY_NAME = "zero-plateau-linear-transition-v1"
CONDITIONAL_GUARD_TRANSITION_WIDTH = 1e-3
CONDITIONAL_GUARD_DOMAIN_FLOOR = -500.0
LOGARITHM_ENDPOINT_POLICY_NAME = "arity-log-table-endpoint-exactification-v1"
CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS = (
    "legacy/old_tpm/src_py/tpm/spn/main.py",
    "legacy/old_tpm/src_py/tpm/spn/encoding.py",
    "legacy/old_tpm/src_py/utils/densities.py",
)


@dataclass(frozen=True, slots=True)
class PiecewiseBreakpointPolicy:
    """Deterministic breakpoint policy preserved from the legacy TPM path."""

    policy_name: str = DEFAULT_BREAKPOINT_POLICY_NAME
    piecewise_breakpoint_count: int = DEFAULT_PIECEWISE_BREAKPOINT_COUNT
    exp_probability_floor: float = DEFAULT_EXP_PROBABILITY_FLOOR
    exp_breakpoint_start: float = DEFAULT_EXP_BREAKPOINT_START

    def __post_init__(self) -> None:
        policy_name = str(self.policy_name)
        if not policy_name:
            raise ValueError("policy_name must be non-empty")
        object.__setattr__(self, "policy_name", policy_name)

        piecewise_breakpoint_count = int(self.piecewise_breakpoint_count)
        if piecewise_breakpoint_count < 2:
            raise ValueError("piecewise_breakpoint_count must be at least 2")
        object.__setattr__(
            self,
            "piecewise_breakpoint_count",
            piecewise_breakpoint_count,
        )

        exp_probability_floor = float(self.exp_probability_floor)
        if not 0.0 < exp_probability_floor < 1.0:
            raise ValueError("exp_probability_floor must be between 0 and 1")
        object.__setattr__(self, "exp_probability_floor", exp_probability_floor)

        exp_breakpoint_start = float(self.exp_breakpoint_start)
        if exp_breakpoint_start <= 0.0:
            raise ValueError("exp_breakpoint_start must be positive")
        object.__setattr__(self, "exp_breakpoint_start", exp_breakpoint_start)

    def to_dict(self) -> dict[str, object]:
        """Serialize the policy into the persisted JSON shape."""

        return {
            "policy_name": self.policy_name,
            "piecewise_breakpoint_count": self.piecewise_breakpoint_count,
            "exp_probability_floor": self.exp_probability_floor,
            "exp_breakpoint_start": self.exp_breakpoint_start,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PiecewiseBreakpointPolicy:
        """Load one persisted breakpoint policy."""

        if not isinstance(payload, Mapping):
            raise TypeError("breakpoint_policy must be a mapping")
        return cls(
            policy_name=str(payload.get("policy_name", DEFAULT_BREAKPOINT_POLICY_NAME)),
            piecewise_breakpoint_count=int(
                payload.get(
                    "piecewise_breakpoint_count",
                    DEFAULT_PIECEWISE_BREAKPOINT_COUNT,
                )
            ),
            exp_probability_floor=float(
                payload.get("exp_probability_floor", DEFAULT_EXP_PROBABILITY_FLOOR)
            ),
            exp_breakpoint_start=float(
                payload.get("exp_breakpoint_start", DEFAULT_EXP_BREAKPOINT_START)
            ),
        )

    def exp_breakpoints(self) -> tuple[float, ...]:
        """Build the legacy log-spaced exponential breakpoint grid."""

        max_magnitude = max(
            self.exp_breakpoint_start,
            -math.log(self.exp_probability_floor),
        )
        positive_points = _logspace(
            self.exp_breakpoint_start,
            max_magnitude,
            num=self.piecewise_breakpoint_count - 1,
        )
        points = [0.0, *positive_points]
        breakpoints = tuple(-value for value in reversed(points))
        return breakpoints[:-1] + (0.0,)

    def exp_values(self) -> tuple[float, ...]:
        """Return the matching `exp(x)` values for the legacy breakpoint grid."""

        return tuple(math.exp(value) for value in self.exp_breakpoints())

    def log_breakpoints(self, *, max_terms: int) -> tuple[float, ...]:
        """Build the legacy log-sum-exp input breakpoint grid."""

        max_terms = int(max_terms)
        if max_terms < 1:
            raise ValueError("max_terms must be at least 1")
        upper = max(1.0, float(max_terms))
        legacy_points = _logspace(
            1.0,
            upper,
            num=self.piecewise_breakpoint_count,
        )
        # ``exp(log(upper))`` may land one or more binary64 steps on either
        # side of an exactly representable integer arity.  Preserve every
        # legacy interior point and make only the closed solver-table endpoint
        # exact.  ``log_values`` remains binary64-identical because log of the
        # legacy endpoint rounds to the same value as log of ``upper``.
        return legacy_points[:-1] + (upper,)

    def log_values(self, *, max_terms: int) -> tuple[float, ...]:
        """Return the matching `log(x)` values for the legacy breakpoint grid."""

        return tuple(math.log(value) for value in self.log_breakpoints(max_terms=max_terms))


@dataclass(frozen=True, slots=True)
class PiecewiseApproximationMetadata:
    """Canonical solver-facing approximation contract for TPM artifacts."""

    approximation_kind: str = DEFAULT_APPROXIMATION_KIND
    leaf_encoding_mode: str = DEFAULT_LEAF_ENCODING_MODE
    sum_encoding_mode: str = DEFAULT_SUM_ENCODING_MODE
    breakpoint_policy: PiecewiseBreakpointPolicy = field(
        default_factory=PiecewiseBreakpointPolicy
    )
    mio_epsilon: float = DEFAULT_MIO_EPSILON
    fit_numeric_tolerance: float = DEFAULT_QUERY_NUMERIC_TOLERANCE
    query_numeric_tolerance: float = DEFAULT_QUERY_NUMERIC_TOLERANCE
    legacy_reference_paths: tuple[str, ...] = field(
        default_factory=lambda: CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS
    )

    def __post_init__(self) -> None:
        approximation_kind = str(self.approximation_kind)
        if approximation_kind != DEFAULT_APPROXIMATION_KIND:
            raise ValueError(
                "PiecewiseApproximationMetadata requires approximation_kind='piecewise'"
            )
        object.__setattr__(self, "approximation_kind", approximation_kind)

        leaf_encoding_mode = str(self.leaf_encoding_mode)
        if not leaf_encoding_mode:
            raise ValueError("leaf_encoding_mode must be non-empty")
        object.__setattr__(self, "leaf_encoding_mode", leaf_encoding_mode)

        sum_encoding_mode = str(self.sum_encoding_mode)
        if not sum_encoding_mode:
            raise ValueError("sum_encoding_mode must be non-empty")
        if sum_encoding_mode == "lower_tangent":
            raise ValueError("lower_tangent is not a supported TPM sum encoding")
        if sum_encoding_mode not in SUPPORTED_SUM_ENCODING_MODES:
            raise ValueError(
                "sum_encoding_mode must be one of "
                f"{SUPPORTED_SUM_ENCODING_MODES!r}"
            )
        object.__setattr__(self, "sum_encoding_mode", sum_encoding_mode)

        breakpoint_policy = self.breakpoint_policy
        if isinstance(breakpoint_policy, Mapping):
            breakpoint_policy = PiecewiseBreakpointPolicy.from_dict(breakpoint_policy)
        if not isinstance(breakpoint_policy, PiecewiseBreakpointPolicy):
            raise TypeError("breakpoint_policy must be a PiecewiseBreakpointPolicy")
        object.__setattr__(self, "breakpoint_policy", breakpoint_policy)

        mio_epsilon = float(self.mio_epsilon)
        if mio_epsilon <= 0.0:
            raise ValueError("mio_epsilon must be positive")
        object.__setattr__(self, "mio_epsilon", mio_epsilon)

        fit_numeric_tolerance = float(self.fit_numeric_tolerance)
        if fit_numeric_tolerance <= 0.0:
            raise ValueError("fit_numeric_tolerance must be positive")
        object.__setattr__(self, "fit_numeric_tolerance", fit_numeric_tolerance)

        query_numeric_tolerance = float(self.query_numeric_tolerance)
        if query_numeric_tolerance <= 0.0:
            raise ValueError("query_numeric_tolerance must be positive")
        object.__setattr__(self, "query_numeric_tolerance", query_numeric_tolerance)

        legacy_reference_paths = tuple(str(path) for path in self.legacy_reference_paths)
        if not legacy_reference_paths:
            raise ValueError("legacy_reference_paths must not be empty")
        if any(not path for path in legacy_reference_paths):
            raise ValueError("legacy_reference_paths must not contain empty entries")
        object.__setattr__(self, "legacy_reference_paths", legacy_reference_paths)

    def to_dict(self) -> dict[str, object]:
        """Serialize the approximation metadata into a persisted mapping."""

        return {
            "approximation_kind": self.approximation_kind,
            "leaf_encoding_mode": self.leaf_encoding_mode,
            "sum_encoding_mode": self.sum_encoding_mode,
            "breakpoint_policy": self.breakpoint_policy.to_dict(),
            "mio_epsilon": self.mio_epsilon,
            "fit_numeric_tolerance": self.fit_numeric_tolerance,
            "query_numeric_tolerance": self.query_numeric_tolerance,
            "tolerance": self.query_numeric_tolerance,
            "legacy_reference_paths": list(self.legacy_reference_paths),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PiecewiseApproximationMetadata:
        """Load one persisted approximation metadata mapping."""

        if not isinstance(payload, Mapping):
            raise TypeError("approximation_metadata must be a mapping")
        tolerance = payload.get("tolerance", DEFAULT_QUERY_NUMERIC_TOLERANCE)
        return cls(
            approximation_kind=str(
                payload.get("approximation_kind", DEFAULT_APPROXIMATION_KIND)
            ),
            leaf_encoding_mode=str(
                payload.get("leaf_encoding_mode", DEFAULT_LEAF_ENCODING_MODE)
            ),
            sum_encoding_mode=str(
                payload.get("sum_encoding_mode", DEFAULT_SUM_ENCODING_MODE)
            ),
            breakpoint_policy=PiecewiseBreakpointPolicy.from_dict(
                _mapping_or_default(payload.get("breakpoint_policy"))
            ),
            mio_epsilon=float(payload.get("mio_epsilon", DEFAULT_MIO_EPSILON)),
            fit_numeric_tolerance=float(
                payload.get("fit_numeric_tolerance", tolerance)
            ),
            query_numeric_tolerance=float(
                payload.get("query_numeric_tolerance", tolerance)
            ),
            legacy_reference_paths=_string_sequence(
                payload.get(
                    "legacy_reference_paths",
                    CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS,
                )
            ),
        )


def build_piecewise_metadata(
    *,
    fit_numeric_tolerance: float,
    query_numeric_tolerance: float = DEFAULT_QUERY_NUMERIC_TOLERANCE,
    leaf_encoding_mode: str = DEFAULT_LEAF_ENCODING_MODE,
    sum_encoding_mode: str = DEFAULT_SUM_ENCODING_MODE,
    breakpoint_policy: PiecewiseBreakpointPolicy | Mapping[str, object] | None = None,
    mio_epsilon: float = DEFAULT_MIO_EPSILON,
    legacy_reference_paths: Sequence[str] = CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS,
) -> PiecewiseApproximationMetadata:
    """Construct the canonical first-release piecewise metadata contract."""

    resolved_policy: PiecewiseBreakpointPolicy | Mapping[str, object]
    if breakpoint_policy is None:
        resolved_policy = PiecewiseBreakpointPolicy()
    else:
        resolved_policy = breakpoint_policy

    return PiecewiseApproximationMetadata(
        leaf_encoding_mode=leaf_encoding_mode,
        sum_encoding_mode=sum_encoding_mode,
        breakpoint_policy=resolved_policy,
        mio_epsilon=mio_epsilon,
        fit_numeric_tolerance=fit_numeric_tolerance,
        query_numeric_tolerance=query_numeric_tolerance,
        legacy_reference_paths=tuple(str(path) for path in legacy_reference_paths),
    )


def load_piecewise_metadata(
    payload: Mapping[str, object] | PiecewiseApproximationMetadata,
) -> PiecewiseApproximationMetadata:
    """Load persisted approximation metadata into the canonical dataclass."""

    if isinstance(payload, PiecewiseApproximationMetadata):
        return payload
    return PiecewiseApproximationMetadata.from_dict(payload)


def resolve_query_numeric_tolerance(
    payload: Mapping[str, object] | PiecewiseApproximationMetadata,
    *,
    default: float = DEFAULT_QUERY_NUMERIC_TOLERANCE,
) -> float:
    """Resolve the query tolerance documented by the artifact metadata."""

    try:
        return load_piecewise_metadata(payload).query_numeric_tolerance
    except (TypeError, ValueError):
        return float(default)


def build_histogram_piecewise_points(
    breaks: Sequence[float],
    values: Sequence[float],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Double histogram endpoints the same way the legacy Pyomo encoder expects."""

    if len(breaks) != len(values) + 1:
        raise ValueError("breaks must contain exactly one more value than values")
    normalized_breaks = tuple(float(point) for point in breaks)
    if any(
        right <= left
        for left, right in zip(normalized_breaks, normalized_breaks[1:], strict=False)
    ):
        raise ValueError("breaks must be strictly increasing")

    normalized_values = tuple(float(value) for value in values)
    doubled_breakpoints = [normalized_breaks[0]]
    for point in normalized_breaks[1:-1]:
        doubled_breakpoints.extend((point, point))
    doubled_breakpoints.append(normalized_breaks[-1])

    doubled_values: list[float] = []
    for value in normalized_values:
        doubled_values.extend((value, value))

    return tuple(doubled_breakpoints), tuple(doubled_values)


def build_logsumexp_piecewise_spec(
    *,
    max_terms: int,
    breakpoint_policy: PiecewiseBreakpointPolicy | Mapping[str, object] | None = None,
) -> dict[str, tuple[float, ...]]:
    """Build deterministic breakpoint/value tables for solver-facing log-sum-exp."""

    policy = (
        PiecewiseBreakpointPolicy.from_dict(breakpoint_policy)
        if isinstance(breakpoint_policy, Mapping)
        else breakpoint_policy
    ) or PiecewiseBreakpointPolicy()
    return {
        "exp_x_points": policy.exp_breakpoints(),
        "exp_y_points": policy.exp_values(),
        "log_x_points": policy.log_breakpoints(max_terms=max_terms),
        "log_y_points": policy.log_values(max_terms=max_terms),
    }


def resolve_guarded_exponential_spec(
    *,
    base_x_points: Sequence[float],
    base_y_points: Sequence[float],
    domain_floor: float = CONDITIONAL_GUARD_DOMAIN_FLOOR,
    probability_floor: float = DEFAULT_EXP_PROBABILITY_FLOOR,
    transition_width: float = CONDITIONAL_GUARD_TRANSITION_WIDTH,
) -> dict[str, object]:
    """Resolve the single-valued conditional exponential guard.

    The persisted base curve remains unchanged from the end of the transition
    onward.  The guard is exactly zero through ``log(probability_floor)`` and
    joins the base curve over one fixed-width linear segment.
    """

    base_x = _strictly_increasing_finite_points(
        base_x_points, field_name="base exponential x points"
    )
    base_y = _finite_points(
        base_y_points, field_name="base exponential y points"
    )
    if len(base_x) != len(base_y):
        raise ValueError("base exponential points and values must align")
    if any(right < left for left, right in zip(base_y, base_y[1:])):
        raise ValueError("base exponential values must be monotone nondecreasing")
    if base_x[-1] != 0.0 or base_y[-1] != 1.0:
        raise ValueError("base exponential curve must end exactly at (0, 1)")
    normalized_probability_floor = float(probability_floor)
    if not math.isfinite(normalized_probability_floor) or not (
        0.0 < normalized_probability_floor < 1.0
    ):
        raise ValueError("guard probability_floor must be finite and between zero and one")
    cutoff = math.log(normalized_probability_floor)
    width = float(transition_width)
    if not math.isfinite(width) or width <= 0.0:
        raise ValueError("guard transition_width must be positive and finite")
    transition_end = cutoff + width
    normalized_domain_floor = float(domain_floor)
    if not math.isfinite(normalized_domain_floor) or normalized_domain_floor >= cutoff:
        raise ValueError("guard domain_floor must be finite and below the cutoff")
    if base_x[0] > transition_end or base_x[-1] < transition_end:
        raise ValueError("base exponential curve must cover the guard transition")
    transition_value = piecewise_linear_interpolate(
        transition_end,
        x_points=base_x,
        y_points=base_y,
    )
    retained = tuple(
        (x_value, y_value)
        for x_value, y_value in zip(base_x, base_y, strict=True)
        if x_value > transition_end
    )
    resolved_x = (
        normalized_domain_floor,
        cutoff,
        transition_end,
        *(value[0] for value in retained),
    )
    resolved_y = (
        0.0,
        0.0,
        transition_value,
        *(value[1] for value in retained),
    )
    _strictly_increasing_finite_points(
        resolved_x, field_name="resolved guarded exponential x points"
    )
    if any(right < left for left, right in zip(resolved_y, resolved_y[1:])):
        raise ValueError(
            "resolved guarded exponential values must be monotone nondecreasing"
        )
    return {
        "guard_policy": CONDITIONAL_GUARD_POLICY_NAME,
        "guard_probability_floor": normalized_probability_floor,
        "guard_cutoff_log": cutoff,
        "guard_cutoff_boundary": "plateau-inclusive",
        "guard_transition_width_log": width,
        "guard_transition_end_log": transition_end,
        "guard_post_transition": "base-pwl-unchanged",
        "exp_domain_floor": normalized_domain_floor,
        "base_exp_x_points": base_x,
        "base_exp_y_points": base_y,
        "exp_x_points": resolved_x,
        "exp_y_points": resolved_y,
    }


def guarded_exponential_points(
    configuration: Mapping[str, object],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Validate and return one persisted canonical guarded table."""

    if not isinstance(configuration, Mapping):
        raise TypeError("guarded exponential configuration must be a mapping")
    required = {
        "guard_policy",
        "guard_probability_floor",
        "guard_cutoff_log",
        "guard_cutoff_boundary",
        "guard_transition_width_log",
        "guard_transition_end_log",
        "guard_post_transition",
        "exp_domain_floor",
        "base_exp_x_points",
        "base_exp_y_points",
        "exp_x_points",
        "exp_y_points",
    }
    missing = sorted(required - set(configuration))
    if missing:
        raise ValueError(
            "guarded exponential configuration is missing: " + ", ".join(missing)
        )
    if configuration["guard_policy"] != CONDITIONAL_GUARD_POLICY_NAME:
        raise ValueError(
            "guarded exponential guard_policy must be "
            f"{CONDITIONAL_GUARD_POLICY_NAME!r}"
        )
    if configuration["guard_cutoff_boundary"] != "plateau-inclusive":
        raise ValueError("guarded exponential cutoff boundary must be plateau-inclusive")
    if configuration["guard_post_transition"] != "base-pwl-unchanged":
        raise ValueError("guarded exponential must preserve the base PWL after transition")
    expected = resolve_guarded_exponential_spec(
        base_x_points=configuration["base_exp_x_points"],
        base_y_points=configuration["base_exp_y_points"],
        domain_floor=float(configuration["exp_domain_floor"]),
        probability_floor=float(configuration["guard_probability_floor"]),
        transition_width=float(configuration["guard_transition_width_log"]),
    )
    for name in required:
        actual = configuration[name]
        expected_value = expected[name]
        if isinstance(expected_value, tuple):
            actual = tuple(float(value) for value in actual)
        if actual != expected_value:
            raise ValueError(
                f"guarded exponential field {name} differs from its canonical resolution"
            )
    return expected["exp_x_points"], expected["exp_y_points"]


def _guarded_exponential_evaluator(configuration):
    """Validate a persisted curve once for repeated scalar evaluations.

    Compilation evaluates one fixed curve for every Sum edge. Revalidating the
    complete serialized policy per edge is unnecessary; the returned closure
    owns immutable points and preserves the public evaluator's arithmetic.
    """
    from bisect import bisect_right
    points, values = guarded_exponential_points(configuration)
    slopes = tuple((b - a) / (right - left)
                   for left, right, a, b in zip(points, points[1:], values, values[1:]))
    def evaluate(value):
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError('guarded exponential input must be finite')
        if normalized < points[0] or normalized > points[-1]:
            raise ValueError(f'guarded exponential input {normalized} is outside [{points[0]}, {points[-1]}]')
        if normalized == points[-1]:
            return values[-1]
        if normalized == points[0]:
            return values[0]
        index = bisect_right(points, normalized) - 1
        return values[index] + slopes[index] * (normalized - points[index])
    return evaluate


def evaluate_guarded_exponential(
    value: float,
    *,
    configuration: Mapping[str, object],
) -> float:
    """Evaluate the exact guarded table persisted by a conditional pair."""

    x_points, y_points = guarded_exponential_points(configuration)
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError("guarded exponential input must be finite")
    if normalized < x_points[0] or normalized > x_points[-1]:
        raise ValueError(
            f"guarded exponential input {normalized} is outside "
            f"[{x_points[0]}, {x_points[-1]}]"
        )
    return piecewise_linear_interpolate(
        normalized,
        x_points=x_points,
        y_points=y_points,
    )


def _finite_points(
    values: Sequence[float], *, field_name: str
) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise TypeError(f"{field_name} must be a sequence")
    normalized = tuple(float(value) for value in values)
    if len(normalized) < 2 or any(not math.isfinite(value) for value in normalized):
        raise ValueError(f"{field_name} must contain at least two finite values")
    return normalized


def _strictly_increasing_finite_points(
    values: Sequence[float], *, field_name: str
) -> tuple[float, ...]:
    normalized = _finite_points(values, field_name=field_name)
    if any(right <= left for left, right in zip(normalized, normalized[1:])):
        raise ValueError(f"{field_name} must be strictly increasing")
    return normalized


def piecewise_linear_interpolate(
    x: float,
    *,
    x_points: Sequence[float],
    y_points: Sequence[float],
) -> float:
    """Evaluate the legacy piecewise-linear lookup used by the TPM approximation."""

    normalized_x = float(x)
    normalized_x_points = tuple(float(point) for point in x_points)
    normalized_y_points = tuple(float(point) for point in y_points)
    if len(normalized_x_points) != len(normalized_y_points):
        raise ValueError("x_points and y_points must have identical lengths")
    if len(normalized_x_points) < 2:
        raise ValueError("at least two piecewise points are required")

    if normalized_x_points[0] > normalized_x_points[1]:
        normalized_x_points = tuple(reversed(normalized_x_points))
        normalized_y_points = tuple(reversed(normalized_y_points))

    if normalized_x <= normalized_x_points[0]:
        return normalized_y_points[0]
    if normalized_x >= normalized_x_points[-1]:
        return normalized_y_points[-1]

    for index, right in enumerate(normalized_x_points[1:], start=1):
        if normalized_x < right:
            left = normalized_x_points[index - 1]
            left_value = normalized_y_points[index - 1]
            right_value = normalized_y_points[index]
            slope = (right_value - left_value) / (right - left)
            return left_value + slope * (normalized_x - left)

    return normalized_y_points[-1]


def interpolate_within_breakpoints(
    value: float,
    *,
    x_values: Sequence[float],
    y_values: Sequence[float],
) -> float:
    """Interpolate inside increasing breakpoints; unlike the lookup above, never clamp."""

    if value == x_values[-1]:
        return float(y_values[-1])
    for left_x, right_x, left_y, right_y in zip(
        x_values,
        x_values[1:],
        y_values,
        y_values[1:],
    ):
        if left_x <= value <= right_x:
            ratio = (value - left_x) / (right_x - left_x)
            return float(left_y) + ratio * (float(right_y) - float(left_y))
    raise ValueError("interpolation value is outside the breakpoint domain")


def approximate_exponential(
    value: float,
    *,
    breakpoint_policy: PiecewiseBreakpointPolicy | Mapping[str, object] | None = None,
) -> float:
    """Evaluate the legacy exponential lookup table used by the piecewise path."""

    policy = (
        PiecewiseBreakpointPolicy.from_dict(breakpoint_policy)
        if isinstance(breakpoint_policy, Mapping)
        else breakpoint_policy
    ) or PiecewiseBreakpointPolicy()
    minimum_value = math.log(policy.exp_probability_floor)
    if value < minimum_value:
        return 0.0
    return piecewise_linear_interpolate(
        float(value),
        x_points=policy.exp_breakpoints(),
        y_points=policy.exp_values(),
    )


def approximate_log(
    value: float,
    *,
    max_terms: int,
    breakpoint_policy: PiecewiseBreakpointPolicy | Mapping[str, object] | None = None,
) -> float:
    """Evaluate the legacy logarithm lookup table used by the piecewise path."""

    policy = (
        PiecewiseBreakpointPolicy.from_dict(breakpoint_policy)
        if isinstance(breakpoint_policy, Mapping)
        else breakpoint_policy
    ) or PiecewiseBreakpointPolicy()
    return piecewise_linear_interpolate(
        float(value),
        x_points=policy.log_breakpoints(max_terms=max_terms),
        y_points=policy.log_values(max_terms=max_terms),
    )


__all__ = [
    "CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS",
    "CONDITIONAL_GUARD_DOMAIN_FLOOR",
    "CONDITIONAL_GUARD_POLICY_NAME",
    "CONDITIONAL_GUARD_TRANSITION_WIDTH",
    "DEFAULT_APPROXIMATION_KIND",
    "DEFAULT_BREAKPOINT_POLICY_NAME",
    "DEFAULT_EXP_BREAKPOINT_START",
    "DEFAULT_EXP_PROBABILITY_FLOOR",
    "DEFAULT_LEAF_ENCODING_MODE",
    "DEFAULT_MIO_EPSILON",
    "DEFAULT_PIECEWISE_BREAKPOINT_COUNT",
    "DEFAULT_QUERY_NUMERIC_TOLERANCE",
    "DEFAULT_SUM_ENCODING_MODE",
    "LOGARITHM_ENDPOINT_POLICY_NAME",
    "PiecewiseApproximationMetadata",
    "PiecewiseBreakpointPolicy",
    "approximate_exponential",
    "approximate_log",
    "build_histogram_piecewise_points",
    "build_logsumexp_piecewise_spec",
    "build_piecewise_metadata",
    "evaluate_guarded_exponential",
    "guarded_exponential_points",
    "load_piecewise_metadata",
    "piecewise_linear_interpolate",
    "resolve_guarded_exponential_spec",
    "resolve_query_numeric_tolerance",
    "SUPPORTED_SUM_ENCODING_MODES",
]


def _logspace(start: float, end: float, *, num: int) -> tuple[float, ...]:
    if num < 1:
        raise ValueError("num must be at least 1")
    start_log = math.log(float(start))
    end_log = math.log(float(end))
    if num == 1:
        return (math.exp(start_log),)
    step = (end_log - start_log) / (num - 1)
    return tuple(math.exp(start_log + step * index) for index in range(num))


def _mapping_or_default(value: object) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise TypeError("breakpoint_policy must be a mapping when provided")
    return value


def _string_sequence(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, Sequence):
        raise TypeError("legacy_reference_paths must be a sequence of strings")
    normalized = tuple(str(item) for item in value)
    if any(not item for item in normalized):
        raise ValueError("legacy_reference_paths must not contain empty strings")
    return normalized
