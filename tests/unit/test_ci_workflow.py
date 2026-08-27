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
        "tests/integration/control/test_robust_fcr_highs.py",
        "tests/integration/control/test_robust_fcr_reference_normalization.py",
        "tests/integration/simulator",
        "tests/unit/test_ci_workflow.py",
        "tests/unit/test_lazy_dependency_boundaries.py",
        "tests/unit/test_import_contract.py",
        "tests/unit/test_no_legacy_imports.py",
    ):
        assert required_path in offline_job

    assert '-m "not reference_benchmark and not external_reference_data"' in offline_job
    assert (
        "--ignore=tests/integration/control/test_robust_fcr_optional_gurobi.py"
        in offline_job
    )
    assert "regulation_signal.csv" not in workflow
    assert "actions/upload-artifact" not in offline_job


def test_ci_required_backend_matrix_collects_only_bounded_feature_013_paths() -> None:
    workflow = CI_WORKFLOW_PATH.read_text(encoding="utf-8")
    required_job = workflow.split("  required-backends:\n", maxsplit=1)[1].split(
        "  offline-feature-regressions:\n",
        maxsplit=1,
    )[0]

    assert 'python-version: ["3.11", "3.12", "3.13", "3.14"]' in required_job
    assert "timeout --signal=TERM --kill-after=10s 120s" in required_job
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
        assert required_path in required_job

    assert '-m "not reference_benchmark and not external_reference_data"' in required_job
    assert (
        "--ignore=tests/integration/control/test_robust_fcr_optional_gurobi.py"
        in required_job
    )
    assert "tests/parity/test_robust_fcr_reference_benchmark.py" not in required_job
    assert "test_robust_fcr_external_reference_replay.py" not in required_job
