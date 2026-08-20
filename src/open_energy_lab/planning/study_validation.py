"""Held-out validation and recommendation gates for planning studies."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from numbers import Real


TWO_SIDED_95_Z = 1.959963984540054
ONE_SIDED_95_Z = 1.6448536269514722


@dataclass(frozen=True, slots=True)
class SPNCandidateScore:
    candidate_name: str
    validation_brier_score: float
    node_count: int
    compilable: bool
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not str(self.candidate_name):
            raise ValueError("candidate_name must be non-empty")
        if not math.isfinite(float(self.validation_brier_score)):
            raise ValueError("validation_brier_score must be finite")
        if isinstance(self.node_count, bool) or int(self.node_count) < 0:
            raise ValueError("node_count must be a non-negative integer")
        if not isinstance(self.compilable, bool):
            raise TypeError("compilable must be boolean")


@dataclass(frozen=True, slots=True)
class ConfigurationCalibration:
    configuration_id: str
    predicted_probability: float
    empirical_probability: float
    event_count: int
    sample_count: int
    confidence_interval_lower: float
    confidence_interval_upper: float
    absolute_error: float


@dataclass(frozen=True, slots=True)
class CalibrationAssessment:
    configuration_results: tuple[ConfigurationCalibration, ...]
    selected_configuration_id: str
    mean_configuration_error: float
    maximum_configuration_error: float
    mean_error_limit: float
    max_error_limit: float
    both_labels_observed: bool
    selected_probability_in_confidence_interval: bool
    passed: bool


@dataclass(frozen=True, slots=True)
class RecommendationAssessment:
    status: str
    one_sided_upper_risk_bound: float
    chance_limit: float
    native_mio_discrepancy: float
    blocking_reasons: tuple[str, ...]

    @property
    def recommendation_allowed(self) -> bool:
        return self.status == "recommended"


def brier_score_by_configuration(
    rows: Sequence[Mapping[str, object]],
    *,
    probabilities: Mapping[str, float],
    event_target_name: str,
    configuration_field: str = "configuration_id",
) -> float:
    """Score configuration-conditional probabilities against held-out labels."""

    if not rows:
        raise ValueError("held-out rows must not be empty")
    total = 0.0
    for index, row in enumerate(rows):
        configuration_id = str(row[configuration_field])
        if configuration_id not in probabilities:
            raise ValueError(
                f"probabilities are missing configuration {configuration_id!r}"
            )
        probability = _probability(
            probabilities[configuration_id],
            field_name=f"probabilities[{configuration_id!r}]",
        )
        label = _binary_label(row[event_target_name], row_index=index)
        total += (probability - label) ** 2
    return total / len(rows)


def select_spn_candidate(
    candidates: Sequence[SPNCandidateScore],
) -> SPNCandidateScore:
    """Select the compilable candidate with best Brier score and smallest graph."""

    compilable = [candidate for candidate in candidates if candidate.compilable]
    if not compilable:
        details = "; ".join(
            f"{candidate.candidate_name}: {candidate.failure_reason or 'not compilable'}"
            for candidate in candidates
        )
        raise ValueError(f"no SPN candidate compiled successfully ({details})")
    return min(
        compilable,
        key=lambda candidate: (
            candidate.validation_brier_score,
            candidate.node_count,
            candidate.candidate_name,
        ),
    )


def assess_calibration(
    rows: Sequence[Mapping[str, object]],
    *,
    probabilities: Mapping[str, float],
    event_target_name: str,
    selected_configuration_id: str,
    configuration_field: str = "configuration_id",
    mean_error_limit: float = 0.05,
    max_error_limit: float = 0.10,
) -> CalibrationAssessment:
    """Apply the study's per-configuration held-out calibration gate."""

    if not rows:
        raise ValueError("held-out rows must not be empty")
    mean_limit = _probability(mean_error_limit, field_name="mean_error_limit")
    maximum_limit = _probability(max_error_limit, field_name="max_error_limit")
    grouped: dict[str, list[int]] = defaultdict(list)
    labels: set[int] = set()
    for index, row in enumerate(rows):
        label = _binary_label(row[event_target_name], row_index=index)
        configuration_id = str(row[configuration_field])
        grouped[configuration_id].append(label)
        labels.add(label)

    missing = sorted(set(grouped) - set(probabilities))
    if missing:
        raise ValueError("probabilities are missing configurations: " + ", ".join(missing))
    results: list[ConfigurationCalibration] = []
    for configuration_id in sorted(grouped):
        configuration_labels = grouped[configuration_id]
        event_count = sum(configuration_labels)
        sample_count = len(configuration_labels)
        empirical = event_count / sample_count
        predicted = _probability(
            probabilities[configuration_id],
            field_name=f"probabilities[{configuration_id!r}]",
        )
        lower, upper = wilson_confidence_interval(event_count, sample_count)
        results.append(
            ConfigurationCalibration(
                configuration_id=configuration_id,
                predicted_probability=predicted,
                empirical_probability=empirical,
                event_count=event_count,
                sample_count=sample_count,
                confidence_interval_lower=lower,
                confidence_interval_upper=upper,
                absolute_error=abs(predicted - empirical),
            )
        )

    try:
        selected = next(
            result
            for result in results
            if result.configuration_id == selected_configuration_id
        )
    except StopIteration as exc:
        raise ValueError(
            f"selected configuration {selected_configuration_id!r} is absent from held-out rows"
        ) from exc
    mean_error = sum(result.absolute_error for result in results) / len(results)
    max_error = max(result.absolute_error for result in results)
    selected_in_interval = (
        selected.confidence_interval_lower
        <= selected.predicted_probability
        <= selected.confidence_interval_upper
    )
    both_labels = labels == {0, 1}
    passed = (
        mean_error <= mean_limit
        and max_error <= maximum_limit
        and both_labels
        and selected_in_interval
    )
    return CalibrationAssessment(
        configuration_results=tuple(results),
        selected_configuration_id=str(selected_configuration_id),
        mean_configuration_error=mean_error,
        maximum_configuration_error=max_error,
        mean_error_limit=mean_limit,
        max_error_limit=maximum_limit,
        both_labels_observed=both_labels,
        selected_probability_in_confidence_interval=selected_in_interval,
        passed=passed,
    )


