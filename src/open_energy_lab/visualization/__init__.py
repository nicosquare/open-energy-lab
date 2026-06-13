"""Stable package-root exports for visualization inspection and reporting.

Ordinary ``open_energy_lab.visualization`` imports stay import-light by
resolving the shipped stable inspection/reporting helpers lazily. Same-family
comparison remains available from ``open_energy_lab.visualization.comparison``,
and experimental plotting remains available only from
``open_energy_lab.visualization.plotting``.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .inspection import build_inspection_view, summarize_inspection_view
    from ._persistence import load_persisted_run_output


_EXPORT_MAP = {
    "build_inspection_view": (".inspection", "build_inspection_view"),
    "load_persisted_run_output": ("._persistence", "load_persisted_run_output"),
    "summarize_inspection_view": (".inspection", "summarize_inspection_view"),
}
_NON_ROOT_EXPORT_GUIDANCE = {
    "compare_inspection_views": (
        "compare_inspection_views is not exported from "
        "open_energy_lab.visualization; import it from "
        "open_energy_lab.visualization.comparison"
    ),
    "plot_inspection_view": (
        "plot_inspection_view is experimental and is not exported from "
        "open_energy_lab.visualization; import it from "
        "open_energy_lab.visualization.plotting"
    ),
}

__all__ = [
    "build_inspection_view",
    "load_persisted_run_output",
    "summarize_inspection_view",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the stable visualization helpers."""

    guidance = _NON_ROOT_EXPORT_GUIDANCE.get(name)
    if guidance is not None:
        raise AttributeError(guidance)

    try:
        module_name, attribute_name = _EXPORT_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name, __name__)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
