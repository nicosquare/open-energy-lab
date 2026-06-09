"""Shared configuration and support declarations for shipped native controllers."""

from __future__ import annotations

from dataclasses import dataclass


def _require_numeric_scalar(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def _require_positive_scalar(value: object, *, field_name: str) -> float:
    normalized = _require_numeric_scalar(value, field_name=field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _require_fraction(value: object, *, field_name: str) -> float:
    normalized = _require_numeric_scalar(value, field_name=field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be within [0.0, 1.0]")
    return normalized


def _require_controller_name(value: str | None, *, default: str) -> str:
    if value is None:
        return default
    if not isinstance(value, str):
        raise TypeError("controller_name must be a string when provided")
    if value == "":
        raise ValueError("controller_name must be non-empty when provided")
    return value


@dataclass(frozen=True, slots=True)
class PriceThresholdConfig:
    """Typed configuration for the native price-threshold controller."""

    charge_below_import_price: float
    discharge_above_import_price: float
    charge_request_kw: float
    discharge_request_kw: float
    controller_name: str | None = "PriceThresholdController"

    def __post_init__(self) -> None:
        charge_below = _require_numeric_scalar(
            self.charge_below_import_price,
            field_name="charge_below_import_price",
        )
        discharge_above = _require_numeric_scalar(
            self.discharge_above_import_price,
            field_name="discharge_above_import_price",
        )
        if charge_below >= discharge_above:
            raise ValueError(
                "charge_below_import_price must be lower than discharge_above_import_price"
            )

        object.__setattr__(self, "charge_below_import_price", charge_below)
        object.__setattr__(self, "discharge_above_import_price", discharge_above)
        object.__setattr__(
            self,
            "charge_request_kw",
            _require_positive_scalar(self.charge_request_kw, field_name="charge_request_kw"),
        )
        object.__setattr__(
            self,
            "discharge_request_kw",
            _require_positive_scalar(
                self.discharge_request_kw,
                field_name="discharge_request_kw",
            ),
        )
        object.__setattr__(
            self,
            "controller_name",
            _require_controller_name(
                self.controller_name,
                default="PriceThresholdController",
            ),
        )


@dataclass(frozen=True, slots=True)
class SocGuardrailConfig:
    """Typed configuration for the native SOC guardrail controller."""

    target_min_soc: float
    target_max_soc: float
    charge_request_kw: float
    discharge_request_kw: float
    controller_name: str | None = "SocGuardrailController"

    def __post_init__(self) -> None:
        target_min = _require_fraction(self.target_min_soc, field_name="target_min_soc")
        target_max = _require_fraction(self.target_max_soc, field_name="target_max_soc")
        if target_min >= target_max:
            raise ValueError("target_min_soc must be lower than target_max_soc")

        object.__setattr__(self, "target_min_soc", target_min)
        object.__setattr__(self, "target_max_soc", target_max)
        object.__setattr__(
            self,
            "charge_request_kw",
            _require_positive_scalar(self.charge_request_kw, field_name="charge_request_kw"),
        )
        object.__setattr__(
            self,
            "discharge_request_kw",
            _require_positive_scalar(
                self.discharge_request_kw,
                field_name="discharge_request_kw",
            ),
        )
        object.__setattr__(
            self,
            "controller_name",
            _require_controller_name(
                self.controller_name,
                default="SocGuardrailController",
            ),
        )


@dataclass(frozen=True, slots=True)
class PVSelfConsumptionConfig:
    """Typed configuration for the native PV self-consumption controller."""

    reserve_min_soc: float
    reserve_max_soc: float
    charge_request_kw: float
    discharge_request_kw: float
    controller_name: str | None = "PVSelfConsumptionController"

    def __post_init__(self) -> None:
        reserve_min = _require_fraction(self.reserve_min_soc, field_name="reserve_min_soc")
        reserve_max = _require_fraction(self.reserve_max_soc, field_name="reserve_max_soc")
        if reserve_min >= reserve_max:
            raise ValueError("reserve_min_soc must be lower than reserve_max_soc")

        object.__setattr__(self, "reserve_min_soc", reserve_min)
        object.__setattr__(self, "reserve_max_soc", reserve_max)
        object.__setattr__(
            self,
            "charge_request_kw",
            _require_positive_scalar(self.charge_request_kw, field_name="charge_request_kw"),
        )
        object.__setattr__(
            self,
            "discharge_request_kw",
            _require_positive_scalar(
                self.discharge_request_kw,
                field_name="discharge_request_kw",
            ),
        )
        object.__setattr__(
            self,
            "controller_name",
            _require_controller_name(
                self.controller_name,
                default="PVSelfConsumptionController",
            ),
        )


@dataclass(frozen=True, slots=True)
class ControllerSupportDeclaration:
    """Documented support declaration for one shipped controller."""

    controller_name: str
    supported_scenario_kinds: tuple[str, ...]
    unsupported_reason_template: str

    def __post_init__(self) -> None:
        if not self.controller_name:
            raise ValueError("controller_name must be non-empty")
        if not self.supported_scenario_kinds:
            raise ValueError("supported_scenario_kinds must be non-empty")
        if len(set(self.supported_scenario_kinds)) != len(self.supported_scenario_kinds):
            raise ValueError("supported_scenario_kinds must not repeat values")
        if not self.unsupported_reason_template:
            raise ValueError("unsupported_reason_template must be non-empty")


SHIPPED_CONTROLLER_SUPPORT = {
    "PriceThresholdController": ControllerSupportDeclaration(
        controller_name="PriceThresholdController",
        supported_scenario_kinds=("ArbitrageScenario",),
        unsupported_reason_template=(
            "{controller_name} unsupported for {scenario_kind}; "
            "supported scenarios: {supported_scenario_kinds}"
        ),
    ),
    "SocGuardrailController": ControllerSupportDeclaration(
        controller_name="SocGuardrailController",
        supported_scenario_kinds=("ArbitrageScenario", "BatteryLoadPVScenario"),
        unsupported_reason_template=(
            "{controller_name} unsupported for {scenario_kind}; "
            "supported scenarios: {supported_scenario_kinds}"
        ),
    ),
    "PVSelfConsumptionController": ControllerSupportDeclaration(
        controller_name="PVSelfConsumptionController",
        supported_scenario_kinds=("BatteryLoadPVScenario",),
        unsupported_reason_template=(
            "{controller_name} unsupported for {scenario_kind}; "
            "supported scenarios: {supported_scenario_kinds}"
        ),
    ),
}


def require_supported_scenario(controller_name: str, scenario_kind: str) -> None:
    """Fail deterministically when a shipped controller is used on an unsupported scenario."""

    declaration = SHIPPED_CONTROLLER_SUPPORT.get(controller_name)
    if declaration is None:
        raise ValueError(f"unknown shipped controller {controller_name!r}")

    if scenario_kind in declaration.supported_scenario_kinds:
        return

    supported_scenario_kinds = ", ".join(declaration.supported_scenario_kinds)
    raise ValueError(
        declaration.unsupported_reason_template.format(
            controller_name=controller_name,
            scenario_kind=scenario_kind,
            supported_scenario_kinds=supported_scenario_kinds,
        )
    )


__all__ = [
    "ControllerSupportDeclaration",
    "PVSelfConsumptionConfig",
    "PriceThresholdConfig",
    "SHIPPED_CONTROLLER_SUPPORT",
    "SocGuardrailConfig",
    "require_supported_scenario",
]
