"""Open Energy Lab unified research library foundation.

The documented ``open_energy_lab`` package is the stable public namespace for
new reusable library code. Immature migrations belong under
``open_energy_lab.experimental`` or private modules until a later spec promotes
them with validation evidence and explicit review.

This foundation scaffold intentionally avoids importing optional research
stacks, external services, solver bindings, GPU/SLURM tooling, notebooks, Rust
tooling, or legacy modules at package import time.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
