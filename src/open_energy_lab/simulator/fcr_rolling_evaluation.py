"""Segmented accepted-plan evaluation composed exclusively from Feature 012.

This module owns no battery transition, tracking, saturation, settlement, or
profit equation. It slices immutable plans and activation, constructs a fresh
Feature 012 battery for each segment, delegates to ``evaluate_fixed_fcr_bid``,
and reconciles the returned reports.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
import math

from open_energy_lab.core.serialization import fingerprint, freeze, thaw
from open_energy_lab.core.validation import finite, non_empty_str, sha256_digest
from open_energy_lab.control.fcr_bid_plan import (
    FixedFCRBidPlan,
    build_fixed_fcr_bid_plan,
)
from open_energy_lab.market.activation import (
    RegulationActivationTrace,
    slice_regulation_activation_trace,
)
from open_energy_lab.market.time import CanonicalInterval

from .fcr_bid_evaluation import (
    DailyFCRBidEvaluationReport,
    EvaluationMarketContext,
    FCRBidEvaluationRequest,
    FCRBidEvaluationValidationError,
    evaluate_fixed_fcr_bid,
)
from .scenario import BatteryComponent
from .stacked_service import (
    MultiRateTimeContract,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
)


FCR_SEGMENTED_EVALUATION_SEMANTICS_VERSION = (
    "oel.fcr-segmented-evaluation.v1"
)


_non_empty = partial(non_empty_str, error=FCRBidEvaluationValidationError, strip=True)
_finite = partial(finite, error=FCRBidEvaluationValidationError, normalize_zero=True)
_fingerprint = partial(fingerprint, error=FCRBidEvaluationValidationError)
_sha256 = partial(sha256_digest, error=FCRBidEvaluationValidationError)
_freeze = partial(freeze, sort_keys=True)
_thaw = thaw


def _interval_payload(period: CanonicalInterval) -> dict[str, object]:
    return period.to_dict()


@dataclass(frozen=True, slots=True)
class FCRAcceptedPlanSegment:
    """One unchanged parent plan viewed over a half-open accepted interval."""

    segment_id: str
    parent_plan_fingerprint: str
    period: CanonicalInterval
    plan: FixedFCRBidPlan
    market_context_fingerprint: str
    segment_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "segment_id", _non_empty(self.segment_id, field_name="segment_id")
        )
        object.__setattr__(
            self,
            "parent_plan_fingerprint",
            _sha256(
                self.parent_plan_fingerprint,
                field_name="parent_plan_fingerprint",
            ),
        )
        if not isinstance(self.period, CanonicalInterval):
            raise FCRBidEvaluationValidationError(
                "segment period must be a CanonicalInterval"
            )
        if not isinstance(self.plan, FixedFCRBidPlan):
            raise FCRBidEvaluationValidationError(
                "segment plan must be a FixedFCRBidPlan"
            )
        if self.plan.energy_schedule.covered_period != self.period:
            raise FCRBidEvaluationValidationError(
                "segment plan schedule must exactly match the segment period"
            )
        object.__setattr__(
            self,
            "market_context_fingerprint",
            _sha256(
                self.market_context_fingerprint,
                field_name="segment market_context_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "segment_fingerprint",
            _fingerprint(self._payload()),
        )

    def _payload(self) -> dict[str, object]:
        return {
            "segment_id": self.segment_id,
            "parent_plan_fingerprint": self.parent_plan_fingerprint,
            "period": _interval_payload(self.period),
            "segment_plan_fingerprint": self.plan.plan_fingerprint,
            "energy_schedule_fingerprint": (
                self.plan.energy_schedule.schedule_fingerprint
            ),
            "fcr_schedule_fingerprint": self.plan.fcr_schedule.schedule_fingerprint,
            "market_context_fingerprint": self.market_context_fingerprint,
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "segment_fingerprint": self.segment_fingerprint}


@dataclass(frozen=True, slots=True)
class FCRSegmentedEvaluationReport:
    """Deterministic reconciliation of ordered Feature 012 reports."""

    evaluation_id: str
    parent_plan_fingerprint: str
    selected_period: CanonicalInterval
    activation_trace_fingerprint: str
    battery_binding_fingerprint: str
    segments: tuple[FCRAcceptedPlanSegment, ...]
    reports: tuple[DailyFCRBidEvaluationReport, ...]
    stored_energy_checkpoints_kwh: tuple[float, ...]
    additive_metrics: Mapping[str, float]
    extrema: Mapping[str, float]
    settlement_components_eur: Mapping[str, float]
    maximum_state_reconciliation_residual_kwh: float
    diagnostics: tuple[str, ...] = ()
    semantics_version: str = FCR_SEGMENTED_EVALUATION_SEMANTICS_VERSION
    semantic_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evaluation_id",
            _non_empty(self.evaluation_id, field_name="evaluation_id"),
        )
        if self.semantics_version != FCR_SEGMENTED_EVALUATION_SEMANTICS_VERSION:
            raise FCRBidEvaluationValidationError(
                "unsupported segmented-evaluation semantics version"
            )
        object.__setattr__(
            self,
            "parent_plan_fingerprint",
            _sha256(
                self.parent_plan_fingerprint,
                field_name="parent_plan_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "activation_trace_fingerprint",
            _sha256(
                self.activation_trace_fingerprint,
                field_name="activation_trace_fingerprint",
            ),
        )
        object.__setattr__(
            self,
            "battery_binding_fingerprint",
            _sha256(
                self.battery_binding_fingerprint,
                field_name="battery_binding_fingerprint",
            ),
        )
        segments = tuple(self.segments)
        reports = tuple(self.reports)
        if not segments or len(segments) != len(reports):
            raise FCRBidEvaluationValidationError(
                "segmented report requires one Feature 012 report per segment"
            )
        if any(item.parent_plan_fingerprint != self.parent_plan_fingerprint for item in segments):
            raise FCRBidEvaluationValidationError(
                "all segments must retain the unchanged parent plan identity"
            )
        if any(report.status != "settled" for report in reports):
            raise FCRBidEvaluationValidationError(
                "segmented report accepts only settled Feature 012 reports"
            )
        checkpoints = tuple(
            _finite(value, field_name="stored energy checkpoint")
            for value in self.stored_energy_checkpoints_kwh
        )
        if len(checkpoints) != len(segments) + 1:
            raise FCRBidEvaluationValidationError(
                "stored-energy checkpoints must contain initial plus every terminal"
            )
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "reports", reports)
        object.__setattr__(self, "stored_energy_checkpoints_kwh", checkpoints)
        object.__setattr__(self, "additive_metrics", _freeze(self.additive_metrics))
        object.__setattr__(self, "extrema", _freeze(self.extrema))
        object.__setattr__(
            self,
            "settlement_components_eur",
            _freeze(self.settlement_components_eur),
        )
        residual = _finite(
            self.maximum_state_reconciliation_residual_kwh,
            field_name="maximum state reconciliation residual",
        )
        if residual < 0.0:
            raise FCRBidEvaluationValidationError(
                "state reconciliation residual must be non-negative"
            )
        object.__setattr__(
            self,
            "maximum_state_reconciliation_residual_kwh",
            residual,
        )
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics)))
        object.__setattr__(
            self,
            "semantic_fingerprint",
            _fingerprint(self._payload()),
        )

    @property
    def initial_stored_energy_kwh(self) -> float:
        return self.stored_energy_checkpoints_kwh[0]

    @property
    def cutoff_stored_energy_kwh(self) -> tuple[float, ...]:
        return self.stored_energy_checkpoints_kwh[1:-1]

    @property
    def terminal_stored_energy_kwh(self) -> float:
        return self.stored_energy_checkpoints_kwh[-1]

    def _payload(self) -> dict[str, object]:
        return {
            "semantics_version": self.semantics_version,
            "evaluation_id": self.evaluation_id,
            "parent_plan_fingerprint": self.parent_plan_fingerprint,
            "selected_period": _interval_payload(self.selected_period),
            "activation_trace_fingerprint": self.activation_trace_fingerprint,
            "battery_binding_fingerprint": self.battery_binding_fingerprint,
            "segment_fingerprints": [item.segment_fingerprint for item in self.segments],
            "feature_012_report_fingerprints": [
                item.result_fingerprint for item in self.reports
            ],
            "stored_energy_checkpoints_kwh": list(
                self.stored_energy_checkpoints_kwh
            ),
            "additive_metrics": _thaw(self.additive_metrics),
            "extrema": _thaw(self.extrema),
            "settlement_components_eur": _thaw(
                self.settlement_components_eur
            ),
            "maximum_state_reconciliation_residual_kwh": (
                self.maximum_state_reconciliation_residual_kwh
            ),
            "diagnostics": list(self.diagnostics),
        }

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "semantic_fingerprint": self.semantic_fingerprint}


def _binding_value(binding: object, name: str) -> object:
    if isinstance(binding, Mapping):
        if name not in binding:
            raise FCRBidEvaluationValidationError(
                f"battery binding is missing {name}"
            )
        return binding[name]
    if hasattr(binding, name):
        return getattr(binding, name)
    battery = getattr(binding, "optimization_battery", None)
    if battery is not None and hasattr(battery, name):
        return getattr(battery, name)
    raise FCRBidEvaluationValidationError(f"battery binding is missing {name}")


def _fresh_battery(
    binding: object,
    *,
    initial_stored_energy_kwh: float,
) -> BatteryComponent:
    capacity = _finite(_binding_value(binding, "capacity_kwh"), field_name="capacity_kwh")
    minimum = _finite(
        _binding_value(binding, "minimum_stored_energy_kwh"),
        field_name="minimum_stored_energy_kwh",
    )
    maximum = _finite(
        _binding_value(binding, "maximum_stored_energy_kwh"),
        field_name="maximum_stored_energy_kwh",
    )
    initial = _finite(
        initial_stored_energy_kwh,
        field_name="initial_stored_energy_kwh",
    )
    if not minimum <= initial <= maximum:
        raise FCRBidEvaluationValidationError(
            "segment initial stored energy is outside the battery binding"
        )
    try:
        return BatteryComponent(
            name=str(
                _binding_value(binding, "component_name")
                if (
                    isinstance(binding, Mapping) and "component_name" in binding
                )
                or hasattr(binding, "component_name")
                else "feature-015-segment-battery"
            ),
            capacity_kwh=capacity,
            max_charge_kw=_finite(
                _binding_value(binding, "maximum_charge_power_kw"),
                field_name="maximum_charge_power_kw",
            ),
            max_discharge_kw=_finite(
                _binding_value(binding, "maximum_discharge_power_kw"),
                field_name="maximum_discharge_power_kw",
            ),
            charge_efficiency=_finite(
                _binding_value(binding, "charge_efficiency"),
                field_name="charge_efficiency",
            ),
            discharge_efficiency=_finite(
                _binding_value(binding, "discharge_efficiency"),
                field_name="discharge_efficiency",
            ),
            initial_soc=initial / capacity,
            min_soc=minimum / capacity,
            max_soc=maximum / capacity,
        )
    except ValueError as exc:
        raise FCRBidEvaluationValidationError(
            f"invalid battery binding for segmented evaluation: {exc}"
        ) from exc


def _slice_plan(
    parent: FixedFCRBidPlan,
    period: CanonicalInterval,
    *,
    segment_index: int,
) -> FixedFCRBidPlan:
    energy = tuple(
        item
        for item in parent.energy_schedule.intervals
        if item.interval.start_utc >= period.start_utc
        and item.interval.end_utc <= period.end_utc
    )
    fcr = tuple(
        item
        for item in parent.fcr_schedule.intervals
        if item.interval.start_utc >= period.start_utc
        and item.interval.end_utc <= period.end_utc
    )
    energy_schedule = build_energy_baseline_schedule(
        schedule_id=f"{parent.energy_schedule.schedule_id}-segment-{segment_index}",
        semantics_version=parent.energy_schedule.semantics_version,
        covered_start_utc=period.start_utc,
        covered_end_utc=period.end_utc,
        intervals=tuple(
            {
                "start_utc": item.interval.start_utc,
                "end_utc": item.interval.end_utc,
                "power_kw": item.power_kw,
                "schedule_source": item.schedule_source,
            }
            for item in energy
        ),
    )
    fcr_schedule = build_fcr_capacity_schedule(
        schedule_id=f"{parent.fcr_schedule.schedule_id}-segment-{segment_index}",
        semantics_version=parent.fcr_schedule.semantics_version,
        product_identity=parent.fcr_schedule.product_identity,
        covered_start_utc=period.start_utc,
        covered_end_utc=period.end_utc,
        intervals=tuple(
            {
                "start_utc": item.interval.start_utc,
                "end_utc": item.interval.end_utc,
                "capacity_kw": item.capacity_kw,
                "volume_observation_ref": item.volume_observation_ref,
                "price_observation_ref": item.price_observation_ref,
            }
            for item in fcr
        ),
    )
    return build_fixed_fcr_bid_plan(
        plan_id=f"{parent.plan_id}-segment-{segment_index}",
        producer=parent.producer,
        information_cutoff_utc=parent.information_cutoff_utc,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        producer_input_fingerprints=parent.producer_input_fingerprints,
        solve_status=parent.solve_status,
        objective=parent.objective,
        objective_bound=parent.objective_bound,
        diagnostics=parent.diagnostics,
    )


def _validate_partition(
    plan: FixedFCRBidPlan,
    periods: Sequence[CanonicalInterval],
    contexts: Sequence[EvaluationMarketContext],
) -> tuple[tuple[CanonicalInterval, ...], tuple[EvaluationMarketContext, ...]]:
    normalized_periods = tuple(periods)
    normalized_contexts = tuple(contexts)
    if not normalized_periods or len(normalized_periods) != len(normalized_contexts):
        raise FCRBidEvaluationValidationError(
            "segment periods and market contexts must be nonempty and equally sized"
        )
    if any(not isinstance(item, CanonicalInterval) for item in normalized_periods):
        raise FCRBidEvaluationValidationError(
            "segment periods must be CanonicalInterval values"
        )
    if any(
        left.end_utc != right.start_utc
        for left, right in zip(
            normalized_periods, normalized_periods[1:], strict=False
        )
    ):
        raise FCRBidEvaluationValidationError(
            "segment periods must form one exact contiguous partition"
        )
    parent_period = plan.energy_schedule.covered_period
    if (
        normalized_periods[0].start_utc < parent_period.start_utc
        or normalized_periods[-1].end_utc > parent_period.end_utc
    ):
        raise FCRBidEvaluationValidationError(
            "segment partition must remain inside the unchanged plan period"
        )
    for index, (period, context) in enumerate(
        zip(normalized_periods, normalized_contexts, strict=True)
    ):
        if not isinstance(context, EvaluationMarketContext):
            raise FCRBidEvaluationValidationError(
                f"market context {index} must be an EvaluationMarketContext"
            )
        if context.period != period:
            raise FCRBidEvaluationValidationError(
                f"market context {index} does not match its segment period"
            )
        if context.context_kind != "accepted_plan":
            raise FCRBidEvaluationValidationError(
                "segmented evaluation requires explicit accepted-plan contexts"
            )
    return normalized_periods, normalized_contexts


def _component_value(settlement: Mapping[str, object], key: str) -> float:
    value = settlement.get(key)
    if isinstance(value, Mapping):
        if value.get("availability") == "available":
            return _finite(value.get("value_eur"), field_name=f"settlement.{key}")
        return 0.0
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _finite(value, field_name=f"settlement.{key}")
    return 0.0


def _reconcile_reports(
    reports: tuple[DailyFCRBidEvaluationReport, ...],
    *,
    initial_stored_energy_kwh: float,
) -> tuple[
    tuple[float, ...],
    dict[str, float],
    dict[str, float],
    dict[str, float],
    float,
]:
    checkpoints = [initial_stored_energy_kwh]
    residuals: list[float] = []
    additive_keys = (
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "throughput_kwh",
        "signed_tracking_error_kw_sum",
        "absolute_tracking_error_kw_sum",
        "non_delivery_energy_kwh",
        "saturation_sample_count",
        "saturation_duration_hours",
        "saturation_event_count",
    )
    additive = {key: 0.0 for key in additive_keys}
    for direction in (
        "requested_fcr_energy_kwh",
        "delivered_fcr_energy_kwh",
    ):
        for field_name in (
            "upward_discharge",
            "downward_charge",
            "signed_net_charge_positive",
        ):
            additive[f"{direction}.{field_name}"] = 0.0
    additive["total_profit_eur"] = 0.0
    minimum_stored = math.inf
    maximum_stored = -math.inf
    minimum_requested = math.inf
    maximum_requested = -math.inf
    minimum_delivered = math.inf
    maximum_delivered = -math.inf
    settlement_totals = {
        key: 0.0
        for key in (
            "day_ahead_revenue",
            "fcr_capacity_revenue",
            "activation_energy_revenue",
            "combined_fcr_revenue",
            "penalty",
            "total_profit_eur",
        )
    }
    for report in reports:
        metrics = report.physical_metrics
        settlement = report.settlement
        assert metrics is not None and settlement is not None
        stored = metrics["stored_energy_kwh"]
        residuals.append(abs(float(stored["initial"]) - checkpoints[-1]))
        checkpoints.append(float(stored["terminal"]))
        minimum_stored = min(minimum_stored, float(stored["minimum"]))
        maximum_stored = max(maximum_stored, float(stored["maximum"]))
        minimum_requested = min(
            minimum_requested, float(metrics["requested_power_kw"]["minimum"])
        )
        maximum_requested = max(
            maximum_requested, float(metrics["requested_power_kw"]["maximum"])
        )
        minimum_delivered = min(
            minimum_delivered, float(metrics["delivered_power_kw"]["minimum"])
        )
        maximum_delivered = max(
            maximum_delivered, float(metrics["delivered_power_kw"]["maximum"])
        )
        for key in additive_keys:
            additive[key] += float(metrics[key])
        for direction in (
            "requested_fcr_energy_kwh",
            "delivered_fcr_energy_kwh",
        ):
            for field_name in (
                "upward_discharge",
                "downward_charge",
                "signed_net_charge_positive",
            ):
                additive[f"{direction}.{field_name}"] += float(
                    metrics[direction][field_name]
                )
        additive["total_profit_eur"] += float(report.total_profit_eur)
        settlement_totals["day_ahead_revenue"] += _component_value(
            settlement, "day_ahead_revenue"
        ) + _component_value(settlement, "day_ahead_energy_revenue_eur")
        settlement_totals["fcr_capacity_revenue"] += _component_value(
            settlement, "fcr_capacity_revenue"
        ) + _component_value(settlement, "fcr_capacity_revenue_eur")
        settlement_totals["activation_energy_revenue"] += _component_value(
            settlement, "activation_energy_revenue"
        )
        settlement_totals["combined_fcr_revenue"] += _component_value(
            settlement, "combined_fcr_revenue"
        )
        settlement_totals["penalty"] += _component_value(
            settlement, "penalty"
        ) + _component_value(settlement, "penalty_eur")
        settlement_totals["total_profit_eur"] += float(report.total_profit_eur)
    extrema = {
        "minimum_stored_energy_kwh": minimum_stored,
        "maximum_stored_energy_kwh": maximum_stored,
        "minimum_requested_power_kw": minimum_requested,
        "maximum_requested_power_kw": maximum_requested,
        "minimum_delivered_power_kw": minimum_delivered,
        "maximum_delivered_power_kw": maximum_delivered,
    }
    return (
        tuple(checkpoints),
        additive,
        extrema,
        settlement_totals,
        max(residuals, default=0.0),
    )


def evaluate_fixed_fcr_bid_segments(
    *,
    evaluation_id: str,
    plan: FixedFCRBidPlan,
    periods: tuple[CanonicalInterval, ...],
    market_contexts: tuple[EvaluationMarketContext, ...],
    activation_trace: RegulationActivationTrace,
    battery_binding: object,
    initial_stored_energy_kwh: float,
    settlement_profile: str,
    numeric_tolerance: float,
) -> FCRSegmentedEvaluationReport:
    """Evaluate ordered accepted-plan segments solely through Feature 012."""

    if not isinstance(plan, FixedFCRBidPlan):
        raise FCRBidEvaluationValidationError("plan must be one FixedFCRBidPlan")
    if not isinstance(activation_trace, RegulationActivationTrace):
        raise FCRBidEvaluationValidationError(
            "activation_trace must be a RegulationActivationTrace"
        )
    tolerance = _finite(numeric_tolerance, field_name="numeric_tolerance")
    if tolerance <= 0.0:
        raise FCRBidEvaluationValidationError("numeric_tolerance must be positive")
    normalized_periods, normalized_contexts = _validate_partition(
        plan, periods, market_contexts
    )
    binding_fingerprint = _sha256(
        _binding_value(battery_binding, "binding_fingerprint"),
        field_name="battery binding_fingerprint",
    )
    initial = _finite(
        initial_stored_energy_kwh,
        field_name="initial_stored_energy_kwh",
    )
    current_stored = initial
    segments: list[FCRAcceptedPlanSegment] = []
    reports: list[DailyFCRBidEvaluationReport] = []
    for index, (period, context) in enumerate(
        zip(normalized_periods, normalized_contexts, strict=True)
    ):
        segment_plan = _slice_plan(plan, period, segment_index=index)
        segment = FCRAcceptedPlanSegment(
            segment_id=f"{evaluation_id}-segment-{index}",
            parent_plan_fingerprint=plan.plan_fingerprint,
            period=period,
            plan=segment_plan,
            market_context_fingerprint=context.context_fingerprint,
        )
        segment_trace = slice_regulation_activation_trace(
            activation_trace,
            period=period,
        )
        battery = _fresh_battery(
            battery_binding,
            initial_stored_energy_kwh=current_stored,
        )
        time_contract = MultiRateTimeContract(
            start_utc=period.start_utc,
            end_utc=period.end_utc,
            activation_resolution=segment_trace.resolution,
            state_checkpoint_resolution=segment_trace.resolution,
            energy_resolution="PT1H",
            fcr_resolution="PT4H",
            market_timezone=period.market_timezone,
            interval_convention="start-inclusive/end-exclusive",
        )
        request = FCRBidEvaluationRequest(
            evaluation_id=f"{evaluation_id}-segment-{index}",
            plan=segment_plan,
            market_context=context,
            activation_trace=segment_trace,
            battery=battery,
            time_contract=time_contract,
            settlement_profile=settlement_profile,
            penalty_rule=None,
            terminal_soc_target=None,
            comparison_fixture=None,
            numeric_tolerance=tolerance,
        )
        report = evaluate_fixed_fcr_bid(request)
        if report.status != "settled" or report.physical_metrics is None:
            raise FCRBidEvaluationValidationError(
                f"Feature 012 segment {index} did not settle"
            )
        current_stored = float(
            report.physical_metrics["stored_energy_kwh"]["terminal"]
        )
        segments.append(segment)
        reports.append(report)
    report_tuple = tuple(reports)
    checkpoints, additive, extrema, settlement, residual = _reconcile_reports(
        report_tuple,
        initial_stored_energy_kwh=initial,
    )
    if residual > tolerance:
        raise FCRBidEvaluationValidationError(
            "Feature 012 segment terminal and successor initial states do not reconcile"
        )
    return FCRSegmentedEvaluationReport(
        evaluation_id=evaluation_id,
        parent_plan_fingerprint=plan.plan_fingerprint,
        selected_period=CanonicalInterval.from_utc(
            normalized_periods[0].start_utc,
            normalized_periods[-1].end_utc,
            market_timezone=normalized_periods[0].market_timezone,
        ),
        activation_trace_fingerprint=activation_trace.artifact_fingerprint,
        battery_binding_fingerprint=binding_fingerprint,
        segments=tuple(segments),
        reports=report_tuple,
        stored_energy_checkpoints_kwh=checkpoints,
        additive_metrics=additive,
        extrema=extrema,
        settlement_components_eur=settlement,
        maximum_state_reconciliation_residual_kwh=residual,
    )


__all__ = [
    "FCRAcceptedPlanSegment",
    "FCRSegmentedEvaluationReport",
    "FCR_SEGMENTED_EVALUATION_SEMANTICS_VERSION",
    "evaluate_fixed_fcr_bid_segments",
]
