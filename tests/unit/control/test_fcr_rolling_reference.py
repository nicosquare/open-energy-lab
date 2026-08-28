"""Strict normalized rolling-reference and comparison contracts for Feature 015."""

from __future__ import annotations

from dataclasses import replace
import builtins
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from open_energy_lab.control.fcr_rolling_reference import (
    ROLLING_FCR_REFERENCE_FIXTURE_ID,
    ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION,
    ROLLING_FCR_REFERENCE_OUTCOMES,
    RollingFCRReferenceFieldResult,
    classify_rolling_fcr_numeric_evidence,
    derive_rolling_fcr_reference_summary,
    load_rolling_fcr_reference_fixture,
    source_precision_interval,
)


FIXTURE_PATH = Path(
    "tests/fixtures/fcr_rolling_backtest/"
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
)
REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
PROFILES = (
    "script-11-relaxation-reset-midnight-v1",
    "script-12-restriction-reset-midnight-v1",
    "script-13-arbitrage-only-midnight-v1",
    "script-14-restriction-rolling-0800-v1",
    "script-15-restriction-rolling-midnight-v1",
)
DATES = ("2023-06-17", "2023-06-18", "2023-06-19", "2023-06-20")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _field(
    outcome: str,
    *,
    mandatory: bool = True,
    index: int = 0,
) -> RollingFCRReferenceFieldResult:
    return RollingFCRReferenceFieldResult(
        profile_id=PROFILES[1],
        delivery_date=DATES[1],
        category="decision",
        field_path=f"hourly_energy[{index}]",
        unit="kW",
        mandatory=mandatory,
        native_value=1.0,
        source_displayed_value=1.0,
        source_interval=(0.9995, 1.0005),
        delta=0.0,
        allowed_envelope=(0.999499, 1.000501),
        outcome=outcome,
        reason_codes=(f"controlled_{outcome}",),
        native_evidence_fingerprint="1" * 64,
        source_evidence_fingerprint="2" * 64,
    )


def test_fixture_loads_strict_five_by_four_provenance_and_fingerprint() -> None:
    fixture = load_rolling_fcr_reference_fixture(FIXTURE_PATH)
    payload = fixture.to_dict()

    assert fixture.schema_version == ROLLING_FCR_REFERENCE_FIXTURE_SCHEMA_VERSION
    assert fixture.fixture_id == ROLLING_FCR_REFERENCE_FIXTURE_ID
    assert fixture.reference_provenance.reference_revision == REFERENCE_REVISION
    assert fixture.reference_provenance.runtime_evidence == {
        "gurobi_runtime_version": "11.0.3",
        "julia_version": "1.10.1",
    }
    assert fixture.reference_provenance.committed_environment == {
        "gurobi_jl": "1.3.1",
        "gurobi_runtime": "11.0.3",
        "julia": "1.10.1",
        "jump": "1.23.3",
    }
    assert fixture.reference_provenance.readme_claims == {
        "gurobi": "11.0.2",
        "julia": "1.10.1",
        "jump": "1.22.2",
    }
    assert len(fixture.solve_records) == len(PROFILES) * len(DATES) == 20
    assert tuple(
        (item.profile_id, item.delivery_date.isoformat())
        for item in fixture.solve_records
    ) == tuple((profile, day) for profile in PROFILES for day in DATES)
    assert len(fixture.delivery_evidence) == 20
    assert len(fixture.problem_inputs) == 20
    artifact_kinds = [item.artifact_kind for item in fixture.raw_input_manifest]
    assert artifact_kinds.count("generated_json") == 20
    assert artifact_kinds.count("generated_log") == 11
    assert fixture.study_window["ordered_dates"] == DATES
    assert fixture.study_window["primary_comparison_dates"] == DATES[1:3]
    assert fixture.precision_policy.source_decimal_places == 3
    assert fixture.precision_policy.joint_certificate_required is True
    assert fixture.precision_policy.restriction_bilinear_violations_is_feasibility_evidence is False
    assert fixture.feature_013_cross_check.governed_fixture_preserved is True
    assert fixture.redistribution_status.normalized_fields_only is True
    assert all(not item.redistributed for item in fixture.raw_input_manifest)
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("fixture_fingerprint")
    assert fixture.fixture_fingerprint == hashlib.sha256(
        _canonical_bytes(fingerprint_payload)
    ).hexdigest()


