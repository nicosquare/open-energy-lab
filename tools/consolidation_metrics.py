"""Print the consolidation metrics tracked in docs/dev/consolidation.md.

Usage: uv run python tools/consolidation_metrics.py
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "open_energy_lab"
TPM = ROOT / "packages" / "sp-tpm" / "src" / "tpm"
TESTS = ROOT / "tests"
# package label -> (source directory, import name)
PACKAGES = {
    "control": (SRC / "control", "open_energy_lab.control"),
    "tpm (sp-tpm)": (TPM, "tpm"),
    "simulator": (SRC / "simulator", "open_energy_lab.simulator"),
    "market": (SRC / "market", "open_energy_lab.market"),
    "planning": (SRC / "planning", "open_energy_lab.planning"),
    "weather": (SRC / "weather", "open_energy_lab.weather"),
    "demand": (SRC / "demand", "open_energy_lab.demand"),
    "visualization": (SRC / "visualization", "open_energy_lab.visualization"),
    "core": (SRC / "core", "open_energy_lab.core"),
}
SMELLS = {
    "`def _finite(` copies": r"def _finite\(",
    "`def _non_empty*` copies": r"def _non_empty",
    "`_sha256` / `_fingerprint` / `_sha` copies": r"def _sha256|def _fingerprint|def _sha\(",
    "canonical-JSON serializers": r"def _canonical_json|def canonical_[a-z_]*json_bytes",
    "`_freeze` / `_deep_freeze` / `_thaw` copies": r"def _freeze|def _deep_freeze|def _thaw",
    "`fingerprint` mentions": r"fingerprint",
    "`object.__setattr__`": r"object\.__setattr__",
    "`Feature 0NN` / `feature-0NN` strings": r"Feature 0[0-9]{2}|feature-0[0-9]{2}|feature_0[0-9]{2}",
    "`legacy` mentions": r"(?i)legacy",
    "`parity` mentions": r"(?i)parity",
    "exception classes": r"^class \w+\((\w*Error|ValueError|RuntimeError|Exception|TypeError)\)",
}


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _sources(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _count(pattern: str, files: list[Path]) -> int:
    regex = re.compile(pattern, re.MULTILINE)
    return sum(1 for f in files for line in _lines(f) if regex.search(line))


def main() -> None:
    print("| Package | Lines | Files | `__all__` exports |")
    print("|---|---|---|---|")
    for name, (directory, module) in PACKAGES.items():
        files = _sources(directory)
        lines = sum(len(_lines(f)) for f in files)
        exports = len(getattr(importlib.import_module(module), "__all__", ()))
        print(f"| {name} | {lines:,} | {len(files)} | {exports} |")
    total = sum(len(_lines(f)) for f in _sources(SRC) + _sources(TPM))
    print(f"| **total src (incl. sp-tpm)** | **{total:,}** | | |")

    tests = [f for f in _sources(TESTS) if f.name.startswith("test_")]
    test_lines = sum(len(_lines(f)) for f in _sources(TESTS))
    print(f"\nTests: {len(tests)} `test_*.py` files, {test_lines:,} lines.\n")

    print("| Smell (grep over `src/open_energy_lab` and sp-tpm) | Count |")
    print("|---|---|")
    files = _sources(SRC) + _sources(TPM)
    for label, pattern in SMELLS.items():
        print(f"| {label} | {_count(pattern, files):,} |")


if __name__ == "__main__":
    main()
