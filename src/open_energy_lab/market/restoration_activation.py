"""Source-independent restoration activation identities and derived mappings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
import hashlib
import math
import re
from typing import Any

from .restoration_artifact import canonical_restoration_json_bytes


RESTORATION_MAPPING_SCHEMA_VERSION = "oel.restoration.derived-mapping.v1"
SUPPORTED_RESTORATION_MAPPING_SCHEMA_VERSIONS = (
    RESTORATION_MAPPING_SCHEMA_VERSION,
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TOLERANCE = 1e-6


class RestorationProduct(str, Enum):
    """Restoration products owned by Feature 011; FCR is intentionally absent."""

    AFRR = "AFRR"
    MFRR = "MFRR"


class RestorationDirection(str, Enum):
    """Directional restoration commitment and delivery identity."""

    UPWARD = "UPWARD"
    DOWNWARD = "DOWNWARD"


class MFRRActivationKind(str, Enum):
    """Non-interchangeable manual restoration activation kinds."""

    SCHEDULED = "SCHEDULED"
    DIRECT = "DIRECT"


class RestorationSourceKind(str, Enum):
    """Provenance kind for one asset-level activation input."""

    ASSET_SUPPLIED = "ASSET_SUPPLIED"
    SYNTHETIC = "SYNTHETIC"
    DERIVED_SIMULATION = "DERIVED_SIMULATION"


class RestorationActivationValidationError(ValueError):
    """Raised when a restoration activation or mapping contract is invalid."""


class RestorationActivationIntegrityError(RestorationActivationValidationError):
    """Raised when a persisted activation identity does not verify."""


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RestorationActivationValidationError(
            f"{field_name} must be a mapping"
        )
    return {str(key): inner for key, inner in value.items()}


def _sequence(value: object, *, field_name: str) -> list[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RestorationActivationValidationError(
            f"{field_name} must be a sequence"
        )
    return list(value)


def _required(
    payload: Mapping[str, Any], names: Sequence[str], *, field_name: str
) -> None:
    missing = [name for name in names if name not in payload]
    if missing:
        raise RestorationActivationValidationError(
            f"{field_name} is missing required fields: {', '.join(missing)}"
        )


def _non_empty(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise RestorationActivationValidationError(
            f"{field_name} must be a non-empty string"
        )
    return value


def _finite(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RestorationActivationValidationError(
            f"{field_name} must be a finite fixed number"
        )
    normalized = float(value)
    if not math.isfinite(normalized):
        raise RestorationActivationValidationError(f"{field_name} must be finite")
    return normalized


def _sha256(value: object, *, field_name: str) -> str:
    normalized = _non_empty(value, field_name=field_name)
    if _SHA256_PATTERN.fullmatch(normalized) is None:
        raise RestorationActivationValidationError(
            f"{field_name} must be a lowercase SHA-256 digest"
        )
    return normalized


def _utc_timestamp(value: object, *, field_name: str) -> str:
    normalized = _non_empty(value, field_name=field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RestorationActivationValidationError(
            f"{field_name} must be an ISO 8601 UTC timestamp"
        ) from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
    ):
        raise RestorationActivationValidationError(
            f"{field_name} must be an aware UTC timestamp"
        )
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _enum(enum_type: type[Enum], value: object, *, field_name: str) -> Any:
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        allowed = ", ".join(str(item.value) for item in enum_type)
        raise RestorationActivationValidationError(
            f"{field_name} must be one of: {allowed}"
        ) from exc


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
        return -magnitude if self.direction is RestorationDirection.UPWARD else magnitude

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
        mapping_fingerprint="0" * 64,
    )
    try:
        fingerprint = hashlib.sha256(
            canonical_restoration_json_bytes(_fingerprint_payload(provisional))
        ).hexdigest()
    except ValueError as exc:
        raise RestorationActivationValidationError(str(exc)) from exc
    return DerivedSimulationMapping(
        **{
            **{
                field: getattr(provisional, field)
                for field in provisional.__dataclass_fields__
                if field != "mapping_fingerprint"
            },
            "mapping_fingerprint": fingerprint,
        }
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


__all__ = [
    "RESTORATION_MAPPING_SCHEMA_VERSION",
    "SUPPORTED_RESTORATION_MAPPING_SCHEMA_VERSIONS",
    "RestorationProduct",
    "RestorationDirection",
    "MFRRActivationKind",
    "RestorationSourceKind",
    "RestorationActivationValidationError",
    "RestorationActivationIntegrityError",
    "DerivedSimulationMapping",
    "build_derived_simulation_mapping",
]
