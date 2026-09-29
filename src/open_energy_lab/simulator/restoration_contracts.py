"""Directional restoration capacity, energy-baseline, and capability contracts.

Controllers produce these schedules and capabilities; the simulator replays
and settles them. The heuristic baseline builders that produce them live in
``open_energy_lab.control.restoration_service``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import fingerprint
from open_energy_lab.core.validation import (
    finite,
    mapping,
    non_empty_str,
    non_negative,
    positive,
    sequence,
)
from open_energy_lab.market.restoration_activation import (
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import (
    CanonicalInterval,
)


RESTORATION_CAPABILITY_SCHEMA_VERSION = "oel.restoration.capability.v1"


class RestorationControlValidationError(ValidationError):
    """Raised when restoration control inputs are incomplete or infeasible."""


_non_empty = partial(non_empty_str, error=RestorationControlValidationError)
_finite = partial(finite, error=RestorationControlValidationError)
_non_negative = partial(non_negative, error=RestorationControlValidationError)
_positive = partial(positive, error=RestorationControlValidationError)


def _product(value: object, *, field_name: str = "product") -> RestorationProduct:
    try:
        return RestorationProduct(value)
    except (TypeError, ValueError) as exc:
        raise RestorationControlValidationError(
            f"{field_name} must be AFRR or MFRR"
        ) from exc


def _direction(value: object) -> RestorationDirection:
    try:
        return RestorationDirection(value)
    except (TypeError, ValueError) as exc:
        raise RestorationControlValidationError(
            "direction must be UPWARD or DOWNWARD"
        ) from exc


def _interval(value: object, *, field_name: str) -> CanonicalInterval:
    if not isinstance(value, CanonicalInterval):
        raise RestorationControlValidationError(
            f"{field_name} must be a CanonicalInterval"
        )
    return value


_mapping = partial(mapping, error=RestorationControlValidationError)
_sequence = partial(sequence, error=RestorationControlValidationError)
_fingerprint = partial(fingerprint, error=RestorationControlValidationError)


@dataclass(frozen=True, slots=True)
class DirectionalCapacityCommitmentInterval:
    interval: CanonicalInterval
    product: RestorationProduct
    direction: RestorationDirection
    committed_capacity_kw: float
    eligibility: bool
    source_or_assumption_ref: str

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "product": self.product.value,
            "direction": self.direction.value,
            "committed_capacity_kw": self.committed_capacity_kw,
            "eligibility": self.eligibility,
            "source_or_assumption_ref": self.source_or_assumption_ref,
        }


@dataclass(frozen=True, slots=True)
class DirectionalCapacitySchedule:
    schedule_id: str
    semantics_version: str
    product: RestorationProduct
    period: CanonicalInterval
    intervals: tuple[DirectionalCapacityCommitmentInterval, ...]
    schedule_fingerprint: str

    def intervals_for(
        self, direction: RestorationDirection
    ) -> tuple[DirectionalCapacityCommitmentInterval, ...]:
        if not isinstance(direction, RestorationDirection):
            raise RestorationControlValidationError(
                "direction must be a RestorationDirection"
            )
        return tuple(item for item in self.intervals if item.direction is direction)

    def commitment_covering(
        self,
        interval: CanonicalInterval,
        direction: RestorationDirection,
    ) -> DirectionalCapacityCommitmentInterval:
        matches = [
            item
            for item in self.intervals_for(direction)
            if item.interval.start_utc <= interval.start_utc
            and item.interval.end_utc >= interval.end_utc
        ]
        if len(matches) != 1:
            raise RestorationControlValidationError(
                f"no unique {direction.value} commitment covers baseline interval"
            )
        return matches[0]

    def commitment_pairs_covering(
        self,
        intervals: Sequence[CanonicalInterval],
    ) -> tuple[
        tuple[
            DirectionalCapacityCommitmentInterval,
            DirectionalCapacityCommitmentInterval,
        ],
        ...,
    ]:
        """Resolve chronological intervals with one linear cursor per direction."""

        targets = tuple(intervals)
        if any(not isinstance(item, CanonicalInterval) for item in targets):
            raise RestorationControlValidationError(
                "covered intervals must be CanonicalInterval values"
            )
        for previous, current in zip(targets, targets[1:]):
            if current.start_utc < previous.end_utc:
                raise RestorationControlValidationError(
                    "covered intervals must be chronological and non-overlapping"
                )

        directional = {
            direction: self.intervals_for(direction)
            for direction in RestorationDirection
        }
        cursors = {direction: 0 for direction in RestorationDirection}
        resolved: list[
            tuple[
                DirectionalCapacityCommitmentInterval,
                DirectionalCapacityCommitmentInterval,
            ]
        ] = []
        for target in targets:
            pair: dict[
                RestorationDirection,
                DirectionalCapacityCommitmentInterval,
            ] = {}
            for direction in RestorationDirection:
                candidates = directional[direction]
                cursor = cursors[direction]
                while (
                    cursor < len(candidates)
                    and candidates[cursor].interval.end_utc <= target.start_utc
                ):
                    cursor += 1
                cursors[direction] = cursor
                if cursor >= len(candidates):
                    raise RestorationControlValidationError(
                        f"no unique {direction.value} commitment covers baseline interval"
                    )
                candidate = candidates[cursor]
                if not (
                    candidate.interval.start_utc <= target.start_utc
                    and candidate.interval.end_utc >= target.end_utc
                ):
                    raise RestorationControlValidationError(
                        f"no unique {direction.value} commitment covers baseline interval"
                    )
                pair[direction] = candidate
            resolved.append(
                (
                    pair[RestorationDirection.UPWARD],
                    pair[RestorationDirection.DOWNWARD],
                )
            )
        return tuple(resolved)

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "semantics_version": self.semantics_version,
            "product": self.product.value,
            "period": self.period.to_dict(),
            "intervals": [item.to_dict() for item in self.intervals],
            "schedule_fingerprint": self.schedule_fingerprint,
        }


def _validate_complete_direction(
    intervals: Sequence[DirectionalCapacityCommitmentInterval],
    *,
    direction: RestorationDirection,
    period: CanonicalInterval,
) -> None:
    selected = sorted(
        (item for item in intervals if item.direction is direction),
        key=lambda item: item.interval.start_utc,
    )
    if not selected:
        raise RestorationControlValidationError(
            f"{direction.value} direction requires explicit complete coverage"
        )
    cursor = period.start_utc
    for item in selected:
        if item.interval.start_utc != cursor:
            raise RestorationControlValidationError(
                f"{direction.value} commitment coverage has a gap or overlap"
            )
        cursor = item.interval.end_utc
    if cursor != period.end_utc:
        raise RestorationControlValidationError(
            f"{direction.value} commitment coverage is incomplete"
        )


def build_directional_capacity_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    product: RestorationProduct | str,
    period: CanonicalInterval,
    intervals: Sequence[Mapping[str, object]],
) -> DirectionalCapacitySchedule:
    """Build complete independent upward and downward capacity schedules."""

    normalized_product = _product(product)
    normalized_period = _interval(period, field_name="period")
    normalized: list[DirectionalCapacityCommitmentInterval] = []
    for index, value in enumerate(_sequence(intervals, field_name="intervals")):
        item = _mapping(value, field_name=f"intervals[{index}]")
        required = {
            "interval",
            "product",
            "direction",
            "committed_capacity_kw",
            "eligibility",
            "source_or_assumption_ref",
        }
        missing = sorted(required - set(item))
        if missing:
            raise RestorationControlValidationError(
                f"intervals[{index}] is missing: {', '.join(missing)}"
            )
        interval = _interval(item["interval"], field_name=f"intervals[{index}].interval")
        if (
            interval.start_utc < normalized_period.start_utc
            or interval.end_utc > normalized_period.end_utc
        ):
            raise RestorationControlValidationError(
                f"intervals[{index}] lies outside the schedule period"
            )
        item_product = _product(item["product"], field_name=f"intervals[{index}].product")
        if item_product is not normalized_product:
            raise RestorationControlValidationError(
                f"intervals[{index}] product does not match the schedule"
            )
        eligibility = item["eligibility"]
        if not isinstance(eligibility, bool):
            raise RestorationControlValidationError("eligibility must be boolean")
        capacity = _non_negative(
            item["committed_capacity_kw"],
            field_name=f"intervals[{index}].committed_capacity_kw",
        )
        if not eligibility and capacity != 0.0:
            raise RestorationControlValidationError(
                "ineligible commitment intervals must declare zero capacity"
            )
        normalized.append(
            DirectionalCapacityCommitmentInterval(
                interval=interval,
                product=item_product,
                direction=_direction(item["direction"]),
                committed_capacity_kw=capacity,
                eligibility=eligibility,
                source_or_assumption_ref=_non_empty(
                    item["source_or_assumption_ref"],
                    field_name=f"intervals[{index}].source_or_assumption_ref",
                ),
            )
        )
    for direction in RestorationDirection:
        _validate_complete_direction(
            normalized, direction=direction, period=normalized_period
        )
    ordered = tuple(
        sorted(
            normalized,
            key=lambda item: (
                0 if item.direction is RestorationDirection.UPWARD else 1,
                item.interval.start_utc,
            ),
        )
    )
    payload = {
        "schedule_id": _non_empty(schedule_id, field_name="schedule_id"),
        "semantics_version": _non_empty(
            semantics_version, field_name="semantics_version"
        ),
        "product": normalized_product.value,
        "period": normalized_period.to_dict(),
        "intervals": [item.to_dict() for item in ordered],
    }
    return DirectionalCapacitySchedule(
        schedule_id=str(payload["schedule_id"]),
        semantics_version=str(payload["semantics_version"]),
        product=normalized_product,
        period=normalized_period,
        intervals=ordered,
        schedule_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class RestorationEnergyBaselineInterval:
    interval: CanonicalInterval
    accepted_baseline_power_kw: float

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "accepted_baseline_power_kw": self.accepted_baseline_power_kw,
        }


@dataclass(frozen=True, slots=True)
class RestorationEnergyBaselineSchedule:
    schedule_id: str
    semantics_version: str
    product: RestorationProduct
    period: CanonicalInterval
    source: str
    intervals: tuple[RestorationEnergyBaselineInterval, ...]
    schedule_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schedule_id": self.schedule_id,
            "semantics_version": self.semantics_version,
            "product": self.product.value,
            "period": self.period.to_dict(),
            "source": self.source,
            "intervals": [item.to_dict() for item in self.intervals],
            "schedule_fingerprint": self.schedule_fingerprint,
        }


def build_restoration_energy_baseline_schedule(
    *,
    schedule_id: str,
    semantics_version: str,
    product: RestorationProduct | str,
    period: CanonicalInterval,
    source: str,
    intervals: Sequence[Mapping[str, object]],
) -> RestorationEnergyBaselineSchedule:
    """Build one complete charge-positive fixed restoration baseline."""

    normalized_period = _interval(period, field_name="period")
    normalized_product = _product(product)
    normalized = []
    for index, value in enumerate(_sequence(intervals, field_name="intervals")):
        item = _mapping(value, field_name=f"intervals[{index}]")
        if "interval" not in item or "accepted_baseline_power_kw" not in item:
            raise RestorationControlValidationError(
                f"intervals[{index}] requires interval and accepted_baseline_power_kw"
            )
        normalized.append(
            RestorationEnergyBaselineInterval(
                interval=_interval(
                    item["interval"], field_name=f"intervals[{index}].interval"
                ),
                accepted_baseline_power_kw=_finite(
                    item["accepted_baseline_power_kw"],
                    field_name=f"intervals[{index}].accepted_baseline_power_kw",
                ),
            )
        )
    normalized.sort(key=lambda item: item.interval.start_utc)
    cursor = normalized_period.start_utc
    for item in normalized:
        if item.interval.start_utc != cursor:
            raise RestorationControlValidationError(
                "restoration baseline coverage has a gap or overlap"
            )
        cursor = item.interval.end_utc
    if not normalized or cursor != normalized_period.end_utc:
        raise RestorationControlValidationError(
            "restoration baseline coverage is incomplete"
        )
    payload = {
        "schedule_id": _non_empty(schedule_id, field_name="schedule_id"),
        "semantics_version": _non_empty(
            semantics_version, field_name="semantics_version"
        ),
        "product": normalized_product.value,
        "period": normalized_period.to_dict(),
        "source": _non_empty(source, field_name="source"),
        "intervals": [item.to_dict() for item in normalized],
    }
    return RestorationEnergyBaselineSchedule(
        schedule_id=str(payload["schedule_id"]),
        semantics_version=str(payload["semantics_version"]),
        product=normalized_product,
        period=normalized_period,
        source=str(payload["source"]),
        intervals=tuple(normalized),
        schedule_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class RestorationCapability:
    schema_version: str
    max_ramp_up_kw_per_second: float
    max_ramp_down_kw_per_second: float
    max_activation_delay_seconds: Mapping[RestorationProduct, float]
    min_supported_duration_seconds: Mapping[RestorationProduct, float]
    max_supported_duration_seconds: Mapping[RestorationProduct, float]
    capability_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "max_ramp_up_kw_per_second": self.max_ramp_up_kw_per_second,
            "max_ramp_down_kw_per_second": self.max_ramp_down_kw_per_second,
            "max_activation_delay_seconds": {
                product.value: self.max_activation_delay_seconds[product]
                for product in RestorationProduct
            },
            "min_supported_duration_seconds": {
                product.value: self.min_supported_duration_seconds[product]
                for product in RestorationProduct
            },
            "max_supported_duration_seconds": {
                product.value: self.max_supported_duration_seconds[product]
                for product in RestorationProduct
            },
            "capability_fingerprint": self.capability_fingerprint,
        }


def _product_values(
    value: object,
    *,
    field_name: str,
    positive: bool,
) -> Mapping[RestorationProduct, float]:
    raw = _mapping(value, field_name=field_name)
    if set(raw) != {product.value for product in RestorationProduct}:
        raise RestorationControlValidationError(
            f"{field_name} must be complete for AFRR and MFRR product values"
        )
    validator = _positive if positive else _non_negative
    return MappingProxyType(
        {
            product: validator(raw[product.value], field_name=f"{field_name}.{product.value}")
            for product in RestorationProduct
        }
    )


def build_restoration_capability(payload: Mapping[str, object]) -> RestorationCapability:
    """Build service ramp, delay, and duration capabilities for both products."""

    data = _mapping(payload, field_name="restoration capability")
    required = {
        "max_ramp_up_kw_per_second",
        "max_ramp_down_kw_per_second",
        "max_activation_delay_seconds",
        "min_supported_duration_seconds",
        "max_supported_duration_seconds",
    }
    missing = sorted(required - set(data))
    if missing:
        raise RestorationControlValidationError(
            f"restoration capability is missing: {', '.join(missing)}"
        )
    delays = _product_values(
        data["max_activation_delay_seconds"],
        field_name="max_activation_delay_seconds",
        positive=False,
    )
    minimums = _product_values(
        data["min_supported_duration_seconds"],
        field_name="min_supported_duration_seconds",
        positive=False,
    )
    maximums = _product_values(
        data["max_supported_duration_seconds"],
        field_name="max_supported_duration_seconds",
        positive=True,
    )
    for product in RestorationProduct:
        if maximums[product] < minimums[product]:
            raise RestorationControlValidationError(
                f"{product.value} maximum duration must be >= minimum duration"
            )
    provisional = RestorationCapability(
        schema_version=RESTORATION_CAPABILITY_SCHEMA_VERSION,
        max_ramp_up_kw_per_second=_positive(
            data["max_ramp_up_kw_per_second"],
            field_name="max_ramp_up_kw_per_second",
        ),
        max_ramp_down_kw_per_second=_positive(
            data["max_ramp_down_kw_per_second"],
            field_name="max_ramp_down_kw_per_second",
        ),
        max_activation_delay_seconds=delays,
        min_supported_duration_seconds=minimums,
        max_supported_duration_seconds=maximums,
        capability_fingerprint="0" * 64,
    )
    payload_for_fingerprint = provisional.to_dict()
    payload_for_fingerprint.pop("capability_fingerprint")
    return RestorationCapability(
        schema_version=provisional.schema_version,
        max_ramp_up_kw_per_second=provisional.max_ramp_up_kw_per_second,
        max_ramp_down_kw_per_second=provisional.max_ramp_down_kw_per_second,
        max_activation_delay_seconds=delays,
        min_supported_duration_seconds=minimums,
        max_supported_duration_seconds=maximums,
        capability_fingerprint=_fingerprint(payload_for_fingerprint),
    )
