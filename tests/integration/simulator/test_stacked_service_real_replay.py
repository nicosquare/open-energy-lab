"""Gated zero-network replay and benchmark for the selected French day."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import socket
from time import perf_counter

import pytest

from open_energy_lab.market import (
    load_market_data_artifact,
    load_regulation_activation_trace,
)
from open_energy_lab.simulator import (
    BatteryComponent,
    MultiRateTimeContract,
    StackedServiceReplayRequest,
    TerminalSOCTarget,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
    replay_stacked_services,
)


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "market"
MARKET_PATH = FIXTURE_DIR / "france_2022-08-19_market_v1.json"
ACTIVATION_PATH = FIXTURE_DIR / "france_2022-08-19_activation_v1.json"
EXPECTED_PATH = FIXTURE_DIR / "france_2022-08-19_expected_replay_v1.json"
BLOCKER = (
    "the ENTSO-E A44 redistribution gate blocks publishing the otherwise "
    "technically validated A44/combined-A81 reference fixture, as recorded in "
    "tests/fixtures/market/README.md"
)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _require_complete_reference_fixture_set() -> None:
    missing = [path.name for path in (MARKET_PATH, ACTIVATION_PATH, EXPECTED_PATH) if not path.is_file()]
    if missing:
        pytest.skip(f"{BLOCKER}; missing {', '.join(missing)}")


def _load_and_replay():
    _require_complete_reference_fixture_set()
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    market = load_market_data_artifact(MARKET_PATH)
    activation = load_regulation_activation_trace(ACTIVATION_PATH)
    period = expected["period"]
    start = _instant(period["start_utc"])
    end = _instant(period["end_utc"])
    battery_config = expected["battery"]
    battery = BatteryComponent(**battery_config)
    energy_config = expected["energy_schedule"]
    energy = build_energy_baseline_schedule(
        schedule_id=energy_config["schedule_id"],
        semantics_version=energy_config["semantics_version"],
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=[
            {
                **item,
                "start_utc": _instant(item["start_utc"]),
                "end_utc": _instant(item["end_utc"]),
            }
            for item in energy_config["intervals"]
        ],
    )
    fcr_config = expected["fcr_schedule"]
    fcr = build_fcr_capacity_schedule(
        schedule_id=fcr_config["schedule_id"],
        semantics_version=fcr_config["semantics_version"],
        product_identity=fcr_config["product_identity"],
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=[
            {
                **item,
                "start_utc": _instant(item["start_utc"]),
                "end_utc": _instant(item["end_utc"]),
            }
            for item in fcr_config["intervals"]
        ],
    )
    terminal = TerminalSOCTarget(**expected["terminal_soc_target"])
    request = StackedServiceReplayRequest(
        market_artifact=market,
        activation_trace=activation,
        battery=battery,
        energy_schedule=energy,
        fcr_schedule=fcr,
        time_contract=MultiRateTimeContract(
            start_utc=start,
            end_utc=end,
            activation_resolution="PT10S",
            state_checkpoint_resolution="PT15M",
            energy_resolution="PT1H",
            fcr_resolution="PT4H",
            market_timezone="Europe/Paris",
            interval_convention="start-inclusive/end-exclusive",
        ),
        penalty_rule=None,
        terminal_soc_target=terminal,
        numeric_tolerance=1e-6,
        simulation_semantics_version="stacked-service-replay-v1",
    )
    result = replay_stacked_services(request)
    return expected, market, activation, energy, fcr, result


def _assert_reference_result(run: tuple[object, ...]) -> None:
    expected, market, activation, energy, fcr, result = run
    counts = expected["expected"]["counts"]
    totals = expected["expected"]["totals"]
    fingerprints = expected["expected"]["fingerprints"]

    assert len(energy.intervals) == counts["energy_intervals"] == 24
    assert len(result.checkpoint_summaries) == counts["checkpoint_intervals"] == 96
    assert len(fcr.intervals) == counts["fcr_blocks"] == 6
    assert len(activation.samples) == counts["activation_samples"] == 8_640
    assert result.throughput_kwh == pytest.approx(totals["throughput_kwh"], abs=1e-6)
    assert result.settlement.day_ahead_energy_revenue_eur == pytest.approx(
        totals["day_ahead_energy_revenue_eur"], abs=1e-6
    )
    assert result.settlement.fcr_capacity_revenue_eur == pytest.approx(
        totals["fcr_capacity_revenue_eur"], abs=1e-6
    )
    assert result.settlement.penalty_eur == pytest.approx(totals["penalty_eur"], abs=1e-6)
    assert result.settlement.total_profit_eur == pytest.approx(
        totals["total_profit_eur"], abs=1e-6
    )
    assert market.artifact_fingerprint == fingerprints["market_artifact"]
    assert activation.artifact_fingerprint == fingerprints["activation_artifact"]
    assert energy.schedule_fingerprint == fingerprints["energy_schedule"]
    assert fcr.schedule_fingerprint == fingerprints["fcr_schedule"]
    assert result.trace_fingerprint == fingerprints["trace"]
    assert result.result_fingerprint == fingerprints["result"]


def test_selected_french_day_replays_offline_with_exact_recorded_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("reference replay attempted network access")

    monkeypatch.setattr(socket, "socket", _network_forbidden)
    _assert_reference_result(_load_and_replay())


@pytest.mark.reference_benchmark
def test_selected_french_day_reference_benchmark(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("reference benchmark attempted network access")

    monkeypatch.setattr(socket, "socket", _network_forbidden)
    _assert_reference_result(_load_and_replay())
    timings: list[float] = []
    for _ in range(5):
        started = perf_counter()
        _assert_reference_result(_load_and_replay())
        timings.append(perf_counter() - started)
    assert all(elapsed < 10.0 for elapsed in timings), timings
