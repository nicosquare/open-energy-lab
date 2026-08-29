from pathlib import Path


CI_WORKFLOW_PATH = Path(".github/workflows/ci.yml")


def test_ci_runs_broad_offline_feature_regressions() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    job_marker = "  offline-feature-regressions:\n"
    assert job_marker in workflow
    offline_job = workflow.split(job_marker, maxsplit=1)[1]

    assert 'python-version: "3.14"' in offline_job
    assert "timeout --signal=TERM --kill-after=10s 120s" in offline_job
    for required_path in (
        "tests/unit/control",
        "tests/unit/simulator",
        "tests/unit/weather",
        "tests/unit/demand",
        "tests/integration/weather",
        "tests/integration/demand",
        "tests/integration/simulator",
        "tests/unit/test_ci_workflow.py",
        "tests/unit/test_lazy_dependency_boundaries.py",
        "tests/unit/test_import_contract.py",
        "tests/unit/test_no_legacy_imports.py",
    ):
        assert required_path in offline_job

    assert "tests/integration/control/test_robust_fcr_highs.py" not in offline_job
    assert (
        "tests/integration/control/test_robust_fcr_reference_normalization.py"
        not in offline_job
    )
    assert '-m "not reference_benchmark and not external_reference_data"' in offline_job
    assert (
        "--ignore=tests/integration/control/test_robust_fcr_optional_gurobi.py"
        in offline_job
    )
    assert "regulation_signal.csv" not in workflow
    assert "actions/upload-artifact" not in offline_job


def test_ci_required_backend_matrix_remains_focused_on_tpm_and_planning() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    required_job = workflow.split("  required-backends:\n", maxsplit=1)[1].split(
        "  conditional-mio-notebook:\n",
        maxsplit=1,
    )[0]

    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in required_job
    assert "timeout --signal=TERM --kill-after=10s 120s" in required_job
    for required_path in (
        "tests/unit/tpm",
        "tests/unit/planning",
        "tests/integration/tpm",
        "tests/integration/planning",
    ):
        assert required_path in required_job

    assert "robust_fcr" not in required_job
    assert "--group notebook" not in required_job
    assert (
        "--ignore=tests/integration/tpm/test_conditional_mio_notebook_execution.py"
        in required_job
    )


def test_ci_runs_conditional_mio_notebook_once_on_locked_python_311() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    notebook_job = workflow.split(
        "  conditional-mio-notebook:\n", maxsplit=1
    )[1].split("  robust-fcr-required-backends:\n", maxsplit=1)[0]

    assert 'python-version: "3.11"' in notebook_job
    assert "matrix.python-version" not in notebook_job
    assert "uv sync --locked --group dev --group notebook" in notebook_job
    for required_import in (
        "import spflow",
        "import pyomo.environ as pyo",
        "import highspy",
        "import nbclient",
        "import nbformat",
        "import ipykernel",
    ):
        assert required_import in notebook_job
    assert 'pyo.SolverFactory("highs")' in notebook_job
    assert "uv run --offline --locked --no-sync pytest" in notebook_job
    assert "tests/unit/tpm/test_conditional_mio_notebook.py" in notebook_job
    assert (
        "tests/integration/tpm/test_conditional_mio_notebook_execution.py"
        in notebook_job
    )


def test_ci_robust_fcr_backend_matrix_collects_only_bounded_feature_013_paths() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    robust_fcr_job = workflow.split(
        "  robust-fcr-required-backends:\n",
        maxsplit=1,
    )[1].split(
        "  offline-feature-regressions:\n",
        maxsplit=1,
    )[0]

    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in robust_fcr_job
    assert "timeout --signal=TERM --kill-after=10s 240s" in robust_fcr_job
    for required_path in (
        "tests/unit/control/test_robust_fcr_backend_compatibility.py",
        "tests/unit/control/test_robust_fcr_equations.py",
        "tests/unit/control/test_robust_fcr_import_boundary.py",
        "tests/unit/control/test_robust_fcr_problem.py",
        "tests/unit/control/test_robust_fcr_reference.py",
        "tests/unit/control/test_robust_fcr_solver.py",
        "tests/unit/control/test_robust_fcr_source_documentation.py",
        "tests/integration/control/test_robust_fcr_highs.py",
        "tests/integration/control/test_robust_fcr_reference_normalization.py",
        "tests/integration/simulator/test_robust_fcr_feature_012_replay.py",
    ):
        assert required_path in robust_fcr_job

    assert (
        '-m "not reference_benchmark and not external_reference_data"'
        in robust_fcr_job
    )
    assert (
        "--ignore=tests/integration/control/test_robust_fcr_optional_gurobi.py"
        in robust_fcr_job
    )
    assert "tests/unit/tpm" not in robust_fcr_job
    assert "tests/unit/planning" not in robust_fcr_job
    assert "tests/parity/test_robust_fcr_reference_benchmark.py" not in robust_fcr_job
    assert "test_robust_fcr_external_reference_replay.py" not in robust_fcr_job


def test_ci_collects_bounded_feature_015_control_and_common_replay_paths() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    robust_fcr_job = workflow.split(
        "  robust-fcr-required-backends:\n",
        maxsplit=1,
    )[1].split(
        "  offline-feature-regressions:\n",
        maxsplit=1,
    )[0]
    offline_job = workflow.split(
        "  offline-feature-regressions:\n",
        maxsplit=1,
    )[1]

    for required_path in (
        "tests/unit/control/test_fcr_rolling_import_boundary.py",
        "tests/unit/control/test_fcr_rolling_manifest.py",
        "tests/unit/control/test_fcr_rolling_orchestration.py",
        "tests/unit/control/test_fcr_rolling_reference.py",
        "tests/unit/control/test_fcr_rolling_results.py",
        "tests/integration/control/test_fcr_rolling_highs.py",
        "tests/integration/control/test_fcr_rolling_reference_normalization.py",
        "tests/integration/control/test_fcr_rolling_resume.py",
    ):
        assert required_path in robust_fcr_job
    assert (
        "tests/integration/simulator/test_fcr_rolling_feature_012_replay.py"
        in offline_job
    )
    assert robust_fcr_job.count(
        "timeout --signal=TERM --kill-after=10s 120s"
    ) >= 1
    assert offline_job.count(
        "timeout --signal=TERM --kill-after=10s 120s"
    ) >= 2

    for job in (robust_fcr_job, offline_job):
        assert '-m "not reference_benchmark and not external_reference_data"' in job
        assert "tests/parity/test_fcr_rolling_reference_benchmark.py" not in job
        assert (
            "tests/integration/simulator/"
            "test_fcr_rolling_external_reference_replay.py"
            not in job
        )
        assert "test_robust_fcr_optional_gurobi.py" not in job or (
            "--ignore=tests/integration/control/"
            "test_robust_fcr_optional_gurobi.py"
            in job
        )
