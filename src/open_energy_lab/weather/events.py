"""Cloud-event calibration, overlays, and physical-bounds enforcement."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import ceil
from random import Random

from open_energy_lab.weather.schema import IRRADIANCE_FIELD_NAMES


DEFAULT_MINIMUM_BASE_IRRADIANCE_W_PER_M2 = 50.0
DEFAULT_MINIMUM_ATTENUATION_FRACTION = 0.15


@dataclass(frozen=True, slots=True)
class CloudEventAnnotation:
    """One contiguous irradiance attenuation event."""

    start_index: int
    duration_steps: int
    attenuation_fraction: float


@dataclass(frozen=True, slots=True)
class CloudEventOverlayResult:
    """Sampled irradiance overlay output for one trace or one daily block."""

    canonical_field_series: dict[str, tuple[float, ...]]
    cloud_event_annotations: tuple[CloudEventAnnotation, ...]


def calibrate_cloud_event_model(
    *,
    canonical_field_series: Mapping[str, Sequence[object]],
    intervals_per_day: int,
    irradiance_fields: Sequence[str] = IRRADIANCE_FIELD_NAMES,
    minimum_base_irradiance_w_per_m2: float = DEFAULT_MINIMUM_BASE_IRRADIANCE_W_PER_M2,
    minimum_attenuation_fraction: float = DEFAULT_MINIMUM_ATTENUATION_FRACTION,
) -> dict[str, object]:
    """Calibrate a contiguous irradiance-event model from canonical GHI history."""

    if intervals_per_day <= 0:
        raise ValueError("intervals_per_day must be positive")

    ghi_values = tuple(
        float(value)
        for value in canonical_field_series["global_horizontal_irradiance_w_per_m2"]
    )
    if not ghi_values:
        raise ValueError("global_horizontal_irradiance_w_per_m2 must not be empty")

    day_blocks = [
        ghi_values[start_index : start_index + intervals_per_day]
        for start_index in range(0, len(ghi_values), intervals_per_day)
    ]
    baseline_by_local_step = _baseline_by_local_step(day_blocks, intervals_per_day=intervals_per_day)

    start_counts = [0] * intervals_per_day
    duration_counts: Counter[int] = Counter()
    attenuation_counts: Counter[float] = Counter()
    detected_event_count = 0

    for day_block in day_blocks:
        local_step = 0
        while local_step < len(day_block):
            baseline = baseline_by_local_step[local_step]
            actual = day_block[local_step]
            attenuation = _attenuation_fraction(
                baseline=baseline,
                actual=actual,
                minimum_base_irradiance_w_per_m2=minimum_base_irradiance_w_per_m2,
            )
            if attenuation < minimum_attenuation_fraction:
                local_step += 1
                continue

            event_start = local_step
            event_attenuations: list[float] = []
            while local_step < len(day_block):
                baseline = baseline_by_local_step[local_step]
                actual = day_block[local_step]
                attenuation = _attenuation_fraction(
                    baseline=baseline,
                    actual=actual,
                    minimum_base_irradiance_w_per_m2=minimum_base_irradiance_w_per_m2,
                )
                if attenuation < minimum_attenuation_fraction:
                    break
                event_attenuations.append(min(0.95, attenuation))
                local_step += 1

            if not event_attenuations:
                local_step += 1
                continue

            detected_event_count += 1
            start_counts[event_start] += 1
            duration_counts[len(event_attenuations)] += 1
            mean_attenuation = round(
                sum(event_attenuations) / len(event_attenuations),
                3,
            )
            attenuation_counts[mean_attenuation] += 1

    duration_distribution = _distribution_from_counter(
        duration_counts,
        default_values=(1,),
    )
    attenuation_distribution = _distribution_from_counter(
        attenuation_counts,
        default_values=(0.25,),
    )

    return {
        "irradiance_fields": [str(field_name) for field_name in irradiance_fields],
        "start_probability_by_local_step": [
            count / len(day_blocks) for count in start_counts
        ],
        "duration_distribution": {
            "kind": "empirical",
            "durations": list(duration_distribution["values"]),
            "probabilities": list(duration_distribution["probabilities"]),
        },
        "attenuation_distribution": {
            "kind": "empirical",
            "attenuation_values": list(attenuation_distribution["values"]),
            "probabilities": list(attenuation_distribution["probabilities"]),
        },
        "minimum_base_irradiance_w_per_m2": minimum_base_irradiance_w_per_m2,
        "calibration_summary": {
            "event_count": detected_event_count,
            "training_record_count": len(ghi_values),
            "inferred_day_count": ceil(len(ghi_values) / intervals_per_day),
        },
    }


def apply_cloud_event_overlay(
    *,
    canonical_field_series: Mapping[str, Sequence[object]],
    cloud_event_model: Mapping[str, object],
    family_seed: int,
    scenario_index: int,
    physical_bounds_policy: Mapping[str, object],
    day_index: int = 0,
) -> CloudEventOverlayResult:
    """Overlay contiguous irradiance attenuation events on one sampled block."""

    if not canonical_field_series:
        raise ValueError("canonical_field_series must not be empty")

    normalized_series = {
        field_name: [float(value) for value in values]
        for field_name, values in canonical_field_series.items()
    }
    series_length = len(next(iter(normalized_series.values())))
    if series_length == 0:
        raise ValueError("canonical_field_series values must not be empty")
    for field_name, values in normalized_series.items():
        if len(values) != series_length:
            raise ValueError(f"canonical_field_series[{field_name!r}] must align in length")

    start_probability_by_local_step = _float_sequence(
        cloud_event_model["start_probability_by_local_step"],
        field_name="start_probability_by_local_step",
    )
    if len(start_probability_by_local_step) != series_length:
        raise ValueError(
            "cloud_event_model start_probability_by_local_step length must match the sampled block"
        )

    irradiance_fields = tuple(str(field_name) for field_name in cloud_event_model["irradiance_fields"])
    minimum_base_irradiance_w_per_m2 = float(
        cloud_event_model["minimum_base_irradiance_w_per_m2"]
    )
    duration_values, duration_probabilities = _distribution_values(
        cloud_event_model["duration_distribution"],
        values_key="durations",
    )
    attenuation_values, attenuation_probabilities = _distribution_values(
        cloud_event_model["attenuation_distribution"],
        values_key="attenuation_values",
    )

    rng = _seeded_random(
        "cloud-overlay",
        family_seed=family_seed,
        scenario_index=scenario_index,
        day_index=day_index,
    )
    annotations: list[CloudEventAnnotation] = []
    local_step = 0
    while local_step < series_length:
        base_ghi = normalized_series["global_horizontal_irradiance_w_per_m2"][local_step]
        start_probability = min(1.0, max(0.0, start_probability_by_local_step[local_step]))
        if (
            base_ghi > minimum_base_irradiance_w_per_m2
            and rng.random() < start_probability
        ):
            duration = int(_weighted_choice(duration_values, duration_probabilities, rng))
            attenuation = float(
                _weighted_choice(attenuation_values, attenuation_probabilities, rng)
            )
            duration = max(1, duration)
            attenuation = min(0.95, max(0.0, attenuation))
            end_index = min(series_length, local_step + duration)
            for field_name in irradiance_fields:
                values = normalized_series[field_name]
                for event_step in range(local_step, end_index):
                    values[event_step] *= 1.0 - attenuation
            annotations.append(
                CloudEventAnnotation(
                    start_index=local_step,
                    duration_steps=end_index - local_step,
                    attenuation_fraction=attenuation,
                )
            )
            local_step = end_index
            continue

        local_step += 1

    bounded_series = enforce_physical_bounds(
        canonical_field_series=normalized_series,
        physical_bounds_policy=physical_bounds_policy,
    )
    return CloudEventOverlayResult(
        canonical_field_series=bounded_series,
        cloud_event_annotations=tuple(annotations),
    )


def enforce_physical_bounds(
    *,
    canonical_field_series: Mapping[str, Sequence[object]],
    physical_bounds_policy: Mapping[str, object],
) -> dict[str, tuple[float, ...]]:
    """Clip sampled weather values to documented physical bounds."""

    bounds_by_field = physical_bounds_policy.get("bounds_by_field", {})
    if not isinstance(bounds_by_field, Mapping):
        raise TypeError("physical_bounds_policy['bounds_by_field'] must be a mapping")

    clipped_series: dict[str, tuple[float, ...]] = {}
    for field_name, values in canonical_field_series.items():
        numeric_values = [float(value) for value in values]
        bounds = bounds_by_field.get(field_name, {})
        if bounds and not isinstance(bounds, Mapping):
            raise TypeError(f"bounds for {field_name!r} must be a mapping")

        minimum = bounds.get("minimum")
        maximum = bounds.get("maximum")
        bounded_values = []
        for value in numeric_values:
            bounded_value = value
            if minimum is not None:
                bounded_value = max(float(minimum), bounded_value)
            if maximum is not None:
                bounded_value = min(float(maximum), bounded_value)
            bounded_values.append(bounded_value)
        clipped_series[field_name] = tuple(bounded_values)

    return clipped_series


def _baseline_by_local_step(
    day_blocks: Sequence[Sequence[float]],
    *,
    intervals_per_day: int,
) -> list[float]:
    baseline: list[float] = []
    for local_step in range(intervals_per_day):
        samples = [
            day_block[local_step]
            for day_block in day_blocks
            if local_step < len(day_block)
        ]
        if not samples:
            baseline.append(0.0)
            continue
        baseline.append(sum(samples) / len(samples))
    return baseline


def _attenuation_fraction(
    *,
    baseline: float,
    actual: float,
    minimum_base_irradiance_w_per_m2: float,
) -> float:
    if baseline <= minimum_base_irradiance_w_per_m2:
        return 0.0
    return max(0.0, 1.0 - (actual / baseline))


def _distribution_from_counter(
    counts: Counter[int] | Counter[float],
    *,
    default_values: Sequence[int] | Sequence[float],
) -> dict[str, tuple[object, ...]]:
    if not counts:
        return {
            "values": tuple(default_values),
            "probabilities": (1.0,),
        }

    ordered_values = tuple(sorted(counts))
    total = sum(counts.values())
    return {
        "values": ordered_values,
        "probabilities": tuple(counts[value] / total for value in ordered_values),
    }


def _distribution_values(
    distribution: object,
    *,
    values_key: str,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if not isinstance(distribution, Mapping):
        raise TypeError("distribution entries must be mappings")

    values = _float_sequence(distribution[values_key], field_name=values_key)
    probabilities = _float_sequence(
        distribution["probabilities"],
        field_name="probabilities",
    )
    if len(values) != len(probabilities):
        raise ValueError(f"{values_key} and probabilities must have equal lengths")
    if not values:
        raise ValueError(f"{values_key} must not be empty")

    total_probability = sum(probabilities)
    if total_probability <= 0.0:
        raise ValueError("distribution probabilities must sum to a positive value")
    normalized_probabilities = tuple(probability / total_probability for probability in probabilities)
    return values, normalized_probabilities


def _float_sequence(value: object, *, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a sequence")
    return tuple(float(item) for item in value)


def _weighted_choice(
    values: Sequence[float],
    probabilities: Sequence[float],
    rng: Random,
) -> float:
    cutoff = rng.random()
    cumulative = 0.0
    for value, probability in zip(values, probabilities, strict=True):
        cumulative += probability
        if cutoff <= cumulative:
            return value
    return values[-1]


def _seeded_random(
    namespace: str,
    *,
    family_seed: int,
    scenario_index: int,
    day_index: int,
) -> Random:
    seed_bytes = sha256(
        f"{namespace}:{family_seed}:{scenario_index}:{day_index}".encode("utf-8")
    ).digest()
    return Random(int.from_bytes(seed_bytes[:8], byteorder="big", signed=False))


__all__ = [
    "CloudEventAnnotation",
    "CloudEventOverlayResult",
    "apply_cloud_event_overlay",
    "calibrate_cloud_event_model",
    "enforce_physical_bounds",
]
