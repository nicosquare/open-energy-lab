"""Contract tests for the explicit reference-result refresh helper."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from oel_validation.scripts.normalize_fcr_bid_reference_result import (
    ReferenceNormalizationError,
    normalize_reference_result,
)


FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _generated_result() -> dict[str, object]:
    fixture = _fixture()
    configuration = fixture["reference_configuration"]
    fixed = fixture["fixed_decisions"]
    prices = fixture["price_inputs"]
    expected = {
        item["reference_field_path"]: item["expected_value"]
        for item in fixture["expected_fields"]
    }
    reference_curr = {
        "x0": fixed["rounded_x0_kw"],
        "xr": fixed["rounded_xr_kw"],
        "xa": [0.0] * 96,
        "xa_dec": [0.0] * 96,
        "profit_total": expected["/bt/curr/profit_total"],
        "profit_da": expected["/bt/curr/profit_da"],
        "profit_fcr": expected["/bt/curr/profit_fcr"],
        "profit_id": expected["/bt/curr/profit_id"],
        "soc_initial": expected["/bt/curr/soc_initial"],
        "soc_min": expected["/bt/curr/soc_min"],
        "soc_max": expected["/bt/curr/soc_max"],
        "soc_terminal": expected["/bt/curr/soc_terminal"],
        "y_in": expected["/bt/curr/y_in"],
        "y_out": expected["/bt/curr/y_out"],
        "xmin": -expected["/bt/curr/xmin"],
        "xmax": -expected["/bt/curr/xmax"],
    }
    return {
        "case_data": {
            "K": configuration["planning_interval_count"],
            "x̅": configuration["max_discharge_kw"],
            "x̲": -configuration["max_charge_kw"],
            "y0": configuration["initial_stored_energy_kwh"],
            "Δt": configuration["planning_resolution_hours"],
            "dt": configuration["activation_resolution_hours"],
            "y̲": configuration["minimum_stored_energy_kwh"],
            "y̅": configuration["maximum_stored_energy_kwh"],
            "ηc": configuration["charge_efficiency"],
            "ηd": configuration["discharge_efficiency"],
            "psoc": configuration["capacity_kwh"],
            "p0": prices["p0"],
            "pr": prices["pr"],
            "day_ahead": configuration["day_ahead"],
            "day_ahead_limited": configuration["day_ahead_limited"],
            "energy_payment": configuration["energy_payment"],
            "intraday_trading": configuration["intraday_trading"],
            "xi_signal": configuration["activation_series"],
            "cst_reg_periods": configuration["fcr_commitment_planning_intervals"],
            "ndigits_prev": configuration["saved_decimal_places"],
            "model_type": configuration["model_type"],
        },
        "bilinear_violations": expected["/bilinear_violations"],
        "objective bound": expected["/objective bound"],
        "bt": {
            "curr": reference_curr,
            "curr_bid": deepcopy(reference_curr),
        },
        "test_date": configuration["test_date"],
        "objective value": expected["/objective value"],
        "solve_time": expected["/solve_time"],
    }


def _write_generated(path: Path, payload: dict[str, object]) -> tuple[Path, str]:
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


def test_normalizer_uses_explicit_paths_and_writes_byte_stable_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, digest = _write_generated(tmp_path / "source" / "result.json", _generated_result())
    output_dir = tmp_path / "normalized"
    source_before = source.read_bytes()

    def forbidden_process(*args, **kwargs):
        raise AssertionError("normalization must not execute Julia, Gurobi, or a shell")

    monkeypatch.setattr(subprocess, "run", forbidden_process)
    monkeypatch.setattr(subprocess, "Popen", forbidden_process)
    first = normalize_reference_result(
        input_path=source,
        expected_sha256=digest,
        output_dir=output_dir,
        fixture_path=FIXTURE_PATH,
    )
    first_bytes = first.output_path.read_bytes()
    repeated = normalize_reference_result(
        input_path=source,
        expected_sha256=digest,
        output_dir=output_dir,
        fixture_path=FIXTURE_PATH,
    )

    assert source.read_bytes() == source_before
    assert first.output_path == output_dir / "normalized_reference_result.json"
    assert repeated.output_path.read_bytes() == first_bytes
    assert first.source_sha256 == digest
    assert first.semantic_differences == ()
    assert repeated.semantic_differences == ()


def test_normalizer_rejects_digest_or_configuration_mismatch(tmp_path: Path) -> None:
    source, digest = _write_generated(tmp_path / "result.json", _generated_result())

    with pytest.raises(ReferenceNormalizationError, match="SHA-256"):
        normalize_reference_result(
            input_path=source,
            expected_sha256="0" * 64,
            output_dir=tmp_path / "wrong-digest",
            fixture_path=FIXTURE_PATH,
        )

    payload = _generated_result()
    payload["case_data"]["model_type"] = "relax"
    changed, changed_digest = _write_generated(tmp_path / "changed.json", payload)
    with pytest.raises(ReferenceNormalizationError, match="configuration.*model_type"):
        normalize_reference_result(
            input_path=changed,
            expected_sha256=changed_digest,
            output_dir=tmp_path / "wrong-config",
            fixture_path=FIXTURE_PATH,
        )

    assert digest != changed_digest


def test_normalizer_reports_ordered_semantic_differences(tmp_path: Path) -> None:
    payload = _generated_result()
    payload["bt"]["curr"]["x0"][0] = 27.594
    payload["bt"]["curr_bid"]["x0"][0] = 27.594
    payload["bt"]["curr"]["profit_total"] = 10.75
    payload["bt"]["curr_bid"]["profit_total"] = 10.75
    source, digest = _write_generated(tmp_path / "changed.json", payload)

    result = normalize_reference_result(
        input_path=source,
        expected_sha256=digest,
        output_dir=tmp_path / "normalized",
        fixture_path=FIXTURE_PATH,
    )

    paths = [item["field_path"] for item in result.semantic_differences]
    assert paths == sorted(paths)
    assert "/expected_fields/settlement.total_profit_eur" in paths
    assert "/fixed_decisions/rounded_x0_kw/0" in paths
    output = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert output["semantic_diff"] == list(result.semantic_differences)


def test_normalizer_refuses_to_write_over_committed_fixture_paths(
    tmp_path: Path,
) -> None:
    source, digest = _write_generated(tmp_path / "result.json", _generated_result())
    committed_before = FIXTURE_PATH.read_bytes()

    with pytest.raises(ReferenceNormalizationError, match="committed|artifacts"):
        normalize_reference_result(
            input_path=source,
            expected_sha256=digest,
            output_dir=FIXTURE_PATH.parent,
            fixture_path=FIXTURE_PATH,
        )

    assert FIXTURE_PATH.read_bytes() == committed_before
