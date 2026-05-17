"""Pricing and deterministic policy tests for the battery arbitrage MVP."""

from __future__ import annotations

import pytest

from open_energy_lab.simulator.pricing import (
    ArbitrageObjectiveRepresentation,
    DeterministicRulePolicy,
    PriceSignal,
)
from open_energy_lab.simulator.scenario import TimeGrid


def test_price_signal_requires_length_matching_time_grid() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="import price length"):
        PriceSignal(
            currency="USD",
            unit_rate_name="energy-price",
            import_prices=[0.10, 0.20],
            export_price_ratio=0.8,
            interpretation="discounted export relative to import prices",
            time_alignment="step-start",
            time_grid=grid,
        )


def test_price_signal_requires_discounted_export_ratio() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)

    with pytest.raises(ValueError, match="export_price_ratio"):
        PriceSignal(
            currency="USD",
            unit_rate_name="energy-price",
            import_prices=[0.10, 0.20, 0.30],
            export_price_ratio=1.2,
            interpretation="discounted export relative to import prices",
            time_alignment="step-start",
            time_grid=grid,
        )


def test_price_signal_uses_step_start_alignment() -> None:
    grid = TimeGrid(num_steps=3, time_step_hours=1.0)
    signal = PriceSignal(
        currency="USD",
        unit_rate_name="energy-price",
        import_prices=[0.10, 0.20, 0.30],
        export_price_ratio=0.8,
        interpretation="discounted export relative to import prices",
        time_alignment="step-start",
        time_grid=grid,
    )

    assert signal.price_at_step(0) == pytest.approx(0.10)
    assert signal.price_at_step(1) == pytest.approx(0.20)
    assert signal.price_at_step(2) == pytest.approx(0.30)
    assert signal.export_price_at_step(2) == pytest.approx(0.24)


def test_price_threshold_policy_charges_holds_and_discharges() -> None:
    policy = DeterministicRulePolicy(
        policy_name="price_threshold",
        price_threshold=0.20,
        below_threshold_action="charge",
        above_threshold_action="discharge",
        at_threshold_action="hold",
    )

    assert policy.action_for_price(0.10) == "charge"
    assert policy.action_for_price(0.20) == "hold"
    assert policy.action_for_price(0.30) == "discharge"


def test_non_price_threshold_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="price_threshold"):
        DeterministicRulePolicy(
            policy_name="target_soc",
            price_threshold=0.20,
            below_threshold_action="charge",
            above_threshold_action="discharge",
            at_threshold_action="hold",
        )


def test_objective_requires_discounted_export_settlement() -> None:
    with pytest.raises(ValueError, match="discounted export"):
        ArbitrageObjectiveRepresentation(
            objective_name="arbitrage",
            settlement_basis="grid-settlement",
            allow_export=True,
            export_price_ratio=1.0,
        )
