"""Stable package-root exports for visualization inspection and reporting.

Ordinary ``open_energy_lab.visualization`` imports stay import-light by
resolving the shipped stable inspection/reporting helpers lazily. Same-family
comparison remains available from ``open_energy_lab.visualization.comparison``,
and experimental plotting remains available only from
``open_energy_lab.visualization.plotting``.
"""

from __future__ import annotations

from ._persistence import (
    load_persisted_run_output,
)
from .inspection import (
    build_inspection_view,
    summarize_inspection_view,
)

__all__ = [
    "build_inspection_view",
    "load_persisted_run_output",
    "summarize_inspection_view",
]
