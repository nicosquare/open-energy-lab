"""Deterministic settlement for fixed day-ahead and symmetric-FCR schedules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
from typing import TYPE_CHECKING

from open_energy_lab.market.time import CanonicalInterval

if TYPE_CHECKING:
    from .stacked_service import ReplaySample, StackedServiceReplayRequest


class FCRSettlementValidationError(ValueError):
    """Raised when explicit settlement inputs have incompatible semantics."""


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FCRSettlementValidationError(f"{field_name} must be finite")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise FCRSettlementValidationError(f"{field_name} must be finite")
    return normalized


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FCRSettlementValidationError(f"{field_name} must be a non-empty string")
    return value


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


def _same_interval(left: CanonicalInterval, right: CanonicalInterval) -> bool:
    return left.start_utc == right.start_utc and left.end_utc == right.end_utc


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
    replay_samples = tuple(samples)
    if len(replay_samples) != len(request.time_contract.index.activation_intervals):
        raise FCRSettlementValidationError(
            "samples must exactly cover every activation interval"
        )
    if any(not isinstance(sample, ReplaySample) for sample in replay_samples):
        raise FCRSettlementValidationError("samples contain a non-ReplaySample value")

    price_observations = request.market_artifact.series["day_ahead_price"].observations
    if len(price_observations) != len(request.energy_schedule.intervals):
        raise FCRSettlementValidationError(
            "day-ahead price observations do not align with the accepted schedule"
        )
    energy_items: list[EnergySettlementInterval] = []
    for index, (schedule, observation) in enumerate(
        zip(request.energy_schedule.intervals, price_observations, strict=True)
    ):
        if not _same_interval(schedule.interval, observation.interval):
            raise FCRSettlementValidationError(
                f"day-ahead price observation {index} is not aligned"
            )
        duration = (
            schedule.interval.end_utc - schedule.interval.start_utc
        ).total_seconds() / 3600.0
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

    fcr_price_observations = request.market_artifact.series[
        "fcr_capacity_price"
    ].observations
    if len(fcr_price_observations) != len(request.fcr_schedule.intervals):
        raise FCRSettlementValidationError(
            "FCR capacity-price observations do not align with commitments"
        )
    fcr_items: list[FCRSettlementBlock] = []
    for index, (commitment, observation) in enumerate(
        zip(request.fcr_schedule.intervals, fcr_price_observations, strict=True)
    ):
        if not _same_interval(commitment.interval, observation.interval):
            raise FCRSettlementValidationError(
                f"FCR capacity-price observation {index} is not aligned"
            )
        duration = (
            commitment.interval.end_utc - commitment.interval.start_utc
        ).total_seconds() / 3600.0
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


__all__ = [
    "EnergySettlementInterval",
    "FCRPenaltyRule",
    "FCRSettlementBlock",
    "FCRSettlementValidationError",
    "SettlementBreakdown",
    "settle_stacked_services",
]
