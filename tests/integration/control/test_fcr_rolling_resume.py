"""Strict persistence and resume evidence for Feature 015."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
import json

import pytest

from open_energy_lab.control import (
    RollingFCRValidationError,
    aggregate_rolling_fcr_records,
    assess_rolling_fcr_resume,
    load_rolling_fcr_study_result,
    run_rolling_fcr_study,
)
from tests.fcr_rolling_case_utils import (
    AUTHORED_DELIVERY_DATES,
    build_authored_activation_trace,
    build_authored_day_input,
    build_authored_manifest,
    build_authored_zero_prices,
)


def _zero_input(manifest: object, delivery_date: date) -> object:
    original = build_authored_day_input(manifest, delivery_date)
    prices = build_authored_zero_prices(delivery_date)
    return replace(
        original,
        prices=prices,
        producer_input_fingerprints={
            **original.producer_input_fingerprints,
            "market_prices": prices.price_input_fingerprint,
        },
    )


@pytest.fixture(scope="module")
def completed_authored_study() -> tuple[object, tuple[object, ...], dict[date, object], object]:
    base = build_authored_manifest(
        "script-13-arbitrage-only-midnight-v1",
        state_carry_policy="source_three_decimal",
    )
    manifest = replace(base, dates=base.dates[:2])
    inputs = tuple(_zero_input(manifest, item.delivery_date) for item in manifest.dates)
    traces = {
        item.delivery_date: build_authored_activation_trace(item.delivery_date)
        for item in manifest.dates
    }
    result = run_rolling_fcr_study(manifest, inputs, activation_traces=traces)
    return manifest, inputs, traces, result


def test_exact_resume_reuses_evidence_and_matches_uninterrupted_semantics(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_energy_lab.control import _fcr_rolling_orchestrator as orchestrator

    manifest, inputs, traces, uninterrupted = completed_authored_study

    def unexpected_solve(*args: object, **kwargs: object) -> object:
        raise AssertionError("complete resume must not load or invoke a solver")

    monkeypatch.setattr(orchestrator, "_solve_midnight_problem", unexpected_solve)

    evidence = assess_rolling_fcr_resume(manifest, uninterrupted)
    resumed = run_rolling_fcr_study(
        manifest,
        inputs,
        activation_traces=traces,
        resume_from=uninterrupted,
    )

    assert evidence.status == "compatible"
    assert evidence.reused_envelope_fingerprints == tuple(
        item.envelope_fingerprint for item in uninterrupted.records
    )
    assert resumed.semantic_fingerprint == uninterrupted.semantic_fingerprint
    assert resumed.records is uninterrupted.records
    assert resumed.resume_lineage is not None


def test_prefix_resume_reuses_completed_record_and_matches_uninterrupted_result(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
) -> None:
    manifest, inputs, traces, uninterrupted = completed_authored_study
    first_record = uninterrupted.records[0]
    first_segment = replace(
        uninterrupted.continuity_segments[0],
        end_date=first_record.classification.delivery_date,
    )
    partial = replace(
        uninterrupted,
        records=(first_record,),
        continuity_segments=(first_segment,),
        state_links=(),
        aggregate_metrics=aggregate_rolling_fcr_records(
            manifest, (first_record,)
        ),
        requested_day_input_fingerprints={
            first_record.classification.delivery_date.isoformat(): (
                uninterrupted.requested_day_input_fingerprints[
                    first_record.classification.delivery_date.isoformat()
                ]
            )
        },
        supplied_activation_fingerprints={
            first_record.classification.delivery_date.isoformat(): (
                uninterrupted.supplied_activation_fingerprints[
                    first_record.classification.delivery_date.isoformat()
                ]
            )
        },
        completeness_status="partial",
        resume_lineage=None,
    )

    resumed = run_rolling_fcr_study(
        manifest,
        inputs,
        activation_traces=traces,
        resume_from=partial,
    )

    assert resumed.records[0] is first_record
    assert resumed.semantic_fingerprint == uninterrupted.semantic_fingerprint
    assert resumed.resume_lineage is not None
    assert resumed.resume_lineage.prior_result_semantic_fingerprint == (
        partial.semantic_fingerprint
    )


@pytest.mark.parametrize(
    "changed_manifest",
    (
        lambda manifest: build_authored_manifest(
            "script-15-restriction-rolling-midnight-v1"
        ),
        lambda manifest: replace(
            manifest,
            dates=tuple(reversed(manifest.dates)),
        ),
        lambda manifest: replace(
            manifest,
            settlement_profile="different-settlement-v1",
        ),
        lambda manifest: replace(
            manifest,
            reference_lineage={**manifest.reference_lineage, "fixture": "b" * 64},
        ),
    ),
)
def test_resume_fails_closed_for_any_manifest_semantic_change(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
    changed_manifest: object,
) -> None:
    manifest, _, _, result = completed_authored_study
    try:
        changed = changed_manifest(manifest)
    except RollingFCRValidationError:
        return

    evidence = assess_rolling_fcr_resume(changed, result)

    assert evidence.status == "incompatible"
    assert evidence.diagnostics


def test_resume_rejects_solver_numeric_rounding_acceptance_and_source_changes(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
) -> None:
    manifest, _, _, result = completed_authored_study
    changed_solver = replace(
        manifest.solve_policy,
        time_limit_seconds=manifest.solve_policy.time_limit_seconds + 1.0,
    )
    solver_manifest = replace(
        manifest,
        solve_policy=changed_solver,
        numeric_policy=replace(
            manifest.numeric_policy,
            solve_policy_fingerprint=changed_solver.solve_policy_fingerprint,
        ),
    )
    rounding_manifest = build_authored_manifest(
        "script-15-restriction-rolling-midnight-v1",
        state_carry_policy="native_full_precision",
    )
    acceptance_manifest = replace(
        manifest,
        acceptance_policy=replace(
            manifest.acceptance_policy,
            assumption_statement="A different explicitly fingerprinted acceptance assumption.",
        ),
    )
    source_manifest = replace(
        manifest,
        day_ahead_descriptor=replace(
            manifest.day_ahead_descriptor,
            content_sha256="e" * 64,
        ),
    )

    for changed in (
        solver_manifest,
        rounding_manifest,
        acceptance_manifest,
        source_manifest,
    ):
        evidence = assess_rolling_fcr_resume(changed, result)
        assert evidence.status == "incompatible"
        assert "resume_mismatch:manifest_fingerprint" in evidence.diagnostics


def test_resume_rejects_changed_continuity_and_carried_state_evidence(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
) -> None:
    manifest, _, _, result = completed_authored_study
    changed_segment = replace(
        result.continuity_segments[0],
        start_reason="caller_supplied",
        source_state_fingerprint="d" * 64,
    )
    changed_continuity = replace(
        result,
        continuity_segments=(changed_segment,),
    )
    link = result.state_links[0]
    delta = 0.0001
    changed_link = replace(
        link,
        replay_checkpoint_kwh=link.replay_checkpoint_kwh + delta,
        carried_stored_energy_kwh=link.carried_stored_energy_kwh + delta,
        source_interval_kwh=(
            link.source_interval_kwh[0] + delta,
            link.source_interval_kwh[1] + delta,
        ),
        successor_initial_stored_energy_kwh=(
            link.successor_initial_stored_energy_kwh + delta
        ),
    )
    changed_state = replace(result, state_links=(changed_link,))

    assert assess_rolling_fcr_resume(manifest, changed_continuity).status == (
        "incompatible"
    )
    assert assess_rolling_fcr_resume(manifest, changed_state).status == "incompatible"


def test_resume_rejects_changed_day_input_activation_or_nested_record(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
) -> None:
    manifest, inputs, traces, result = completed_authored_study
    changed_input = replace(
        inputs[0],
        producer_input_fingerprints={
            **inputs[0].producer_input_fingerprints,
            "authored_change": "f" * 64,
        },
    )
    original_trace = traces[AUTHORED_DELIVERY_DATES[0]]
    changed_trace = build_authored_activation_trace(
        AUTHORED_DELIVERY_DATES[0],
        values=(0.25,) * len(original_trace.samples),
    )
    tampered_revision = replace(
        result.records[0].latest_revision,
        objective_value_eur=result.records[0].latest_revision.objective_value_eur + 1.0,
    )
    tampered_record = replace(
        result.records[0],
        revisions=(*result.records[0].revisions[:-1], tampered_revision),
    )
    tampered_result = replace(result, records=(tampered_record, *result.records[1:]))

    with pytest.raises(RollingFCRValidationError, match="day input"):
        run_rolling_fcr_study(
            manifest,
            (changed_input, *inputs[1:]),
            activation_traces=traces,
            resume_from=result,
        )
    with pytest.raises(RollingFCRValidationError, match="activation"):
        run_rolling_fcr_study(
            manifest,
            inputs,
            activation_traces={**traces, AUTHORED_DELIVERY_DATES[0]: changed_trace},
            resume_from=result,
        )
    assert assess_rolling_fcr_resume(manifest, tampered_result).status == "incompatible"


def test_round_trip_loader_recomputes_every_nested_fingerprint(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
    tmp_path: object,
) -> None:
    _, _, _, result = completed_authored_study
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result.to_dict()), encoding="utf-8")

    loaded = load_rolling_fcr_study_result(result_path)

    assert loaded == result
    assert loaded.semantic_fingerprint == result.semantic_fingerprint
    assert loaded.to_dict() == result.to_dict()


def test_loader_ignores_volatile_runtime_for_identity_but_detects_solver_version(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
    tmp_path: object,
) -> None:
    _, _, _, result = completed_authored_study
    payload = result.to_dict()
    payload["runtime_metadata"] = {
        **payload["runtime_metadata"],
        "started_at_utc": "2026-08-28T00:00:00Z",
        "finished_at_utc": "2026-08-28T00:10:00Z",
        "duration_seconds": 600.0,
        "host": "research-host",
        "pid": 123,
        "output_path": "/private/result.json",
    }
    volatile_path = tmp_path / "volatile.json"
    volatile_path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_rolling_fcr_study_result(volatile_path)
    assert loaded.semantic_fingerprint == result.semantic_fingerprint

    changed_solver = result.to_dict()
    changed_solver["records"][0]["revisions"][0]["runtime_metadata"]["backend"][
        "solver_version"
    ] = "9.9.9"
    solver_path = tmp_path / "changed-solver.json"
    solver_path.write_text(json.dumps(changed_solver), encoding="utf-8")
    with pytest.raises(
        RollingFCRValidationError,
        match="stable_runtime_evidence|revision_fingerprint",
    ):
        load_rolling_fcr_study_result(solver_path)


def test_loader_rejects_unknown_schema_keys_and_nested_tampering(
    completed_authored_study: tuple[object, tuple[object, ...], dict[date, object], object],
    tmp_path: object,
) -> None:
    _, _, _, result = completed_authored_study
    unknown = result.to_dict()
    unknown["unexpected"] = True
    unknown_path = tmp_path / "unknown.json"
    unknown_path.write_text(json.dumps(unknown), encoding="utf-8")
    with pytest.raises(RollingFCRValidationError, match="unknown keys"):
        load_rolling_fcr_study_result(unknown_path)

    tampered = result.to_dict()
    tampered["records"][0]["revisions"][0]["problem_fingerprint"] = "f" * 64
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RollingFCRValidationError, match="revision_fingerprint"):
        load_rolling_fcr_study_result(tampered_path)


def test_process_integrity_errors_are_not_normalized_as_failed_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from open_energy_lab.control import _fcr_rolling_orchestrator as orchestrator

    base = build_authored_manifest("script-12-restriction-reset-midnight-v1")
    manifest = replace(base, dates=base.dates[:1])
    day_input = _zero_input(manifest, manifest.dates[0].delivery_date)

    def fail_integrity(*args: object, **kwargs: object) -> object:
        raise MemoryError("process integrity unavailable")

    monkeypatch.setattr(orchestrator, "_solve_day", fail_integrity)
    with pytest.raises(MemoryError, match="process integrity"):
        run_rolling_fcr_study(manifest, (day_input,))
