"""Executable-script, result-directory, paper, and workbook crosswalk."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_energy_lab.control import build_rolling_fcr_experiment_profile


@pytest.mark.parametrize(
    (
        "profile_id",
        "script",
        "result_directory",
        "formulation",
        "state_mode",
        "paper_experiment",
        "workbook_column",
        "classification",
    ),
    (
        (
            "script-11-relaxation-reset-midnight-v1",
            "11.jl",
            "/01",
            "relaxation",
            "reset",
            1,
            11,
            "diagnostic_non_robust",
        ),
        (
            "script-12-restriction-reset-midnight-v1",
            "12.jl",
            "/02",
            "restriction",
            "reset",
            2,
            12,
            "robust_candidate",
        ),
        (
            "script-13-arbitrage-only-midnight-v1",
            "13.jl",
            "/03",
            "arbitrage_only",
            "midnight_carry",
            4,
            14,
            "arbitrage_only",
        ),
        (
            "script-14-restriction-rolling-0800-v1",
            "14.jl",
            "/04",
            "restriction",
            "rolling_0800",
            5,
            15,
            "robust_candidate",
        ),
        (
            "script-15-restriction-rolling-midnight-v1",
            "15.jl",
            "/05",
            "restriction",
            "midnight_carry",
            3,
            13,
            "robust_candidate",
        ),
    ),
)
def test_executable_profiles_have_the_exact_source_and_crosswalk_mapping(
    profile_id: str,
    script: str,
    result_directory: str,
    formulation: str,
    state_mode: str,
    paper_experiment: int,
    workbook_column: int,
    classification: str,
) -> None:
    profile = build_rolling_fcr_experiment_profile(profile_id)

    assert profile.source_script.endswith(script)
    assert profile.source_result_directory.endswith(result_directory)
    assert profile.formulation_kind == formulation
    assert profile.state_mode == state_mode
    assert profile.paper_experiment == paper_experiment
    assert profile.workbook_column == workbook_column
    assert profile.plan_classification == classification


def test_crosswalk_records_metric_discrepancy_and_never_claims_table_a1_parity() -> None:
    for profile_id in (
        "script-11-relaxation-reset-midnight-v1",
        "script-12-restriction-reset-midnight-v1",
        "script-13-arbitrage-only-midnight-v1",
        "script-14-restriction-rolling-0800-v1",
        "script-15-restriction-rolling-midnight-v1",
    ):
        profile = build_rolling_fcr_experiment_profile(profile_id)
        payload = profile.to_dict()

        assert profile.crosswalk_reconciliation_status == (
            "executable-crosswalk-known-metric-discrepancies-v1"
        )
        assert profile.table_a1_parity_claim is False
        assert payload["crosswalk"]["table_a1_parity_claim"] is False
        assert any("result_overview.xlsx" in ref for ref in profile.source_refs)
        assert any(profile.source_script in ref for ref in profile.source_refs)


def test_migration_ledger_cites_every_authoritative_source_line_range() -> None:
    ledger = Path("docs/migration/fcr-rolling-backtest-parity.md").read_text(
        encoding="utf-8"
    )
    required = (
        "code/01_datastruct.jl:3-48",
        "code/02_model.jl:15-32",
        "code/02_model.jl:34-75",
        "code/02_model.jl:86-99,137-143",
        "code/02_model.jl:175-188,252-263,289-291",
        "code/03_backtest_save.jl:5-83",
        "code/03_backtest_save.jl:86-158",
        "code/03_backtest_save.jl:161-204",
        "code/04_parse_results.jl:4-39,43-100",
        "code/05_dates.txt:1-1453",
        "code/11.jl:23-95",
        "code/12.jl:23-95",
        "code/13.jl:23-103",
        "code/14.jl:23-104",
        "code/15.jl:23-104",
    )
    assert all(reference in ledger for reference in required)


def test_documentation_retains_script_workbook_and_paper_discrepancies() -> None:
    ledger = Path("docs/migration/fcr-rolling-backtest-parity.md").read_text(
        encoding="utf-8"
    ).casefold()

    assert "scripts 11/12/13/14/15" in ledger
    assert "experiments 1/2/4/5/3" in ledger
    assert "columns 11/12/14/15/13" in ledger
    assert "script 13" in ledger and "3,600" in ledger
    assert "900" in ledger
    assert "charging input" in ledger
    assert "charging efficiency" in ledger
    assert "discharge-energy output" in ledger
    assert "no table a1 parity claim" in ledger
    assert "bounded four-day rerun" in ledger
    assert "bilinear_violations=0" in ledger
