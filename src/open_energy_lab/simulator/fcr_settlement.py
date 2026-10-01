"""Deterministic settlement for fixed day-ahead and symmetric-FCR schedules."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from functools import partial
from typing import TYPE_CHECKING, Any

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.validation import finite, non_empty_str
from open_energy_lab.market.time import CanonicalInterval

if TYPE_CHECKING:
    from .fcr_bid_evaluation import (
        ComponentAvailability,
        FCRBidEvaluationRequest,
    )
    from .stacked_service import ReplaySample, StackedServiceReplayRequest


class FCRSettlementValidationError(ValidationError):
    """Raised when explicit settlement inputs have incompatible semantics."""


_finite = partial(finite, error=FCRSettlementValidationError)
_non_empty = partial(non_empty_str, error=FCRSettlementValidationError, strip=True)


@dataclass(frozen=True, slots=True)
class FCRPenaltyRule:
    rule_id: str
    measure: str
    rate: float
    rate_unit: str
    application: str

    def __post_init__(self) -> None:
        rule_id = _non_empty(self.rule_id, field_name="penalty rule_id")
        rate = _finite(self.rate, field_name="penalty rate")
        if rate < 0.0:
            raise FCRSettlementValidationError("penalty rate must be non-negative")
        if self.measure != "absolute_fcr_non_delivery_energy_kwh":
            raise FCRSettlementValidationError(
                "penalty measure must be absolute_fcr_non_delivery_energy_kwh"
            )
        if self.rate_unit != "EUR/kWh":
            raise FCRSettlementValidationError("penalty rate unit must be EUR/kWh")
        if self.application != "sum per activation interval":
            raise FCRSettlementValidationError(
                "penalty application must be sum per activation interval"
            )
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "rate", rate)

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "measure": self.measure,
            "rate": self.rate,
            "rate_unit": self.rate_unit,
            "application": self.application,
        }


@dataclass(frozen=True, slots=True)
class EnergySettlementInterval:
    interval: CanonicalInterval
    accepted_power_kw: float
    duration_hours: float
    price_eur_per_mwh: float
    revenue_eur: float

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "accepted_power_kw": self.accepted_power_kw,
            "duration_hours": self.duration_hours,
            "price_eur_per_mwh": self.price_eur_per_mwh,
            "revenue_eur": self.revenue_eur,
        }


@dataclass(frozen=True, slots=True)
class FCRSettlementBlock:
    interval: CanonicalInterval
    committed_capacity_kw: float
    duration_hours: float
    capacity_price_eur_per_mw_per_h: float
    revenue_eur: float

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "committed_capacity_kw": self.committed_capacity_kw,
            "duration_hours": self.duration_hours,
            "capacity_price_eur_per_mw_per_h": self.capacity_price_eur_per_mw_per_h,
            "revenue_eur": self.revenue_eur,
        }


@dataclass(frozen=True, slots=True)
class SettlementBreakdown:
    energy_intervals: tuple[EnergySettlementInterval, ...]
    fcr_blocks: tuple[FCRSettlementBlock, ...]
    day_ahead_energy_revenue_eur: float
    fcr_capacity_revenue_eur: float
    non_delivery_energy_kwh: float
    penalty_rule_id: str | None
    penalty_eur: float
    charge_energy_kwh: float
    discharge_energy_kwh: float
    throughput_kwh: float
    activation_energy_settlement_status: str
    imbalance_settlement_status: str
    degradation_cost_status: str
    total_profit_eur: float

    def to_dict(self) -> dict[str, object]:
        return {
            "energy_intervals": [item.to_dict() for item in self.energy_intervals],
            "fcr_blocks": [item.to_dict() for item in self.fcr_blocks],
            "day_ahead_energy_revenue_eur": self.day_ahead_energy_revenue_eur,
            "fcr_capacity_revenue_eur": self.fcr_capacity_revenue_eur,
            "non_delivery_energy_kwh": self.non_delivery_energy_kwh,
            "penalty_rule_id": self.penalty_rule_id,
            "penalty_eur": self.penalty_eur,
            "charge_energy_kwh": self.charge_energy_kwh,
            "discharge_energy_kwh": self.discharge_energy_kwh,
            "throughput_kwh": self.throughput_kwh,
            "activation_energy_settlement_status": self.activation_energy_settlement_status,
            "imbalance_settlement_status": self.imbalance_settlement_status,
            "degradation_cost_status": self.degradation_cost_status,
            "total_profit_eur": self.total_profit_eur,
        }


@dataclass(frozen=True, slots=True)
class DirectionalFCREnergy:
    """Non-cancelling directional FCR energy under charge-positive power."""

    upward_discharge_kwh: float
    downward_charge_kwh: float
    signed_net_charge_positive_kwh: float
    numeric_tolerance: float = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        upward = _finite(
            self.upward_discharge_kwh,
            field_name="upward_discharge_kwh",
        )
        downward = _finite(
            self.downward_charge_kwh,
            field_name="downward_charge_kwh",
        )
        signed = _finite(
            self.signed_net_charge_positive_kwh,
            field_name="signed_net_charge_positive_kwh",
        )
        tolerance = _finite(self.numeric_tolerance, field_name="numeric_tolerance")
        if upward < 0.0 or downward < 0.0 or tolerance <= 0.0:
            raise FCRSettlementValidationError(
                "directional FCR energy must be non-negative and tolerance positive"
            )
        if abs(signed - (downward - upward)) > tolerance:
            raise FCRSettlementValidationError(
                "directional FCR signed net must equal downward minus upward energy"
            )
        object.__setattr__(self, "upward_discharge_kwh", upward)
        object.__setattr__(self, "downward_charge_kwh", downward)
        object.__setattr__(self, "signed_net_charge_positive_kwh", signed)
        object.__setattr__(self, "numeric_tolerance", tolerance)

    def to_dict(self) -> dict[str, float]:
        return {
            "upward_discharge_kwh": self.upward_discharge_kwh,
            "downward_charge_kwh": self.downward_charge_kwh,
            "signed_net_charge_positive_kwh": self.signed_net_charge_positive_kwh,
        }


@dataclass(frozen=True, slots=True)
class FixedFCRBidSettlement:
    """Additive delivered-energy settlement for reference-result evaluation."""

    profile_id: str
    day_ahead_revenue: ComponentAvailability
    fcr_capacity_revenue: ComponentAvailability
    activation_energy_revenue: ComponentAvailability
    combined_fcr_revenue: ComponentAvailability
    penalty: ComponentAvailability
    intraday: ComponentAvailability
    imbalance: ComponentAvailability
    degradation: ComponentAvailability
    terminal_value: ComponentAvailability
    penalty_rule_id: str
    requested_fcr_energy: DirectionalFCREnergy
    delivered_fcr_energy: DirectionalFCREnergy
    non_delivery_energy_kwh: float
    charge_energy_kwh: float
    discharge_energy_kwh: float
    throughput_kwh: float
    total_profit_eur: float
    reconciliation_error_eur: float
    numeric_tolerance: float = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        from .fcr_bid_evaluation import ComponentAvailability

        if self.profile_id != "robust-storage-bidding-reference-settlement-v1":
            raise FCRSettlementValidationError(
                "reference settlement profile_id is not supported"
            )
        components = (
            self.day_ahead_revenue,
            self.fcr_capacity_revenue,
            self.activation_energy_revenue,
            self.combined_fcr_revenue,
            self.penalty,
            self.intraday,
            self.imbalance,
            self.degradation,
            self.terminal_value,
        )
        if any(not isinstance(item, ComponentAvailability) for item in components):
            raise FCRSettlementValidationError(
                "reference settlement components must declare availability"
            )
        if not isinstance(self.requested_fcr_energy, DirectionalFCREnergy):
            raise FCRSettlementValidationError(
                "requested_fcr_energy must be DirectionalFCREnergy"
            )
        if not isinstance(self.delivered_fcr_energy, DirectionalFCREnergy):
            raise FCRSettlementValidationError(
                "delivered_fcr_energy must be DirectionalFCREnergy"
            )
        for field_name in (
            "non_delivery_energy_kwh",
            "charge_energy_kwh",
            "discharge_energy_kwh",
            "throughput_kwh",
            "total_profit_eur",
            "reconciliation_error_eur",
        ):
            value = _finite(getattr(self, field_name), field_name=field_name)
            object.__setattr__(self, field_name, value)
        tolerance = _finite(self.numeric_tolerance, field_name="numeric_tolerance")
        if tolerance <= 0.0:
            raise FCRSettlementValidationError("numeric_tolerance must be positive")
        object.__setattr__(self, "numeric_tolerance", tolerance)
        if any(
            value < 0.0
            for value in (
                self.non_delivery_energy_kwh,
                self.charge_energy_kwh,
                self.discharge_energy_kwh,
                self.throughput_kwh,
                self.reconciliation_error_eur,
            )
        ):
            raise FCRSettlementValidationError(
                "reference settlement energy and reconciliation values must be non-negative"
            )
        if abs(
            self.throughput_kwh
            - (self.charge_energy_kwh + self.discharge_energy_kwh)
        ) > tolerance:
            raise FCRSettlementValidationError(
                "reference settlement throughput must equal charge plus discharge energy"
            )
        required_available = (
            self.day_ahead_revenue,
            self.fcr_capacity_revenue,
            self.activation_energy_revenue,
            self.combined_fcr_revenue,
            self.penalty,
        )
        if any(item.status != "available" for item in required_available):
            raise FCRSettlementValidationError(
                "reference profile revenue and penalty components must be available"
            )
        combined_error = abs(
            self.combined_fcr_revenue.value_eur
            - (
                self.fcr_capacity_revenue.value_eur
                + self.activation_energy_revenue.value_eur
            )
        )
        if combined_error > tolerance:
            raise FCRSettlementValidationError(
                "combined FCR revenue must equal capacity plus activation revenue"
            )
        reconstructed = (
            self.day_ahead_revenue.value_eur
            + self.combined_fcr_revenue.value_eur
            - self.penalty.value_eur
        )
        actual_error = abs(self.total_profit_eur - reconstructed)
        if actual_error > tolerance:
            raise FCRSettlementValidationError(
                "reference settlement components do not reconcile to total profit"
            )
        if abs(self.reconciliation_error_eur - actual_error) > tolerance:
            raise FCRSettlementValidationError(
                "reference settlement reconciliation_error_eur is inconsistent"
            )
        object.__setattr__(
            self,
            "penalty_rule_id",
            _non_empty(self.penalty_rule_id, field_name="penalty_rule_id"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "day_ahead_revenue": self.day_ahead_revenue.to_dict(),
            "fcr_capacity_revenue": self.fcr_capacity_revenue.to_dict(),
            "activation_energy_revenue": self.activation_energy_revenue.to_dict(),
            "combined_fcr_revenue": self.combined_fcr_revenue.to_dict(),
            "penalty": self.penalty.to_dict(),
            "intraday": self.intraday.to_dict(),
            "imbalance": self.imbalance.to_dict(),
            "degradation": self.degradation.to_dict(),
            "terminal_value": self.terminal_value.to_dict(),
            "penalty_rule_id": self.penalty_rule_id,
            "requested_fcr_energy": self.requested_fcr_energy.to_dict(),
            "delivered_fcr_energy": self.delivered_fcr_energy.to_dict(),
            "non_delivery_energy_kwh": self.non_delivery_energy_kwh,
            "charge_energy_kwh": self.charge_energy_kwh,
            "discharge_energy_kwh": self.discharge_energy_kwh,
            "throughput_kwh": self.throughput_kwh,
            "total_profit_eur": self.total_profit_eur,
            "reconciliation_error_eur": self.reconciliation_error_eur,
        }



def _same_interval(left: CanonicalInterval, right: CanonicalInterval) -> bool:
    return left.start_utc == right.start_utc and left.end_utc == right.end_utc


def _aligned_with_prices(
    scheduled: Sequence[Any],
    prices: Sequence[Any],
    *,
    label: str,
) -> Iterator[tuple[Any, Any, float]]:
    """Pair schedule intervals with same-interval prices and their duration in hours."""

    if len(prices) != len(scheduled):
        raise FCRSettlementValidationError(
            f"{label} prices do not align with the accepted schedule"
        )
    for index, (item, price) in enumerate(zip(scheduled, prices, strict=True)):
        if not _same_interval(item.interval, price.interval):
            raise FCRSettlementValidationError(
                f"{label} price observation {index} is not aligned"
            )
        duration = (item.interval.end_utc - item.interval.start_utc).total_seconds() / 3600.0
        yield item, price, duration


def settle_stacked_services(
    request: StackedServiceReplayRequest,
    samples: Sequence[ReplaySample],
) -> SettlementBreakdown:
    """Settle accepted schedules and an optional explicit non-delivery rule."""

    from .stacked_service import ReplaySample, StackedServiceReplayRequest

    if not isinstance(request, StackedServiceReplayRequest):
        raise FCRSettlementValidationError(
            "request must be a validated StackedServiceReplayRequest"
        )
    if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence):
        raise FCRSettlementValidationError("samples must be a replay-sample sequence")
    replay_samples = samples if isinstance(samples, tuple) else tuple(samples)
    if len(replay_samples) != len(request.time_contract.index.activation_intervals):
        raise FCRSettlementValidationError(
            "samples must exactly cover every activation interval"
        )
    if any(not isinstance(sample, ReplaySample) for sample in replay_samples):
        raise FCRSettlementValidationError("samples contain a non-ReplaySample value")

    energy_items: list[EnergySettlementInterval] = []
    for schedule, observation, duration in _aligned_with_prices(
        request.energy_schedule.intervals,
        request.market_artifact.series["day_ahead_price"].observations,
        label="day-ahead",
    ):
        revenue = -(schedule.power_kw * duration) * observation.value / 1000.0
        energy_items.append(
            EnergySettlementInterval(
                interval=schedule.interval,
                accepted_power_kw=schedule.power_kw,
                duration_hours=duration,
                price_eur_per_mwh=observation.value,
                revenue_eur=revenue,
            )
        )

    fcr_items: list[FCRSettlementBlock] = []
    for commitment, observation, duration in _aligned_with_prices(
        request.fcr_schedule.intervals,
        request.market_artifact.series["fcr_capacity_price"].observations,
        label="FCR capacity",
    ):
        revenue = commitment.capacity_kw / 1000.0 * observation.value * duration
        fcr_items.append(
            FCRSettlementBlock(
                interval=commitment.interval,
                committed_capacity_kw=commitment.capacity_kw,
                duration_hours=duration,
                capacity_price_eur_per_mw_per_h=observation.value,
                revenue_eur=revenue,
            )
        )

    energy_revenue = sum(item.revenue_eur for item in energy_items)
    fcr_revenue = sum(item.revenue_eur for item in fcr_items)
    non_delivery = sum(sample.non_delivery_energy_kwh for sample in replay_samples)
    charge_energy = sum(sample.charge_energy_kwh for sample in replay_samples)
    discharge_energy = sum(sample.discharge_energy_kwh for sample in replay_samples)
    rule = request.penalty_rule
    if rule is None:
        rule_id = None
        penalty = 0.0
    elif isinstance(rule, FCRPenaltyRule):
        rule_id = rule.rule_id
        penalty = non_delivery * rule.rate
    else:
        raise FCRSettlementValidationError(
            "penalty rule must be an explicit FCRPenaltyRule or None"
        )
    return SettlementBreakdown(
        energy_intervals=tuple(energy_items),
        fcr_blocks=tuple(fcr_items),
        day_ahead_energy_revenue_eur=energy_revenue,
        fcr_capacity_revenue_eur=fcr_revenue,
        non_delivery_energy_kwh=non_delivery,
        penalty_rule_id=rule_id,
        penalty_eur=penalty,
        charge_energy_kwh=charge_energy,
        discharge_energy_kwh=discharge_energy,
        throughput_kwh=charge_energy + discharge_energy,
        activation_energy_settlement_status="not_modeled",
        imbalance_settlement_status="not_modeled",
        degradation_cost_status="not_modeled",
        total_profit_eur=energy_revenue + fcr_revenue - penalty,
    )


def settle_fixed_fcr_bid(
    request: FCRBidEvaluationRequest,
    samples: Sequence[ReplaySample],
) -> FixedFCRBidSettlement:
    """Settle one valid fixed plan under the explicit reference-result profile."""

    from .fcr_bid_evaluation import (
        ComponentAvailability,
        FCRBidEvaluationRequest,
        REFERENCE_SETTLEMENT_PROFILE,
    )
    from .stacked_service import ReplaySample

    if not isinstance(request, FCRBidEvaluationRequest):
        raise FCRSettlementValidationError(
            "request must be a validated FCRBidEvaluationRequest"
        )
    if request.settlement_profile != REFERENCE_SETTLEMENT_PROFILE:
        raise FCRSettlementValidationError(
            "reference settlement requires the explicit reference profile"
        )
    if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence):
        raise FCRSettlementValidationError("samples must be a replay-sample sequence")
    replay_samples = samples if isinstance(samples, tuple) else tuple(samples)
    if len(replay_samples) != len(request.time_contract.index.activation_intervals):
        raise FCRSettlementValidationError(
            "samples must exactly cover every activation interval"
        )
    energy_revenue = 0.0
    for schedule, price, duration in _aligned_with_prices(
        request.energy_schedule.intervals,
        request.market_context.day_ahead_prices,
        label="day-ahead",
    ):
        if price.canonical_unit != "EUR/MWh":
            raise FCRSettlementValidationError(
                "day-ahead price canonical unit must be EUR/MWh"
            )
        energy_revenue += -(
            schedule.power_kw * duration * price.canonical_value / 1000.0
        )

    capacity_revenue = 0.0
    for commitment, price, duration in _aligned_with_prices(
        request.fcr_schedule.intervals,
        request.market_context.fcr_capacity_prices,
        label="FCR capacity",
    ):
        if price.canonical_unit == "EUR/kW/block":
            capacity_revenue += commitment.capacity_kw * price.canonical_value
        elif price.canonical_unit == "EUR/MW/h":
            capacity_revenue += (
                commitment.capacity_kw
                / 1000.0
                * price.canonical_value
                * duration
            )
        else:
            raise FCRSettlementValidationError(
                "FCR capacity price must be EUR/kW/block or EUR/MW/h"
            )

    index = request.time_contract.index
    activation_revenue = 0.0
    requested_upward = 0.0
    requested_downward = 0.0
    delivered_upward = 0.0
    delivered_downward = 0.0
    aggregate_values: list[tuple[float, float, float]] = []
    for sample_index, sample in enumerate(replay_samples):
        if not isinstance(sample, ReplaySample):
            raise FCRSettlementValidationError(
                "samples contain a non-ReplaySample value"
            )
        energy_index = index.activation_to_energy[sample_index]
        price = request.market_context.day_ahead_prices[energy_index]
        duration = (
            sample.interval.end_utc - sample.interval.start_utc
        ).total_seconds() / 3600.0
        activation_revenue += -(
            sample.delivered_fcr_power_kw
            * duration
            * price.canonical_value
            / 1000.0
        )
        requested_upward += max(-sample.requested_fcr_power_kw, 0.0) * duration
        requested_downward += max(sample.requested_fcr_power_kw, 0.0) * duration
        delivered_upward += max(-sample.delivered_fcr_power_kw, 0.0) * duration
        delivered_downward += max(sample.delivered_fcr_power_kw, 0.0) * duration
        aggregate_values.append(
            (
                sample.non_delivery_energy_kwh,
                sample.charge_energy_kwh,
                sample.discharge_energy_kwh,
            )
        )

    non_delivery = sum(item[0] for item in aggregate_values)
    charge_energy = sum(item[1] for item in aggregate_values)
    discharge_energy = sum(item[2] for item in aggregate_values)
    if request.penalty_rule is None:
        penalty_rule_id = "no_penalty_rule"
        penalty = 0.0
    elif isinstance(request.penalty_rule, FCRPenaltyRule):
        penalty_rule_id = request.penalty_rule.rule_id
        penalty = non_delivery * request.penalty_rule.rate
    else:
        raise FCRSettlementValidationError(
            "penalty rule must be an explicit FCRPenaltyRule or None"
        )
    total = energy_revenue + capacity_revenue + activation_revenue - penalty
    combined_fcr_revenue = capacity_revenue + activation_revenue
    reconstructed = energy_revenue + combined_fcr_revenue - penalty
    reconciliation_error = abs(total - reconstructed)
    if reconciliation_error > request.numeric_tolerance:
        raise FCRSettlementValidationError(
            "reference settlement components do not reconcile to total profit"
        )
    return FixedFCRBidSettlement(
        profile_id=REFERENCE_SETTLEMENT_PROFILE,
        day_ahead_revenue=ComponentAvailability.available(energy_revenue),
        fcr_capacity_revenue=ComponentAvailability.available(capacity_revenue),
        activation_energy_revenue=ComponentAvailability.available(activation_revenue),
        combined_fcr_revenue=ComponentAvailability.available(combined_fcr_revenue),
        penalty=ComponentAvailability.available(penalty),
        intraday=ComponentAvailability.unavailable(
            "intraday settlement is unavailable in reference profile v1"
        ),
        imbalance=ComponentAvailability.unavailable(
            "imbalance settlement is unavailable in reference profile v1"
        ),
        degradation=ComponentAvailability.unavailable(
            "degradation cost is unavailable in reference profile v1"
        ),
        terminal_value=ComponentAvailability.unavailable(
            "terminal value is unavailable in reference profile v1"
        ),
        penalty_rule_id=penalty_rule_id,
        requested_fcr_energy=DirectionalFCREnergy(
            upward_discharge_kwh=requested_upward,
            downward_charge_kwh=requested_downward,
            signed_net_charge_positive_kwh=(
                requested_downward - requested_upward
            ),
            numeric_tolerance=request.numeric_tolerance,
        ),
        delivered_fcr_energy=DirectionalFCREnergy(
            upward_discharge_kwh=delivered_upward,
            downward_charge_kwh=delivered_downward,
            signed_net_charge_positive_kwh=(
                delivered_downward - delivered_upward
            ),
            numeric_tolerance=request.numeric_tolerance,
        ),
        non_delivery_energy_kwh=non_delivery,
        charge_energy_kwh=charge_energy,
        discharge_energy_kwh=discharge_energy,
        throughput_kwh=charge_energy + discharge_energy,
        total_profit_eur=total,
        reconciliation_error_eur=reconciliation_error,
        numeric_tolerance=request.numeric_tolerance,
    )


__all__ = [
    "EnergySettlementInterval",
    "DirectionalFCREnergy",
    "FCRPenaltyRule",
    "FCRSettlementBlock",
    "FCRSettlementValidationError",
    "SettlementBreakdown",
    "FixedFCRBidSettlement",
    "settle_fixed_fcr_bid",
    "settle_stacked_services",
]
