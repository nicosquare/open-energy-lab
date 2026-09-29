from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from types import MappingProxyType

import pytest

from examples.fcr_bid_evaluation.run_reference_parity import (
    assemble_reference_request,
)
from oel_validation.reference_schedule_mapping import map_reference_decisions_to_schedules
from open_energy_lab.market.activation import (
    ActivationImportRequest,
    import_regulation_activation_trace,
)
from oel_validation.reference_fcr import (
    ReferenceFCRIntegrityError,
    ReferenceFCRValidationError,
    build_reference_market_context,
    canonical_reference_json_bytes,
    golden_reference_fixture_from_dict,
    load_golden_reference_fixture,
)
from open_energy_lab.simulator import evaluate_fixed_fcr_bid


FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)


def _payload() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _refingerprint(payload: dict[str, object]) -> None:
    semantic = deepcopy(payload)
    semantic.pop("fixture_fingerprint", None)
    payload["fixture_fingerprint"] = hashlib.sha256(
        json.dumps(
            semantic,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def test_golden_reference_fixture_has_locked_provenance_and_counts() -> None:
    fixture = load_golden_reference_fixture(FIXTURE_PATH)

    assert fixture.schema_version == "oel.fcr-reference-aggregate.v1"
    assert fixture.reference_provenance["reference_commit"] == (
        "7e44738bb30e5c8204efe40103b9be4c2203685c"
    )
    assert fixture.reference_provenance["original_result_sha256"] == (
        "8c13f8318d533c35755e90e4e45bcef336cb7b31c09afccbe616844acbddc1e6"
    )
    assert len(fixture.rounded_x0_kw) == 24
    assert len(fixture.rounded_xr_kw) == 6
    assert len(fixture.p0_eur_per_kwh) == 24
    assert len(fixture.pr_eur_per_kw_block) == 6
    assert fixture.external_activation.selected_row_count == 8640
    assert fixture.fixture_fingerprint == (
        "6bce7f00bb38b257a6f5e4186a8b8dab06d7f5f41336238b499b153b3f7a59fd"
    )


def test_fixture_runtime_and_redistribution_provenance_is_explicit() -> None:
    fixture = load_golden_reference_fixture(FIXTURE_PATH)

    assert fixture.runtime_provenance["generation_runtime"]["status"] == (
        "not_recorded"
    )
    assert fixture.runtime_provenance["locked_manifest"]["julia_version"] == "1.10.1"
    assert fixture.runtime_provenance["locked_manifest"]["packages"] == {
        "CSV": "0.10.15",
        "DataFrames": "1.7.0",
        "Gurobi": "1.3.1",
        "Gurobi_jll": "11.0.3",
        "JSON": "0.21.4",
        "JuMP": "1.23.3",
    }
    assert fixture.redistribution_status["activation_csv"] == "external_only"
    assert all(
        value is False
        for value in fixture.external_activation.redistribution_policy.values()
    )


def test_expected_and_unsupported_reference_evidence_are_disjoint() -> None:
    fixture = load_golden_reference_fixture(FIXTURE_PATH)
    expected = {item.field_id for item in fixture.expected_fields}
    unsupported = {item.field_id for item in fixture.unsupported_fields}

    assert expected.isdisjoint(unsupported)
    assert {
        "settlement.total_profit_eur",
        "physical.terminal_stored_energy_kwh",
        "physical.minimum_delivered_power_kw",
    } <= expected
    assert {
        "physical.detailed_trace",
        "physical.directional_fcr_energy",
        "physical.throughput_kwh",
    } <= unsupported


def test_fixture_semantics_have_byte_stable_canonical_serialization() -> None:
    first = load_golden_reference_fixture(FIXTURE_PATH)
    second = load_golden_reference_fixture(FIXTURE_PATH)

    assert canonical_reference_json_bytes(first.to_dict()) == (
        canonical_reference_json_bytes(second.to_dict())
    )
    assert first.fixture_fingerprint == second.fixture_fingerprint
    assert first.mapping.mapping_fingerprint == second.mapping.mapping_fingerprint
    assert (
        first.precision_policy.policy_fingerprint
        == second.precision_policy.policy_fingerprint
    )


def test_golden_fixture_offline_evaluation_is_canonically_stable_without_csv() -> None:
    fixture = load_golden_reference_fixture(FIXTURE_PATH)
    period = fixture.mapping.target_period
    step = timedelta(seconds=10)
    activation = import_regulation_activation_trace(
        ActivationImportRequest(
            source_name="Feature 012 offline determinism oracle",
            source_locator="authored-zero-activation",
            source_revision="v1",
            source_timezone="Europe/Paris",
            requested_start_utc=period.start_utc,
            requested_end_utc=period.end_utc,
            source_resolution="PT10S",
            source_value_kind="interval_average",
            source_sign_meaning="positive is upward/discharge",
            normalization_rule={
                "conversion": "identity",
                "formula": "activation",
                "point_to_interval": "already_interval_average",
                "clip_min": -1.0,
                "clip_max": 1.0,
                "target_sign": "positive is upward/discharge",
            },
            redistribution_basis={"source": "project-authored test data"},
        ),
        [
            {
                "start_utc": period.start_utc + index * step,
                "end_utc": period.start_utc + (index + 1) * step,
                "value": 0.0,
                "source_value": 0.0,
                "source_unit": "dimensionless",
            }
            for index in range(8640)
        ],
        trace_id="feature-012-offline-zero-reference-activation-v1",
        created_at_utc=datetime(2026, 8, 26, tzinfo=UTC),
    )
    zero_activation_bounds = {
        "charge_energy_kwh": 0.012,
        "discharge_energy_kwh": 0.012,
        "stored_energy_kwh": 0.012 / 0.92,
        "power_extrema_kw": 0.0005,
        "day_ahead_revenue_eur": 0.001073575,
        "fcr_capacity_revenue_eur": 0.00037976,
        "activation_revenue_eur": 0.0,
        "combined_fcr_revenue_eur": 0.00037976,
        "total_revenue_eur": 0.001453335,
    }
    policy = replace(
        fixture.precision_policy,
        field_bounds=MappingProxyType(
            {
                key: replace(value, decision_bound=zero_activation_bounds[key])
                for key, value in fixture.precision_policy.field_bounds.items()
            }
        ),
    )
    fixture = replace(fixture, precision_policy=policy)
    request = assemble_reference_request(fixture=fixture, activation_trace=activation)

    first = evaluate_fixed_fcr_bid(request)
    repeated = evaluate_fixed_fcr_bid(request)

    assert first.status == "settled"
    assert first.canonical_bytes() == repeated.canonical_bytes()
    assert request.plan.plan_fingerprint == repeated.plan_fingerprint
    assert request.evaluation_input_fingerprint == (
        repeated.evaluation_input_fingerprint
    )
    assert first.trace_fingerprint == repeated.trace_fingerprint
    assert first.settlement_fingerprint == repeated.settlement_fingerprint
    assert first.comparison_fingerprint == repeated.comparison_fingerprint
    assert first.result_fingerprint == repeated.result_fingerprint


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.__setitem__("schema_version", "unsupported"), "schema"),
        (
            lambda data: data["fixed_decisions"]["rounded_x0_kw"].pop(),
            "24",
        ),
        (
            lambda data: data["runtime_provenance"]["locked_manifest"][
                "packages"
            ].pop("JuMP"),
            "package provenance",
        ),
        (
            lambda data: data["redistribution_status"].pop("activation_csv"),
            "redistribution",
        ),
        (
            lambda data: data["expected_fields"][0].__setitem__(
                "reference_field_path", "not-a-pointer"
            ),
            "JSON pointer",
        ),
        (
            lambda data: data["unsupported_fields"].append(
                deepcopy(data["unsupported_fields"][0])
            ),
            "unique",
        ),
    ],
)
def test_fixture_rejects_schema_count_pointer_and_provenance_errors(
    mutation,
    message: str,
) -> None:
    payload = _payload()
    mutation(payload)
    _refingerprint(payload)

    with pytest.raises(ReferenceFCRValidationError, match=message):
        golden_reference_fixture_from_dict(payload)


