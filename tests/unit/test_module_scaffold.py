import importlib
from pathlib import Path


SCAFFOLD_MODULES = [
    "experimental",
    "simulator",
    "core",
    "planning",
    "control",
    "visualization",
]


def test_roadmap_modules_are_importable_source_packages():
    for module_name in SCAFFOLD_MODULES:
        module = importlib.import_module(f"open_energy_lab.{module_name}")
        module_file = Path(module.__file__).resolve()

        assert module.__name__ == f"open_energy_lab.{module_name}"
        assert module_file.name == "__init__.py"
        assert module_file.parent.name == module_name
        assert module_file.parent.parent.name == "open_energy_lab"
        assert module_file.parent.parent.parent.name == "src"