def assess_recommendation(
    *,
    calibration: CalibrationAssessment,
    solve_status: str,
    native_mio_discrepancy: float,
    chance_limit: float,
    parity_tolerance: float = 1e-6,
) -> RecommendationAssessment:
    """Require calibration, parity, and a one-sided held-out risk bound."""

    chance = _probability(chance_limit, field_name="chance_limit")
    discrepancy = float(native_mio_discrepancy)
    tolerance = float(parity_tolerance)
    if discrepancy < 0.0 or tolerance <= 0.0:
        raise ValueError("native_mio_discrepancy must be non-negative and tolerance positive")
    selected = next(
        result
        for result in calibration.configuration_results
        if result.configuration_id == calibration.selected_configuration_id
    )
    upper_bound = wilson_upper_bound(
        selected.event_count,
        selected.sample_count,
    )
    reasons: list[str] = []
    if not calibration.passed:
        reasons.append("held-out calibration gate did not pass")
    if solve_status != "optimal":
        reasons.append(f"planning solve status is {solve_status!r}, not 'optimal'")
    if discrepancy > tolerance:
        reasons.append(
            f"native/MIO discrepancy {discrepancy:g} exceeds {tolerance:g}"
        )
    if upper_bound > chance:
        reasons.append(
            f"one-sided held-out 95% risk bound {upper_bound:.6f} exceeds {chance:.6f}"
        )
    return RecommendationAssessment(
        status="recommended" if not reasons else "exploratory",
        one_sided_upper_risk_bound=upper_bound,
        chance_limit=chance,
        native_mio_discrepancy=discrepancy,
        blocking_reasons=tuple(reasons),
    )


def wilson_confidence_interval(
    event_count: int,
    sample_count: int,
    *,
    z_score: float = TWO_SIDED_95_Z,
) -> tuple[float, float]:
    """Return the two-sided Wilson binomial confidence interval."""

    count, total = _validated_binomial_counts(event_count, sample_count)
    z = float(z_score)
    if z <= 0.0:
        raise ValueError("z_score must be positive")
    proportion = count / total
    denominator = 1.0 + (z * z / total)
    center = (proportion + (z * z / (2.0 * total))) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / total
            + z * z / (4.0 * total * total)
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def wilson_upper_bound(
    event_count: int,
    sample_count: int,
    *,
    z_score: float = ONE_SIDED_95_Z,
) -> float:
    """Return a one-sided Wilson upper confidence bound for event risk."""

    return wilson_confidence_interval(
        event_count,
        sample_count,
        z_score=z_score,
    )[1]


def _validated_binomial_counts(event_count: int, sample_count: int) -> tuple[int, int]:
    if isinstance(event_count, bool) or isinstance(sample_count, bool):
        raise TypeError("event_count and sample_count must be integers")
    count = int(event_count)
    total = int(sample_count)
    if total <= 0 or not 0 <= count <= total:
        raise ValueError("binomial counts must satisfy 0 <= event_count <= sample_count")
    return count, total


def _probability(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be a finite probability")
    return normalized


def _binary_label(value: object, *, row_index: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, Real) and float(value) in {0.0, 1.0}:
        return int(value)
    raise ValueError(f"held-out event label at row {row_index} must be binary")


__all__ = [
    "CalibrationAssessment",
    "ConfigurationCalibration",
    "RecommendationAssessment",
    "SPNCandidateScore",
    "assess_calibration",
    "assess_recommendation",
    "brier_score_by_configuration",
    "select_spn_candidate",
    "wilson_confidence_interval",
    "wilson_upper_bound",
]
