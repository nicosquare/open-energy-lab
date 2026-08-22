"""Limiting-case compatibility for deterministic stacked-service baselines."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from open_energy_lab.control import PriceThresholdConfig
from open_energy_lab.simulator import (
    ArbitrageObjectiveRepresentation,
    ArbitrageScenario,
    DispatchRequestSeries,
    PriceSignal,
    TerminalSOCTarget,
    TimeGrid,
)
from open_energy_lab.simulator._units import POSITIVE_DISPATCH_MEANING
from tests.unit.control.test_stacked_service import (
    _arbitrage_config,
    _regulation_config,
    _require as _require_control,
    _stacked_config,
)
from tests.unit.market.test_artifact import _build_artifact
from tests.unit.simulator.test_stacked_service import (
    _activation_trace,
    _battery,
    _fcr_schedule,
    _replay_request,
    _require as _require_simulator,
)


EXPECTED_REFERENCE_PATH = Path(
    "tests/fixtures/market/france_2022-08-19_expected_replay_v1.json"
)
MARKET_REFERENCE_PATH = Path(
    "tests/fixtures/market/france_2022-08-19_market_v1.json"
)


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def test_zero_fcr_reproduces_existing_arbitrage_physics_throughput_and_settlement() -> None:
    build = _require_control("build_arbitrage_only_baseline")
    replay = _require_simulator("replay_stacked_services")
    market = _build_artifact()
    battery = _battery(capacity_kwh=1_000.0, initial_soc=0.5)
    baseline = build(
        _arbitrage_config(request_kw=5.0),
        market_artifact=market,
        battery=battery,
    )
    stacked = replay(
        _replay_request(
            market_artifact=market,
            battery=baseline.battery,
            energy_schedule=baseline.energy_schedule,
            fcr_schedule=baseline.fcr_schedule,
        )
    )
    prices_eur_per_mwh = [
        observation.value
        for observation in market.series["day_ahead_price"].observations
    ]
    powers = [item.power_kw for item in baseline.energy_schedule.intervals]
    export_price_ratio = 0.8
    legacy_import_prices = [
        price / 1000.0
        if power >= 0.0
        else price / 1000.0 / export_price_ratio
        for price, power in zip(prices_eur_per_mwh, powers, strict=True)
    ]
    grid = TimeGrid(num_steps=8, time_step_hours=1.0)
    arbitrage = ArbitrageScenario(
        scenario_id="feature-010-zero-fcr-parity",
        time_grid=grid,
        battery=battery,
        price_signal=PriceSignal(
            currency="EUR",
            unit_rate_name="EUR/kWh",
            import_prices=legacy_import_prices,
            export_price_ratio=export_price_ratio,
            interpretation="discounted export aligned to day-ahead schedule price",
            time_alignment="step-start",
            time_grid=grid,
        ),
        dispatch_requests=DispatchRequestSeries(
            requested_power_kw=powers,
            sign_convention=POSITIVE_DISPATCH_MEANING,
            source="feature-010-arbitrage-only",
        ),
        objective=ArbitrageObjectiveRepresentation(
            objective_name="day-ahead-parity",
            settlement_basis="grid-settlement",
            allow_export=True,
            export_price_ratio=export_price_ratio,
        ),
    ).evaluate_trace()

    assert [sample.delivered_combined_power_kw for sample in stacked.samples[::4]] == pytest.approx(
        arbitrage.realized_power_kw
    )
    assert [checkpoint.stored_energy_kwh for checkpoint in stacked.state_checkpoints[4::4]] == pytest.approx(
        [state.stored_energy_kwh for state in arbitrage.states]
    )
    assert stacked.throughput_kwh == pytest.approx(
        sum(abs(power) for power in arbitrage.realized_power_kw)
    )
    assert stacked.settlement.total_profit_eur == pytest.approx(
        arbitrage.total_settlement
    )


def test_zero_energy_regulation_only_replay_delivers_fcr_and_zero_energy_revenue() -> None:
    build = _require_control("build_regulation_only_baseline")
    replay = _require_simulator("replay_stacked_services")
    baseline = build(_regulation_config(), battery=_battery())

    result = replay(
        _replay_request(
            battery=baseline.battery,
            energy_schedule=baseline.energy_schedule,
            fcr_schedule=baseline.fcr_schedule,
        )
    )

    assert any(sample.delivered_fcr_power_kw != 0.0 for sample in result.samples)
    assert result.settlement.day_ahead_energy_revenue_eur == 0.0


def test_stacked_baseline_and_replay_are_deterministic() -> None:
    build = _require_control("build_stacked_heuristic_baseline")
    replay = _require_simulator("replay_stacked_services")
    market = _build_artifact()
    battery = _battery(max_charge_kw=10.0, max_discharge_kw=10.0)
    first_baseline = build(
        _stacked_config(),
        market_artifact=market,
        battery=battery,
    )
    second_baseline = build(
        _stacked_config(),
        market_artifact=market,
        battery=battery,
    )
    first = replay(
        _replay_request(
            market_artifact=market,
            battery=battery,
            energy_schedule=first_baseline.energy_schedule,
            fcr_schedule=first_baseline.fcr_schedule,
        )
    )
    second = replay(
        _replay_request(
            market_artifact=market,
            battery=battery,
            energy_schedule=second_baseline.energy_schedule,
            fcr_schedule=second_baseline.fcr_schedule,
        )
    )

    assert first_baseline.configuration_fingerprint == second_baseline.configuration_fingerprint
    assert first.samples == second.samples
    assert first.trace_fingerprint == second.trace_fingerprint
    assert first.result_fingerprint == second.result_fingerprint


def test_terminal_target_is_report_only_for_dispatch_and_settlement() -> None:
    replay = _require_simulator("replay_stacked_services")
    untargeted = replay(_replay_request())
    targeted = replay(
        _replay_request(
            terminal_soc_target=TerminalSOCTarget(
                target_kind="stored_energy_kwh",
                target_value=55.0,
                tolerance=0.01,
            )
        )
    )

    assert targeted.terminal_soc_report is not None
    assert untargeted.samples == targeted.samples
    assert untargeted.settlement == targeted.settlement
    assert untargeted.trace_fingerprint == targeted.trace_fingerprint
    assert untargeted.result_fingerprint != targeted.result_fingerprint


def test_stacked_builder_reproduces_the_recorded_reference_schedule() -> None:
    if not EXPECTED_REFERENCE_PATH.is_file() or not MARKET_REFERENCE_PATH.is_file():
        pytest.skip(
            "the complete restricted private-repository reference fixture "
            "set has not been staged"
        )
    from open_energy_lab.market import load_market_data_artifact
    from open_energy_lab.simulator import BatteryComponent, build_fcr_capacity_schedule

    expected = json.loads(EXPECTED_REFERENCE_PATH.read_text(encoding="utf-8"))
    market = load_market_data_artifact(MARKET_REFERENCE_PATH)
    period = expected["period"]
    start = _instant(period["start_utc"])
    end = _instant(period["end_utc"])
    fcr_payload = expected["fcr_schedule"]
    fcr = build_fcr_capacity_schedule(
        schedule_id=fcr_payload["schedule_id"],
        semantics_version=fcr_payload["semantics_version"],
        product_identity=fcr_payload["product_identity"],
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=[
            {
                **item,
                "start_utc": _instant(item["start_utc"]),
                "end_utc": _instant(item["end_utc"]),
            }
            for item in fcr_payload["intervals"]
        ],
    )
    config_type = _require_control("StackedHeuristicConfig")
    config = config_type(
        schedule_id=expected["energy_schedule"]["schedule_id"],
        semantics_version=expected["energy_schedule"]["semantics_version"],
        price_threshold_config=PriceThresholdConfig(
            charge_below_import_price=475.0,
            discharge_above_import_price=540.0,
            charge_request_kw=5.0,
            discharge_request_kw=5.0,
            controller_name="feature-010-price-threshold",
        ),
        fcr_schedule=fcr,
    )
    baseline = _require_control("build_stacked_heuristic_baseline")(
        config,
        market_artifact=market,
        battery=BatteryComponent(**expected["battery"]),
    )

    assert [item.power_kw for item in baseline.energy_schedule.intervals] == [
        item["power_kw"] for item in expected["energy_schedule"]["intervals"]
    ]
    assert baseline.energy_schedule.schedule_fingerprint == expected["expected"][
        "fingerprints"
    ]["energy_schedule"]