def test_fixture_retains_status_edges_unavailable_fields_and_no_raw_payloads() -> None:
    fixture = load_rolling_fcr_reference_fixture(FIXTURE_PATH)
    script_14 = {
        item.delivery_date.isoformat(): item
        for item in fixture.delivery_evidence
        if item.profile_id == PROFILES[3]
    }
    assert script_14[DATES[0]].source_lifecycle_status == "initialization_only"
    assert script_14[DATES[1]].source_lifecycle_status == "finalized"
    assert script_14[DATES[2]].source_lifecycle_status == "finalized"
    assert script_14[DATES[3]].source_lifecycle_status == "unfinalized"
    time_limited = {
        (item.profile_id, item.delivery_date.isoformat())
        for item in fixture.solve_records
        if item.solver_evidence.termination_condition == "TIME_LIMIT"
    }
    assert (PROFILES[3], DATES[1]) in time_limited
    assert (PROFILES[4], DATES[2]) in time_limited
    unavailable = {item.field_path for item in fixture.unavailable_fields}
    assert "source.unrounded_decisions" in unavailable
    assert "source.restriction_independent_residual_audit" in unavailable
    assert "profiles.script-14.exact_full_precision_restart" in unavailable
    payload_text = json.dumps(fixture.to_dict(), sort_keys=True)
    for forbidden in (
        "License ID",
        "Academic license",
        "regulation_signal.csv,datetime",
        "Gurobi Optimizer version",
        "/home/",
        "\\\\Users\\",
    ):
        assert forbidden not in payload_text


def test_fixture_loader_rejects_unknown_keys_tampering_and_missing_evidence(
    tmp_path: Path,
) -> None:
    payload = _fixture_payload()
    payload["unexpected"] = True
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected|exact"):
        load_rolling_fcr_reference_fixture(unknown)

    payload = _fixture_payload()
    payload["solve_records"][0]["objective_eur"] += 0.001
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        load_rolling_fcr_reference_fixture(tampered)

    payload = _fixture_payload()
    payload["raw_input_manifest"] = payload["raw_input_manifest"][:-1]
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="raw input|artifact|fingerprint"):
        load_rolling_fcr_reference_fixture(missing)


def test_fixture_loader_reads_only_explicit_path_and_is_offline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "selected.json"
    selected.write_bytes(FIXTURE_PATH.read_bytes())
    original_read_bytes = Path.read_bytes
    allowed = selected.resolve()
    reads: list[Path] = []

    def guarded_read_bytes(path: Path) -> bytes:
        resolved = path.resolve()
        reads.append(resolved)
        if resolved != allowed:
            raise AssertionError(f"unexpected reference read: {resolved}")
        return original_read_bytes(path)

    def forbidden(action: str):
        def fail(*args, **kwargs):
            raise AssertionError(f"reference loader attempted {action}")

        return fail

    monkeypatch.setattr(Path, "read_bytes", guarded_read_bytes)
    monkeypatch.setattr(socket, "socket", forbidden("network"))
    monkeypatch.setattr(subprocess, "run", forbidden("subprocess"))
    monkeypatch.setattr(subprocess, "Popen", forbidden("subprocess"))
    monkeypatch.setattr(builtins, "input", forbidden("credential input"))
    fixture = load_rolling_fcr_reference_fixture(selected)

    assert fixture.fixture_id == ROLLING_FCR_REFERENCE_FIXTURE_ID
    assert reads == [allowed]


@pytest.mark.parametrize(
    ("displayed", "half_unit", "expected"),
    (
        (1.234, 0.0005, (1.2335, 1.2345)),
        (-0.0, 0.0005, (-0.0005, 0.0005)),
        (50.0, 0.0005, (49.9995, 50.0005)),
    ),
)
def test_closed_source_precision_interval_uses_decimal_endpoints(
    displayed: float,
    half_unit: float,
    expected: tuple[float, float],
) -> None:
    assert source_precision_interval(displayed, half_unit) == expected


