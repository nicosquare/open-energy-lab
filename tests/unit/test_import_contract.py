import importlib
import sys
from pathlib import Path


OPTIONAL_RESEARCH_MODULES = {
    "citylearn",
    "docplex",
    "gurobipy",
    "jupyter",
    "pyomo",
    "spflow",
    "torch",
    "torchrl",
    "wandb",
}


def test_root_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)

    package = importlib.import_module("open_energy_lab")

    assert package.__file__ is not None, "open_energy_lab must be a regular package"
    package_file = Path(package.__file__).resolve()
    assert package.__name__ == "open_energy_lab"
    assert package_file.name == "__init__.py"
    assert package_file.parent.name == "open_energy_lab"
    assert package_file.parent.parent.name == "src"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()


def test_core_package_imports_from_source_tree_without_optional_stacks():
    before_import = set(sys.modules)

    module = importlib.import_module("open_energy_lab.core")

    assert module.__file__ is not None
    module_file = Path(module.__file__).resolve()
    assert module.__name__ == "open_energy_lab.core"
    assert module_file.name == "__init__.py"
    assert module_file.parent.name == "core"
    assert module_file.parent.parent.name == "open_energy_lab"
    assert module.__all__ == [
        "ControllerContext",
        "ControllerEvaluationResult",
        "ControllerInterface",
        "DispatchProposal",
    ]
    assert module.ControllerContext.__module__ == "open_energy_lab.core.controller"
    assert module.ControllerEvaluationResult.__module__ == "open_energy_lab.core.controller"
    assert module.ControllerInterface.__module__ == "open_energy_lab.core.controller"
    assert module.DispatchProposal.__module__ == "open_energy_lab.core.controller"

    newly_loaded_optional_modules = OPTIONAL_RESEARCH_MODULES & (
        set(sys.modules) - before_import
    )
    assert newly_loaded_optional_modules == set()
