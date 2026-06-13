"""Deterministic same-family comparison helpers for inspection views."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .inspection import build_inspection_view


def _run_descriptor(view: Mapping[str, object]) -> dict[str, object]:
    return {
        "scenario_id": view["scenario_id"],
        "source_kind": view["source_kind"],
    }


def _unsupported_comparison(
    *,
    left_view: Mapping[str, object],
    right_view: Mapping[str, object],
    reason: str,
    scenario_kind: str | None,
) -> dict[str, object]:
    return {
        "scenario_kind": scenario_kind,
        "left_run": _run_descriptor(left_view),
        "right_run": _run_descriptor(right_view),
        "aligned_series": [],
        "series_differences": [],
        "summary_differences": [],
        "unsupported_reason": reason,
    }


def _series_by_name(view: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    return {
        str(series["series_name"]): series
        for series in view["trace_series"]
    }


def _summary_by_name(view: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    return {
        str(summary["summary_name"]): summary
        for summary in view["summary_outcomes"]
    }


def _is_numeric_sequence(values: Sequence[object]) -> bool:
    return all(
        isinstance(value, int | float) and not isinstance(value, bool)
        for value in values
    )


def _build_series_difference(
    *,
    series_name: str,
    left_values: Sequence[object],
    right_values: Sequence[object],
    units: str,
) -> dict[str, object]:
    if _is_numeric_sequence(left_values) and _is_numeric_sequence(right_values):
        return {
            "series_name": series_name,
            "units": units,
            "delta_values": [
                float(right_value) - float(left_value)
                for left_value, right_value in zip(
                    left_values, right_values, strict=True
                )
            ],
        }

    return {
        "series_name": series_name,
        "units": units,
        "difference_kind": "categorical",
        "changed_steps": [
            left_value != right_value
            for left_value, right_value in zip(left_values, right_values, strict=True)
        ],
    }


def _build_summary_difference(
    *,
    summary_name: str,
    left_summary: Mapping[str, object],
    right_summary: Mapping[str, object],
) -> dict[str, object]:
    left_value = float(left_summary["value"])
    right_value = float(right_summary["value"])
    return {
        "summary_name": summary_name,
        "units": left_summary["units"],
        "left_value": left_value,
        "right_value": right_value,
        "delta_value": right_value - left_value,
    }


def compare_inspection_views(
    left_value: object,
    right_value: object,
    *,
    left_scenario: object | None = None,
    right_scenario: object | None = None,
) -> dict[str, object]:
    """Compare two supported deterministic inputs through the inspection surface."""

    left_view = build_inspection_view(left_value, scenario=left_scenario)
    right_view = build_inspection_view(right_value, scenario=right_scenario)

    left_scenario_kind = str(left_view["scenario_kind"])
    right_scenario_kind = str(right_view["scenario_kind"])
    if left_scenario_kind != right_scenario_kind:
        return _unsupported_comparison(
            left_view=left_view,
            right_view=right_view,
            reason=(
                "cross-family comparison is unsupported in the visualization MVP: "
                f"{left_scenario_kind} vs {right_scenario_kind}"
            ),
            scenario_kind=None,
        )

    left_series = _series_by_name(left_view)
    right_series = _series_by_name(right_view)
    left_series_order = [
        str(series["series_name"]) for series in left_view["trace_series"]
    ]
    right_series_names = set(right_series)

    if set(left_series) != right_series_names:
        missing_from_right = sorted(set(left_series) - right_series_names)
        missing_from_left = sorted(right_series_names - set(left_series))
        reasons: list[str] = []
        if missing_from_right:
            reasons.append(f"missing from right run: {', '.join(missing_from_right)}")
        if missing_from_left:
            reasons.append(f"missing from left run: {', '.join(missing_from_left)}")
        return _unsupported_comparison(
            left_view=left_view,
            right_view=right_view,
            reason=(
                "comparison requires the same canonical trace series; "
                + "; ".join(reasons)
            ),
            scenario_kind=left_scenario_kind,
        )

    aligned_series: list[dict[str, object]] = []
    series_differences: list[dict[str, object]] = []

    for series_name in left_series_order:
        left_series_entry = left_series[series_name]
        right_series_entry = right_series[series_name]
        left_values = list(left_series_entry["values"])
        right_values = list(right_series_entry["values"])
        left_step_labels = list(left_series_entry["step_labels"])
        right_step_labels = list(right_series_entry["step_labels"])

        if len(left_values) != len(right_values):
            return _unsupported_comparison(
                left_view=left_view,
                right_view=right_view,
                reason=(
                    f"comparison requires matching length for series {series_name}: "
                    f"{len(left_values)} vs {len(right_values)}"
                ),
                scenario_kind=left_scenario_kind,
            )

        if (
            len(left_values) != len(left_step_labels)
            or len(right_values) != len(right_step_labels)
        ):
            return _unsupported_comparison(
                left_view=left_view,
                right_view=right_view,
                reason=(
                    "comparison requires aligned step labels for series "
                    f"{series_name}"
                ),
                scenario_kind=left_scenario_kind,
            )

        if left_step_labels != right_step_labels:
            return _unsupported_comparison(
                left_view=left_view,
                right_view=right_view,
                reason=(
                    "comparison requires identical timestep labels for series "
                    f"{series_name}"
                ),
                scenario_kind=left_scenario_kind,
            )

        left_units = str(left_series_entry["units"])
        right_units = str(right_series_entry["units"])
        if left_units != right_units:
            return _unsupported_comparison(
                left_view=left_view,
                right_view=right_view,
                reason=f"comparison requires matching units for series {series_name}",
                scenario_kind=left_scenario_kind,
            )

        aligned_series.append(
            {
                "series_name": series_name,
                "units": left_units,
                "step_labels": left_step_labels,
                "left_values": left_values,
                "right_values": right_values,
                "display_category": left_series_entry["display_category"],
                "optional": bool(left_series_entry.get("optional", False)),
            }
        )
        series_differences.append(
            _build_series_difference(
                series_name=series_name,
                left_values=left_values,
                right_values=right_values,
                units=left_units,
            )
        )

    left_summaries = _summary_by_name(left_view)
    right_summaries = _summary_by_name(right_view)
    left_summary_order = [
        str(summary["summary_name"]) for summary in left_view["summary_outcomes"]
    ]
    right_summary_names = set(right_summaries)

    if set(left_summaries) != right_summary_names:
        missing_from_right = sorted(set(left_summaries) - right_summary_names)
        missing_from_left = sorted(right_summary_names - set(left_summaries))
        reasons: list[str] = []
        if missing_from_right:
            reasons.append(f"missing from right run: {', '.join(missing_from_right)}")
        if missing_from_left:
            reasons.append(f"missing from left run: {', '.join(missing_from_left)}")
        return _unsupported_comparison(
            left_view=left_view,
            right_view=right_view,
            reason=(
                "comparison requires the same summary outcomes; "
                + "; ".join(reasons)
            ),
            scenario_kind=left_scenario_kind,
        )

    summary_differences: list[dict[str, object]] = []
    for summary_name in left_summary_order:
        left_summary = left_summaries[summary_name]
        right_summary = right_summaries[summary_name]
        if str(left_summary["units"]) != str(right_summary["units"]):
            return _unsupported_comparison(
                left_view=left_view,
                right_view=right_view,
                reason=f"comparison requires matching units for summary {summary_name}",
                scenario_kind=left_scenario_kind,
            )
        summary_differences.append(
            _build_summary_difference(
                summary_name=summary_name,
                left_summary=left_summary,
                right_summary=right_summary,
            )
        )

    return {
        "scenario_kind": left_scenario_kind,
        "left_run": _run_descriptor(left_view),
        "right_run": _run_descriptor(right_view),
        "aligned_series": aligned_series,
        "series_differences": series_differences,
        "summary_differences": summary_differences,
        "unsupported_reason": None,
    }


__all__ = ["compare_inspection_views"]
