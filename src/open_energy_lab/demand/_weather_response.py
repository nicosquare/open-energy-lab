"""Weather-conditioned demand-response fitting helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isclose

from ._aligned_history import AlignedTrainingHistory


REQUIRED_DEMAND_WEATHER_DRIVERS = (
    "dry_bulb_air_temperature_c",
    "relative_humidity_pct",
    "global_horizontal_irradiance_w_per_m2",
)

_OUTPUT_ORDER = (
    "non_thermal_electric_demand_kw",
    "cooling_demand_rt",
)


@dataclass(frozen=True, slots=True)
class FittedDemandResponseModel:
    """One fitted output-specific weather response model."""

    model_kind: str
    local_step_baseline: tuple[float, ...]
    weather_response_terms: dict[str, float]
    training_day_count: int
    residual_scale_summary: dict[str, float]
    supported_weather_drivers: tuple[str, ...]
    explicit_training_requirement: str | None = None

    def to_dict(self, *, baseline_field_name: str) -> dict[str, object]:
        """Serialize the fitted model into artifact payload shape."""

        payload: dict[str, object] = {
            "model_kind": self.model_kind,
            baseline_field_name: list(self.local_step_baseline),
            "weather_response_terms": dict(self.weather_response_terms),
            "training_day_count": self.training_day_count,
            "residual_scale_summary": dict(self.residual_scale_summary),
            "supported_weather_drivers": list(self.supported_weather_drivers),
        }
        if self.explicit_training_requirement is not None:
            payload["explicit_training_requirement"] = self.explicit_training_requirement
        return payload


@dataclass(frozen=True, slots=True)
class FittedSharedResidualModel:
    """Shared residual model that preserves output correlation."""

    model_kind: str
    intervals_per_day: int
    output_order: tuple[str, ...]
    joint_residual_summary: dict[str, object]
    correlation_matrix: tuple[tuple[float, ...], ...]
    sampling_notes: str

    def to_dict(self) -> dict[str, object]:
        """Serialize the shared residual model into artifact payload shape."""

        return {
            "model_kind": self.model_kind,
            "intervals_per_day": self.intervals_per_day,
            "output_order": list(self.output_order),
            "joint_residual_summary": dict(self.joint_residual_summary),
            "correlation_matrix": [
                list(row) for row in self.correlation_matrix
            ],
            "sampling_notes": self.sampling_notes,
        }


@dataclass(frozen=True, slots=True)
class FittedDualDemandWeatherResponse:
    """First-release dual-output demand-response fit."""

    required_weather_field_order: tuple[str, ...]
    non_thermal_electric_model: FittedDemandResponseModel
    cooling_demand_model: FittedDemandResponseModel
    shared_residual_model: FittedSharedResidualModel


def fit_dual_output_weather_response(
    dataset: AlignedTrainingHistory,
) -> FittedDualDemandWeatherResponse:
    """Fit the first-release dual-output weather-conditioned demand model."""

    required_weather_field_order = _required_weather_drivers(dataset)
    intervals_per_day = _intervals_per_day(dataset.timestep_hours)
    design_matrix = _build_design_matrix(
        dataset,
        intervals_per_day=intervals_per_day,
        required_weather_field_order=required_weather_field_order,
    )
    training_day_count = _training_day_count(dataset, intervals_per_day=intervals_per_day)

    non_thermal_electric_model, non_thermal_residuals = _fit_output_model(
        output_values=dataset.non_thermal_electric_demand_kw,
        design_matrix=design_matrix,
        intervals_per_day=intervals_per_day,
        required_weather_field_order=required_weather_field_order,
        training_day_count=training_day_count,
        unit_suffix="kw",
        explicit_training_requirement=None,
    )
    cooling_demand_model, cooling_residuals = _fit_output_model(
        output_values=dataset.cooling_demand_rt,
        design_matrix=design_matrix,
        intervals_per_day=intervals_per_day,
        required_weather_field_order=required_weather_field_order,
        training_day_count=training_day_count,
        unit_suffix="rt",
        explicit_training_requirement="historical_cooling_demand_rt_required",
    )
    shared_residual_model = _fit_shared_residual_model(
        intervals_per_day=intervals_per_day,
        training_day_count=training_day_count,
        non_thermal_residuals=non_thermal_residuals,
        cooling_residuals=cooling_residuals,
    )

    return FittedDualDemandWeatherResponse(
        required_weather_field_order=required_weather_field_order,
        non_thermal_electric_model=non_thermal_electric_model,
        cooling_demand_model=cooling_demand_model,
        shared_residual_model=shared_residual_model,
    )


__all__ = [
    "REQUIRED_DEMAND_WEATHER_DRIVERS",
    "FittedDemandResponseModel",
    "FittedSharedResidualModel",
    "FittedDualDemandWeatherResponse",
    "fit_dual_output_weather_response",
]


def _required_weather_drivers(dataset: AlignedTrainingHistory) -> tuple[str, ...]:
    missing = [
        field_name
        for field_name in REQUIRED_DEMAND_WEATHER_DRIVERS
        if field_name not in dataset.weather_field_series
    ]
    if missing:
        raise ValueError(
            "aligned training history is missing required weather drivers: "
            + ", ".join(missing)
        )
    return REQUIRED_DEMAND_WEATHER_DRIVERS


def _intervals_per_day(timestep_hours: float) -> int:
    intervals = 24.0 / timestep_hours
    rounded = round(intervals)
    if not isclose(intervals, rounded, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("timestep_hours must evenly divide one local civil day")
    return max(1, int(rounded))


def _training_day_count(dataset: AlignedTrainingHistory, *, intervals_per_day: int) -> int:
    if intervals_per_day <= 1:
        return dataset.record_count
    return max(1, len(dataset.timestamp_utc) // intervals_per_day)


def _build_design_matrix(
    dataset: AlignedTrainingHistory,
    *,
    intervals_per_day: int,
    required_weather_field_order: Sequence[str],
) -> list[list[float]]:
    design_matrix: list[list[float]] = []
    for row_index in range(dataset.record_count):
        local_timestamp = datetime.fromisoformat(
            dataset.local_civil_step_labels[row_index]
        )
        local_hour = local_timestamp.hour + (local_timestamp.minute / 60.0)
        step_index = int(round(local_hour / dataset.timestep_hours)) % intervals_per_day
        row = [0.0] * (intervals_per_day + len(required_weather_field_order))
        row[step_index] = 1.0
        for offset, field_name in enumerate(required_weather_field_order):
            row[intervals_per_day + offset] = float(
                dataset.weather_field_series[field_name][row_index]
            )
        design_matrix.append(row)
    return design_matrix


def _fit_output_model(
    *,
    output_values: Sequence[float],
    design_matrix: Sequence[Sequence[float]],
    intervals_per_day: int,
    required_weather_field_order: Sequence[str],
    training_day_count: int,
    unit_suffix: str,
    explicit_training_requirement: str | None,
) -> tuple[FittedDemandResponseModel, tuple[float, ...]]:
    coefficients = _solve_ridge_regression(
        design_matrix=design_matrix,
        response=output_values,
        regularization=1e-6,
    )
    predictions = [
        sum(value * coefficient for value, coefficient in zip(row, coefficients))
        for row in design_matrix
    ]
    residuals = tuple(
        float(actual) - prediction for actual, prediction in zip(output_values, predictions)
    )
    absolute_residuals = tuple(abs(value) for value in residuals)

    residual_scale_summary = {
        f"mae_{unit_suffix}": sum(absolute_residuals) / len(absolute_residuals),
        f"max_abs_error_{unit_suffix}": max(absolute_residuals),
    }
    model = FittedDemandResponseModel(
        model_kind="local-civil-baseline",
        local_step_baseline=tuple(coefficients[:intervals_per_day]),
        weather_response_terms={
            field_name: coefficients[intervals_per_day + offset]
            for offset, field_name in enumerate(required_weather_field_order)
        },
        training_day_count=training_day_count,
        residual_scale_summary=residual_scale_summary,
        supported_weather_drivers=tuple(required_weather_field_order),
        explicit_training_requirement=explicit_training_requirement,
    )
    return model, residuals


def _fit_shared_residual_model(
    *,
    intervals_per_day: int,
    training_day_count: int,
    non_thermal_residuals: Sequence[float],
    cooling_residuals: Sequence[float],
) -> FittedSharedResidualModel:
    return FittedSharedResidualModel(
        model_kind="gaussian-copula",
        intervals_per_day=intervals_per_day,
        output_order=_OUTPUT_ORDER,
        joint_residual_summary={
            "training_day_count": training_day_count,
            "output_count": len(_OUTPUT_ORDER),
        },
        correlation_matrix=(
            (1.0, _correlation(non_thermal_residuals, cooling_residuals)),
            (_correlation(cooling_residuals, non_thermal_residuals), 1.0),
        ),
        sampling_notes="paired_residual_correlation",
    )


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("residual sequences must align")
    if len(left) < 2:
        return 0.0

    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum(
        (left_value - left_mean) * (right_value - right_mean)
        for left_value, right_value in zip(left, right)
    )
    left_scale = sum((value - left_mean) ** 2 for value in left)
    right_scale = sum((value - right_mean) ** 2 for value in right)
    if left_scale <= 0.0 or right_scale <= 0.0:
        return 0.0
    return max(-1.0, min(1.0, numerator / (left_scale * right_scale) ** 0.5))


def _solve_ridge_regression(
    *,
    design_matrix: Sequence[Sequence[float]],
    response: Sequence[float],
    regularization: float,
) -> list[float]:
    if not design_matrix:
        raise ValueError("design_matrix must not be empty")
    if len(design_matrix) != len(response):
        raise ValueError("design_matrix row count must match response length")

    feature_count = len(design_matrix[0])
    normal_matrix = [[0.0 for _ in range(feature_count)] for _ in range(feature_count)]
    rhs = [0.0 for _ in range(feature_count)]

    for row, output in zip(design_matrix, response):
        if len(row) != feature_count:
            raise ValueError("design_matrix rows must have a consistent feature count")
        output_value = float(output)
        for row_index, row_value in enumerate(row):
            rhs[row_index] += row_value * output_value
            for column_index, column_value in enumerate(row):
                normal_matrix[row_index][column_index] += row_value * column_value

    for diagonal_index in range(feature_count):
        normal_matrix[diagonal_index][diagonal_index] += regularization

    return _solve_linear_system(normal_matrix, rhs)


def _solve_linear_system(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    size = len(matrix)
    augmented = [row[:] + [rhs_value] for row, rhs_value in zip(matrix, rhs)]

    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row_index: abs(augmented[row_index][pivot_index]),
        )
        pivot_value = augmented[pivot_row][pivot_index]
        if abs(pivot_value) <= 1e-12:
            raise ValueError("unable to solve regularized demand fit linear system")
        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[pivot_index],
            )

        pivot_value = augmented[pivot_index][pivot_index]
        for column_index in range(pivot_index, size + 1):
            augmented[pivot_index][column_index] /= pivot_value

        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            if factor == 0.0:
                continue
            for column_index in range(pivot_index, size + 1):
                augmented[row_index][column_index] -= (
                    factor * augmented[pivot_index][column_index]
                )

    return [augmented[row_index][size] for row_index in range(size)]
