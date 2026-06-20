"""Cooling-service configuration primitives for demand-aware simulator paths."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


_SUPPORTED_SERVICE_PATHS = {"local-electric", "district-cooling"}


@dataclass(slots=True)
class LocalElectricCoolingConfiguration:
    """Deterministic local-electric conversion for cooling demand."""

    source_name: str
    electric_kw_per_rt: float
    valid_for_feature_version: str
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.electric_kw_per_rt <= 0.0:
            raise ValueError("electric_kw_per_rt must be positive")
        if not self.source_name:
            raise ValueError("source_name must be provided")
        if not self.valid_for_feature_version:
            raise ValueError("valid_for_feature_version must be provided")


@dataclass(slots=True)
class DistrictCoolingTariff:
    """Deterministic district-cooling settlement definition."""

    currency: str
    rate_per_rt_hour: float
    time_alignment: str
    tariff_name: str

    def __post_init__(self) -> None:
        if self.rate_per_rt_hour < 0.0:
            raise ValueError("rate_per_rt_hour must be non-negative")
        if self.time_alignment != "step-start":
            raise ValueError("time_alignment must be step-start")
        if not self.currency:
            raise ValueError("currency must be provided")
        if not self.tariff_name:
            raise ValueError("tariff_name must be provided")


@dataclass(slots=True)
class CoolingServiceConfiguration:
    """Exactly one configured cooling-service path for one scenario family."""

    service_path: str
    source: str
    local_electric_cooling: LocalElectricCoolingConfiguration | None = None
    district_cooling_tariff: DistrictCoolingTariff | None = None
    district_served_cooling_rt: Sequence[Sequence[float]] | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.service_path not in _SUPPORTED_SERVICE_PATHS:
            raise ValueError("service_path must be one of local-electric or district-cooling")
        if not self.source:
            raise ValueError("source must be provided")

        if self.service_path == "local-electric":
            if self.local_electric_cooling is None:
                raise ValueError("local-electric service path requires local_electric_cooling")
            if self.district_cooling_tariff is not None or self.district_served_cooling_rt is not None:
                raise ValueError(
                    "exactly one cooling service path must be configured; mixed service paths are invalid"
                )
            return

        if self.local_electric_cooling is not None:
            raise ValueError(
                "exactly one cooling service path must be configured; mixed service paths are invalid"
            )
        if self.district_cooling_tariff is None:
            raise ValueError("district-cooling service path requires district_cooling_tariff")
        if self.district_served_cooling_rt is not None:
            if isinstance(self.district_served_cooling_rt, (str, bytes, bytearray)):
                raise TypeError("district_served_cooling_rt must be a sequence of per-scenario sequences")
            for scenario_values in self.district_served_cooling_rt:
                if isinstance(scenario_values, (str, bytes, bytearray)):
                    raise TypeError(
                        "district_served_cooling_rt must be a sequence of per-scenario sequences"
                    )


def derive_local_cooling_electric_kw(
    *,
    cooling_demand_rt: Sequence[float],
    config: LocalElectricCoolingConfiguration,
) -> list[float]:
    """Convert cooling demand in RT to site electric demand in kW."""

    derived: list[float] = []
    for value in cooling_demand_rt:
        cooling_value = float(value)
        if cooling_value < 0.0:
            raise ValueError("cooling_demand_rt values must be non-negative")
        derived.append(cooling_value * config.electric_kw_per_rt)
    return derived


__all__ = [
    "CoolingServiceConfiguration",
    "DistrictCoolingTariff",
    "LocalElectricCoolingConfiguration",
    "derive_local_cooling_electric_kw",
]
