"""Source-independent restoration activation identities and derived mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from functools import partial
from typing import Any

from open_energy_lab.core.artifact import (
    PLACEHOLDER_FINGERPRINT,
    payload_without,
    seal_fingerprints,
)
from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.time import format_utc, utc_timestamp_text
from open_energy_lab.core.validation import (
    enum_member,
    finite,
    mapping,
    non_empty_str,
    require_fields,
    sequence,
    sha256_digest,
)

from .time import (
    CanonicalInterval,
    MarketTimeValidationError,
    parse_iso8601_duration,
)


RESTORATION_MAPPING_SCHEMA_VERSION = "oel.restoration.derived-mapping.v1"
SUPPORTED_RESTORATION_MAPPING_SCHEMA_VERSIONS = (
    RESTORATION_MAPPING_SCHEMA_VERSION,
)
AFRR_TRAJECTORY_SCHEMA_VERSION = "oel.restoration.afrr-trajectory.v1"
SUPPORTED_AFRR_TRAJECTORY_SCHEMA_VERSIONS = (AFRR_TRAJECTORY_SCHEMA_VERSION,)
AFRR_SAMPLE_SEMANTICS = "interval_average_requested_bess_power_kw"
RESTORATION_SIGN_CONVENTION = "positive_charge_negative_discharge"
MFRR_EVENTS_SCHEMA_VERSION = "oel.restoration.mfrr-events.v1"
SUPPORTED_MFRR_EVENTS_SCHEMA_VERSIONS = (MFRR_EVENTS_SCHEMA_VERSION,)
MFRR_EVENT_SHAPE_SEMANTICS = "delay_linear_ramp_hold_linear_ramp"
_TOLERANCE = 1e-6


class RestorationProduct(str, Enum):
    """aFRR and mFRR restoration products; FCR is intentionally absent."""

    AFRR = "AFRR"
    MFRR = "MFRR"


class RestorationDirection(str, Enum):
    """Directional restoration commitment and delivery identity.

    Battery power is positive for charge, so an upward (discharge) request is
    negative and a downward (charge) request is positive.
    """

    UPWARD = "UPWARD"
    DOWNWARD = "DOWNWARD"

    def signed(self, magnitude: float) -> float:
        """Battery-signed power or energy for a non-negative magnitude."""

        return -magnitude if self is RestorationDirection.UPWARD else magnitude

    def magnitude_of(self, signed_value: float) -> float:
        """The part of a battery-signed value that goes in this direction."""

        return max(0.0, -signed_value if self is RestorationDirection.UPWARD else signed_value)

    @classmethod
    def of_signed(cls, signed_value: float) -> RestorationDirection | None:
        """Direction of a battery-signed value; ``None`` for zero."""

        if signed_value < 0.0:
            return cls.UPWARD
        if signed_value > 0.0:
            return cls.DOWNWARD
        return None

    @classmethod
    def of_two_sided(cls, upward: float, downward: float) -> RestorationDirection | None:
        """Direction of a source that reports upward and downward volumes separately."""

        if upward > 0.0:
            return cls.UPWARD
        if downward > 0.0:
            return cls.DOWNWARD
        return None


class MFRRActivationKind(str, Enum):
    """Non-interchangeable manual restoration activation kinds."""

    SCHEDULED = "SCHEDULED"
    DIRECT = "DIRECT"


class RestorationSourceKind(str, Enum):
    """Provenance kind for one asset-level activation input."""

    ASSET_SUPPLIED = "ASSET_SUPPLIED"
    SYNTHETIC = "SYNTHETIC"
    DERIVED_SIMULATION = "DERIVED_SIMULATION"


class RestorationActivationValidationError(ValidationError):
    """Raised when a restoration activation or mapping contract is invalid."""


class RestorationActivationIntegrityError(RestorationActivationValidationError):
    """Raised when a persisted activation identity does not verify."""


_mapping = partial(mapping, error=RestorationActivationValidationError)
_sequence = partial(sequence, error=RestorationActivationValidationError)
_required = partial(require_fields, error=RestorationActivationValidationError)
_non_empty = partial(non_empty_str, error=RestorationActivationValidationError)
_finite = partial(finite, error=RestorationActivationValidationError)
_sha256 = partial(sha256_digest, error=RestorationActivationValidationError)
_utc_timestamp = partial(utc_timestamp_text, error=RestorationActivationValidationError)
_enum = partial(enum_member, error=RestorationActivationValidationError)


def _unique_digests(value: object, *, field_name: str, required: bool) -> tuple[str, ...]:
    digests = tuple(
        _sha256(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(_sequence(value, field_name=field_name))
    )
    if required and not digests:
        raise RestorationActivationValidationError(
            f"{field_name} must be non-empty"
        )
    if len(set(digests)) != len(digests):
        raise RestorationActivationValidationError(f"{field_name} must be unique")
    return digests


def _interval(value: object, *, field_name: str) -> CanonicalInterval:
    if isinstance(value, CanonicalInterval):
        return value
    try:
        return CanonicalInterval.from_dict(_mapping(value, field_name=field_name))
    except MarketTimeValidationError as exc:
        raise RestorationActivationValidationError(
            f"{field_name}: {exc}"
        ) from exc


def _source_refs(value: object, *, field_name: str) -> tuple[str, ...]:
    refs = tuple(
        _non_empty(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(_sequence(value, field_name=field_name))
    )
    if not refs:
        raise RestorationActivationValidationError(
            f"{field_name} must be non-empty"
        )
    if len(set(refs)) != len(refs):
        raise RestorationActivationValidationError(f"{field_name} must be unique")
    return refs


@dataclass(frozen=True, slots=True)
class DerivedSimulationMapping:
    """Auditable fixed-fraction mapping from an area aggregate to one BESS."""

    schema_version: str
    mapping_id: str
    source_artifact_fingerprint: str
    source_series_fingerprints: tuple[str, ...]
    product: RestorationProduct
    direction: RestorationDirection
    asset_allocation_fraction: float
    unit_scale_kw_per_mw: float
    capacity_commitment_ref: str
    driver_semantics: str
    comparison_series: tuple[str, ...]
    assumptions: tuple[str, ...]
    created_at_utc: str
    source_kind: RestorationSourceKind
    output_label: str
    mapping_fingerprint: str

    def map_area_value_kw(self, area_requested_mw: float) -> float:
        """Apply the disclosed formula directly, without clipping or normalization."""

        area_value = _finite(area_requested_mw, field_name="area_requested_mw")
        if area_value < 0:
            raise RestorationActivationValidationError(
                "area_requested_mw driver must be non-negative"
            )
        magnitude = (
            area_value * self.unit_scale_kw_per_mw * self.asset_allocation_fraction
        )
        if magnitude == 0.0:
            return 0.0
        return self.direction.signed(magnitude)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "mapping_id": self.mapping_id,
            "source_artifact_fingerprint": self.source_artifact_fingerprint,
            "source_series_fingerprints": list(self.source_series_fingerprints),
            "product": self.product.value,
            "direction": self.direction.value,
            "asset_allocation_fraction": self.asset_allocation_fraction,
            "unit_scale_kw_per_mw": self.unit_scale_kw_per_mw,
            "capacity_commitment_ref": self.capacity_commitment_ref,
            "driver_semantics": self.driver_semantics,
            "comparison_series": list(self.comparison_series),
            "assumptions": list(self.assumptions),
            "created_at_utc": self.created_at_utc,
            "source_kind": self.source_kind.value,
            "output_label": self.output_label,
            "mapping_fingerprint": self.mapping_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DerivedSimulationMapping:
        recorded = _sha256(
            payload.get("mapping_fingerprint"), field_name="mapping_fingerprint"
        )
        mapping = _build_mapping(payload)
        if mapping.mapping_fingerprint != recorded:
            raise RestorationActivationIntegrityError(
                "mapping_fingerprint mismatch"
            )
        return mapping


def _fingerprint_payload(mapping: DerivedSimulationMapping) -> dict[str, object]:
    payload = mapping.to_dict()
    payload.pop("mapping_fingerprint")
    return payload


def _build_mapping(payload: Mapping[str, Any]) -> DerivedSimulationMapping:
    data = _mapping(payload, field_name="derived simulation mapping")
    _required(
        data,
        (
            "mapping_id",
            "source_artifact_fingerprint",
            "source_series_fingerprints",
            "product",
            "direction",
            "asset_allocation_fraction",
            "unit_scale_kw_per_mw",
            "capacity_commitment_ref",
            "driver_semantics",
            "comparison_series",
            "assumptions",
            "created_at_utc",
            "output_label",
        ),
        field_name="derived simulation mapping",
    )
    schema_version = data.get("schema_version", RESTORATION_MAPPING_SCHEMA_VERSION)
    if schema_version not in SUPPORTED_RESTORATION_MAPPING_SCHEMA_VERSIONS:
        raise RestorationActivationValidationError(
            f"unsupported derived mapping schema_version {schema_version!r}"
        )
    product = _enum(RestorationProduct, data["product"], field_name="product")
    direction = _enum(
        RestorationDirection, data["direction"], field_name="direction"
    )
    fraction = _finite(
        data["asset_allocation_fraction"], field_name="asset_allocation_fraction"
    )
    if not 0.0 <= fraction <= 1.0:
        raise RestorationActivationValidationError(
            "asset_allocation_fraction must be finite and in [0, 1]"
        )
    scale = _finite(data["unit_scale_kw_per_mw"], field_name="unit scale")
    if scale != 1000.0:
        raise RestorationActivationValidationError(
            "unit scale must be exactly 1000 kW per MW"
        )
    drivers = _unique_digests(
        data["source_series_fingerprints"],
        field_name="source_series_fingerprints",
        required=True,
    )
    comparisons = _unique_digests(
        data["comparison_series"], field_name="comparison_series", required=False
    )
    if set(drivers) & set(comparisons):
        raise RestorationActivationValidationError(
            "comparison series cannot also be a driver source series"
        )
    assumptions = tuple(
        _non_empty(item, field_name=f"assumptions[{index}]")
        for index, item in enumerate(
            _sequence(data["assumptions"], field_name="assumptions")
        )
    )
    if not assumptions:
        raise RestorationActivationValidationError("assumptions must be non-empty")
    driver_semantics = _non_empty(
        data["driver_semantics"], field_name="driver_semantics"
    )
    allowed_semantics = {
        RestorationProduct.AFRR: {"afrr_requested_need"},
        RestorationProduct.MFRR: {
            "mfrr_sa_requested_volume",
            "mfrr_da_requested_volume",
        },
    }
    if driver_semantics not in allowed_semantics[product]:
        raise RestorationActivationValidationError(
            f"driver_semantics {driver_semantics!r} is incompatible with {product.value}"
        )
    source_kind_value = data.get(
        "source_kind", RestorationSourceKind.DERIVED_SIMULATION.value
    )
    source_kind = _enum(
        RestorationSourceKind, source_kind_value, field_name="source_kind"
    )
    if source_kind is not RestorationSourceKind.DERIVED_SIMULATION:
        raise RestorationActivationValidationError(
            "DerivedSimulationMapping source_kind must be DERIVED_SIMULATION"
        )
    output_label = _non_empty(data["output_label"], field_name="output_label")
    if output_label != "derived_simulation":
        raise RestorationActivationValidationError(
            "output_label must be exactly derived_simulation"
        )
    provisional = DerivedSimulationMapping(
        schema_version=str(schema_version),
        mapping_id=_non_empty(data["mapping_id"], field_name="mapping_id"),
        source_artifact_fingerprint=_sha256(
            data["source_artifact_fingerprint"],
            field_name="source_artifact_fingerprint",
        ),
        source_series_fingerprints=drivers,
        product=product,
        direction=direction,
        asset_allocation_fraction=fraction,
        unit_scale_kw_per_mw=scale,
        capacity_commitment_ref=_sha256(
            data["capacity_commitment_ref"], field_name="capacity_commitment_ref"
        ),
        driver_semantics=driver_semantics,
        comparison_series=comparisons,
        assumptions=assumptions,
        created_at_utc=_utc_timestamp(
            data["created_at_utc"], field_name="created_at_utc"
        ),
        source_kind=source_kind,
        output_label=output_label,
        mapping_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional,
        (("mapping_fingerprint", _fingerprint_payload),),
        error=RestorationActivationValidationError,
    )


def build_derived_simulation_mapping(
    payload: Mapping[str, Any],
    *,
    driver_values_mw: Sequence[float],
    committed_capacity_kw: float,
) -> DerivedSimulationMapping:
    """Build a fixed mapping and reject every source value above commitment."""

    mapping = _build_mapping(payload)
    capacity = _finite(committed_capacity_kw, field_name="committed_capacity_kw")
    if capacity < 0:
        raise RestorationActivationValidationError(
            "committed_capacity_kw must be non-negative"
        )
    values = tuple(
        _finite(value, field_name=f"driver_values_mw[{index}]")
        for index, value in enumerate(driver_values_mw)
    )
    if not values:
        raise RestorationActivationValidationError(
            "driver_values_mw must be non-empty"
        )
    for area_value in values:
        if area_value < 0:
            raise RestorationActivationValidationError(
                "driver_values_mw must be non-negative"
            )
        mapped_magnitude = abs(mapping.map_area_value_kw(area_value))
        if mapped_magnitude > capacity + _TOLERANCE:
            raise RestorationActivationValidationError(
                f"{mapping.product.value} {mapping.direction.value} mapping of "
                f"{area_value} MW at allocation fraction "
                f"{mapping.asset_allocation_fraction} produces {mapped_magnitude} kW, "
                f"exceeding commitment capacity {capacity} kW"
            )
    return mapping


@dataclass(frozen=True, slots=True)
class AFRRActivationSample:
    """One signed interval-average automatic balancing-power request."""

    interval: CanonicalInterval
    requested_balancing_power_kw: float
    direction: RestorationDirection | None
    source_observation_refs: tuple[str, ...]

    @property
    def signed_requested_energy_kwh(self) -> float:
        interval_hours = (
            self.interval.end_utc - self.interval.start_utc
        ).total_seconds() / 3600.0
        return self.requested_balancing_power_kw * interval_hours

    def to_dict(self) -> dict[str, object]:
        return {
            "interval": self.interval.to_dict(),
            "requested_balancing_power_kw": self.requested_balancing_power_kw,
            "direction": None if self.direction is None else self.direction.value,
            "source_observation_refs": list(self.source_observation_refs),
        }


@dataclass(frozen=True, slots=True)
class AFRRActivationTrajectory:
    """Complete native-grid aFRR input with auditable provenance and identity."""

    schema_version: str
    trajectory_id: str
    semantics_version: str
    product: RestorationProduct
    period: CanonicalInterval
    resolution: str
    sample_semantics: str
    sign_convention: str
    source_kind: RestorationSourceKind
    created_or_retrieved_at_utc: str
    mapping_fingerprint: str | None
    samples: tuple[AFRRActivationSample, ...]
    trajectory_fingerprint: str

    @property
    def requested_upward_energy_kwh(self) -> float:
        return sum(
            -sample.signed_requested_energy_kwh
            for sample in self.samples
            if sample.direction is RestorationDirection.UPWARD
        )

    @property
    def requested_downward_energy_kwh(self) -> float:
        return sum(
            sample.signed_requested_energy_kwh
            for sample in self.samples
            if sample.direction is RestorationDirection.DOWNWARD
        )

    @property
    def net_requested_energy_kwh(self) -> float:
        return sum(sample.signed_requested_energy_kwh for sample in self.samples)

    @property
    def absolute_requested_energy_kwh(self) -> float:
        return self.requested_upward_energy_kwh + self.requested_downward_energy_kwh

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trajectory_id": self.trajectory_id,
            "semantics_version": self.semantics_version,
            "product": self.product.value,
            "period": self.period.to_dict(),
            "resolution": self.resolution,
            "sample_semantics": self.sample_semantics,
            "sign_convention": self.sign_convention,
            "source_kind": self.source_kind.value,
            "created_or_retrieved_at_utc": self.created_or_retrieved_at_utc,
            "mapping_fingerprint": self.mapping_fingerprint,
            "samples": [sample.to_dict() for sample in self.samples],
            "trajectory_fingerprint": self.trajectory_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AFRRActivationTrajectory:
        recorded = _sha256(
            payload.get("trajectory_fingerprint"),
            field_name="trajectory_fingerprint",
        )
        trajectory = _build_afrr_activation_trajectory(payload)
        if trajectory.trajectory_fingerprint != recorded:
            raise RestorationActivationIntegrityError(
                "trajectory_fingerprint mismatch"
            )
        return trajectory


def _afrr_direction_for_power(power_kw: float) -> RestorationDirection | None:
    return RestorationDirection.of_signed(power_kw)


def _afrr_sample(value: object, *, index: int) -> AFRRActivationSample:
    data = _mapping(value, field_name=f"samples[{index}]")
    _required(
        data,
        (
            "interval",
            "requested_balancing_power_kw",
            "direction",
            "source_observation_refs",
        ),
        field_name=f"samples[{index}]",
    )
    power = _finite(
        data["requested_balancing_power_kw"],
        field_name=f"samples[{index}].requested_balancing_power_kw",
    )
    expected_direction = _afrr_direction_for_power(power)
    raw_direction = data["direction"]
    if raw_direction is None:
        direction = None
    else:
        direction = _enum(
            RestorationDirection,
            raw_direction,
            field_name=f"samples[{index}].direction",
        )
    if direction is not expected_direction:
        expected = (
            "null for zero power"
            if expected_direction is None
            else f"{expected_direction.value} for {'negative' if power < 0 else 'positive'} power"
        )
        raise RestorationActivationValidationError(
            f"samples[{index}].direction must be {expected}"
        )
    return AFRRActivationSample(
        interval=_interval(data["interval"], field_name=f"samples[{index}].interval"),
        requested_balancing_power_kw=power,
        direction=direction,
        source_observation_refs=_source_refs(
            data["source_observation_refs"],
            field_name=f"samples[{index}].source_observation_refs",
        ),
    )


def _build_afrr_activation_trajectory(
    payload: Mapping[str, Any],
) -> AFRRActivationTrajectory:
    data = _mapping(payload, field_name="aFRR activation trajectory")
    _required(
        data,
        (
            "trajectory_id",
            "semantics_version",
            "product",
            "period",
            "resolution",
            "sample_semantics",
            "sign_convention",
            "source_kind",
            "created_or_retrieved_at_utc",
            "mapping_fingerprint",
            "samples",
        ),
        field_name="aFRR activation trajectory",
    )
    schema_version = data.get("schema_version", AFRR_TRAJECTORY_SCHEMA_VERSION)
    if schema_version not in SUPPORTED_AFRR_TRAJECTORY_SCHEMA_VERSIONS:
        raise RestorationActivationValidationError(
            f"unsupported aFRR trajectory schema_version {schema_version!r}"
        )
    product = _enum(RestorationProduct, data["product"], field_name="product")
    if product is not RestorationProduct.AFRR:
        raise RestorationActivationValidationError(
            "aFRR activation trajectory product must be exactly AFRR"
        )
    period = _interval(data["period"], field_name="period")
    resolution = _non_empty(data["resolution"], field_name="resolution")
    try:
        duration = parse_iso8601_duration(resolution)
    except MarketTimeValidationError as exc:
        raise RestorationActivationValidationError(str(exc)) from exc
    sample_semantics = _non_empty(
        data["sample_semantics"], field_name="sample_semantics"
    )
    if sample_semantics != AFRR_SAMPLE_SEMANTICS:
        raise RestorationActivationValidationError(
            "sample_semantics must be interval_average_requested_bess_power_kw"
        )
    sign_convention = _non_empty(
        data["sign_convention"], field_name="sign_convention"
    )
    if sign_convention != RESTORATION_SIGN_CONVENTION:
        raise RestorationActivationValidationError(
            "sign_convention must be positive_charge_negative_discharge"
        )
    source_kind = _enum(
        RestorationSourceKind,
        data["source_kind"],
        field_name="source_kind",
    )
    raw_mapping_fingerprint = data["mapping_fingerprint"]
    mapping_fingerprint = (
        None
        if raw_mapping_fingerprint is None
        else _sha256(
            raw_mapping_fingerprint,
            field_name="mapping_fingerprint",
        )
    )
    if source_kind is RestorationSourceKind.DERIVED_SIMULATION:
        if mapping_fingerprint is None:
            raise RestorationActivationValidationError(
                "DERIVED_SIMULATION trajectory requires mapping_fingerprint"
            )
    elif mapping_fingerprint is not None:
        raise RestorationActivationValidationError(
            f"{source_kind.value} trajectory cannot declare a derived mapping_fingerprint"
        )
    samples = tuple(
        _afrr_sample(item, index=index)
        for index, item in enumerate(_sequence(data["samples"], field_name="samples"))
    )
    if not samples:
        raise RestorationActivationValidationError("samples must be non-empty")
    cursor = period.start_utc
    for index, sample in enumerate(samples):
        if sample.interval.start_utc != cursor:
            relation = (
                "overlap"
                if sample.interval.start_utc < cursor
                else "gap"
            )
            raise RestorationActivationValidationError(
                f"aFRR sample coverage has a {relation} at sample {index}"
            )
        if sample.interval.end_utc - sample.interval.start_utc != duration:
            raise RestorationActivationValidationError(
                f"aFRR sample {index} duration does not match resolution"
            )
        cursor = sample.interval.end_utc
    if cursor != period.end_utc:
        raise RestorationActivationValidationError(
            "aFRR sample coverage is incomplete"
        )
    provisional = AFRRActivationTrajectory(
        schema_version=str(schema_version),
        trajectory_id=_non_empty(data["trajectory_id"], field_name="trajectory_id"),
        semantics_version=_non_empty(
            data["semantics_version"], field_name="semantics_version"
        ),
        product=product,
        period=period,
        resolution=resolution,
        sample_semantics=sample_semantics,
        sign_convention=sign_convention,
        source_kind=source_kind,
        created_or_retrieved_at_utc=_utc_timestamp(
            data["created_or_retrieved_at_utc"],
            field_name="created_or_retrieved_at_utc",
        ),
        mapping_fingerprint=mapping_fingerprint,
        samples=samples,
        trajectory_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional,
        (("trajectory_fingerprint", partial(payload_without, field="trajectory_fingerprint")),),
        error=RestorationActivationValidationError,
    )


def build_afrr_activation_trajectory(
    payload: Mapping[str, Any],
) -> AFRRActivationTrajectory:
    """Build a complete native-grid signed aFRR activation trajectory."""

    return _build_afrr_activation_trajectory(payload)


def build_afrr_trajectory_from_rte_requested_need(
    *,
    trajectory_id: str,
    semantics_version: str,
    period: CanonicalInterval,
    resolution: str,
    created_or_retrieved_at_utc: str,
    mapping: DerivedSimulationMapping,
    intervals: Sequence[CanonicalInterval],
    upward_requested_need_mw: Sequence[float],
    downward_requested_need_mw: Sequence[float],
    committed_capacity_kw: Sequence[float],
    source_observation_refs: Sequence[Sequence[str]],
) -> AFRRActivationTrajectory:
    """Map one directional RTE requested-need series without netting or clipping."""

    if type(mapping) is not DerivedSimulationMapping:
        raise RestorationActivationValidationError(
            "mapping must be exactly a DerivedSimulationMapping"
        )
    if mapping.product is not RestorationProduct.AFRR:
        raise RestorationActivationValidationError(
            "RTE requested-need mapping must have product AFRR"
        )
    normalized_intervals = tuple(intervals)
    upward = tuple(
        _finite(value, field_name=f"upward_requested_need_mw[{index}]")
        for index, value in enumerate(upward_requested_need_mw)
    )
    downward = tuple(
        _finite(value, field_name=f"downward_requested_need_mw[{index}]")
        for index, value in enumerate(downward_requested_need_mw)
    )
    capacities = tuple(
        _finite(value, field_name=f"committed_capacity_kw[{index}]")
        for index, value in enumerate(committed_capacity_kw)
    )
    refs = tuple(source_observation_refs)
    count = len(normalized_intervals)
    if count == 0 or not (
        len(upward) == len(downward) == len(capacities) == len(refs) == count
    ):
        raise RestorationActivationValidationError(
            "RTE requested-need inputs must have one value, capacity, and lineage set per interval"
        )
    samples: list[dict[str, object]] = []
    for index, (interval, upward_mw, downward_mw, capacity, lineage) in enumerate(
        zip(
            normalized_intervals,
            upward,
            downward,
            capacities,
            refs,
            strict=True,
        )
    ):
        normalized_interval = _interval(
            interval, field_name=f"intervals[{index}]"
        )
        if upward_mw < 0.0 or downward_mw < 0.0:
            raise RestorationActivationValidationError(
                f"RTE requested need must be non-negative at interval {index}"
            )
        if capacity < 0.0:
            raise RestorationActivationValidationError(
                f"committed capacity must be non-negative at interval {index}"
            )
        if upward_mw > 0.0 and downward_mw > 0.0:
            raise RestorationActivationValidationError(
                f"ambiguous opposing upward and downward aFRR requested need at interval {index}"
            )
        source_value = upward_mw if upward_mw > 0.0 else downward_mw
        source_direction = RestorationDirection.of_two_sided(upward_mw, downward_mw)
        if source_direction is not None and source_direction is not mapping.direction:
            raise RestorationActivationValidationError(
                f"RTE requested need direction at interval {index} does not match "
                f"the fixed {mapping.direction.value} mapping"
            )
        power = 0.0 if source_direction is None else mapping.map_area_value_kw(source_value)
        if abs(power) > capacity + _TOLERANCE:
            raise RestorationActivationValidationError(
                f"AFRR {mapping.direction.value} mapping at interval {index} of "
                f"{source_value} MW with allocation fraction "
                f"{mapping.asset_allocation_fraction} produces {abs(power)} kW, "
                f"exceeding committed capacity {capacity} kW"
            )
        normalized_lineage = _source_refs(
            lineage,
            field_name=f"source_observation_refs[{index}]",
        )
        samples.append(
            {
                "interval": normalized_interval,
                "requested_balancing_power_kw": power,
                "direction": None if source_direction is None else source_direction.value,
                "source_observation_refs": list(normalized_lineage),
            }
        )
    return build_afrr_activation_trajectory(
        {
            "trajectory_id": trajectory_id,
            "semantics_version": semantics_version,
            "product": RestorationProduct.AFRR.value,
            "period": period,
            "resolution": resolution,
            "sample_semantics": AFRR_SAMPLE_SEMANTICS,
            "sign_convention": RESTORATION_SIGN_CONVENTION,
            "source_kind": RestorationSourceKind.DERIVED_SIMULATION.value,
            "created_or_retrieved_at_utc": created_or_retrieved_at_utc,
            "mapping_fingerprint": mapping.mapping_fingerprint,
            "samples": samples,
        }
    )


def _utc_datetime(value: object, *, field_name: str) -> datetime:
    normalized = _utc_timestamp(value, field_name=field_name)
    return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(UTC)


_format_utc = format_utc


@dataclass(frozen=True, slots=True)
class MFRRActivationEvent:
    """One typed manual activation with an analytic piecewise request shape."""

    event_id: str
    product: RestorationProduct
    kind: MFRRActivationKind
    direction: RestorationDirection
    requested_start_utc: str
    activation_delay_seconds: float
    ramp_up_seconds: float
    hold_seconds: float
    ramp_down_seconds: float
    requested_power_kw: float
    source_kind: RestorationSourceKind
    mapping_fingerprint: str | None
    source_observation_refs: tuple[str, ...]
    event_fingerprint: str

    @property
    def total_duration_seconds(self) -> float:
        return (
            self.activation_delay_seconds
            + self.ramp_up_seconds
            + self.hold_seconds
            + self.ramp_down_seconds
        )

    @property
    def activation_start_utc(self) -> str:
        return _format_utc(
            _utc_datetime(
                self.requested_start_utc, field_name="requested_start_utc"
            )
            + timedelta(seconds=self.activation_delay_seconds)
        )

    @property
    def requested_completion_utc(self) -> str:
        return _format_utc(
            _utc_datetime(
                self.requested_start_utc, field_name="requested_start_utc"
            )
            + timedelta(seconds=self.total_duration_seconds)
        )

    @property
    def complete_interval(self) -> CanonicalInterval:
        return CanonicalInterval.from_utc(
            _utc_datetime(
                self.requested_start_utc, field_name="requested_start_utc"
            ),
            _utc_datetime(
                self.requested_completion_utc,
                field_name="requested_completion_utc",
            ),
        )

    @property
    def requested_energy_kwh(self) -> float:
        effective_seconds = (
            self.hold_seconds
            + 0.5 * self.ramp_up_seconds
            + 0.5 * self.ramp_down_seconds
        )
        return self.requested_power_kw * effective_seconds / 3600.0

    @property
    def signed_requested_energy_kwh(self) -> float:
        return self.direction.signed(self.requested_energy_kwh)

    def _cumulative_magnitude_kw_seconds(self, elapsed_seconds: float) -> float:
        elapsed = min(max(elapsed_seconds, 0.0), self.total_duration_seconds)
        if elapsed <= self.activation_delay_seconds:
            return 0.0
        cursor = elapsed - self.activation_delay_seconds
        energy = 0.0
        if self.ramp_up_seconds > 0.0:
            ramp_elapsed = min(cursor, self.ramp_up_seconds)
            energy += (
                self.requested_power_kw
                * ramp_elapsed
                * ramp_elapsed
                / (2.0 * self.ramp_up_seconds)
            )
            if cursor <= self.ramp_up_seconds:
                return energy
            cursor -= self.ramp_up_seconds
        hold_elapsed = min(cursor, self.hold_seconds)
        energy += self.requested_power_kw * hold_elapsed
        if cursor <= self.hold_seconds:
            return energy
        cursor -= self.hold_seconds
        if self.ramp_down_seconds > 0.0:
            ramp_elapsed = min(cursor, self.ramp_down_seconds)
            energy += self.requested_power_kw * (
                ramp_elapsed
                - ramp_elapsed * ramp_elapsed / (2.0 * self.ramp_down_seconds)
            )
        return energy

    def signed_average_power_kw(self, interval: CanonicalInterval) -> float:
        """Integrate the analytic event over one caller interval exactly."""

        if not isinstance(interval, CanonicalInterval):
            raise RestorationActivationValidationError(
                "interval must be a CanonicalInterval"
            )
        event_start = _utc_datetime(
            self.requested_start_utc, field_name="requested_start_utc"
        )
        start_elapsed = (interval.start_utc - event_start).total_seconds()
        end_elapsed = (interval.end_utc - event_start).total_seconds()
        magnitude_kw_seconds = self._cumulative_magnitude_kw_seconds(
            end_elapsed
        ) - self._cumulative_magnitude_kw_seconds(start_elapsed)
        interval_seconds = (interval.end_utc - interval.start_utc).total_seconds()
        magnitude = magnitude_kw_seconds / interval_seconds
        return self.direction.signed(magnitude)

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "product": self.product.value,
            "kind": self.kind.value,
            "direction": self.direction.value,
            "requested_start_utc": self.requested_start_utc,
            "activation_delay_seconds": self.activation_delay_seconds,
            "ramp_up_seconds": self.ramp_up_seconds,
            "hold_seconds": self.hold_seconds,
            "ramp_down_seconds": self.ramp_down_seconds,
            "requested_power_kw": self.requested_power_kw,
            "source_kind": self.source_kind.value,
            "mapping_fingerprint": self.mapping_fingerprint,
            "source_observation_refs": list(self.source_observation_refs),
            "event_fingerprint": self.event_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MFRRActivationEvent:
        recorded = _sha256(
            payload.get("event_fingerprint"), field_name="event_fingerprint"
        )
        event = _build_mfrr_event(payload)
        if event.event_fingerprint != recorded:
            raise RestorationActivationIntegrityError(
                "event_fingerprint mismatch"
            )
        return event


def _build_mfrr_event(value: object, *, index: int | None = None) -> MFRRActivationEvent:
    prefix = "event" if index is None else f"events[{index}]"
    data = _mapping(value, field_name=prefix)
    if "requested_energy_kwh" in data:
        raise RestorationActivationValidationError(
            f"{prefix}.requested_energy_kwh is derived and cannot be supplied as input"
        )
    _required(
        data,
        (
            "event_id",
            "product",
            "kind",
            "direction",
            "requested_start_utc",
            "activation_delay_seconds",
            "ramp_up_seconds",
            "hold_seconds",
            "ramp_down_seconds",
            "requested_power_kw",
            "source_kind",
            "mapping_fingerprint",
            "source_observation_refs",
        ),
        field_name=prefix,
    )
    product = _enum(
        RestorationProduct, data["product"], field_name=f"{prefix}.product"
    )
    if product is not RestorationProduct.MFRR:
        raise RestorationActivationValidationError(
            f"{prefix}.product must be exactly MFRR"
        )
    durations = {
        field_name: _finite(data[field_name], field_name=f"{prefix}.{field_name}")
        for field_name in (
            "activation_delay_seconds",
            "ramp_up_seconds",
            "hold_seconds",
            "ramp_down_seconds",
        )
    }
    for field_name, duration in durations.items():
        if duration < 0.0:
            raise RestorationActivationValidationError(
                f"{prefix}.{field_name} must be non-negative"
            )
    total_duration = sum(durations.values())
    if total_duration <= 0.0:
        raise RestorationActivationValidationError(
            f"{prefix} total duration must be positive"
        )
    power = _finite(data["requested_power_kw"], field_name=f"{prefix}.requested_power_kw")
    if power < 0.0:
        raise RestorationActivationValidationError(
            f"{prefix}.requested_power_kw must be non-negative"
        )
    source_kind = _enum(
        RestorationSourceKind,
        data["source_kind"],
        field_name=f"{prefix}.source_kind",
    )
    raw_mapping = data["mapping_fingerprint"]
    mapping_fingerprint = (
        None
        if raw_mapping is None
        else _sha256(raw_mapping, field_name=f"{prefix}.mapping_fingerprint")
    )
    if source_kind is RestorationSourceKind.DERIVED_SIMULATION:
        if mapping_fingerprint is None:
            raise RestorationActivationValidationError(
                f"{prefix} DERIVED_SIMULATION requires mapping_fingerprint"
            )
    elif mapping_fingerprint is not None:
        raise RestorationActivationValidationError(
            f"{prefix} {source_kind.value} cannot declare mapping_fingerprint"
        )
    provisional = MFRRActivationEvent(
        event_id=_non_empty(data["event_id"], field_name=f"{prefix}.event_id"),
        product=product,
        kind=_enum(
            MFRRActivationKind,
            data["kind"],
            field_name=f"{prefix}.kind",
        ),
        direction=_enum(
            RestorationDirection,
            data["direction"],
            field_name=f"{prefix}.direction",
        ),
        requested_start_utc=_utc_timestamp(
            data["requested_start_utc"],
            field_name=f"{prefix}.requested_start_utc",
        ),
        activation_delay_seconds=durations["activation_delay_seconds"],
        ramp_up_seconds=durations["ramp_up_seconds"],
        hold_seconds=durations["hold_seconds"],
        ramp_down_seconds=durations["ramp_down_seconds"],
        requested_power_kw=power,
        source_kind=source_kind,
        mapping_fingerprint=mapping_fingerprint,
        source_observation_refs=_source_refs(
            data["source_observation_refs"],
            field_name=f"{prefix}.source_observation_refs",
        ),
        event_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional,
        (("event_fingerprint", partial(payload_without, field="event_fingerprint")),),
        error=RestorationActivationValidationError,
    )


@dataclass(frozen=True, slots=True)
class MFRRActivationSequence:
    """Complete mFRR horizon with ordered, non-overlapping typed events."""

    schema_version: str
    sequence_id: str
    semantics_version: str
    product: RestorationProduct
    period: CanonicalInterval
    shape_semantics: str
    sign_convention: str
    source_kind: RestorationSourceKind
    created_or_retrieved_at_utc: str
    events: tuple[MFRRActivationEvent, ...]
    sequence_fingerprint: str

    @property
    def requested_upward_energy_kwh(self) -> float:
        return sum(
            event.requested_energy_kwh
            for event in self.events
            if event.direction is RestorationDirection.UPWARD
        )

    @property
    def requested_downward_energy_kwh(self) -> float:
        return sum(
            event.requested_energy_kwh
            for event in self.events
            if event.direction is RestorationDirection.DOWNWARD
        )

    @property
    def net_requested_energy_kwh(self) -> float:
        return sum(event.signed_requested_energy_kwh for event in self.events)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "sequence_id": self.sequence_id,
            "semantics_version": self.semantics_version,
            "product": self.product.value,
            "period": self.period.to_dict(),
            "shape_semantics": self.shape_semantics,
            "sign_convention": self.sign_convention,
            "source_kind": self.source_kind.value,
            "created_or_retrieved_at_utc": self.created_or_retrieved_at_utc,
            "events": [event.to_dict() for event in self.events],
            "sequence_fingerprint": self.sequence_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> MFRRActivationSequence:
        recorded = _sha256(
            payload.get("sequence_fingerprint"), field_name="sequence_fingerprint"
        )
        sequence = _build_mfrr_activation_sequence(payload)
        if sequence.sequence_fingerprint != recorded:
            raise RestorationActivationIntegrityError(
                "sequence_fingerprint mismatch"
            )
        return sequence


def _build_mfrr_activation_sequence(
    payload: Mapping[str, Any],
) -> MFRRActivationSequence:
    data = _mapping(payload, field_name="mFRR activation sequence")
    _required(
        data,
        (
            "sequence_id",
            "semantics_version",
            "product",
            "period",
            "shape_semantics",
            "sign_convention",
            "source_kind",
            "created_or_retrieved_at_utc",
            "events",
        ),
        field_name="mFRR activation sequence",
    )
    schema_version = data.get("schema_version", MFRR_EVENTS_SCHEMA_VERSION)
    if schema_version not in SUPPORTED_MFRR_EVENTS_SCHEMA_VERSIONS:
        raise RestorationActivationValidationError(
            f"unsupported mFRR sequence schema_version {schema_version!r}"
        )
    product = _enum(RestorationProduct, data["product"], field_name="product")
    if product is not RestorationProduct.MFRR:
        raise RestorationActivationValidationError(
            "mFRR activation sequence product must be exactly MFRR"
        )
    period = _interval(data["period"], field_name="period")
    shape_semantics = _non_empty(
        data["shape_semantics"], field_name="shape_semantics"
    )
    if shape_semantics != MFRR_EVENT_SHAPE_SEMANTICS:
        raise RestorationActivationValidationError(
            "shape_semantics must be delay_linear_ramp_hold_linear_ramp"
        )
    sign_convention = _non_empty(
        data["sign_convention"], field_name="sign_convention"
    )
    if sign_convention != RESTORATION_SIGN_CONVENTION:
        raise RestorationActivationValidationError(
            "sign_convention must be positive_charge_negative_discharge"
        )
    source_kind = _enum(
        RestorationSourceKind, data["source_kind"], field_name="source_kind"
    )
    events = tuple(
        sorted(
            (
                _build_mfrr_event(item, index=index)
                for index, item in enumerate(
                    _sequence(data["events"], field_name="events")
                )
            ),
            key=lambda event: (event.complete_interval.start_utc, event.event_id),
        )
    )
    event_ids = [event.event_id for event in events]
    if len(set(event_ids)) != len(event_ids):
        raise RestorationActivationValidationError("mFRR event IDs must be unique")
    fingerprints = [event.event_fingerprint for event in events]
    if len(set(fingerprints)) != len(fingerprints):
        raise RestorationActivationValidationError(
            "mFRR event fingerprints must be unique"
        )
    for index, event in enumerate(events):
        if event.source_kind is not source_kind:
            raise RestorationActivationValidationError(
                f"event {event.event_id} source_kind does not match the sequence"
            )
        if (
            event.complete_interval.start_utc < period.start_utc
            or event.complete_interval.end_utc > period.end_utc
        ):
            raise RestorationActivationValidationError(
                f"event {event.event_id} lies outside the sequence horizon period"
            )
        if index:
            previous = events[index - 1]
            if event.complete_interval.start_utc < previous.complete_interval.end_utc:
                raise RestorationActivationValidationError(
                    f"mFRR event overlap between {previous.event_id} and {event.event_id}"
                )
    provisional = MFRRActivationSequence(
        schema_version=str(schema_version),
        sequence_id=_non_empty(data["sequence_id"], field_name="sequence_id"),
        semantics_version=_non_empty(
            data["semantics_version"], field_name="semantics_version"
        ),
        product=product,
        period=period,
        shape_semantics=shape_semantics,
        sign_convention=sign_convention,
        source_kind=source_kind,
        created_or_retrieved_at_utc=_utc_timestamp(
            data["created_or_retrieved_at_utc"],
            field_name="created_or_retrieved_at_utc",
        ),
        events=events,
        sequence_fingerprint=PLACEHOLDER_FINGERPRINT,
    )
    return seal_fingerprints(
        provisional,
        (("sequence_fingerprint", partial(payload_without, field="sequence_fingerprint")),),
        error=RestorationActivationValidationError,
    )


def build_mfrr_activation_sequence(
    payload: Mapping[str, Any],
) -> MFRRActivationSequence:
    """Build one complete, ordered, non-overlapping mFRR event horizon."""

    return _build_mfrr_activation_sequence(payload)


def _optional_rte_volume(
    value: object, *, field_name: str
) -> float | None:
    if value is None:
        return None
    normalized = _finite(value, field_name=field_name)
    if normalized < 0.0:
        raise RestorationActivationValidationError(
            f"{field_name} must be non-negative when present"
        )
    return normalized


def build_mfrr_sequence_from_rte_sa_requested_volume(
    *,
    sequence_id: str,
    semantics_version: str,
    period: CanonicalInterval,
    created_or_retrieved_at_utc: str,
    mapping: DerivedSimulationMapping,
    intervals: Sequence[CanonicalInterval],
    upward_requested_volume_mw: Sequence[float | None],
    downward_requested_volume_mw: Sequence[float | None],
    committed_capacity_kw: Sequence[float],
    source_observation_refs: Sequence[Sequence[str]],
) -> MFRRActivationSequence:
    """Map only RTE SA requested volume to rectangular derived events."""

    if type(mapping) is not DerivedSimulationMapping:
        raise RestorationActivationValidationError(
            "mapping must be exactly a DerivedSimulationMapping"
        )
    if (
        mapping.product is not RestorationProduct.MFRR
        or mapping.driver_semantics != "mfrr_sa_requested_volume"
    ):
        raise RestorationActivationValidationError(
            "RTE mFRR mapping must use product MFRR and SA requested-volume semantics"
        )
    normalized_intervals = tuple(intervals)
    upward = tuple(
        _optional_rte_volume(
            value, field_name=f"upward_requested_volume_mw[{index}]"
        )
        for index, value in enumerate(upward_requested_volume_mw)
    )
    downward = tuple(
        _optional_rte_volume(
            value, field_name=f"downward_requested_volume_mw[{index}]"
        )
        for index, value in enumerate(downward_requested_volume_mw)
    )
    capacities = tuple(
        _finite(value, field_name=f"committed_capacity_kw[{index}]")
        for index, value in enumerate(committed_capacity_kw)
    )
    refs = tuple(source_observation_refs)
    count = len(normalized_intervals)
    if count == 0 or not (
        len(upward) == len(downward) == len(capacities) == len(refs) == count
    ):
        raise RestorationActivationValidationError(
            "RTE SA inputs must have one directional value, capacity, and lineage set per interval"
        )
    events: list[dict[str, object]] = []
    for index, (interval, raw_upward, raw_downward, capacity, lineage) in enumerate(
        zip(
            normalized_intervals,
            upward,
            downward,
            capacities,
            refs,
            strict=True,
        )
    ):
        normalized_interval = _interval(
            interval, field_name=f"intervals[{index}]"
        )
        upward_value = 0.0 if raw_upward is None else raw_upward
        downward_value = 0.0 if raw_downward is None else raw_downward
        if capacity < 0.0:
            raise RestorationActivationValidationError(
                f"committed capacity must be non-negative at interval {index}"
            )
        if upward_value > 0.0 and downward_value > 0.0:
            raise RestorationActivationValidationError(
                f"opposing upward and downward mFRR SA volume at interval {index}"
            )
        source_direction = RestorationDirection.of_two_sided(upward_value, downward_value)
        if source_direction is None:
            continue
        if source_direction is not mapping.direction:
            raise RestorationActivationValidationError(
                f"RTE SA direction at interval {index} does not match fixed "
                f"{mapping.direction.value} mapping"
            )
        source_value = (
            upward_value
            if source_direction is RestorationDirection.UPWARD
            else downward_value
        )
        power = abs(mapping.map_area_value_kw(source_value))
        if power > capacity + _TOLERANCE:
            raise RestorationActivationValidationError(
                f"MFRR {mapping.direction.value} mapping at interval {index} of "
                f"{source_value} MW with allocation fraction "
                f"{mapping.asset_allocation_fraction} produces {power} kW, "
                f"exceeding committed capacity {capacity} kW"
            )
        normalized_lineage = _source_refs(
            lineage,
            field_name=f"source_observation_refs[{index}]",
        )
        duration_seconds = (
            normalized_interval.end_utc - normalized_interval.start_utc
        ).total_seconds()
        events.append(
            {
                "event_id": (
                    f"{sequence_id}-{index:04d}-scheduled-"
                    f"{source_direction.value.lower()}"
                ),
                "product": RestorationProduct.MFRR.value,
                "kind": MFRRActivationKind.SCHEDULED.value,
                "direction": source_direction.value,
                "requested_start_utc": _format_utc(
                    normalized_interval.start_utc
                ),
                "activation_delay_seconds": 0.0,
                "ramp_up_seconds": 0.0,
                "hold_seconds": duration_seconds,
                "ramp_down_seconds": 0.0,
                "requested_power_kw": power,
                "source_kind": RestorationSourceKind.DERIVED_SIMULATION.value,
                "mapping_fingerprint": mapping.mapping_fingerprint,
                "source_observation_refs": list(normalized_lineage),
            }
        )
    return build_mfrr_activation_sequence(
        {
            "sequence_id": sequence_id,
            "semantics_version": semantics_version,
            "product": RestorationProduct.MFRR.value,
            "period": period,
            "shape_semantics": MFRR_EVENT_SHAPE_SEMANTICS,
            "sign_convention": RESTORATION_SIGN_CONVENTION,
            "source_kind": RestorationSourceKind.DERIVED_SIMULATION.value,
            "created_or_retrieved_at_utc": created_or_retrieved_at_utc,
            "events": events,
        }
    )


__all__ = [
    "RESTORATION_MAPPING_SCHEMA_VERSION",
    "SUPPORTED_RESTORATION_MAPPING_SCHEMA_VERSIONS",
    "AFRR_TRAJECTORY_SCHEMA_VERSION",
    "SUPPORTED_AFRR_TRAJECTORY_SCHEMA_VERSIONS",
    "AFRR_SAMPLE_SEMANTICS",
    "RESTORATION_SIGN_CONVENTION",
    "MFRR_EVENTS_SCHEMA_VERSION",
    "SUPPORTED_MFRR_EVENTS_SCHEMA_VERSIONS",
    "MFRR_EVENT_SHAPE_SEMANTICS",
    "RestorationProduct",
    "RestorationDirection",
    "MFRRActivationKind",
    "RestorationSourceKind",
    "RestorationActivationValidationError",
    "RestorationActivationIntegrityError",
    "DerivedSimulationMapping",
    "AFRRActivationSample",
    "AFRRActivationTrajectory",
    "MFRRActivationEvent",
    "MFRRActivationSequence",
    "build_derived_simulation_mapping",
    "build_afrr_activation_trajectory",
    "build_afrr_trajectory_from_rte_requested_need",
    "build_mfrr_activation_sequence",
    "build_mfrr_sequence_from_rte_sa_requested_volume",
]
