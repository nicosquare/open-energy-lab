"""Atomic, product-specific settlement for aFRR and mFRR physical replays."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from functools import partial
from types import MappingProxyType

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import fingerprint, thaw
from open_energy_lab.core.validation import (
    enum_member,
    finite,
    non_empty_str,
    non_negative,
    positive,
    sha256_digest,
)
from open_energy_lab.market.restoration_activation import (
    MFRRActivationKind,
    RestorationDirection,
    RestorationProduct,
)
from open_energy_lab.market.time import CanonicalInterval

from .restoration_service import (
    AFRRReplayResult,
    MFRRReplayResult,
)


RESTORATION_SETTLEMENT_SCHEMA_VERSION = "oel.restoration.settlement.v1"
RESTORATION_PRICE_SCHEMA_VERSION = "oel.restoration.price.v1"
AREA_PRICE_PROXY_SCHEMA_VERSION = "oel.restoration.area-price-proxy.v1"
RESTORATION_PENALTY_RULE_SCHEMA_VERSION = "oel.restoration.penalty-rule.v1"
THROUGHPUT_DEGRADATION_RULE_SCHEMA_VERSION = (
    "oel.restoration.throughput-degradation-rule.v1"
)
DEFAULT_RESTORATION_SETTLEMENT_TOLERANCE = 1e-6


class RestorationSettlementValidationError(ValidationError):
    """Raised when a settlement entity itself is malformed."""


class SettlementAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class SettlementComponentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    UNCONFIGURED = "UNCONFIGURED"
    INELIGIBLE = "INELIGIBLE"


class SettlementPriceState(str, Enum):
    VALUE = "VALUE"
    SOURCE_NULL = "SOURCE_NULL"
    FIELD_ABSENT = "FIELD_ABSENT"
    AMBIGUOUS = "AMBIGUOUS"


_non_empty = partial(non_empty_str, error=RestorationSettlementValidationError, strip=True)
_finite = partial(finite, error=RestorationSettlementValidationError)
_positive = partial(positive, error=RestorationSettlementValidationError)
_non_negative = partial(non_negative, error=RestorationSettlementValidationError)


def _interval(value: object, *, field_name: str) -> CanonicalInterval:
    if not isinstance(value, CanonicalInterval):
        raise RestorationSettlementValidationError(
            f"{field_name} must be a CanonicalInterval"
        )
    return value


_product = partial(
    enum_member, RestorationProduct, field_name="product", error=RestorationSettlementValidationError
)


def _direction(value: object) -> RestorationDirection:
    try:
        return RestorationDirection(value)
    except (TypeError, ValueError) as exc:
        raise RestorationSettlementValidationError(
            "direction must be exactly UPWARD or DOWNWARD"
        ) from exc


def _optional_direction(value: object) -> RestorationDirection | None:
    return None if value is None else _direction(value)


def _optional_kind(value: object) -> MFRRActivationKind | None:
    if value is None:
        return None
    try:
        return MFRRActivationKind(value)
    except (TypeError, ValueError) as exc:
        raise RestorationSettlementValidationError(
            "mfrr_kind must be SCHEDULED, DIRECT, or None"
        ) from exc


def _price_state(value: object) -> SettlementPriceState:
    try:
        return SettlementPriceState(value)
    except (TypeError, ValueError) as exc:
        raise RestorationSettlementValidationError(
            "value_state must be VALUE, SOURCE_NULL, FIELD_ABSENT, or AMBIGUOUS"
        ) from exc


def _normalized_price(
    value: object,
    *,
    state: SettlementPriceState,
    field_name: str = "price",
) -> float | None:
    if state is SettlementPriceState.VALUE:
        return _finite(value, field_name=field_name)
    if value is not None:
        raise RestorationSettlementValidationError(
            f"{field_name} must be None when value_state is {state.value}"
        )
    return None


_sha256 = partial(sha256_digest, error=RestorationSettlementValidationError)
_plain = thaw
_fingerprint = partial(fingerprint, error=RestorationSettlementValidationError)


def _covers(coverage: CanonicalInterval, target: CanonicalInterval) -> bool:
    return (
        coverage.start_utc <= target.start_utc
        and coverage.end_utc >= target.end_utc
    )


@dataclass(frozen=True, slots=True)
class DayAheadEnergyPrice:
    schema_version: str
    price_id: str
    product: RestorationProduct
    interval: CanonicalInterval
    value_state: SettlementPriceState
    price: float | None
    unit: str
    currency: str
    source_or_assumption_ref: str
    source_field: str
    price_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "price_id": self.price_id,
            "product": self.product.value,
            "interval": self.interval.to_dict(),
            "value_state": self.value_state.value,
            "price": self.price,
            "unit": self.unit,
            "currency": self.currency,
            "source_or_assumption_ref": self.source_or_assumption_ref,
            "source_field": self.source_field,
            "price_fingerprint": self.price_fingerprint,
        }


def build_day_ahead_energy_price(
    *,
    price_id: str,
    product: RestorationProduct | str,
    interval: CanonicalInterval,
    value_state: SettlementPriceState | str,
    price: float | None,
    unit: str,
    currency: str,
    source_or_assumption_ref: str,
    source_field: str,
) -> DayAheadEnergyPrice:
    state = _price_state(value_state)
    payload = {
        "schema_version": RESTORATION_PRICE_SCHEMA_VERSION,
        "price_id": _non_empty(price_id, field_name="price_id"),
        "product": _product(product).value,
        "interval": _interval(interval, field_name="interval").to_dict(),
        "value_state": state.value,
        "price": _normalized_price(price, state=state),
        "unit": _non_empty(unit, field_name="unit"),
        "currency": _non_empty(currency, field_name="currency"),
        "source_or_assumption_ref": _non_empty(
            source_or_assumption_ref,
            field_name="source_or_assumption_ref",
        ),
        "source_field": _non_empty(source_field, field_name="source_field"),
    }
    return DayAheadEnergyPrice(
        schema_version=RESTORATION_PRICE_SCHEMA_VERSION,
        price_id=str(payload["price_id"]),
        product=RestorationProduct(str(payload["product"])),
        interval=interval,
        value_state=state,
        price=payload["price"],
        unit=str(payload["unit"]),
        currency=str(payload["currency"]),
        source_or_assumption_ref=str(payload["source_or_assumption_ref"]),
        source_field=str(payload["source_field"]),
        price_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class DirectionalCapacityPrice:
    schema_version: str
    price_id: str
    product: RestorationProduct
    direction: RestorationDirection
    interval: CanonicalInterval
    value_state: SettlementPriceState
    price: float | None
    unit: str
    currency: str
    eligibility: bool
    source_or_assumption_ref: str
    source_field: str
    price_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "price_id": self.price_id,
            "product": self.product.value,
            "direction": self.direction.value,
            "interval": self.interval.to_dict(),
            "value_state": self.value_state.value,
            "price": self.price,
            "unit": self.unit,
            "currency": self.currency,
            "eligibility": self.eligibility,
            "source_or_assumption_ref": self.source_or_assumption_ref,
            "source_field": self.source_field,
            "price_fingerprint": self.price_fingerprint,
        }


def build_directional_capacity_price(
    *,
    price_id: str,
    product: RestorationProduct | str,
    direction: RestorationDirection | str,
    interval: CanonicalInterval,
    value_state: SettlementPriceState | str,
    price: float | None,
    unit: str,
    currency: str,
    eligibility: bool,
    source_or_assumption_ref: str,
    source_field: str,
) -> DirectionalCapacityPrice:
    if not isinstance(eligibility, bool):
        raise RestorationSettlementValidationError("eligibility must be boolean")
    state = _price_state(value_state)
    normalized_product = _product(product)
    normalized_direction = _direction(direction)
    normalized_interval = _interval(interval, field_name="interval")
    payload = {
        "schema_version": RESTORATION_PRICE_SCHEMA_VERSION,
        "price_id": _non_empty(price_id, field_name="price_id"),
        "product": normalized_product.value,
        "direction": normalized_direction.value,
        "interval": normalized_interval.to_dict(),
        "value_state": state.value,
        "price": _normalized_price(price, state=state),
        "unit": _non_empty(unit, field_name="unit"),
        "currency": _non_empty(currency, field_name="currency"),
        "eligibility": eligibility,
        "source_or_assumption_ref": _non_empty(
            source_or_assumption_ref,
            field_name="source_or_assumption_ref",
        ),
        "source_field": _non_empty(source_field, field_name="source_field"),
    }
    return DirectionalCapacityPrice(
        schema_version=RESTORATION_PRICE_SCHEMA_VERSION,
        price_id=str(payload["price_id"]),
        product=normalized_product,
        direction=normalized_direction,
        interval=normalized_interval,
        value_state=state,
        price=payload["price"],
        unit=str(payload["unit"]),
        currency=str(payload["currency"]),
        eligibility=eligibility,
        source_or_assumption_ref=str(payload["source_or_assumption_ref"]),
        source_field=str(payload["source_field"]),
        price_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class AreaPriceProxyMapping:
    schema_version: str
    mapping_id: str
    source_artifact_fingerprint: str
    source_series_fingerprint: str
    derived_activation_mapping_fingerprint: str
    product: RestorationProduct
    direction: RestorationDirection
    price_field: str
    coverage: CanonicalInterval
    source_unit: str
    canonical_unit: str
    transformation: str
    assumptions: tuple[str, ...]
    output_label: str
    mapping_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "mapping_id": self.mapping_id,
            "source_artifact_fingerprint": self.source_artifact_fingerprint,
            "source_series_fingerprint": self.source_series_fingerprint,
            "derived_activation_mapping_fingerprint": (
                self.derived_activation_mapping_fingerprint
            ),
            "product": self.product.value,
            "direction": self.direction.value,
            "price_field": self.price_field,
            "coverage": self.coverage.to_dict(),
            "source_unit": self.source_unit,
            "canonical_unit": self.canonical_unit,
            "transformation": self.transformation,
            "assumptions": list(self.assumptions),
            "output_label": self.output_label,
            "mapping_fingerprint": self.mapping_fingerprint,
        }


def build_area_price_proxy_mapping(
    *,
    mapping_id: str,
    source_artifact_fingerprint: str,
    source_series_fingerprint: str,
    derived_activation_mapping_fingerprint: str,
    product: RestorationProduct | str,
    direction: RestorationDirection | str,
    price_field: str,
    coverage: CanonicalInterval,
    source_unit: str,
    canonical_unit: str,
    transformation: str,
    assumptions: Sequence[str],
    output_label: str,
) -> AreaPriceProxyMapping:
    normalized_assumptions = tuple(
        _non_empty(item, field_name=f"assumptions[{index}]")
        for index, item in enumerate(assumptions)
    )
    if not normalized_assumptions:
        raise RestorationSettlementValidationError(
            "area-price proxy assumptions must be non-empty"
        )
    normalized_label = _non_empty(output_label, field_name="output_label")
    if normalized_label != "scenario_proxy":
        raise RestorationSettlementValidationError(
            "area price output_label must be scenario_proxy and cannot claim asset_invoice"
        )
    normalized_product = _product(product)
    normalized_direction = _direction(direction)
    normalized_coverage = _interval(coverage, field_name="coverage")
    payload = {
        "schema_version": AREA_PRICE_PROXY_SCHEMA_VERSION,
        "mapping_id": _non_empty(mapping_id, field_name="mapping_id"),
        "source_artifact_fingerprint": _sha256(
            source_artifact_fingerprint,
            field_name="source_artifact_fingerprint",
        ),
        "source_series_fingerprint": _sha256(
            source_series_fingerprint,
            field_name="source_series_fingerprint",
        ),
        "derived_activation_mapping_fingerprint": _sha256(
            derived_activation_mapping_fingerprint,
            field_name="derived_activation_mapping_fingerprint",
        ),
        "product": normalized_product.value,
        "direction": normalized_direction.value,
        "price_field": _non_empty(price_field, field_name="price_field"),
        "coverage": normalized_coverage.to_dict(),
        "source_unit": _non_empty(source_unit, field_name="source_unit"),
        "canonical_unit": _non_empty(
            canonical_unit, field_name="canonical_unit"
        ),
        "transformation": _non_empty(
            transformation, field_name="transformation"
        ),
        "assumptions": list(normalized_assumptions),
        "output_label": normalized_label,
    }
    return AreaPriceProxyMapping(
        schema_version=AREA_PRICE_PROXY_SCHEMA_VERSION,
        mapping_id=str(payload["mapping_id"]),
        source_artifact_fingerprint=str(payload["source_artifact_fingerprint"]),
        source_series_fingerprint=str(payload["source_series_fingerprint"]),
        derived_activation_mapping_fingerprint=str(
            payload["derived_activation_mapping_fingerprint"]
        ),
        product=normalized_product,
        direction=normalized_direction,
        price_field=str(payload["price_field"]),
        coverage=normalized_coverage,
        source_unit=str(payload["source_unit"]),
        canonical_unit=str(payload["canonical_unit"]),
        transformation=str(payload["transformation"]),
        assumptions=normalized_assumptions,
        output_label=normalized_label,
        mapping_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class DirectionalActivationPrice:
    schema_version: str
    price_id: str
    product: RestorationProduct
    direction: RestorationDirection
    mfrr_kind: MFRRActivationKind | None
    interval: CanonicalInterval
    value_state: SettlementPriceState
    price: float | None
    unit: str
    currency: str
    pricing_basis: str
    source_or_assumption_ref: str
    source_field: str
    area_price_proxy_mapping: AreaPriceProxyMapping | None
    result_label: str
    price_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "price_id": self.price_id,
            "product": self.product.value,
            "direction": self.direction.value,
            "mfrr_kind": None if self.mfrr_kind is None else self.mfrr_kind.value,
            "interval": self.interval.to_dict(),
            "value_state": self.value_state.value,
            "price": self.price,
            "unit": self.unit,
            "currency": self.currency,
            "pricing_basis": self.pricing_basis,
            "source_or_assumption_ref": self.source_or_assumption_ref,
            "source_field": self.source_field,
            "area_price_proxy_mapping_fingerprint": (
                None
                if self.area_price_proxy_mapping is None
                else self.area_price_proxy_mapping.mapping_fingerprint
            ),
            "result_label": self.result_label,
            "price_fingerprint": self.price_fingerprint,
        }


def build_directional_activation_price(
    *,
    price_id: str,
    product: RestorationProduct | str,
    direction: RestorationDirection | str,
    mfrr_kind: MFRRActivationKind | str | None,
    interval: CanonicalInterval,
    value_state: SettlementPriceState | str,
    price: float | None,
    unit: str,
    currency: str,
    pricing_basis: str,
    source_or_assumption_ref: str,
    source_field: str,
    area_price_proxy_mapping: AreaPriceProxyMapping | None,
) -> DirectionalActivationPrice:
    normalized_product = _product(product)
    normalized_direction = _direction(direction)
    normalized_kind = _optional_kind(mfrr_kind)
    if normalized_product is RestorationProduct.AFRR and normalized_kind is not None:
        raise RestorationSettlementValidationError(
            "AFRR activation prices cannot declare an mFRR kind"
        )
    if normalized_product is RestorationProduct.MFRR and normalized_kind is None:
        raise RestorationSettlementValidationError(
            "MFRR activation prices require SCHEDULED or DIRECT kind"
        )
    normalized_interval = _interval(interval, field_name="interval")
    state = _price_state(value_state)
    normalized_unit = _non_empty(unit, field_name="unit")
    normalized_field = _non_empty(source_field, field_name="source_field")
    basis = _non_empty(pricing_basis, field_name="pricing_basis")
    if basis not in {"STUDY_ASSUMPTION", "RTE_AREA_PRICE_PROXY"}:
        raise RestorationSettlementValidationError(
            "pricing_basis must be STUDY_ASSUMPTION or RTE_AREA_PRICE_PROXY"
        )
    if basis == "RTE_AREA_PRICE_PROXY":
        if type(area_price_proxy_mapping) is not AreaPriceProxyMapping:
            raise RestorationSettlementValidationError(
                "RTE area-price proxy pricing requires an AreaPriceProxyMapping"
            )
        mapping = area_price_proxy_mapping
        if (
            mapping.product is not normalized_product
            or mapping.direction is not normalized_direction
        ):
            raise RestorationSettlementValidationError(
                "area-price proxy mapping product/direction is incompatible with price"
            )
        if not _covers(mapping.coverage, normalized_interval):
            raise RestorationSettlementValidationError(
                "area-price proxy mapping coverage does not contain price interval"
            )
        if mapping.canonical_unit != normalized_unit:
            raise RestorationSettlementValidationError(
                "area-price proxy mapping canonical unit does not match price unit"
            )
        if mapping.price_field != normalized_field:
            raise RestorationSettlementValidationError(
                "area-price proxy mapping field does not match price source_field"
            )
        result_label = "scenario_proxy"
    else:
        if area_price_proxy_mapping is not None:
            raise RestorationSettlementValidationError(
                "STUDY_ASSUMPTION price cannot declare an area-price proxy mapping"
            )
        result_label = "study_assumption"
    payload = {
        "schema_version": RESTORATION_PRICE_SCHEMA_VERSION,
        "price_id": _non_empty(price_id, field_name="price_id"),
        "product": normalized_product.value,
        "direction": normalized_direction.value,
        "mfrr_kind": None if normalized_kind is None else normalized_kind.value,
        "interval": normalized_interval.to_dict(),
        "value_state": state.value,
        "price": _normalized_price(price, state=state),
        "unit": normalized_unit,
        "currency": _non_empty(currency, field_name="currency"),
        "pricing_basis": basis,
        "source_or_assumption_ref": _non_empty(
            source_or_assumption_ref,
            field_name="source_or_assumption_ref",
        ),
        "source_field": normalized_field,
        "area_price_proxy_mapping_fingerprint": (
            None
            if area_price_proxy_mapping is None
            else area_price_proxy_mapping.mapping_fingerprint
        ),
        "result_label": result_label,
    }
    return DirectionalActivationPrice(
        schema_version=RESTORATION_PRICE_SCHEMA_VERSION,
        price_id=str(payload["price_id"]),
        product=normalized_product,
        direction=normalized_direction,
        mfrr_kind=normalized_kind,
        interval=normalized_interval,
        value_state=state,
        price=payload["price"],
        unit=normalized_unit,
        currency=str(payload["currency"]),
        pricing_basis=basis,
        source_or_assumption_ref=str(payload["source_or_assumption_ref"]),
        source_field=normalized_field,
        area_price_proxy_mapping=area_price_proxy_mapping,
        result_label=result_label,
        price_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class RestorationPenaltyRule:
    schema_version: str
    rule_id: str
    product: RestorationProduct
    direction: RestorationDirection | None
    mfrr_kind: MFRRActivationKind | None
    interval: CanonicalInterval
    measure: str
    rate: float
    rate_unit: str
    application: str
    rule_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "rule_id": self.rule_id,
            "product": self.product.value,
            "direction": None if self.direction is None else self.direction.value,
            "mfrr_kind": None if self.mfrr_kind is None else self.mfrr_kind.value,
            "interval": self.interval.to_dict(),
            "measure": self.measure,
            "rate": self.rate,
            "rate_unit": self.rate_unit,
            "application": self.application,
            "rule_fingerprint": self.rule_fingerprint,
        }


def build_restoration_penalty_rule(
    *,
    rule_id: str,
    product: RestorationProduct | str,
    direction: RestorationDirection | str | None,
    mfrr_kind: MFRRActivationKind | str | None,
    interval: CanonicalInterval,
    measure: str,
    rate: float,
    rate_unit: str,
    application: str,
) -> RestorationPenaltyRule:
    normalized_product = _product(product)
    normalized_direction = _optional_direction(direction)
    normalized_kind = _optional_kind(mfrr_kind)
    if normalized_product is RestorationProduct.AFRR and normalized_kind is not None:
        raise RestorationSettlementValidationError(
            "AFRR penalty rule cannot declare an mFRR kind"
        )
    if _non_empty(measure, field_name="measure") != "undelivered_activation_energy_kwh":
        raise RestorationSettlementValidationError(
            "penalty measure must be undelivered_activation_energy_kwh"
        )
    if _non_empty(rate_unit, field_name="rate_unit") != "EUR/kWh":
        raise RestorationSettlementValidationError(
            "penalty rate_unit must be EUR/kWh"
        )
    if _non_empty(application, field_name="application") != "sum_eligible_shortfall":
        raise RestorationSettlementValidationError(
            "penalty application must be sum_eligible_shortfall"
        )
    normalized_interval = _interval(interval, field_name="interval")
    payload = {
        "schema_version": RESTORATION_PENALTY_RULE_SCHEMA_VERSION,
        "rule_id": _non_empty(rule_id, field_name="rule_id"),
        "product": normalized_product.value,
        "direction": (
            None if normalized_direction is None else normalized_direction.value
        ),
        "mfrr_kind": None if normalized_kind is None else normalized_kind.value,
        "interval": normalized_interval.to_dict(),
        "measure": "undelivered_activation_energy_kwh",
        "rate": _non_negative(rate, field_name="rate"),
        "rate_unit": "EUR/kWh",
        "application": "sum_eligible_shortfall",
    }
    return RestorationPenaltyRule(
        schema_version=RESTORATION_PENALTY_RULE_SCHEMA_VERSION,
        rule_id=str(payload["rule_id"]),
        product=normalized_product,
        direction=normalized_direction,
        mfrr_kind=normalized_kind,
        interval=normalized_interval,
        measure="undelivered_activation_energy_kwh",
        rate=float(payload["rate"]),
        rate_unit="EUR/kWh",
        application="sum_eligible_shortfall",
        rule_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class ThroughputDegradationRule:
    schema_version: str
    rule_id: str
    cost_per_kwh: float
    unit: str
    description: str
    rule_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "rule_id": self.rule_id,
            "cost_per_kwh": self.cost_per_kwh,
            "unit": self.unit,
            "description": self.description,
            "rule_fingerprint": self.rule_fingerprint,
        }


def build_throughput_degradation_rule(
    *,
    rule_id: str,
    cost_per_kwh: float,
    unit: str,
    description: str,
) -> ThroughputDegradationRule:
    normalized_unit = _non_empty(unit, field_name="unit")
    if normalized_unit != "EUR/kWh":
        raise RestorationSettlementValidationError(
            "degradation unit must be EUR/kWh"
        )
    normalized_description = _non_empty(description, field_name="description")
    lowered = normalized_description.lower()
    if "proxy" not in lowered or "not" not in lowered or "aging" not in lowered:
        raise RestorationSettlementValidationError(
            "degradation description must identify a comparison proxy, not an aging model"
        )
    payload = {
        "schema_version": THROUGHPUT_DEGRADATION_RULE_SCHEMA_VERSION,
        "rule_id": _non_empty(rule_id, field_name="rule_id"),
        "cost_per_kwh": _non_negative(
            cost_per_kwh, field_name="cost_per_kwh"
        ),
        "unit": normalized_unit,
        "description": normalized_description,
    }
    return ThroughputDegradationRule(
        schema_version=THROUGHPUT_DEGRADATION_RULE_SCHEMA_VERSION,
        rule_id=str(payload["rule_id"]),
        cost_per_kwh=float(payload["cost_per_kwh"]),
        unit=normalized_unit,
        description=normalized_description,
        rule_fingerprint=_fingerprint(payload),
    )


@dataclass(frozen=True, slots=True)
class RestorationSettlementDiagnostic:
    code: str
    component: str
    source_or_assumption_ref: str
    source_field: str
    requested_period: CanonicalInterval
    product: RestorationProduct
    direction: RestorationDirection | None
    observed_condition: str
    expected_condition: str
    public_message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "component": self.component,
            "source_or_assumption_ref": self.source_or_assumption_ref,
            "source_field": self.source_field,
            "requested_period": self.requested_period.to_dict(),
            "product": self.product.value,
            "direction": None if self.direction is None else self.direction.value,
            "observed_condition": self.observed_condition,
            "expected_condition": self.expected_condition,
            "public_message": self.public_message,
        }


def _diagnostic(
    *,
    code: str,
    component: str,
    period: CanonicalInterval,
    product: RestorationProduct,
    direction: RestorationDirection | None,
    observed: str,
    expected: str,
    source_ref: str = "settlement_input",
    source_field: str = "required_price",
) -> RestorationSettlementDiagnostic:
    direction_text = "" if direction is None else f" {direction.value}"
    message = (
        f"{component} settlement for {product.value}{direction_text} over "
        f"[{period.start_utc.isoformat()},{period.end_utc.isoformat()}) observed "
        f"{observed}; expected {expected}"
    )
    return RestorationSettlementDiagnostic(
        code=code,
        component=component,
        source_or_assumption_ref=source_ref,
        source_field=source_field,
        requested_period=period,
        product=product,
        direction=direction,
        observed_condition=observed,
        expected_condition=expected,
        public_message=message,
    )


@dataclass(frozen=True, slots=True)
class RestorationSettlement:
    schema_version: str
    settlement_id: str
    semantics_version: str
    product: RestorationProduct
    availability: SettlementAvailability
    physical_result_fingerprint: str
    unavailable_reasons: tuple[RestorationSettlementDiagnostic, ...]
    day_ahead_status: SettlementComponentStatus
    upward_capacity_status: SettlementComponentStatus
    downward_capacity_status: SettlementComponentStatus
    upward_activation_status: SettlementComponentStatus
    downward_activation_status: SettlementComponentStatus
    penalty_status: SettlementComponentStatus
    degradation_status: SettlementComponentStatus
    day_ahead_energy_revenue_eur: float | None
    upward_capacity_revenue_eur: float | None
    downward_capacity_revenue_eur: float | None
    upward_activation_revenue_eur: float | None
    downward_activation_revenue_eur: float | None
    non_performance_penalty_eur: float | None
    throughput_kwh: float
    degradation_cost_eur: float | None
    gross_revenue_eur: float | None
    net_result_eur: float | None
    price_mapping_labels: tuple[str, ...]
    tolerance: float
    settlement_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "settlement_id": self.settlement_id,
            "semantics_version": self.semantics_version,
            "product": self.product.value,
            "availability": self.availability.value,
            "physical_result_fingerprint": self.physical_result_fingerprint,
            "unavailable_reasons": [
                item.to_dict() for item in self.unavailable_reasons
            ],
            "component_status": {
                "day_ahead": self.day_ahead_status.value,
                "upward_capacity": self.upward_capacity_status.value,
                "downward_capacity": self.downward_capacity_status.value,
                "upward_activation": self.upward_activation_status.value,
                "downward_activation": self.downward_activation_status.value,
                "penalty": self.penalty_status.value,
                "degradation": self.degradation_status.value,
            },
            "throughput_kwh": self.throughput_kwh,
            "price_mapping_labels": list(self.price_mapping_labels),
            "tolerance": self.tolerance,
            "settlement_fingerprint": self.settlement_fingerprint,
        }
        if self.availability is SettlementAvailability.AVAILABLE:
            payload.update(
                {
                    "day_ahead_energy_revenue_eur": (
                        self.day_ahead_energy_revenue_eur
                    ),
                    "upward_capacity_revenue_eur": (
                        self.upward_capacity_revenue_eur
                    ),
                    "downward_capacity_revenue_eur": (
                        self.downward_capacity_revenue_eur
                    ),
                    "upward_activation_revenue_eur": (
                        self.upward_activation_revenue_eur
                    ),
                    "downward_activation_revenue_eur": (
                        self.downward_activation_revenue_eur
                    ),
                    "non_performance_penalty_eur": (
                        self.non_performance_penalty_eur
                    ),
                    "degradation_cost_eur": self.degradation_cost_eur,
                    "gross_revenue_eur": self.gross_revenue_eur,
                    "net_result_eur": self.net_result_eur,
                }
            )
        return payload


@dataclass(frozen=True, slots=True)
class AFRRRestorationSettlement(RestorationSettlement):
    """aFRR settlement with no mFRR-kind placeholder fields."""


@dataclass(frozen=True, slots=True)
class MFRRRestorationSettlement(RestorationSettlement):
    """mFRR settlement retaining distinct scheduled/direct revenue."""

    activation_revenue_by_mfrr_kind_eur: Mapping[str, float] | None

    def to_dict(self) -> dict[str, object]:
        payload = RestorationSettlement.to_dict(self)
        if (
            self.availability is SettlementAvailability.AVAILABLE
            and self.activation_revenue_by_mfrr_kind_eur is not None
        ):
            payload["activation_revenue_by_mfrr_kind_eur"] = dict(
                self.activation_revenue_by_mfrr_kind_eur
            )
        return payload


def _typed_prices(value: object, *, expected_type: type, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RestorationSettlementValidationError(
            f"{field_name} must be a sequence"
        )
    normalized = tuple(value)
    if any(type(item) is not expected_type for item in normalized):
        raise RestorationSettlementValidationError(
            f"{field_name} contains an incompatible price type"
        )
    return normalized


def _identity_candidates(
    prices: Sequence,
    *,
    product: RestorationProduct,
    direction: RestorationDirection | None,
    kind: MFRRActivationKind | None,
    period: CanonicalInterval,
) -> tuple:
    result = []
    for price in prices:
        if price.product is not product:
            continue
        if direction is not None and getattr(price, "direction", None) is not direction:
            continue
        if hasattr(price, "mfrr_kind") and price.mfrr_kind is not kind:
            continue
        if _covers(price.interval, period):
            result.append(price)
    return tuple(result)


def _validate_single_price(
    *,
    prices: Sequence,
    candidates: Sequence,
    component: str,
    product: RestorationProduct,
    direction: RestorationDirection | None,
    kind: MFRRActivationKind | None,
    period: CanonicalInterval,
    expected_unit: str,
    diagnostics: list[RestorationSettlementDiagnostic],
) -> object | None:
    expected_identity = f"one {product.value}"
    if direction is not None:
        expected_identity += f" {direction.value}"
    if kind is not None:
        expected_identity += f" {kind.value}"
    expected_identity += f" {expected_unit} price covering the interval"
    if len(candidates) == 0:
        observed_identities = ", ".join(
            (
                f"{item.product.value}/"
                f"{getattr(getattr(item, 'direction', None), 'value', 'NONE')}/"
                f"{getattr(getattr(item, 'mfrr_kind', None), 'value', 'NONE')}/"
                f"{item.unit}"
            )
            for item in prices
        ) or "missing price"
        diagnostics.append(
            _diagnostic(
                code=f"{component}_price_missing_or_uncovered",
                component=component,
                period=period,
                product=product,
                direction=direction,
                observed=f"missing compatible price; available identities: {observed_identities}",
                expected=expected_identity,
            )
        )
        return None
    if len(candidates) != 1:
        diagnostics.append(
            _diagnostic(
                code=f"{component}_price_ambiguous",
                component=component,
                period=period,
                product=product,
                direction=direction,
                observed=f"ambiguous multiple prices ({len(candidates)})",
                expected=expected_identity,
            )
        )
        return None
    price = candidates[0]
    if price.value_state is not SettlementPriceState.VALUE:
        diagnostics.append(
            _diagnostic(
                code=f"{component}_price_{price.value_state.value.lower()}",
                component=component,
                period=period,
                product=product,
                direction=direction,
                observed=f"{price.value_state.value} in {price.source_field}",
                expected=expected_identity,
                source_ref=price.source_or_assumption_ref,
                source_field=price.source_field,
            )
        )
        return None
    if price.unit != expected_unit or price.currency != "EUR":
        diagnostics.append(
            _diagnostic(
                code=f"{component}_price_unit_or_currency",
                component=component,
                period=period,
                product=product,
                direction=direction,
                observed=f"unit {price.unit} and currency {price.currency}",
                expected=f"unit {expected_unit} and currency EUR",
                source_ref=price.source_or_assumption_ref,
                source_field=price.source_field,
            )
        )
        return None
    return price


def _unavailable_settlement(
    *,
    settlement_id: str,
    semantics_version: str,
    product: RestorationProduct,
    replay_result: AFRRReplayResult | MFRRReplayResult,
    diagnostics: Sequence[RestorationSettlementDiagnostic],
    penalty_status: SettlementComponentStatus,
    degradation_status: SettlementComponentStatus,
    price_labels: tuple[str, ...],
    tolerance: float,
    input_fingerprints: Mapping[str, object],
) -> RestorationSettlement:
    reasons = tuple(diagnostics)
    payload = {
        "schema_version": RESTORATION_SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": settlement_id,
        "semantics_version": semantics_version,
        "product": product.value,
        "availability": SettlementAvailability.UNAVAILABLE.value,
        "physical_result_fingerprint": replay_result.result_fingerprint,
        "unavailable_reasons": [item.to_dict() for item in reasons],
        "component_status": {
            "day_ahead": SettlementComponentStatus.UNAVAILABLE.value,
            "upward_capacity": SettlementComponentStatus.UNAVAILABLE.value,
            "downward_capacity": SettlementComponentStatus.UNAVAILABLE.value,
            "upward_activation": SettlementComponentStatus.UNAVAILABLE.value,
            "downward_activation": SettlementComponentStatus.UNAVAILABLE.value,
            "penalty": penalty_status.value,
            "degradation": degradation_status.value,
        },
        "throughput_kwh": replay_result.totals.throughput_kwh,
        "price_mapping_labels": list(price_labels),
        "tolerance": tolerance,
        "input_fingerprints": dict(input_fingerprints),
    }
    common = dict(
        schema_version=RESTORATION_SETTLEMENT_SCHEMA_VERSION,
        settlement_id=settlement_id,
        semantics_version=semantics_version,
        product=product,
        availability=SettlementAvailability.UNAVAILABLE,
        physical_result_fingerprint=replay_result.result_fingerprint,
        unavailable_reasons=reasons,
        day_ahead_status=SettlementComponentStatus.UNAVAILABLE,
        upward_capacity_status=SettlementComponentStatus.UNAVAILABLE,
        downward_capacity_status=SettlementComponentStatus.UNAVAILABLE,
        upward_activation_status=SettlementComponentStatus.UNAVAILABLE,
        downward_activation_status=SettlementComponentStatus.UNAVAILABLE,
        penalty_status=penalty_status,
        degradation_status=degradation_status,
        day_ahead_energy_revenue_eur=None,
        upward_capacity_revenue_eur=None,
        downward_capacity_revenue_eur=None,
        upward_activation_revenue_eur=None,
        downward_activation_revenue_eur=None,
        non_performance_penalty_eur=None,
        throughput_kwh=replay_result.totals.throughput_kwh,
        degradation_cost_eur=None,
        gross_revenue_eur=None,
        net_result_eur=None,
        price_mapping_labels=price_labels,
        tolerance=tolerance,
        settlement_fingerprint=_fingerprint(payload),
    )
    if product is RestorationProduct.AFRR:
        return AFRRRestorationSettlement(**common)
    return MFRRRestorationSettlement(
        **common,
        activation_revenue_by_mfrr_kind_eur=None,
    )


def settle_restoration_services(
    *,
    settlement_id: str,
    semantics_version: str,
    replay_result: AFRRReplayResult | MFRRReplayResult,
    day_ahead_prices: Sequence[DayAheadEnergyPrice],
    capacity_prices: Sequence[DirectionalCapacityPrice],
    activation_prices: Sequence[DirectionalActivationPrice],
    penalty_rule: RestorationPenaltyRule | None,
    degradation_rule: ThroughputDegradationRule | None,
    require_day_ahead_prices: bool,
    require_capacity_prices: bool,
    require_activation_prices: bool,
    tolerance: float = DEFAULT_RESTORATION_SETTLEMENT_TOLERANCE,
) -> RestorationSettlement:
    """Settle one exact physical replay, or return one atomic unavailable result."""

    normalized_settlement_id = _non_empty(
        settlement_id, field_name="settlement_id"
    )
    normalized_semantics = _non_empty(
        semantics_version, field_name="semantics_version"
    )
    if type(replay_result) is AFRRReplayResult:
        product = RestorationProduct.AFRR
    elif type(replay_result) is MFRRReplayResult:
        product = RestorationProduct.MFRR
    else:
        raise RestorationSettlementValidationError(
            "replay_result must be exactly an AFRRReplayResult or MFRRReplayResult"
        )
    for value, field_name in (
        (require_day_ahead_prices, "require_day_ahead_prices"),
        (require_capacity_prices, "require_capacity_prices"),
        (require_activation_prices, "require_activation_prices"),
    ):
        if not isinstance(value, bool):
            raise RestorationSettlementValidationError(
                f"{field_name} must be boolean"
            )
    normalized_tolerance = _positive(tolerance, field_name="tolerance")
    day_ahead = _typed_prices(
        day_ahead_prices,
        expected_type=DayAheadEnergyPrice,
        field_name="day_ahead_prices",
    )
    capacity = _typed_prices(
        capacity_prices,
        expected_type=DirectionalCapacityPrice,
        field_name="capacity_prices",
    )
    activation = _typed_prices(
        activation_prices,
        expected_type=DirectionalActivationPrice,
        field_name="activation_prices",
    )
    if penalty_rule is not None and type(penalty_rule) is not RestorationPenaltyRule:
        raise RestorationSettlementValidationError(
            "penalty_rule must be a RestorationPenaltyRule or None"
        )
    if degradation_rule is not None and type(degradation_rule) is not ThroughputDegradationRule:
        raise RestorationSettlementValidationError(
            "degradation_rule must be a ThroughputDegradationRule or None"
        )
    penalty_status = (
        SettlementComponentStatus.UNCONFIGURED
        if penalty_rule is None
        else SettlementComponentStatus.AVAILABLE
    )
    degradation_status = (
        SettlementComponentStatus.UNCONFIGURED
        if degradation_rule is None
        else SettlementComponentStatus.AVAILABLE
    )
    diagnostics: list[RestorationSettlementDiagnostic] = []
    day_ahead_matches: dict[int, DayAheadEnergyPrice] = {}
    capacity_matches: dict[int, DirectionalCapacityPrice] = {}
    activation_matches: dict[int, DirectionalActivationPrice] = {}

    if require_day_ahead_prices:
        for index, baseline in enumerate(replay_result.request.baseline.intervals):
            candidates = _identity_candidates(
                day_ahead,
                product=product,
                direction=None,
                kind=None,
                period=baseline.interval,
            )
            matched = _validate_single_price(
                prices=day_ahead,
                candidates=candidates,
                component="day-ahead",
                product=product,
                direction=None,
                kind=None,
                period=baseline.interval,
                expected_unit="EUR/MWh",
                diagnostics=diagnostics,
            )
            if matched is not None:
                day_ahead_matches[index] = matched

    if require_capacity_prices:
        for index, commitment in enumerate(replay_result.request.commitments.intervals):
            if (
                not commitment.eligibility
                or commitment.committed_capacity_kw <= normalized_tolerance
            ):
                continue
            candidates = _identity_candidates(
                capacity,
                product=product,
                direction=commitment.direction,
                kind=None,
                period=commitment.interval,
            )
            matched = _validate_single_price(
                prices=capacity,
                candidates=candidates,
                component="capacity",
                product=product,
                direction=commitment.direction,
                kind=None,
                period=commitment.interval,
                expected_unit="EUR/MW/h",
                diagnostics=diagnostics,
            )
            if matched is not None:
                capacity_matches[index] = matched

    if require_activation_prices:
        if product is RestorationProduct.AFRR:
            assert isinstance(replay_result, AFRRReplayResult)
            for index, (activation_sample, replay_sample) in enumerate(
                zip(
                    replay_result.request.activation_trajectory.samples,
                    replay_result.samples,
                    strict=True,
                )
            ):
                if abs(activation_sample.requested_balancing_power_kw) <= normalized_tolerance:
                    continue
                direction = (
                    RestorationDirection.UPWARD
                    if activation_sample.requested_balancing_power_kw < 0.0
                    else RestorationDirection.DOWNWARD
                )
                candidates = _identity_candidates(
                    activation,
                    product=product,
                    direction=direction,
                    kind=None,
                    period=replay_sample.interval,
                )
                matched = _validate_single_price(
                    prices=activation,
                    candidates=candidates,
                    component="activation",
                    product=product,
                    direction=direction,
                    kind=None,
                    period=replay_sample.interval,
                    expected_unit="EUR/MWh",
                    diagnostics=diagnostics,
                )
                if matched is not None:
                    activation_matches[index] = matched
        else:
            assert isinstance(replay_result, MFRRReplayResult)
            for index, (event, performance) in enumerate(
                zip(
                    replay_result.request.activation_sequence.events,
                    replay_result.event_performance,
                    strict=True,
                )
            ):
                if performance.requested_energy_kwh <= normalized_tolerance:
                    continue
                candidates = _identity_candidates(
                    activation,
                    product=product,
                    direction=event.direction,
                    kind=event.kind,
                    period=event.complete_interval,
                )
                matched = _validate_single_price(
                    prices=activation,
                    candidates=candidates,
                    component="activation",
                    product=product,
                    direction=event.direction,
                    kind=event.kind,
                    period=event.complete_interval,
                    expected_unit="EUR/MWh",
                    diagnostics=diagnostics,
                )
                if matched is not None:
                    activation_matches[index] = matched

    replay_period = replay_result.request.integration_grid.period
    if penalty_rule is not None:
        if penalty_rule.product is not product:
            diagnostics.append(
                _diagnostic(
                    code="penalty_product_mismatch",
                    component="penalty",
                    period=replay_period,
                    product=product,
                    direction=penalty_rule.direction,
                    observed=f"penalty product {penalty_rule.product.value}",
                    expected=f"penalty product {product.value}",
                    source_ref=penalty_rule.rule_id,
                    source_field="product",
                )
            )
        if not _covers(penalty_rule.interval, replay_period):
            diagnostics.append(
                _diagnostic(
                    code="penalty_coverage_mismatch",
                    component="penalty",
                    period=replay_period,
                    product=product,
                    direction=penalty_rule.direction,
                    observed="penalty interval does not cover replay period",
                    expected="complete replay-period coverage",
                    source_ref=penalty_rule.rule_id,
                    source_field="interval",
                )
            )

    price_labels = tuple(
        sorted({price.result_label for price in activation})
    )
    input_fingerprints = {
        "replay": replay_result.result_fingerprint,
        "day_ahead_prices": [item.price_fingerprint for item in day_ahead],
        "capacity_prices": [item.price_fingerprint for item in capacity],
        "activation_prices": [item.price_fingerprint for item in activation],
        "penalty_rule": (
            None if penalty_rule is None else penalty_rule.rule_fingerprint
        ),
        "degradation_rule": (
            None if degradation_rule is None else degradation_rule.rule_fingerprint
        ),
    }
    if diagnostics:
        return _unavailable_settlement(
            settlement_id=normalized_settlement_id,
            semantics_version=normalized_semantics,
            product=product,
            replay_result=replay_result,
            diagnostics=diagnostics,
            penalty_status=penalty_status,
            degradation_status=degradation_status,
            price_labels=price_labels,
            tolerance=normalized_tolerance,
            input_fingerprints=input_fingerprints,
        )

    day_ahead_revenue = 0.0
    if require_day_ahead_prices:
        for index, baseline in enumerate(replay_result.request.baseline.intervals):
            price = day_ahead_matches[index]
            assert price.price is not None
            duration_hours = (
                baseline.interval.end_utc - baseline.interval.start_utc
            ).total_seconds() / 3600.0
            day_ahead_revenue += (
                -baseline.accepted_baseline_power_kw
                * duration_hours
                / 1000.0
                * price.price
            )

    capacity_revenue = {
        RestorationDirection.UPWARD: 0.0,
        RestorationDirection.DOWNWARD: 0.0,
    }
    capacity_eligible = {
        RestorationDirection.UPWARD: False,
        RestorationDirection.DOWNWARD: False,
    }
    if require_capacity_prices:
        for index, commitment in enumerate(replay_result.request.commitments.intervals):
            if (
                not commitment.eligibility
                or commitment.committed_capacity_kw <= normalized_tolerance
            ):
                continue
            price = capacity_matches[index]
            assert price.price is not None
            if not price.eligibility:
                continue
            duration_hours = (
                commitment.interval.end_utc - commitment.interval.start_utc
            ).total_seconds() / 3600.0
            capacity_revenue[commitment.direction] += (
                commitment.committed_capacity_kw
                / 1000.0
                * duration_hours
                * price.price
            )
            capacity_eligible[commitment.direction] = True

    activation_revenue = {
        RestorationDirection.UPWARD: 0.0,
        RestorationDirection.DOWNWARD: 0.0,
    }
    by_kind = {
        MFRRActivationKind.SCHEDULED.value: 0.0,
        MFRRActivationKind.DIRECT.value: 0.0,
    }
    if product is RestorationProduct.AFRR:
        assert isinstance(replay_result, AFRRReplayResult)
        for index, (activation_sample, replay_sample) in enumerate(
            zip(
                replay_result.request.activation_trajectory.samples,
                replay_result.samples,
                strict=True,
            )
        ):
            if abs(activation_sample.requested_balancing_power_kw) <= normalized_tolerance:
                continue
            direction = (
                RestorationDirection.UPWARD
                if activation_sample.requested_balancing_power_kw < 0.0
                else RestorationDirection.DOWNWARD
            )
            price = activation_matches[index]
            assert price.price is not None
            activation_revenue[direction] += (
                replay_sample.delivered_activation_energy_kwh / 1000.0 * price.price
            )
        by_kind_result = None
    else:
        assert isinstance(replay_result, MFRRReplayResult)
        for index, (event, performance) in enumerate(
            zip(
                replay_result.request.activation_sequence.events,
                replay_result.event_performance,
                strict=True,
            )
        ):
            if performance.requested_energy_kwh <= normalized_tolerance:
                continue
            price = activation_matches[index]
            assert price.price is not None
            revenue = performance.delivered_energy_kwh / 1000.0 * price.price
            activation_revenue[event.direction] += revenue
            by_kind[event.kind.value] += revenue
        by_kind_result = MappingProxyType(by_kind)

    shortfall = 0.0
    if penalty_rule is not None:
        if product is RestorationProduct.AFRR:
            assert isinstance(replay_result, AFRRReplayResult)
            for activation_sample, sample in zip(
                replay_result.request.activation_trajectory.samples,
                replay_result.samples,
                strict=True,
            ):
                direction = activation_sample.direction
                if direction is None:
                    continue
                if penalty_rule.direction is not None and direction is not penalty_rule.direction:
                    continue
                shortfall += sample.undelivered_activation_energy_kwh
        else:
            assert isinstance(replay_result, MFRRReplayResult)
            for performance in replay_result.event_performance:
                if (
                    penalty_rule.direction is not None
                    and performance.direction is not penalty_rule.direction
                ):
                    continue
                if (
                    penalty_rule.mfrr_kind is not None
                    and performance.kind is not penalty_rule.mfrr_kind
                ):
                    continue
                shortfall += performance.undelivered_energy_kwh
        penalty = shortfall * penalty_rule.rate
    else:
        penalty = 0.0

    throughput = replay_result.totals.throughput_kwh
    degradation = (
        0.0
        if degradation_rule is None
        else throughput * degradation_rule.cost_per_kwh
    )
    upward_capacity = capacity_revenue[RestorationDirection.UPWARD]
    downward_capacity = capacity_revenue[RestorationDirection.DOWNWARD]
    upward_activation = activation_revenue[RestorationDirection.UPWARD]
    downward_activation = activation_revenue[RestorationDirection.DOWNWARD]
    gross = (
        day_ahead_revenue
        + upward_capacity
        + downward_capacity
        + upward_activation
        + downward_activation
    )
    net = gross - penalty - degradation
    if abs(net - (gross - penalty - degradation)) > normalized_tolerance:
        raise RestorationSettlementValidationError(
            "restoration gross/net reconciliation failed"
        )
    upward_capacity_status = (
        SettlementComponentStatus.AVAILABLE
        if capacity_eligible[RestorationDirection.UPWARD]
        else SettlementComponentStatus.INELIGIBLE
    )
    downward_capacity_status = (
        SettlementComponentStatus.AVAILABLE
        if capacity_eligible[RestorationDirection.DOWNWARD]
        else SettlementComponentStatus.INELIGIBLE
    )
    payload = {
        "schema_version": RESTORATION_SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": normalized_settlement_id,
        "semantics_version": normalized_semantics,
        "product": product.value,
        "availability": SettlementAvailability.AVAILABLE.value,
        "physical_result_fingerprint": replay_result.result_fingerprint,
        "unavailable_reasons": [],
        "component_status": {
            "day_ahead": SettlementComponentStatus.AVAILABLE.value,
            "upward_capacity": upward_capacity_status.value,
            "downward_capacity": downward_capacity_status.value,
            "upward_activation": SettlementComponentStatus.AVAILABLE.value,
            "downward_activation": SettlementComponentStatus.AVAILABLE.value,
            "penalty": penalty_status.value,
            "degradation": degradation_status.value,
        },
        "day_ahead_energy_revenue_eur": day_ahead_revenue,
        "upward_capacity_revenue_eur": upward_capacity,
        "downward_capacity_revenue_eur": downward_capacity,
        "upward_activation_revenue_eur": upward_activation,
        "downward_activation_revenue_eur": downward_activation,
        "non_performance_penalty_eur": penalty,
        "throughput_kwh": throughput,
        "degradation_cost_eur": degradation,
        "gross_revenue_eur": gross,
        "net_result_eur": net,
        "price_mapping_labels": list(price_labels),
        "tolerance": normalized_tolerance,
        "input_fingerprints": input_fingerprints,
    }
    if by_kind_result is not None:
        payload["activation_revenue_by_mfrr_kind_eur"] = dict(by_kind_result)
    common = dict(
        schema_version=RESTORATION_SETTLEMENT_SCHEMA_VERSION,
        settlement_id=normalized_settlement_id,
        semantics_version=normalized_semantics,
        product=product,
        availability=SettlementAvailability.AVAILABLE,
        physical_result_fingerprint=replay_result.result_fingerprint,
        unavailable_reasons=(),
        day_ahead_status=SettlementComponentStatus.AVAILABLE,
        upward_capacity_status=upward_capacity_status,
        downward_capacity_status=downward_capacity_status,
        upward_activation_status=SettlementComponentStatus.AVAILABLE,
        downward_activation_status=SettlementComponentStatus.AVAILABLE,
        penalty_status=penalty_status,
        degradation_status=degradation_status,
        day_ahead_energy_revenue_eur=day_ahead_revenue,
        upward_capacity_revenue_eur=upward_capacity,
        downward_capacity_revenue_eur=downward_capacity,
        upward_activation_revenue_eur=upward_activation,
        downward_activation_revenue_eur=downward_activation,
        non_performance_penalty_eur=penalty,
        throughput_kwh=throughput,
        degradation_cost_eur=degradation,
        gross_revenue_eur=gross,
        net_result_eur=net,
        price_mapping_labels=price_labels,
        tolerance=normalized_tolerance,
        settlement_fingerprint=_fingerprint(payload),
    )
    if product is RestorationProduct.AFRR:
        return AFRRRestorationSettlement(**common)
    return MFRRRestorationSettlement(
        **common,
        activation_revenue_by_mfrr_kind_eur=by_kind_result,
    )


__all__ = [
    "RESTORATION_SETTLEMENT_SCHEMA_VERSION",
    "RESTORATION_PRICE_SCHEMA_VERSION",
    "AREA_PRICE_PROXY_SCHEMA_VERSION",
    "RESTORATION_PENALTY_RULE_SCHEMA_VERSION",
    "THROUGHPUT_DEGRADATION_RULE_SCHEMA_VERSION",
    "DEFAULT_RESTORATION_SETTLEMENT_TOLERANCE",
    "RestorationSettlementValidationError",
    "SettlementAvailability",
    "SettlementComponentStatus",
    "SettlementPriceState",
    "DayAheadEnergyPrice",
    "DirectionalCapacityPrice",
    "AreaPriceProxyMapping",
    "DirectionalActivationPrice",
    "RestorationPenaltyRule",
    "ThroughputDegradationRule",
    "RestorationSettlementDiagnostic",
    "RestorationSettlement",
    "AFRRRestorationSettlement",
    "MFRRRestorationSettlement",
    "build_day_ahead_energy_price",
    "build_directional_capacity_price",
    "build_area_price_proxy_mapping",
    "build_directional_activation_price",
    "build_restoration_penalty_rule",
    "build_throughput_degradation_rule",
    "settle_restoration_services",
]
