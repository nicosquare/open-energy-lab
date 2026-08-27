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

    assert '-m "not external_reference_data"' in offline_job
    assert "regulation_signal.csv" not in workflow
    assert "actions/upload-artifact" not in offline_job
