"""Experimental plotting helpers for stable visualization inspection views."""

from __future__ import annotations

from collections.abc import Sequence

from .inspection import build_inspection_view


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


def plot_inspection_view(
    value: object,
    *,
    series_names: Sequence[str],
    backend: object,
    scenario: object | None = None,
) -> object:
    """Render a deterministic static single-run plot through an injected backend."""

    if not hasattr(backend, "render_static_plot"):
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
        "scenario_id": inspection_view["scenario_id"],
        "scenario_kind": inspection_view["scenario_kind"],
        "source_kind": inspection_view["source_kind"],
        "plot_kind": "static_single_run",
        "output_mode": "backend_result",
        "maturity": "experimental",
        "series": [series_by_name[series_name] for series_name in normalized_series_names],
        "available_sections": dict(inspection_view["available_sections"]),
    }
    return backend.render_static_plot(plot_spec)


__all__ = ["plot_inspection_view"]
