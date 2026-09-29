"""The library never depends on oel_validation, and the wheel does not ship it."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap
import tomllib

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "src" / "open_energy_lab"


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_library_sources_never_import_oel_validation() -> None:
    offenders = sorted(
        str(path.relative_to(ROOT))
        for path in LIBRARY.rglob("*.py")
        if "oel_validation" in _imported_roots(path)
    )
    assert offenders == []


def test_importing_every_library_package_does_not_load_oel_validation() -> None:
    source = textwrap.dedent(
        """
        import importlib
        import pkgutil
        import sys

        import open_energy_lab

        for info in pkgutil.walk_packages(open_energy_lab.__path__, "open_energy_lab."):
            if info.name.startswith("open_energy_lab.tpm"):
                continue  # heavy optional backends; covered by tpm boundary tests
            importlib.import_module(info.name)

        loaded = sorted(name for name in sys.modules if name.split(".")[0] == "oel_validation")
        assert loaded == [], loaded
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_wheel_ships_only_the_library_package() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/open_energy_lab"
    ]
