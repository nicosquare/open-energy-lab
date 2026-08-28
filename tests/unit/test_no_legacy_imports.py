import ast
from pathlib import Path
import re


TARGET_PACKAGE = Path("src/open_energy_lab")
CONTROL_PACKAGE = TARGET_PACKAGE / "control"
FEATURE_010_MODULES = (
    TARGET_PACKAGE / "market" / "time.py",
    TARGET_PACKAGE / "market" / "artifact.py",
    TARGET_PACKAGE / "market" / "activation.py",
    TARGET_PACKAGE / "market" / "entsoe.py",
    TARGET_PACKAGE / "control" / "stacked_service.py",
    TARGET_PACKAGE / "simulator" / "stacked_service.py",
    TARGET_PACKAGE / "simulator" / "fcr_settlement.py",
)
FEATURE_011_OFFLINE_MODULES = (
    TARGET_PACKAGE / "market" / "restoration_artifact.py",
    TARGET_PACKAGE / "market" / "restoration_activation.py",
    TARGET_PACKAGE / "control" / "restoration_service.py",
    TARGET_PACKAGE / "simulator" / "restoration_service.py",
    TARGET_PACKAGE / "simulator" / "restoration_settlement.py",
)
FEATURE_012_OFFLINE_MODULES = (
    TARGET_PACKAGE / "control" / "fcr_bid_plan.py",
    TARGET_PACKAGE / "market" / "reference_fcr.py",
    TARGET_PACKAGE / "simulator" / "fcr_bid_evaluation.py",
    TARGET_PACKAGE / "simulator" / "fcr_settlement.py",
)
FEATURE_014_DOMAIN_MODULES = (
    TARGET_PACKAGE / "tpm" / "domains.py",
    TARGET_PACKAGE / "tpm" / "mio.py",
    TARGET_PACKAGE / "planning" / "piecewise.py",
    TARGET_PACKAGE / "planning" / "problem.py",
    TARGET_PACKAGE / "planning" / "workflow.py",
FEATURE_013_OFFLINE_MODULES = (
    TARGET_PACKAGE / "control" / "robust_fcr_bidding.py",
    TARGET_PACKAGE / "control" / "_robust_fcr_formulation.py",
    TARGET_PACKAGE / "control" / "_robust_fcr_solver.py",
)
FEATURE_012_FORBIDDEN_IMPORTS = {
    "IPython",
    "aiohttp",
    "baselines",
    "gurobipy",
    "httpx",
    "julia",
    "juliacall",
    "legacy",
    "nbclient",
    "nbformat",
    "notebook",
    "pyomo",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
FEATURE_013_FORBIDDEN_IMPORTS = FEATURE_012_FORBIDDEN_IMPORTS | {
    "highspy",
    "pandas",
}
FEATURE_011_FORBIDDEN_IMPORTS = {
    "IPython",
    "citylearn",
    "cupy",
    "docplex",
    "gurobipy",
    "highspy",
    "ipykernel",
    "jupyter",
    "legacy",
    "mlflow",
    "nbclient",
    "nbformat",
    "notebook",
    "open_energy_lab.market.entsoe",
    "open_energy_lab.market.rte",
    "pyomo",
    "slurm",
    "spflow",
    "submitit",
    "tensorboard",
    "torch",
    "torchrl",
    "wandb",
}
FEATURE_011_CREDENTIAL_IDENTIFIERS = {
    "ENTSOE_API_TOKEN",
    "RTE_ACCESS_TOKEN",
    "RTE_CLIENT_ID",
    "RTE_CLIENT_SECRET",
}
LEGACY_IMPORT_PATTERN = re.compile(r"\b(?:from|import)\s+legacy\b")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.as_posix())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_target_package_does_not_import_legacy_modules():
    checked_files = 0
    offending_files = []

    for path in TARGET_PACKAGE.rglob("*.py"):
        checked_files += 1
        contents = path.read_text(encoding="utf-8")
        if LEGACY_IMPORT_PATTERN.search(contents):
            offending_files.append(path.as_posix())

    assert checked_files > 0
    assert offending_files == []


def test_control_package_modules_do_not_import_legacy_modules() -> None:
    checked_files = 0
    offending_files = []

    assert CONTROL_PACKAGE.is_dir()

    for path in sorted(CONTROL_PACKAGE.glob("*.py")):
        checked_files += 1
        contents = path.read_text(encoding="utf-8")
        if LEGACY_IMPORT_PATTERN.search(contents):
            offending_files.append(path.as_posix())

    assert checked_files > 0
    assert offending_files == []


def test_feature_010_modules_exist_and_do_not_import_legacy_modules() -> None:
    offending_files = []
    for path in FEATURE_010_MODULES:
        assert path.is_file(), f"missing Feature 010 module: {path}"
        if LEGACY_IMPORT_PATTERN.search(path.read_text(encoding="utf-8")):
            offending_files.append(path.as_posix())

    assert offending_files == []


def test_feature_011_offline_modules_have_zero_adapter_credential_or_research_leakage() -> None:
    import_violations: dict[str, list[str]] = {}
    credential_violations: dict[str, list[str]] = {}

    for path in FEATURE_011_OFFLINE_MODULES:
        assert path.is_file(), f"missing Feature 011 offline module: {path}"
        imported = _imported_modules(path)
        forbidden = sorted(
            name
            for name in imported
            if any(
                name == blocked or name.startswith(f"{blocked}.")
                for blocked in FEATURE_011_FORBIDDEN_IMPORTS
            )
        )
        if forbidden:
            import_violations[path.as_posix()] = forbidden

        contents = path.read_text(encoding="utf-8")
        leaked_credentials = sorted(
            identifier
            for identifier in FEATURE_011_CREDENTIAL_IDENTIFIERS
            if identifier in contents
        )
        if leaked_credentials:
            credential_violations[path.as_posix()] = leaked_credentials

    assert import_violations == {}
    assert credential_violations == {}


def test_feature_012_offline_modules_import_no_baseline_solver_network_or_notebook_code() -> None:
    violations: dict[str, list[str]] = {}

    for path in FEATURE_012_OFFLINE_MODULES:
        assert path.is_file(), f"missing Feature 012 offline module: {path}"
        imported = _imported_modules(path)
        forbidden = sorted(
            name
            for name in imported
            if any(
                name == blocked or name.startswith(f"{blocked}.")
                for blocked in FEATURE_012_FORBIDDEN_IMPORTS
            )
        )
        if forbidden:
            violations[path.as_posix()] = forbidden

    assert violations == {}


def test_feature_014_domain_and_planning_modules_import_no_legacy_code() -> None:
    offending_files = []
    for path in FEATURE_014_DOMAIN_MODULES:
        assert path.is_file(), f"missing Feature 014 module: {path}"
        if LEGACY_IMPORT_PATTERN.search(path.read_text(encoding="utf-8")):
            offending_files.append(path.as_posix())

    assert offending_files == []
def test_feature_013_pure_modules_import_no_reference_solver_or_external_data_code() -> None:
    violations: dict[str, list[str]] = {}
    runtime_read_tokens = (
        "regulation_signal.csv",
        "Path(\"baselines",
        "Path('baselines",
        "Path(\"legacy",
        "Path('legacy",
        "open(\"baselines",
        "open('baselines",
        "open(\"legacy",
        "open('legacy",
    )

    for path in FEATURE_013_OFFLINE_MODULES:
        assert path.is_file(), f"missing Feature 013 offline module: {path}"
        imported = _imported_modules(path)
        forbidden = sorted(
            name
            for name in imported
            if any(
                name == blocked or name.startswith(f"{blocked}.")
                for blocked in FEATURE_013_FORBIDDEN_IMPORTS
            )
        )
        source = path.read_text(encoding="utf-8")
        forbidden.extend(token for token in runtime_read_tokens if token in source)
        if forbidden:
            violations[path.as_posix()] = forbidden

    assert violations == {}