@pytest.mark.parametrize(
    ("case", "expected"),
    (
        (
            dict(native_value=1.0, source_value=1.0),
            "exact_displayed_decision_parity",
        ),
        (
            dict(native_value=1.0004, source_value=1.0),
            "source_precision_compatible",
        ),
        (
            dict(
                native_value=1.1,
                source_value=1.0,
                both_optimal=True,
                objective_equivalent=True,
            ),
            "alternative_optimum_compatible",
        ),
        (
            dict(
                native_value=1.1,
                source_value=1.0,
                source_termination="TIME_LIMIT",
                objective_equivalent=True,
            ),
            "source_incumbent_equivalent",
        ),
        (
            dict(
                native_value=1.1,
                source_value=1.0,
                source_termination="TIME_LIMIT",
                source_objective_eur=10.0,
                source_bound_eur=12.0,
                native_objective_eur=11.0,
            ),
            "improved_feasible_incumbent_compatible_with_source_bound",
        ),
        (
            dict(
                native_value=1.1,
                source_value=1.0,
                source_termination="TIME_LIMIT",
                source_objective_eur=10.0,
                source_bound_eur=12.0,
                native_objective_eur=12.1,
            ),
            "bound_incompatible",
        ),
        (
            dict(native_value=1.1, source_value=1.0),
            "mismatch",
        ),
        (
            dict(native_value=None, source_value=1.0),
            "unavailable",
        ),
        (
            dict(native_value=1.0, source_value=1.0, lifecycle_complete=False),
            "incomplete_or_unfinalized",
        ),
    ),
)
def test_field_comparison_assigns_each_declared_outcome(
    case: dict[str, object],
    expected: str,
) -> None:
    arguments = {
        "native_value": 1.0,
        "source_value": 1.0,
        "source_half_unit": 0.0005,
        "native_tolerance": 1e-6,
        "source_termination": "OPTIMAL",
        "native_termination": "optimal",
        "native_feasible": True,
        "source_joint_feasible": True,
        "both_optimal": False,
        "objective_equivalent": False,
        "source_objective_eur": 10.0,
        "source_bound_eur": 10.0,
        "native_objective_eur": 10.0,
        "lifecycle_complete": True,
    }
    arguments.update(case)
    assert classify_rolling_fcr_numeric_evidence(**arguments) == expected


def test_alternative_optimum_requires_both_optimal_and_common_feasibility() -> None:
    base = {
        "native_value": 2.0,
        "source_value": 1.0,
        "source_half_unit": 0.0005,
        "native_tolerance": 1e-6,
        "source_termination": "OPTIMAL",
        "native_termination": "optimal",
        "native_feasible": True,
        "source_joint_feasible": True,
        "both_optimal": True,
        "objective_equivalent": True,
        "source_objective_eur": 10.0,
        "source_bound_eur": 10.0,
        "native_objective_eur": 10.0,
        "lifecycle_complete": True,
    }
    assert classify_rolling_fcr_numeric_evidence(**base) == (
        "alternative_optimum_compatible"
    )
    assert classify_rolling_fcr_numeric_evidence(
        **{**base, "source_termination": "TIME_LIMIT", "both_optimal": False}
    ) != "alternative_optimum_compatible"
    assert classify_rolling_fcr_numeric_evidence(
        **{**base, "source_joint_feasible": False}
    ) != "alternative_optimum_compatible"
    assert classify_rolling_fcr_numeric_evidence(
        **{**base, "native_feasible": False}
    ) != "alternative_optimum_compatible"


def test_summary_derivation_preserves_canonical_evidence_bases() -> None:
    compatible = derive_rolling_fcr_reference_summary(
        scope_id="compatible",
        field_results=(
            _field("source_precision_compatible", index=0),
            _field("source_incumbent_equivalent", index=1),
        ),
    )
    assert compatible.overall_compatibility == "compatible"
    assert compatible.evidence_bases == tuple(
        value
        for value in ROLLING_FCR_REFERENCE_OUTCOMES
        if value in {
            "source_precision_compatible",
            "source_incumbent_equivalent",
        }
    )

    incomplete = derive_rolling_fcr_reference_summary(
        scope_id="incomplete",
        field_results=(
            _field("source_precision_compatible", index=0),
            _field("unavailable", index=1),
        ),
    )
    assert incomplete.overall_compatibility == "incomplete"

    incompatible = derive_rolling_fcr_reference_summary(
        scope_id="incompatible",
        field_results=(
            _field("unavailable", mandatory=False, index=0),
            _field("bound_incompatible", index=1),
        ),
    )
    assert incompatible.overall_compatibility == "incompatible"


def test_field_result_is_immutable_fingerprinted_and_detects_bad_envelopes() -> None:
    result = _field("source_precision_compatible")
    assert result.field_result_fingerprint == replace(
        result,
        reason_codes=tuple(result.reason_codes),
    ).field_result_fingerprint
    payload = result.to_dict()
    payload["reason_codes"].append("detached")
    assert "detached" not in result.reason_codes
    with pytest.raises(ValueError, match="allowed envelope"):
        replace(result, allowed_envelope=(2.0, 1.0))