def test_fixture_rejects_nonfinite_values_before_exposure() -> None:
    payload = _payload()
    payload["fixed_decisions"]["rounded_x0_kw"][0] = float("inf")
    payload["fixture_fingerprint"] = "0" * 64

    with pytest.raises(ReferenceFCRValidationError, match="finite|fingerprint"):
        golden_reference_fixture_from_dict(payload)


def test_fixture_detects_digest_tampering() -> None:
    payload = _payload()
    payload["fixed_decisions"]["rounded_x0_kw"][0] = 0.0

    with pytest.raises(ReferenceFCRIntegrityError, match="fingerprint mismatch"):
        golden_reference_fixture_from_dict(payload)


def test_offline_fixture_assembly_maps_existing_schedule_and_price_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    real_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        rendered = path.as_posix()
        opened.append(rendered)
        assert "baselines/" not in rendered
        assert "artifacts/reference/" not in rendered
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    fixture = load_golden_reference_fixture(FIXTURE_PATH)
    mapped = map_reference_decisions_to_schedules(fixture)
    context = build_reference_market_context(
        fixture,
        energy_schedule=mapped.energy_schedule,
        fcr_schedule=mapped.fcr_schedule,
    )

    assert opened == [FIXTURE_PATH.as_posix()]
    assert len(mapped.energy_schedule.intervals) == 24
    assert len(mapped.fcr_schedule.intervals) == 6
    assert len(context.day_ahead_prices) == 24
    assert len(context.fcr_capacity_prices) == 6
    assert context.day_ahead_prices[0].source_value == 0.12678
    assert context.day_ahead_prices[0].canonical_value == 126.78
    assert context.day_ahead_prices[0].canonical_unit == "EUR/MWh"
    assert context.fcr_capacity_prices[0].source_value == 0.06672
    assert context.fcr_capacity_prices[0].canonical_unit == "EUR/kW/block"
    assert all(
        reference.startswith("reference_accepted_fcr_bid:")
        for reference in context.accepted_bid_evidence
    )


