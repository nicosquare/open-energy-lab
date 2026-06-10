"""Stable package-root exports for visualization inspection and reporting.

Ordinary ``open_energy_lab.visualization`` imports stay import-light by
resolving the shipped stable inspection/reporting helpers lazily. Experimental
plotting remains outside the package-root exports.
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

__all__ = [
    "build_inspection_view",
    "load_persisted_run_output",
    "summarize_inspection_view",
]


def __getattr__(name: str) -> Any:
    """Lazily resolve the stable visualization helpers."""

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
