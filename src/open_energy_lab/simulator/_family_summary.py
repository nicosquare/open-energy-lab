"""Per-step summary statistics and trace lookups shared by the stochastic family evaluators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def validated_summary_fields(
    summary_output_fields: Sequence[str],
    *,
    supported: tuple[str, ...],
) -> tuple[str, ...]:
    if not summary_output_fields:
        return supported
    normalized = tuple(dict.fromkeys(str(field_name) for field_name in summary_output_fields))
    unsupported = [
        field_name for field_name in normalized if field_name not in supported
    ]
    if unsupported:
        raise ValueError(
            "summary_output_fields must be limited to the supported simulator fields: "
            + ", ".join(unsupported)
        )
    return normalized


def summary_bucket(
    scenario_results: Sequence[object],
    field_name: str,
) -> dict[str, tuple[float, ...]]:
    series_by_scenario = [getattr(result, field_name) for result in scenario_results]
    if not series_by_scenario:
        raise ValueError("scenario_results must not be empty")

    per_step_values = [
        [float(values[step_index]) for values in series_by_scenario]
        for step_index in range(len(series_by_scenario[0]))
    ]
    return {
        "min": reduce_per_step(per_step_values, "min"),
        "mean": reduce_per_step(per_step_values, "mean"),
        "max": reduce_per_step(per_step_values, "max"),
        "p05": reduce_per_step(per_step_values, "5"),
        "p50": reduce_per_step(per_step_values, "50"),
        "p95": reduce_per_step(per_step_values, "95"),
    }


def reduce_per_step(
    per_step_values: Sequence[Sequence[float]],
    statistic: str,
) -> tuple[float, ...]:
    reduced: list[float] = []
    for step_values in per_step_values:
        ordered = sorted(float(value) for value in step_values)
        if statistic == "min":
            reduced.append(ordered[0])
        elif statistic == "mean":
            reduced.append(sum(ordered) / len(ordered))
        elif statistic == "max":
            reduced.append(ordered[-1])
        else:
            reduced.append(percentile(ordered, float(statistic)))
    return tuple(reduced)


def percentile(sorted_values: Sequence[float], percentile: float) -> float:
    if len(sorted_values) == 1:
        return float(sorted_values[0])

    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    lower_index = int(rank)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - lower_index
    lower_value = float(sorted_values[lower_index])
    upper_value = float(sorted_values[upper_index])
    return lower_value + ((upper_value - lower_value) * fraction)


def lookup(source: object, field_name: str) -> object:
    if isinstance(source, Mapping):
        if field_name not in source:
            raise ValueError(f"blackout trace is missing {field_name!r}")
        return source[field_name]
    if not hasattr(source, field_name):
        raise ValueError(f"blackout trace is missing {field_name!r}")
    return getattr(source, field_name)


def lookup_optional(source: object, field_name: str) -> object | None:
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def bool_series(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> tuple[bool, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a boolean sequence")
    if any(not isinstance(item, bool) for item in value):
        raise TypeError(f"{field_name} values must be booleans")
    series = tuple(value)
    if len(series) != expected_length:
        raise ValueError(f"{field_name} length must match the weather family horizon")
    return series


def string_series(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a string sequence")
    series = tuple(str(item) for item in value)
    if len(series) != expected_length:
        raise ValueError(f"{field_name} length must match the weather family horizon")
    return series
