"""Compare a fixed-FCR-bid evaluation with the pinned robust-storage-bidding reference.

Moved from ``open_energy_lab.simulator.fcr_bid_evaluation`` in consolidation
step A3. The evaluator keeps a generic hook: when a request carries a
``comparison_fixture``, it calls that fixture's ``compare`` or
``domain_unavailable`` method, which ``GoldenReferenceFixture`` implements
with the functions below.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
from types import MappingProxyType

from open_energy_lab.market.activation import RegulationActivationTrace
from open_energy_lab.simulator.fcr_bid_evaluation import (
    DailyFCRBidEvaluationReport,
    FCRBidEvaluationRequest,
    FCRBidEvaluationValidationError,
    _fingerprint,
    _finite,
    _non_empty,
)

from .reference_fcr import GoldenReferenceFixture


@dataclass(frozen=True, slots=True)
class ReferenceFieldComparison:
    """One evidence-scoped aggregate comparison against the normalized fixture."""

    field_id: str
    status: str
    comparison_rule: str
    actual_value: float | None
    expected_value: float | None
    unit: str | None
    actual_interval: tuple[float, float] | None
    expected_interval: tuple[float, float] | None
    decision_bound: float | None
    aggregate_half_unit: float | None
    exact_rounded_match: bool | None
    evidence_ref: str | None
    reason: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_id", _non_empty(self.field_id, field_name="field_id"))
        if self.status not in {
            "exact",
            "source_precision_compatible",
            "mismatch",
            "unavailable",
        }:
            raise FCRBidEvaluationValidationError(
                "reference field comparison status is unsupported"
            )
        if self.comparison_rule not in {
            "exact",
            "source-precision",
            "metadata-only",
            "unavailable",
        }:
            raise FCRBidEvaluationValidationError(
                "reference field comparison rule is unsupported"
            )
        if self.status == "unavailable":
            if self.reason is None:
                raise FCRBidEvaluationValidationError(
                    "unavailable comparison requires a reason"
                )
            object.__setattr__(
                self,
                "reason",
                _non_empty(self.reason, field_name="comparison unavailable reason"),
            )
        elif self.actual_value is None or self.expected_value is None:
            raise FCRBidEvaluationValidationError(
                "available comparison requires actual and expected values"
            )
        for name in (
            "actual_value",
            "expected_value",
            "decision_bound",
            "aggregate_half_unit",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _finite(value, field_name=name))
        for name in ("actual_interval", "expected_interval"):
            value = getattr(self, name)
            if value is not None:
                if len(value) != 2:
                    raise FCRBidEvaluationValidationError(
                        f"{name} must contain lower and upper endpoints"
                    )
                lower = _finite(value[0], field_name=f"{name} lower")
                upper = _finite(value[1], field_name=f"{name} upper")
                if lower > upper:
                    raise FCRBidEvaluationValidationError(
                        f"{name} lower endpoint cannot exceed its upper endpoint"
                    )
                object.__setattr__(self, name, (lower, upper))

    def to_dict(self) -> dict[str, object]:
        return {
            "field_id": self.field_id,
            "status": self.status,
            "comparison_rule": self.comparison_rule,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "unit": self.unit,
            "actual_interval": (
                None if self.actual_interval is None else list(self.actual_interval)
            ),
            "expected_interval": (
                None if self.expected_interval is None else list(self.expected_interval)
            ),
            "decision_bound": self.decision_bound,
            "aggregate_half_unit": self.aggregate_half_unit,
            "exact_rounded_match": self.exact_rounded_match,
            "evidence_ref": self.evidence_ref,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ReferenceComparisonReport:
    fixture_id: str
    policy_id: str
    overall_status: str
    fields: tuple[ReferenceFieldComparison, ...]
    comparison_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "fixture_id", _non_empty(self.fixture_id, field_name="fixture_id")
        )
        object.__setattr__(
            self, "policy_id", _non_empty(self.policy_id, field_name="policy_id")
        )
        if self.overall_status not in {
            "exact",
            "source_precision_compatible",
            "mismatch",
            "unavailable",
        }:
            raise FCRBidEvaluationValidationError(
                "reference comparison overall status is unsupported"
            )
        comparisons = tuple(self.fields)
        if not comparisons or any(
            not isinstance(item, ReferenceFieldComparison) for item in comparisons
        ):
            raise FCRBidEvaluationValidationError(
                "reference comparison must contain typed field results"
            )
        field_ids = [item.field_id for item in comparisons]
        if len(set(field_ids)) != len(field_ids):
            raise FCRBidEvaluationValidationError(
                "reference comparison field IDs must be unique"
            )
        object.__setattr__(self, "fields", comparisons)
        object.__setattr__(
            self,
            "comparison_fingerprint",
            _fingerprint(self._payload()),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "fixture_id": self.fixture_id,
            "policy_id": self.policy_id,
            "overall_status": self.overall_status,
            "fields": [item.to_dict() for item in self.fields],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            **self._payload(),
            "comparison_fingerprint": self.comparison_fingerprint,
        }


def recompute_reference_precision_bounds(
    fixture: object,
    activation_trace: RegulationActivationTrace,
) -> Mapping[str, float]:
    """Recompute every analytic decision-rounding bound from declared inputs."""

    if not isinstance(fixture, GoldenReferenceFixture):
        raise FCRBidEvaluationValidationError(
            "fixture must be one validated GoldenReferenceFixture"
        )
    if not isinstance(activation_trace, RegulationActivationTrace):
        raise FCRBidEvaluationValidationError(
            "activation_trace must be one RegulationActivationTrace"
        )
    if activation_trace.covered_period != fixture.mapping.target_period:
        raise FCRBidEvaluationValidationError(
            "activation trace does not match the reference fixture period"
        )
    if len(activation_trace.samples) != fixture.external_activation.selected_row_count:
        raise FCRBidEvaluationValidationError(
            "activation trace does not contain the declared reference row count"
        )
    half = fixture.precision_policy.decision_half_unit_kw
    first_duration = (
        activation_trace.samples[0].interval.end_utc
        - activation_trace.samples[0].interval.start_utc
    )
    duration_hours = first_duration.total_seconds() / 3600.0
    activation_values = tuple(sample.activation for sample in activation_trace.samples)
    if any(
        abs(
            (sample.interval.end_utc - sample.interval.start_utc).total_seconds()
            / 3600.0
            - duration_hours
        )
        > 1e-12
        for sample in activation_trace.samples
    ):
        raise FCRBidEvaluationValidationError(
            "reference activation intervals must have one fixed duration"
        )
    energy_bound = half * (
        24.0 + duration_hours * sum(abs(value) for value in activation_values)
    )
    configuration = fixture.reference_configuration
    efficiency_factor = max(
        float(configuration["charge_efficiency"]),
        1.0 / float(configuration["discharge_efficiency"]),
    )
    stored_energy_bound = energy_bound * efficiency_factor
    power_bound = half * (1.0 + max(abs(value) for value in activation_values))
    day_ahead_bound = half * sum(abs(value) for value in fixture.p0_eur_per_kwh)
    capacity_bound = half * sum(abs(value) for value in fixture.pr_eur_per_kw_block)
    activation_bound = half * duration_hours * sum(
        abs(
            fixture.p0_eur_per_kwh[index // 360]
            * activation
        )
        for index, activation in enumerate(activation_values)
    )
    computed = {
        "charge_energy_kwh": energy_bound,
        "discharge_energy_kwh": energy_bound,
        "stored_energy_kwh": stored_energy_bound,
        "power_extrema_kw": power_bound,
        "day_ahead_revenue_eur": day_ahead_bound,
        "fcr_capacity_revenue_eur": capacity_bound,
        "activation_revenue_eur": activation_bound,
        "combined_fcr_revenue_eur": capacity_bound + activation_bound,
        "total_revenue_eur": day_ahead_bound + capacity_bound + activation_bound,
    }
    if set(computed) != set(fixture.precision_policy.field_bounds):
        raise FCRBidEvaluationValidationError(
            "reference precision policy field-bound declarations are incomplete"
        )
    for bound_id, value in computed.items():
        declared = fixture.precision_policy.field_bounds[bound_id].decision_bound
        if not math.isclose(value, declared, rel_tol=0.0, abs_tol=5e-7):
            raise FCRBidEvaluationValidationError(
                f"reference precision bound {bound_id} does not recompute from declared inputs"
            )
    return MappingProxyType(dict(sorted(computed.items())))


def compare_reference_values(
    *,
    fixture: object,
    actual_values: Mapping[str, float],
    activation_trace: RegulationActivationTrace,
    requested_field_ids: Sequence[str] | None = None,
) -> ReferenceComparisonReport:
    """Compare supported fields without applying a blanket numeric tolerance."""

    if not isinstance(fixture, GoldenReferenceFixture):
        raise FCRBidEvaluationValidationError(
            "fixture must be one validated GoldenReferenceFixture"
        )
    if not isinstance(actual_values, Mapping):
        raise FCRBidEvaluationValidationError("actual_values must be a mapping")
    normalized_actual = {
        _non_empty(key, field_name="actual field ID"): _finite(
            value, field_name=f"actual value {key}"
        )
        for key, value in actual_values.items()
    }
    supported = {item.field_id: item for item in fixture.expected_fields}
    unsupported = {item.field_id: item for item in fixture.unsupported_fields}
    if requested_field_ids is None:
        requested = tuple(item.field_id for item in fixture.expected_fields)
    else:
        requested = tuple(
            _non_empty(item, field_name="requested reference field ID")
            for item in requested_field_ids
        )
        if len(set(requested)) != len(requested):
            raise FCRBidEvaluationValidationError(
                "requested reference field IDs must be unique"
            )
    unknown = [item for item in requested if item not in supported and item not in unsupported]
    if unknown:
        raise FCRBidEvaluationValidationError(
            "requested reference fields are undeclared: " + ", ".join(unknown)
        )
    bounds = recompute_reference_precision_bounds(fixture, activation_trace)
    fields: list[ReferenceFieldComparison] = []
    parity_statuses: list[str] = []
    aggregate_half = fixture.precision_policy.aggregate_half_unit
    decimal_places = fixture.precision_policy.aggregate_decimal_places
    for field_id in requested:
        if field_id in unsupported:
            item = unsupported[field_id]
            fields.append(
                ReferenceFieldComparison(
                    field_id=field_id,
                    status="unavailable",
                    comparison_rule="unavailable",
                    actual_value=normalized_actual.get(field_id),
                    expected_value=None,
                    unit=None,
                    actual_interval=None,
                    expected_interval=None,
                    decision_bound=None,
                    aggregate_half_unit=None,
                    exact_rounded_match=None,
                    evidence_ref=None,
                    reason=item.reason,
                )
            )
            continue
        expected = supported[field_id]
        if not isinstance(expected.expected_value, (int, float)):
            raise FCRBidEvaluationValidationError(
                f"numeric comparison requested for nonnumeric field {field_id}"
            )
        expected_value = float(expected.expected_value)
        actual = normalized_actual.get(field_id)
        if actual is None:
            fields.append(
                ReferenceFieldComparison(
                    field_id=field_id,
                    status="unavailable",
                    comparison_rule=expected.comparison_rule,
                    actual_value=None,
                    expected_value=expected_value,
                    unit=expected.unit,
                    actual_interval=None,
                    expected_interval=None,
                    decision_bound=None,
                    aggregate_half_unit=None,
                    exact_rounded_match=None,
                    evidence_ref=expected.reference_field_path,
                    reason="Open Energy Lab has no comparable value for this metadata field",
                )
            )
            continue
        if expected.comparison_rule == "metadata-only":
            status = "exact" if actual == expected_value else "mismatch"
            fields.append(
                ReferenceFieldComparison(
                    field_id=field_id,
                    status=status,
                    comparison_rule="metadata-only",
                    actual_value=actual,
                    expected_value=expected_value,
                    unit=expected.unit,
                    actual_interval=None,
                    expected_interval=None,
                    decision_bound=0.0,
                    aggregate_half_unit=0.0,
                    exact_rounded_match=actual == expected_value,
                    evidence_ref=expected.reference_field_path,
                    reason=None,
                )
            )
            continue
        if expected.comparison_rule == "exact":
            status = "exact" if actual == expected_value else "mismatch"
            parity_statuses.append(status)
            fields.append(
                ReferenceFieldComparison(
                    field_id=field_id,
                    status=status,
                    comparison_rule="exact",
                    actual_value=actual,
                    expected_value=expected_value,
                    unit=expected.unit,
                    actual_interval=(actual, actual),
                    expected_interval=(expected_value, expected_value),
                    decision_bound=0.0,
                    aggregate_half_unit=0.0,
                    exact_rounded_match=actual == expected_value,
                    evidence_ref=expected.reference_field_path,
                    reason=None,
                )
            )
            continue
        if expected.precision_bound_id is None:
            raise FCRBidEvaluationValidationError(
                f"source-precision field {field_id} has no field-specific bound"
            )
        decision_bound = bounds[expected.precision_bound_id]
        actual_interval = (actual - decision_bound, actual + decision_bound)
        expected_interval = (
            expected_value - aggregate_half,
            expected_value + aggregate_half,
        )
        rounded_match = round(actual, decimal_places) == expected_value
        if rounded_match:
            status = "exact"
        elif (
            actual_interval[0] <= expected_interval[1]
            and expected_interval[0] <= actual_interval[1]
        ):
            status = "source_precision_compatible"
        else:
            status = "mismatch"
        parity_statuses.append(status)
        fields.append(
            ReferenceFieldComparison(
                field_id=field_id,
                status=status,
                comparison_rule="source-precision",
                actual_value=actual,
                expected_value=expected_value,
                unit=expected.unit,
                actual_interval=actual_interval,
                expected_interval=expected_interval,
                decision_bound=decision_bound,
                aggregate_half_unit=aggregate_half,
                exact_rounded_match=rounded_match,
                evidence_ref=expected.reference_field_path,
                reason=None,
            )
        )
    if not parity_statuses:
        overall = "unavailable"
    elif "mismatch" in parity_statuses:
        overall = "mismatch"
    elif "source_precision_compatible" in parity_statuses:
        overall = "source_precision_compatible"
    else:
        overall = "exact"
    return ReferenceComparisonReport(
        fixture_id=fixture.fixture_id,
        policy_id=fixture.precision_policy.policy_id,
        overall_status=overall,
        fields=tuple(fields),
    )


def _reference_domain_unavailable_comparison(
    fixture: object,
    *,
    reason: str,
) -> ReferenceComparisonReport:
    if not isinstance(fixture, GoldenReferenceFixture):
        raise FCRBidEvaluationValidationError(
            "comparison fixture must be one GoldenReferenceFixture"
        )
    return ReferenceComparisonReport(
        fixture_id=fixture.fixture_id,
        policy_id=fixture.precision_policy.policy_id,
        overall_status="unavailable",
        fields=tuple(
            ReferenceFieldComparison(
                field_id=item.field_id,
                status="unavailable",
                comparison_rule=item.comparison_rule,
                actual_value=None,
                expected_value=(
                    float(item.expected_value)
                    if isinstance(item.expected_value, (int, float))
                    else None
                ),
                unit=item.unit,
                actual_interval=None,
                expected_interval=None,
                decision_bound=None,
                aggregate_half_unit=None,
                exact_rounded_match=None,
                evidence_ref=item.reference_field_path,
                reason=reason,
            )
            for item in fixture.expected_fields
        ),
    )


def compare_reference_evaluation(
    request: FCRBidEvaluationRequest,
    report: DailyFCRBidEvaluationReport,
    *,
    requested_field_ids: Sequence[str] | None = None,
) -> ReferenceComparisonReport:
    """Materialize the field report whose fingerprint is retained by evaluation."""

    if request.comparison_fixture is None:
        raise FCRBidEvaluationValidationError(
            "reference comparison requires a bound comparison fixture"
        )
    if not isinstance(report, DailyFCRBidEvaluationReport) or report.status != "settled":
        raise FCRBidEvaluationValidationError(
            "reference comparison requires one settled evaluation report"
        )
    if report.evaluation_input_fingerprint != request.evaluation_input_fingerprint:
        raise FCRBidEvaluationValidationError(
            "evaluation report does not belong to the supplied request"
        )
    if report.physical_metrics is None or report.settlement is None:
        raise FCRBidEvaluationValidationError(
            "settled report is missing physical or settlement values"
        )
    settlement = report.settlement
    physical = report.physical_metrics
    stored = physical["stored_energy_kwh"]
    delivered = physical["delivered_power_kw"]
    values: dict[str, float] = {
        "settlement.total_profit_eur": float(settlement["total_profit_eur"]),
        "settlement.day_ahead_revenue_eur": float(
            settlement["day_ahead_revenue"]["value_eur"]
        ),
        "settlement.combined_fcr_revenue_eur": float(
            settlement["fcr_capacity_revenue"]["value_eur"]
        )
        + float(settlement["activation_energy_revenue"]["value_eur"]),
        "physical.initial_stored_energy_kwh": float(stored["initial"]),
        "physical.minimum_stored_energy_kwh": float(stored["minimum"]),
        "physical.maximum_stored_energy_kwh": float(stored["maximum"]),
        "physical.terminal_stored_energy_kwh": float(stored["terminal"]),
        "physical.charge_energy_kwh": float(physical["charge_energy_kwh"]),
        "physical.discharge_energy_kwh": float(physical["discharge_energy_kwh"]),
        "physical.maximum_delivered_power_kw": float(delivered["maximum"]),
        "physical.minimum_delivered_power_kw": float(delivered["minimum"]),
    }
    if request.plan.objective.availability == "available":
        values["plan.objective"] = float(request.plan.objective.value)
    if request.plan.objective_bound.availability == "available":
        values["plan.objective_bound"] = float(request.plan.objective_bound.value)
    if (
        physical["saturation_event_count"] > 0
        or physical["non_delivery_energy_kwh"] > request.numeric_tolerance
    ):
        if requested_field_ids is not None:
            raise FCRBidEvaluationValidationError(
                "field selection is unavailable outside the reference parity domain"
            )
        comparison = _reference_domain_unavailable_comparison(
            request.comparison_fixture,
            reason=(
                "dynamic saturation or non-delivery is outside the declared "
                "no-curtailment reference parity domain"
            ),
        )
    else:
        comparison = compare_reference_values(
            fixture=request.comparison_fixture,
            actual_values=values,
            activation_trace=request.activation_trace,
            requested_field_ids=requested_field_ids,
        )
    if requested_field_ids is None and (
        report.comparison_fingerprint != comparison.comparison_fingerprint
    ):
        raise FCRBidEvaluationValidationError(
            "report comparison fingerprint does not match recomputed field results"
        )
    return comparison


__all__ = [
    "ReferenceComparisonReport",
    "ReferenceFieldComparison",
    "compare_reference_evaluation",
    "compare_reference_values",
    "recompute_reference_precision_bounds",
]
