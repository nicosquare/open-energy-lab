"""Closed Feature 010 contracts that Feature 012 must preserve exactly."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pytest

from open_energy_lab.simulator.stacked_service import (
    StackedServiceValidationError,
    replay_stacked_services,
)
from tests.unit.simulator.test_stacked_service import _replay_request


FIXTURE_DIGESTS = {
    "tests/fixtures/market/france_2022-08-19_market_v1.json": (
        "7558ffd7b07470d77d50b4c5baf20eb196808324e99b0ee575060f42a83b1c8d"
    ),
    "tests/fixtures/market/france_2022-08-19_activation_v1.json": (
        "859f9bfb40e94d756f1e45eaa6c9ca6dd0e31ef943fc065659a62b343a616779"
    ),
    "tests/fixtures/market/france_2022-08-19_expected_replay_v1.json": (
        "13df60b98ca511bf6f71252ab669eb828f00ba04363fec7064043e730118208f"
    ),
    "tests/fixtures/market/manual_stacked_service_v1.json": (
        "bda0615f7585c4f52507141e500ddad013e260d5c9e22ec3ff9b8dda47cdac83"
    ),
}


def test_feature_010_fixture_bytes_are_closed_compatibility_evidence() -> None:
    assert {
        path: sha256(Path(path).read_bytes()).hexdigest()
        for path in FIXTURE_DIGESTS
    } == FIXTURE_DIGESTS


@pytest.mark.parametrize(
    ("override", "message"),
    (
        ({"battery": object()}, "replay requires exactly one BatteryComponent battery"),
        ({"energy_schedule": object()}, "energy_schedule has the wrong type"),
        ({"fcr_schedule": object()}, "fcr_schedule has the wrong type"),
        ({"time_contract": object()}, "time_contract has the wrong type"),
    ),
)
def test_feature_010_request_validation_messages_remain_exact(
    override: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(StackedServiceValidationError) as caught:
        _replay_request(**override)

    assert str(caught.value) == message


def test_feature_010_sample_order_and_fingerprints_remain_exact() -> None:
    result = replay_stacked_services(_replay_request())

    assert [sample.energy_interval_ref for sample in result.samples] == [
        f"energy:{index // 4}" for index in range(32)
    ]
    assert [sample.fcr_interval_ref for sample in result.samples] == [
        f"fcr:{index // 16}" for index in range(32)
    ]
    assert [sample.activation for sample in result.samples] == [
        (1.0, -1.0, 0.0, 0.0)[index % 4] for index in range(32)
    ]
    assert [sample.interval.start_utc for sample in result.samples] == sorted(
        sample.interval.start_utc for sample in result.samples
    )
    assert result.trace_fingerprint == (
        "07c7c079e17b42fedbe544539384cac73cb85aee9ef206b9b13ac9a15a9adaab"
    )
    assert result.result_fingerprint == (
        "7bd2549dedd1c77ae826c94fb23778a1b8dab2339da81cad4e6c846c1f2d90a9"
    )


def test_feature_010_default_settlement_payload_remains_exact() -> None:
    settlement = replay_stacked_services(_replay_request()).settlement.to_dict()

    assert tuple(settlement) == (
        "energy_intervals",
        "fcr_blocks",
        "day_ahead_energy_revenue_eur",
        "fcr_capacity_revenue_eur",
        "non_delivery_energy_kwh",
        "penalty_rule_id",
        "penalty_eur",
        "charge_energy_kwh",
        "discharge_energy_kwh",
        "throughput_kwh",
        "activation_energy_settlement_status",
        "imbalance_settlement_status",
        "degradation_cost_status",
        "total_profit_eur",
    )
    assert all(
        tuple(item) == (
            "interval",
            "accepted_power_kw",
            "duration_hours",
            "price_eur_per_mwh",
            "revenue_eur",
        )
        for item in settlement["energy_intervals"]
    )
    assert all(
        tuple(item) == (
            "interval",
            "committed_capacity_kw",
            "duration_hours",
            "capacity_price_eur_per_mw_per_h",
            "revenue_eur",
        )
        for item in settlement["fcr_blocks"]
    )
    assert [item["price_eur_per_mwh"] for item in settlement["energy_intervals"]] == [
        50.0,
        -5.0,
        52.0,
        53.0,
        54.0,
        55.0,
        56.0,
        57.0,
    ]
    assert [item["revenue_eur"] for item in settlement["fcr_blocks"]] == [0.4, 0.42]
    assert settlement == {
        **settlement,
        "day_ahead_energy_revenue_eur": 0.0,
        "fcr_capacity_revenue_eur": 0.8200000000000001,
        "non_delivery_energy_kwh": 0.0,
        "penalty_rule_id": None,
        "penalty_eur": 0.0,
        "charge_energy_kwh": 10.0,
        "discharge_energy_kwh": 10.0,
        "throughput_kwh": 20.0,
        "activation_energy_settlement_status": "not_modeled",
        "imbalance_settlement_status": "not_modeled",
        "degradation_cost_status": "not_modeled",
        "total_profit_eur": 0.8200000000000001,
    }
