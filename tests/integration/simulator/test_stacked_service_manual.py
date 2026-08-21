"""End-to-end assertions for the published four-hour arithmetic oracle."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import json
from pathlib import Path
import socket

import pytest

from tests.unit.market.test_artifact import (
    _build_artifact,
    _canonical_interval_payload,
    _valid_artifact_input,
)
from tests.unit.simulator.test_stacked_service import (
    _activation_trace,
    _battery,
    _energy_schedule,
    _fcr_schedule,
    _replay_request,
    _require,
    _time_contract,
)


FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "fixtures"
    / "market"
    / "manual_stacked_service_v1.json"
)
TOLERANCE = 1e-6


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _manual_market_artifact(fixture: dict[str, object]):
    payload = deepcopy(_valid_artifact_input())
    period = fixture["period"]
    assert isinstance(period, dict)
    start = _instant(period["start_utc"])
    end = _instant(period["end_utc"])
    canonical_period = _canonical_interval_payload(start, end)
    payload["artifact_id"] = "manual-stacked-market-v1"
    payload["requested_period"] = canonical_period
    payload["actual_covered_period"] = canonical_period

    energy_schedule = fixture["energy_schedule"]
    fcr_schedule = fixture["fcr_schedule"]
    assert isinstance(energy_schedule, dict)
    assert isinstance(fcr_schedule, dict)
    series = payload["series"]
    prices = energy_schedule["prices_eur_per_mwh"]
    energy_observations = series["day_ahead_price"]["observations"][:4]
    for observation, price in zip(energy_observations, prices, strict=True):
        observation["value"] = price
    series["day_ahead_price"]["observations"] = energy_observations

    volume_observation = series["fcr_contracted_volume"]["observations"][0]
    volume_observation["value"] = fcr_schedule["market_volume_mw"][0]
    series["fcr_contracted_volume"]["observations"] = [volume_observation]
    price_observation = series["fcr_capacity_price"]["observations"][0]
    price_observation["value"] = fcr_schedule[
        "capacity_price_eur_per_mw_per_h"
    ][0]
    series["fcr_capacity_price"]["observations"] = [price_observation]

    for window in payload["query_windows"]:
        window["start_utc"] = period["start_utc"]
        window["end_utc"] = period["end_utc"]
    for document in payload["source_documents"]:
        document["document_period"] = canonical_period
    return _build_artifact(payload)


def test_manual_fixture_encodes_the_independent_arithmetic_oracle() -> None:
    fixture = _fixture()

    assert fixture["schema_version"] == "oel.stacked-service-manual.v1"
    assert fixture["interval_convention"] == "start-inclusive/end-exclusive"
    battery = fixture["battery"]
    energy = fixture["energy_schedule"]
    fcr = fixture["fcr_schedule"]
    activation = fixture["activation"]
    expected = fixture["expected"]
    assert battery["capacity_kwh"] == 4.0
    assert battery["initial_stored_energy_kwh"] == 2.0
    assert energy["power_kw"] == [1.0, 0.0, 0.0, -1.0]
    assert activation["values"] == [1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0, -1.0]
    assert fcr["capacity_kw"] == [1.0]
    independent_energy_revenue = sum(
        -power * price / 1000.0
        for power, price in zip(
            energy["power_kw"],
            energy["prices_eur_per_mwh"],
            strict=True,
        )
    )
    independent_fcr_revenue = (
        fcr["capacity_kw"][0]
        / 1000.0
        * fcr["capacity_price_eur_per_mw_per_h"][0]
        * 4.0
    )
    assert independent_energy_revenue == pytest.approx(0.05, abs=TOLERANCE)
    assert independent_fcr_revenue == pytest.approx(0.08, abs=TOLERANCE)
    assert expected["total_profit_eur"] == pytest.approx(
        independent_energy_revenue + independent_fcr_revenue,
        abs=TOLERANCE,
    )
    assert len(fixture["sample_assertions"]) == 8


def test_manual_stacked_service_replay_matches_every_published_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    period = fixture["period"]
    start = _instant(period["start_utc"])
    end = _instant(period["end_utc"])
    energy = fixture["energy_schedule"]
    fcr = fixture["fcr_schedule"]
    activation = fixture["activation"]
    expected = fixture["expected"]

    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("manual replay attempted network access")

    monkeypatch.setattr(socket, "socket", _network_forbidden)
    request = _replay_request(
        market_artifact=_manual_market_artifact(fixture),
        activation_trace=_activation_trace(
            activation["values"],
            resolution="PT30M",
            start=start,
            end=end,
        ),
        battery=_battery(
            capacity_kwh=4.0,
            max_charge_kw=2.0,
            max_discharge_kw=2.0,
            initial_soc=0.5,
            min_soc=0.0,
            max_soc=1.0,
            efficiency=1.0,
        ),
        energy_schedule=_energy_schedule(energy["power_kw"], start=start, end=end),
        fcr_schedule=_fcr_schedule(fcr["capacity_kw"], start=start, end=end),
        time_contract=_time_contract(
            activation_resolution="PT30M",
            checkpoint_resolution="PT30M",
            start=start,
            end=end,
        ),
    )
    replay = _require("replay_stacked_services")

    result = replay(request)
    repeated = replay(request)

    assert result.validation_status == "validated"
    assert len(result.samples) == 8
    assert result.saturation_events == ()
    for actual, oracle in zip(
        result.samples,
        fixture["sample_assertions"],
        strict=True,
    ):
        assert actual.interval.start_utc == _instant(oracle["start_utc"])
        assert actual.interval.end_utc == _instant(oracle["end_utc"])
        for field in (
            "baseline_power_kw",
            "activation",
            "requested_fcr_power_kw",
            "requested_combined_power_kw",
            "delivered_fcr_power_kw",
            "delivered_combined_power_kw",
            "stored_energy_before_kwh",
            "stored_energy_after_kwh",
        ):
            assert getattr(actual, field) == pytest.approx(
                oracle[field],
                abs=TOLERANCE,
            )
        assert actual.signed_tracking_error_kw == pytest.approx(0.0, abs=TOLERANCE)
        assert actual.non_delivery_energy_kwh == pytest.approx(0.0, abs=TOLERANCE)

    stored_states = [result.state_checkpoints[0].stored_energy_kwh] + [
        sample.stored_energy_after_kwh for sample in result.samples
    ]
    assert stored_states == pytest.approx(expected["stored_energy_kwh"], abs=TOLERANCE)
    assert [sample.requested_combined_power_kw for sample in result.samples] == pytest.approx(
        expected["requested_combined_power_kw"], abs=TOLERANCE
    )
    assert [sample.delivered_combined_power_kw for sample in result.samples] == pytest.approx(
        expected["delivered_combined_power_kw"], abs=TOLERANCE
    )
    assert result.throughput_kwh == pytest.approx(expected["throughput_kwh"], abs=TOLERANCE)
    assert result.tracking_summary["non_delivery_energy_kwh"] == pytest.approx(
        expected["non_delivery_energy_kwh"], abs=TOLERANCE
    )
    assert result.settlement.day_ahead_energy_revenue_eur == pytest.approx(
        expected["day_ahead_energy_revenue_eur"], abs=TOLERANCE
    )
    assert result.settlement.fcr_capacity_revenue_eur == pytest.approx(
        expected["fcr_capacity_revenue_eur"], abs=TOLERANCE
    )
    assert result.settlement.penalty_eur == pytest.approx(
        expected["penalty_eur"], abs=TOLERANCE
    )
    assert result.settlement.total_profit_eur == pytest.approx(
        expected["total_profit_eur"], abs=TOLERANCE
    )
    assert result.trace_fingerprint == repeated.trace_fingerprint
    assert result.result_fingerprint == repeated.result_fingerprint
