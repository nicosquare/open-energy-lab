"""Explicit digest-first normalization governance for Feature 015 evidence."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import subprocess

import pytest

from examples.fcr_rolling_backtest.normalize_reference_fixture import (
    RollingFCRReferenceNormalizationError,
    normalize_rolling_fcr_reference_fixture,
)
from open_energy_lab.control.fcr_rolling_reference import (
    load_rolling_fcr_reference_fixture,
)


COMMITTED_FEATURE_013_FIXTURE = Path(
    "tests/fixtures/fcr_bidding/"
    "robust_storage_bidding_2023-06-18_restriction_v1.json"
)
COMMITTED_ROLLING_FIXTURE = Path(
    "tests/fixtures/fcr_rolling_backtest/"
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
)
REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
DATES = tuple(f"2023-06-{day:02d}" for day in range(17, 21))
PROFILE_DATA = (
    (1, 11, "relax", 24.0),
    (2, 12, "restrict", 24.0),
    (3, 13, "no_reg", 24.0),
    (4, 14, "restrict", 8.0),
    (5, 15, "restrict", 24.0),
)
SOURCE_FILES = (
    "code/01_datastruct.jl",
    "code/02_model.jl",
    "code/03_backtest_save.jl",
    "code/04_parse_results.jl",
    "code/05_dates.txt",
    "code/11.jl",
    "code/12.jl",
    "code/13.jl",
    "code/14.jl",
    "code/15.jl",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _write(path: Path, payload: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _source_json(profile: int, script: int, day_index: int) -> dict[str, object]:
    day = DATES[day_index]
    model_type = PROFILE_DATA[profile - 1][2]
    bidding_time = PROFILE_DATA[profile - 1][3]
    if profile == 4 and day_index == 0:
        bidding_time = 24.0
    objective = round(5.0 + profile + day_index * 0.25, 3)
    bound = round(
        objective + (0.5 if profile in {4, 5} and day_index < 3 else 0.0),
        3,
    )
    x0 = [round((profile * 0.1) + index * 0.01, 3) for index in range(24)]
    xr = [0.0] * 6 if profile == 3 else [round(profile * 0.05 + i * 0.01, 3) for i in range(6)]
    if profile == 2 and day_index == 1:
        governed = json.loads(COMMITTED_FEATURE_013_FIXTURE.read_text(encoding="utf-8"))
        recorded = governed["recorded_result"]
        objective = recorded["objective_value_eur"]
        bound = recorded["objective_bound_eur"]
        x0 = recorded["rounded_x0_kw"]
        xr = recorded["rounded_xr_kw"]
    current = {
        "x0": x0,
        "xr": xr,
        "soc_initial": round(53.328 + day_index * 0.1, 3),
        "soc_bid": round(53.4 + day_index * 0.1, 3),
        "soc_terminal": round(53.5 + day_index * 0.1, 3),
    }
    bt: dict[str, object] = {"curr": current, "curr_bid": dict(current)}
    if profile == 4:
        if day_index < 3:
            bt["curr_org"] = dict(current)
        if day_index:
            bt["prev"] = {
                "x0": [round((profile * 0.1) + i * 0.01, 3) for i in range(8, 24)],
                "xr": [round(profile * 0.05 + i * 0.01, 3) for i in range(2, 6)],
                "soc_initial": round(53.3 + day_index * 0.1, 3),
                "soc_bid": round(53.3 + day_index * 0.1, 3),
                "soc_terminal": round(53.4 + day_index * 0.1, 3),
            }
    return {
        "case_data": {
            "K": 96,
            "x̅": 50.0,
            "x̲": -50.0,
            "y0": current["soc_initial"],
            "γ": 0.25,
            "Γ": 2.25,
            "Δt": 0.25,
            "dt": 1.0 / 360.0,
            "y̲": 10.0,
            "y̅": 90.0,
            "ηc": 0.92,
            "ηd": 0.92,
            "p0": [round(0.02 + day_index * 0.001 + i * 0.0001, 5) for i in range(40 if profile == 4 and day_index else 24)],
            "pr": [round(0.01 + day_index * 0.001 + i * 0.0001, 5) for i in range(10 if profile == 4 and day_index else 6)],
            "psoc": 100.0,
            "bidding_time": bidding_time,
            "ndigits_prev": 3,
            "intraday_trading": False,
            "date_prev": None if profile < 3 or day_index == 0 else DATES[day_index - 1],
            "cst_reg_periods": 16,
            "ylK": 53.327556325823224,
            "model_type": model_type,
            "u_restrict": 0.0,
            "solver": "Gurobi",
            "timelimit": 900.0 if profile in {4, 5} else 3600.0,
        },
        "bilinear_violations": 0,
        "objective bound": bound,
        "bt": bt,
        "test_date": day,
        "objective value": objective,
        "solve_time": 900.0 if bound > objective else 1.0,
    }


def _log_segment(profile: int, day_index: int, payload: dict[str, object]) -> str:
    objective = payload["objective value"]
    bound = payload["objective bound"]
    limited = profile in {4, 5} and day_index < 3
    termination = "TIME_LIMIT" if limited else "OPTIMAL"
    gap = (float(bound) - float(objective)) / max(abs(float(objective)), 1.0)
    return "\n".join(
        (
            f"Test run: {DATES[day_index]}",
            "Gurobi Optimizer version 11.0.3 build v11.0.3rc0 (linux64)",
            "Academic license - for non-commercial use only - expires 2027-01-01",
            "Set parameter Username to value hidden-user",
            f"Best objective {float(objective):.12e}, best bound {float(bound):.12e}, gap {gap:.4%}",
            "* Solver : Gurobi",
            f"  Termination status : {termination}",
            "  Primal status      : FEASIBLE_POINT",
            "  Dual status        : NO_SOLUTION",
            f"  Objective value    : {float(objective):.8e}",
            f"  Objective bound    : {float(bound):.8e}",
            f"  Relative gap       : {gap:.8e}",
            f"  Solve time (sec)   : {float(payload['solve_time']):.8e}",
            f"../results/{profile:02d}/{DATES[day_index]}.json",
            f"Save to {DATES[day_index]}.json is complete.",
            "",
        )
    )


def _build_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    repository = tmp_path / "repository"
    source_root = repository / "baselines/robust_storage_bidding"
    artifact_root = repository / "artifacts"
    artifacts: list[dict[str, object]] = []

    def add(
        relative_path: str,
        payload: bytes,
        *,
        artifact_id: str,
        artifact_kind: str,
        root_kind: str = "source",
        used_fields: tuple[str, ...] = (),
    ) -> None:
        root = source_root if root_kind == "source" else repository
        digest = _write(root / relative_path, payload)
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_kind": artifact_kind,
                "root_kind": root_kind,
                "relative_path": relative_path,
                "sha256": digest,
                "used_fields": list(used_fields),
                "redistributed": False,
            }
        )

    for relative_path in SOURCE_FILES:
        add(
            relative_path,
            f"source evidence {relative_path}\n".encode(),
            artifact_id=relative_path.replace("/", "-").replace(".", "-"),
            artifact_kind="source",
            used_fields=("source_citation",),
        )

    source_payloads: dict[tuple[int, int], dict[str, object]] = {}
    for profile, script, _model_type, _bidding_time in PROFILE_DATA:
        for day_index, day in enumerate(DATES):
            payload = _source_json(profile, script, day_index)
            source_payloads[(profile, day_index)] = payload
            add(
                f"results/{profile:02d}/{day}.json",
                _canonical_bytes(payload),
                artifact_id=f"result-{profile:02d}-{day}",
                artifact_kind="generated_json",
                used_fields=("problem_inputs", "solve_record", "delivery_evidence"),
            )

    for profile, script, _model_type, _bidding_time in PROFILE_DATA:
        if profile <= 2:
            for day_index, day in enumerate(DATES):
                add(
                    f"code/{script}-{day}.log",
                    _log_segment(profile, day_index, source_payloads[(profile, day_index)]).encode(),
                    artifact_id=f"log-{script}-{day}",
                    artifact_kind="generated_log",
                    used_fields=("termination", "bound", "runtime"),
                )
        else:
            contents = "".join(
                _log_segment(profile, day_index, source_payloads[(profile, day_index)])
                for day_index in range(4)
            )
            add(
                f"code/{script}.log",
                contents.encode(),
                artifact_id=f"log-{script}-bounded",
                artifact_kind="generated_log",
                used_fields=("termination", "bound", "runtime"),
            )

    add(
        "data/day_ahead_FR.csv",
        b"date,price\n2023-06-17,1\n",
        artifact_id="day-ahead-fr",
        artifact_kind="input_data",
        used_fields=("day_ahead_descriptor",),
    )
    add(
        "data/FCR_RTE.csv",
        b"date,price\n2023-06-17,1\n",
        artifact_id="fcr-rte",
        artifact_kind="input_data",
        used_fields=("fcr_capacity_descriptor",),
    )
    add(
        "data/regulation_signal.csv",
        b"timestamp,value\n2023-06-17T00:00:00Z,0\n",
        artifact_id="activation-trace",
        artifact_kind="input_data",
        used_fields=("activation_descriptor_only",),
    )
    add(
        "code/Project.toml",
        b"[deps]\nGurobi=\"x\"\nJuMP=\"y\"\n",
        artifact_id="julia-project",
        artifact_kind="project",
        used_fields=("environment_lineage",),
    )
    add(
        "code/Manifest.toml",
        b'julia_version = "1.10.1"\n[[deps.Gurobi]]\nversion = "1.3.1"\n[[deps.Gurobi_jll]]\nversion = "11.0.3"\n[[deps.JuMP]]\nversion = "1.23.3"\n',
        artifact_id="julia-manifest",
        artifact_kind="manifest",
        used_fields=("committed_environment",),
    )
    add(
        "README.md",
        b"Julia 1.10.1\nJuMP 1.22.2\nGurobi 11.0.2\n",
        artifact_id="reference-readme",
        artifact_kind="source",
        used_fields=("readme_claims",),
    )
    add(
        "results/result_overview.xlsx",
        b"synthetic workbook evidence",
        artifact_id="result-overview-workbook",
        artifact_kind="workbook",
        used_fields=("profile_crosswalk", "metric_discrepancy"),
    )
    add(
        "tests/fixtures/fcr_bidding/robust_storage_bidding_2023-06-18_restriction_v1.json",
        COMMITTED_FEATURE_013_FIXTURE.read_bytes(),
        artifact_id="feature-013-governed-fixture",
        artifact_kind="input_data",
        root_kind="repository",
        used_fields=("feature_013_cross_check",),
    )
    manifest_payload = {
        "schema_version": "fcr-rolling-reference-input-manifest-v1",
        "fixture_id": "robust-storage-bidding-experiments-01-05-2023-06-17-20-v1",
        "reference_revision": REFERENCE_REVISION,
        "runtime_evidence": {
            "julia_version": "1.10.1",
            "gurobi_runtime_version": "11.0.3",
        },
        "committed_environment": {
            "julia": "1.10.1",
            "jump": "1.23.3",
            "gurobi_jl": "1.3.1",
            "gurobi_runtime": "11.0.3",
        },
        "readme_claims": {
            "julia": "1.10.1",
            "jump": "1.22.2",
            "gurobi": "11.0.2",
        },
        "artifacts": artifacts,
    }
    manifest_path = repository / "reference_inputs_v1.json"
    _write(manifest_path, _canonical_bytes(manifest_payload))
    return repository, source_root, artifact_root, manifest_path


def test_normalizer_is_digest_first_explicit_redacting_and_byte_stable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, source_root, artifact_root, manifest_path = _build_inputs(tmp_path)
    destination = artifact_root / "reference/fcr_rolling_backtest"
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("normalization must not use discovery, processes, or network")

    monkeypatch.setattr(Path, "glob", forbidden)
    monkeypatch.setattr(Path, "rglob", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    first = normalize_rolling_fcr_reference_fixture(
        source_root=source_root,
        input_manifest=manifest_path,
        destination_dir=destination,
        committed_fixture=COMMITTED_ROLLING_FIXTURE,
    )
    first_candidate = first.candidate_path.read_bytes()
    first_diff = first.semantic_diff_path.read_bytes()
    repeated = normalize_rolling_fcr_reference_fixture(
        source_root=source_root,
        input_manifest=manifest_path,
        destination_dir=destination,
        committed_fixture=COMMITTED_ROLLING_FIXTURE,
    )

    assert repeated.candidate_path.read_bytes() == first_candidate
    assert repeated.semantic_diff_path.read_bytes() == first_diff
    assert first.candidate_path.is_relative_to(artifact_root)
    assert not tuple(path for path in destination.iterdir() if path.suffix == ".tmp")
    fixture = load_rolling_fcr_reference_fixture(first.candidate_path)
    assert len(fixture.solve_records) == 20
    candidate_text = first_candidate.decode("utf-8")
    assert "Academic license" not in candidate_text
    assert "hidden-user" not in candidate_text
    assert "Gurobi Optimizer version" not in candidate_text
    assert str(source_root) not in candidate_text


def test_normalizer_checks_every_digest_before_parsing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, source_root, artifact_root, manifest_path = _build_inputs(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"][0]["sha256"] = "0" * 64
    manifest_path.write_bytes(_canonical_bytes(manifest))
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )
    first_json = source_root / "results/01/2023-06-17.json"
    first_json.write_bytes(b"not json")

    with pytest.raises(RollingFCRReferenceNormalizationError, match="SHA-256"):
        normalize_rolling_fcr_reference_fixture(
            source_root=source_root,
            input_manifest=manifest_path,
            destination_dir=artifact_root / "reference/fcr_rolling_backtest",
            committed_fixture=COMMITTED_ROLLING_FIXTURE,
        )


def test_normalizer_rejects_log_segmentation_and_json_log_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, source_root, artifact_root, manifest_path = _build_inputs(tmp_path)
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )
    log_path = source_root / "code/14.log"
    log_path.write_text(
        log_path.read_text(encoding="utf-8").replace(
            "Test run: 2023-06-19",
            "Test run: 2023-06-18",
            1,
        ),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        if item["relative_path"] == "code/14.log":
            item["sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
    manifest_path.write_bytes(_canonical_bytes(manifest))
    with pytest.raises(RollingFCRReferenceNormalizationError, match="run marker|segment"):
        normalize_rolling_fcr_reference_fixture(
            source_root=source_root,
            input_manifest=manifest_path,
            destination_dir=artifact_root / "reference/fcr_rolling_backtest",
            committed_fixture=COMMITTED_ROLLING_FIXTURE,
        )

    repository, source_root, artifact_root, manifest_path = _build_inputs(tmp_path / "mismatch")
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )
    log_path = source_root / "code/11-2023-06-17.log"
    log_path.write_text(
        log_path.read_text(encoding="utf-8").replace(
            "6.000000000000e+00",
            "6.100000000000e+00",
            1,
        ),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["artifacts"]:
        if item["relative_path"] == "code/11-2023-06-17.log":
            item["sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
    manifest_path.write_bytes(_canonical_bytes(manifest))
    with pytest.raises(RollingFCRReferenceNormalizationError, match="objective|reconcile"):
        normalize_rolling_fcr_reference_fixture(
            source_root=source_root,
            input_manifest=manifest_path,
            destination_dir=artifact_root / "reference/fcr_rolling_backtest",
            committed_fixture=COMMITTED_ROLLING_FIXTURE,
        )


def test_normalizer_rejects_committed_destination_and_preserves_feature_013(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, source_root, artifact_root, manifest_path = _build_inputs(tmp_path)
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )
    governed = repository / COMMITTED_FEATURE_013_FIXTURE
    before = governed.read_bytes()
    before_digest = hashlib.sha256(before).hexdigest()

    with pytest.raises(RollingFCRReferenceNormalizationError, match="artifacts"):
        normalize_rolling_fcr_reference_fixture(
            source_root=source_root,
            input_manifest=manifest_path,
            destination_dir=repository / "tests/fixtures/fcr_rolling_backtest",
            committed_fixture=COMMITTED_ROLLING_FIXTURE,
        )
    normalize_rolling_fcr_reference_fixture(
        source_root=source_root,
        input_manifest=manifest_path,
        destination_dir=artifact_root / "reference/fcr_rolling_backtest",
        committed_fixture=COMMITTED_ROLLING_FIXTURE,
    )
    assert governed.read_bytes() == before
    assert hashlib.sha256(governed.read_bytes()).hexdigest() == before_digest


def test_normalizer_emits_ordered_semantic_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, source_root, artifact_root, manifest_path = _build_inputs(tmp_path)
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._REPOSITORY_ROOT",
        repository,
    )
    monkeypatch.setattr(
        "examples.fcr_rolling_backtest.normalize_reference_fixture._ARTIFACT_ROOT",
        artifact_root,
    )
    result = normalize_rolling_fcr_reference_fixture(
        source_root=source_root,
        input_manifest=manifest_path,
        destination_dir=artifact_root / "reference/fcr_rolling_backtest",
        committed_fixture=COMMITTED_ROLLING_FIXTURE,
    )
    paths = [item["field_path"] for item in result.semantic_differences]
    assert paths == sorted(paths)
    diff_payload = json.loads(result.semantic_diff_path.read_text(encoding="utf-8"))
    assert diff_payload["semantic_differences"] == list(result.semantic_differences)
