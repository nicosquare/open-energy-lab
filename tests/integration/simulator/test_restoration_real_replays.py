"""Bounded zero-network replays of the restricted French restoration references."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import urllib.request

import pytest

from examples.restoration_services.generate_reference_results import (
    AFRR_SCENARIO_FILENAME,
    EXPECTED_RESULTS_FILENAME,
    MFRR_SCENARIO_FILENAME,
    build_reference_case,
    build_reference_results_payload,
    load_reference_scenario,
)
from examples.restoration_services.run_offline_replays import (
    build_offline_audit,
    run_offline_replays,
)
from open_energy_lab.market.restoration_activation import (
    AFRRActivationTrajectory,
    MFRRActivationKind,
    MFRRActivationSequence,
    RestorationDirection,
)
from open_energy_lab.market.restoration_artifact import ObservationValueState
from open_energy_lab.simulator.restoration_settlement import SettlementAvailability


FIXTURES = Path("tests/fixtures/restoration")


@pytest.fixture(autouse=True)
def _offline_only(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("real reference replay attempted network access")

    real_getenv = os.getenv

    def guarded_getenv(key: str, default: str | None = None) -> str | None:
        if key in {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}:
            raise AssertionError(f"real reference replay read {key}")
        return real_getenv(key, default)

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(os, "getenv", guarded_getenv)


def _scenarios():
    return (
        load_reference_scenario(
            FIXTURES / AFRR_SCENARIO_FILENAME,
            fixture_directory=FIXTURES,
        ),
        load_reference_scenario(
            FIXTURES / MFRR_SCENARIO_FILENAME,
            fixture_directory=FIXTURES,
        ),
    )


def test_real_afrr_mapping_replay_and_proxy_settlement_are_exact() -> None:
    afrr, _mfrr = _scenarios()
    driver = next(
        item
        for item in afrr.market.series
        if item.series_id == "afrr_requested_need_upward"
    )
    price = next(
        item
        for item in afrr.market.series
        if item.series_id == "afrr_weighted_average_price_upward"
    )
    assert isinstance(afrr.activation, AFRRActivationTrajectory)
    assert afrr.payload["output_label"] == "derived_simulation"
    assert afrr.mapping.asset_allocation_fraction == 0.001
    assert afrr.mapping.driver_semantics == "afrr_requested_need"
    assert driver.source_field == "upward_afrr_requested_need"
    assert price.source_field == (
        "upward_weighted_average_price_afrr_activated_for_fr"
    )
    assert afrr.mapping.source_series_fingerprints == (
        driver.series_fingerprint,
    )
    assert [
        item.requested_balancing_power_kw for item in afrr.activation.samples
    ] == [-425.0, -315.0, -290.0, -345.0]
    assert [
        item.interval.start_utc for item in afrr.activation.samples
    ] == sorted(item.interval.start_utc for item in afrr.activation.samples)

    case = build_reference_case(afrr)

    assert case.replay.totals.requested_activation_energy_kwh == 343.75
    assert case.replay.totals.delivered_activation_energy_kwh == 343.75
    assert case.replay.totals.undelivered_activation_energy_kwh == 0.0
    assert case.replay.directional_performance[
        RestorationDirection.UPWARD
    ].delivered_energy_kwh == 343.75
    assert case.settlement.availability is SettlementAvailability.AVAILABLE
    assert case.settlement.price_mapping_labels == ("scenario_proxy",)
    assert case.settlement.upward_activation_revenue_eur == pytest.approx(
        59.2551625, abs=1e-6
    )
    assert case.settlement.downward_activation_revenue_eur == 0.0
    assert case.settlement.degradation_cost_eur == 6.875
    assert case.settlement.net_result_eur == pytest.approx(52.3801625, abs=1e-6)
    assert case.settlement.net_result_eur == pytest.approx(
        case.settlement.gross_revenue_eur
        - case.settlement.non_performance_penalty_eur
        - case.settlement.degradation_cost_eur,
        abs=1e-6,
    )
    assert all(
        afrr.battery.min_soc <= sample.state.soc <= afrr.battery.max_soc
        and abs(sample.delivered_combined_power_kw) <= 500.0
        for sample in case.replay.samples
    )


def test_real_mfrr_preserves_sa_and_reports_sparse_da_without_fabrication() -> None:
    _afrr, mfrr = _scenarios()
    driver = next(
        item
        for item in mfrr.market.series
        if item.series_id == "mfrr_sa_requested_volume_downward"
    )
    satisfied = next(
        item
        for item in mfrr.market.series
        if item.series_id == "mfrr_sa_satisfied_need_downward"
    )
    clearing = next(
        item
        for item in mfrr.market.series
        if item.series_id == "mfrr_clearing_price_downward"
    )
    assert isinstance(mfrr.activation, MFRRActivationSequence)
    assert mfrr.payload["direct_activation_status"].startswith("source-null")
    assert len(mfrr.activation.events) == 1
    event = mfrr.activation.events[0]
    assert event.kind is MFRRActivationKind.SCHEDULED
    assert event.direction is RestorationDirection.DOWNWARD
    assert event.requested_power_kw == 357.0
    assert event.hold_seconds == 900.0
    assert event.requested_energy_kwh == 89.25
    assert driver.source_field == "total_requested_volume_SA"
    assert satisfied.source_field == "total_satisfied_need_SA"
    assert satisfied.observations[0].value == 300.0
    assert clearing.source_field == "clearing_price"
    assert clearing.observations[0].value == 64.83
    assert mfrr.mapping.source_series_fingerprints == (
        driver.series_fingerprint,
    )
    direct = next(
        series
        for series in mfrr.market.series
        if series.series_id == "mfrr_da_requested_volume_downward"
    )
    assert direct.observations[0].value_state is ObservationValueState.SOURCE_NULL

    case = build_reference_case(mfrr)

    assert case.replay.totals.requested_activation_energy_kwh == 89.25
    assert case.replay.totals.delivered_activation_energy_kwh == 89.25
    assert case.replay.kind_performance[
        MFRRActivationKind.SCHEDULED
    ].delivered_energy_kwh == 89.25
    assert case.replay.kind_performance[
        MFRRActivationKind.DIRECT
    ].requested_energy_kwh == 0.0
    assert case.settlement.availability is SettlementAvailability.AVAILABLE
    assert case.settlement.price_mapping_labels == ("scenario_proxy",)
    assert case.settlement.activation_revenue_by_mfrr_kind_eur == {
        "SCHEDULED": pytest.approx(5.7860775, abs=1e-6),
        "DIRECT": 0.0,
    }
    assert case.settlement.downward_activation_revenue_eur == pytest.approx(
        5.7860775, abs=1e-6
    )
    assert case.settlement.degradation_cost_eur == pytest.approx(1.785, abs=1e-6)
    assert case.settlement.net_result_eur == pytest.approx(4.0010775, abs=1e-6)
    assert all(
        mfrr.battery.min_soc <= sample.state.soc <= mfrr.battery.max_soc
        and abs(sample.delivered_combined_power_kw) <= 500.0
        for sample in case.replay.samples
    )


def test_real_result_generation_is_two_run_and_fixture_byte_stable() -> None:
    first = build_reference_results_payload(FIXTURES)
    second = build_reference_results_payload(FIXTURES)
    recorded = json.loads((FIXTURES / EXPECTED_RESULTS_FILENAME).read_bytes())

    assert first == second == recorded
    assert first["result_set_fingerprint"] == (
        "abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f"
    )
    assert json.dumps(first, allow_nan=False, sort_keys=True) == json.dumps(
        second, allow_nan=False, sort_keys=True
    )


def test_offline_runner_publishes_concise_audit_tables(capsys) -> None:
    source = Path(
        "examples/restoration_services/run_offline_replays.py"
    ).read_text(encoding="utf-8")
    assert "open_energy_lab.market.rte" not in source
    assert "fetch_rte" not in source
    assert "RTE_CLIENT_ID" not in source
    assert "RTE_CLIENT_SECRET" not in source

    audit = build_offline_audit(FIXTURES)
    assert audit["result_set_fingerprint"] == (
        "abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f"
    )
    assert audit["notebook_display_fingerprint"] == (
        "88ab88e3859e4fe81555651468bcc9e4c474db43feee11ecd1eef6b18568e976"
    )
    assert {row["product"] for row in audit["cases"]} == {"AFRR", "MFRR"}
    assert all(row["scenario_label"] == "derived_simulation" for row in audit["cases"])
    assert all(row["price_label"] == "scenario_proxy" for row in audit["cases"])

    assert run_offline_replays(FIXTURES) == 0
    output = capsys.readouterr().out
    assert "SOURCE AND MAPPING AUDIT" in output
    assert "PHYSICAL REPLAY AUDIT" in output
    assert "SETTLEMENT AUDIT" in output
    assert "derived_simulation" in output
    assert "scenario_proxy" in output
    assert "DIRECT source status: source-null; no event fabricated" in output
    assert "notebook_display_fingerprint=88ab88e" in output