def test_routine_fixture_path_never_consults_network_environment_or_tooling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    real_open = Path.open

    def guarded_open(path: Path, *args, **kwargs):
        rendered = path.as_posix()
        opened.append(rendered)
        assert rendered == FIXTURE_PATH.as_posix()
        return real_open(path, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "routine fixture validation must not inspect network, environment, "
            "Julia, Gurobi, the external CSV, or the reference submodule"
        )

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "getenv", forbidden)

    first = load_golden_reference_fixture(FIXTURE_PATH)
    repeated = load_golden_reference_fixture(FIXTURE_PATH)
    first_mapping = map_reference_decisions_to_schedules(first)
    repeated_mapping = map_reference_decisions_to_schedules(repeated)

    assert opened == [FIXTURE_PATH.as_posix(), FIXTURE_PATH.as_posix()]
    assert first.fixture_fingerprint == repeated.fixture_fingerprint
    assert first_mapping.mapping_fingerprint == repeated_mapping.mapping_fingerprint
    assert (
        first_mapping.energy_schedule.schedule_fingerprint
        == repeated_mapping.energy_schedule.schedule_fingerprint
    )
    assert (
        first_mapping.fcr_schedule.schedule_fingerprint
        == repeated_mapping.fcr_schedule.schedule_fingerprint
    )


def test_objective_metadata_is_not_the_realized_profit_evidence() -> None:
    fixture = load_golden_reference_fixture(FIXTURE_PATH)
    expected = {item.field_id: item.expected_value for item in fixture.expected_fields}

    assert expected["plan.objective"] == 11.028
    assert expected["plan.objective_bound"] == 11.028
    assert expected["settlement.total_profit_eur"] == 10.749
    assert expected["plan.objective"] != expected["settlement.total_profit_eur"]
