"""Fail fast if the required solver backends are missing or at the wrong version.

Usage: uv run python tools/verify_backends.py [--notebook]
"""

from __future__ import annotations

from importlib.metadata import version
import sys

REQUIRED = {"spflow": "1.1.0", "pyomo": "6.10.1", "highspy": "1.15.1"}
NOTEBOOK = ("nbclient", "nbformat", "ipykernel")


def main() -> None:
    import highspy
    import pyomo.environ as pyo
    import spflow  # noqa: F401 - import proves the backend loads

    actual = {package: version(package) for package in REQUIRED}
    if actual != REQUIRED:
        raise RuntimeError(f"required backend versions differ: {actual!r}")
    if not pyo.SolverFactory("highs").available(exception_flag=False):
        raise RuntimeError("required Pyomo HiGHS solver is unavailable")
    print(f"required backend versions: {actual}")
    print(f"HiGHS runtime version: {highspy.Highs().version()}")

    if "--notebook" in sys.argv[1:]:
        for package in NOTEBOOK:
            __import__(package)
        print(f"notebook dependency versions: { {p: version(p) for p in NOTEBOOK} }")


if __name__ == "__main__":
    main()
