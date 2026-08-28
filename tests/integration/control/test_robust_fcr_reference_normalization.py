"""Explicit-path normalization governance for Feature 013 reference evidence."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from examples.robust_fcr_bidding.normalize_reference_fixture import (
    ReferenceFixtureNormalizationError,
    normalize_reference_fixture,
)


COMMITTED_FIXTURE = Path(
    "tests/fixtures/fcr_bidding/"
    "robust_storage_bidding_2023-06-18_restriction_v1.json"
)


def _source_payload() -> dict[str, object]:
    committed = json.loads(COMMITTED_FIXTURE.read_text(encoding="utf-8"))
    problem = committed["problem"]
    battery = problem["battery"]
    uncertainty = problem["uncertainty"]
    terminal = problem["terminal_rule"]
    prices = problem["prices"]
    recorded = committed["recorded_result"]
    return {
        "case_data": {
            "K": 96,
            "x̅": battery["maximum_discharge_power_kw"],
            "x̲": -battery["maximum_charge_power_kw"],
            "y0": battery["initial_stored_energy_kwh"],
            "γ": uncertainty["recovery_activation_budget_hours"],
            "Γ": uncertainty["recovery_window_hours"],
            "Δt": 0.25,
            "y̲": battery["minimum_stored_energy_kwh"],
            "y̅": battery["maximum_stored_energy_kwh"],
            "ηc": battery["charge_efficiency"],
            "ηd": battery["discharge_efficiency"],
            "p0": prices["day_ahead_energy_prices"],
            "pr": prices["fcr_capacity_prices"],
            "psoc": terminal["shortfall_penalty_eur_per_kwh"],
            "intraday_trading": False,
            "cst_reg_periods": 16,
            "ylK": terminal["minimum_terminal_stored_energy_kwh"],
            "model_type": "restrict",
            "u_restrict": 0.0,
            "solver": "Gurobi",
            "timelimit": 3600.0,
        },
        "bilinear_violations": 0,
        "objective bound": recorded["objective_bound_eur"],
        "bt": {
            "curr": {
                "x0": recorded["rounded_x0_kw"],
                "xr": recorded["rounded_xr_kw"],
                "symin": [0.0] * 96,
                "symax": [0.0] * 96,
                "syK": 0.0,
            }
        },
        "test_date": "2023-06-18",
        "objective value": recorded["objective_value_eur"],
        "solve_time": recorded["solve_time_seconds"],
    }


def _write_source(path: Path, payload: dict[str, object]) -> tuple[Path, str]:
    data = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def test_normalizer_uses_explicit_digest_and_writes_byte_stable_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, digest = _write_source(tmp_path / "source.json", _source_payload())
    repository = tmp_path / "repo"
    artifact_root = repository / "artifacts"
    destination = artifact_root / "reference/robust_fcr_bidding"
    monkeypatch.setattr(
        "examples.robust_fcr_bidding.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.robust_fcr_bidding.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("normalization must not execute a process or access network")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    first = normalize_reference_fixture(
        source_json=source,
        expected_sha256=digest,
        destination_dir=destination,
        committed_fixture=COMMITTED_FIXTURE,
    )
    first_candidate = first.candidate_path.read_bytes()
    first_diff = first.semantic_diff_path.read_bytes()
    repeated = normalize_reference_fixture(
        source_json=source,
        expected_sha256=digest,
        destination_dir=destination,
        committed_fixture=COMMITTED_FIXTURE,
    )

    assert repeated.candidate_path.read_bytes() == first_candidate
    assert repeated.semantic_diff_path.read_bytes() == first_diff
    assert first.source_sha256 == digest
    assert first.semantic_differences == ()
    assert first.candidate_path.is_relative_to(artifact_root)


def test_normalizer_rejects_digest_mismatch_and_committed_destination(
    tmp_path: Path,
) -> None:
    source, digest = _write_source(tmp_path / "source.json", _source_payload())
    with pytest.raises(ReferenceFixtureNormalizationError, match="SHA-256"):
        normalize_reference_fixture(
            source_json=source,
            expected_sha256="0" * 64,
            destination_dir=tmp_path / "out",
            committed_fixture=COMMITTED_FIXTURE,
        )
    with pytest.raises(
        ReferenceFixtureNormalizationError,
        match="artifacts|committed",
    ):
        normalize_reference_fixture(
            source_json=source,
            expected_sha256=digest,
            destination_dir=COMMITTED_FIXTURE.parent,
            committed_fixture=COMMITTED_FIXTURE,
        )


def test_normalizer_emits_ordered_semantic_diff_without_overwriting_source(
    tmp_path: Path,
) -> None:
    source_payload = _source_payload()
    source_payload["bt"]["curr"]["x0"][0] += 0.001
    source_payload["objective value"] += 0.001
    source, digest = _write_source(tmp_path / "source.json", source_payload)
    source_before = source.read_bytes()
    result = normalize_reference_fixture(
        source_json=source,
        expected_sha256=digest,
        destination_dir=tmp_path / "normalized",
        committed_fixture=COMMITTED_FIXTURE,
    )

    assert source.read_bytes() == source_before
    paths = [item["field_path"] for item in result.semantic_differences]
    assert paths == sorted(paths)
    assert "/recorded_result/objective_value_eur" in paths
    assert "/recorded_result/rounded_x0_kw/0" in paths
    diff_payload = json.loads(result.semantic_diff_path.read_text(encoding="utf-8"))
    assert diff_payload["semantic_differences"] == list(
        result.semantic_differences
    )


def test_normalizer_rejects_wrong_reference_configuration(tmp_path: Path) -> None:
    payload = deepcopy(_source_payload())
    payload["case_data"]["model_type"] = "relax"
    source, digest = _write_source(tmp_path / "wrong.json", payload)
    with pytest.raises(ReferenceFixtureNormalizationError, match="model_type"):
        normalize_reference_fixture(
            source_json=source,
            expected_sha256=digest,
            destination_dir=tmp_path / "normalized",
            committed_fixture=COMMITTED_FIXTURE,
        )
