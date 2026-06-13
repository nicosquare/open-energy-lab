"""Experimental plotting helpers for stable visualization inspection views."""

from __future__ import annotations

from collections.abc import Sequence

from .inspection import build_inspection_view


_SOURCE_LOCATION_BY_KIND = {
    "simulation_trace": "in_memory",
    "controller_evaluation": "in_memory",
    "persisted_output": "persisted_output",
}


def _normalize_series_names(value: Sequence[str]) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("series_names must be a sequence of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            raise ValueError("series_names entries must be non-empty strings")
        normalized.append(item)

    if not normalized:
        raise ValueError("series_names must not be empty")
    return normalized


def _source_location_for_view(source_kind: str) -> str:
    try:
        return _SOURCE_LOCATION_BY_KIND[source_kind]
    except KeyError as exc:
        raise ValueError(
            f"unsupported inspection source_kind for plotting: {source_kind!r}"
        ) from exc


def plot_inspection_view(
    value: object,
    *,
    series_names: Sequence[str],
    backend: object,
    scenario: object | None = None,
) -> object:
    """Render a deterministic static single-run plot through an injected backend."""

    render_static_plot = getattr(backend, "render_static_plot", None)
    if not callable(render_static_plot):
        raise TypeError("backend must define render_static_plot(plot_spec)")

    normalized_series_names = _normalize_series_names(series_names)
    inspection_view = build_inspection_view(value, scenario=scenario)
    series_by_name = {
        series["series_name"]: dict(series) for series in inspection_view["trace_series"]
    }

    missing_series = [
        series_name
        for series_name in normalized_series_names
        if series_name not in series_by_name
    ]
    if missing_series:
        raise ValueError(f"unsupported series_names requested for plotting: {missing_series}")

    plot_spec = {
        "target_run": {
            "scenario_id": inspection_view["scenario_id"],
            "scenario_kind": inspection_view["scenario_kind"],
            "source_kind": inspection_view["source_kind"],
        },
        "scenario_id": inspection_view["scenario_id"],
        "scenario_kind": inspection_view["scenario_kind"],
        "source_kind": inspection_view["source_kind"],
        "plot_kind": "static_single_run",
        "output_mode": "backend_result",
        "source_location": _source_location_for_view(inspection_view["source_kind"]),
        "requires_optional_backend": True,
        "maturity": "experimental",
        "series": [series_by_name[series_name] for series_name in normalized_series_names],
        "available_sections": dict(inspection_view["available_sections"]),
    }
    return render_static_plot(plot_spec)


__all__ = ["plot_inspection_view"]
