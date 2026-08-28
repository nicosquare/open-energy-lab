"""Deterministic authored inputs shared by Feature 015 tests.

The module contains no solver or simulator imports at import time. Builders
resolve existing public Open Energy Lab contracts only when called, so import
boundary tests can use this helper without eagerly loading Pyomo or HiGHS.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
from typing import Any


AUTHORED_DELIVERY_DATES = tuple(date(2023, 6, day) for day in range(17, 21))
AUTHORED_MARKET_TIMEZONE = "Europe/Paris"
AUTHORED_ACTIVATION_CREATED_AT_UTC = datetime(2026, 8, 28, 12, tzinfo=UTC)


def fingerprint(value: object) -> str:
    """Return the repository's deterministic canonical authored-data digest."""

    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def authored_battery_mapping(
    *,
    initial_stored_energy_kwh: float = 10.0,
) -> dict[str, float]:
    """Return the bounded battery values shared by authored rolling cases."""

    return {
        "maximum_charge_power_kw": 10.0,
        "maximum_discharge_power_kw": 10.0,
        "minimum_stored_energy_kwh": 0.0,
        "maximum_stored_energy_kwh": 20.0,
        "initial_stored_energy_kwh": float(initial_stored_energy_kwh),
        "charge_efficiency": 0.92,
        "discharge_efficiency": 0.92,
    }


def build_authored_battery(
    *,
    initial_stored_energy_kwh: float = 10.0,
) -> Any:
    """Build one Feature 013 battery through its public contract."""

    from open_energy_lab.control import RobustFCRBatteryParameters

    return RobustFCRBatteryParameters(
        **authored_battery_mapping(
            initial_stored_energy_kwh=initial_stored_energy_kwh
        )
    )


def authored_price_mapping(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> dict[str, tuple[float, ...]]:
    """Return deterministic 24/6 prices with a visible date-dependent shift."""

    if delivery_date not in AUTHORED_DELIVERY_DATES:
        raise ValueError("delivery_date must belong to the authored four-date window")
    day_offset = float((delivery_date - AUTHORED_DELIVERY_DATES[0]).days)
    energy = (
        0.050,
        0.045,
        0.040,
        0.035,
        0.030,
        0.025,
        0.040,
        0.055,
        0.070,
        0.085,
        0.100,
        0.090,
        0.075,
        0.060,
        0.050,
        0.045,
        0.055,
        0.070,
        0.095,
        0.120,
        0.110,
        0.090,
        0.070,
        0.055,
    )
    fcr = (0.060, 0.055, 0.050, 0.052, 0.058, 0.065)
    return {
        "day_ahead_energy_prices_eur_per_kwh": tuple(
            value + 0.001 * day_offset for value in energy
        ),
        "fcr_capacity_prices_eur_per_kw_block": tuple(
            value + 0.002 * day_offset for value in fcr
        ),
    }


def build_authored_prices(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> Any:
    """Build one Feature 013 24/6 price input through its public contract."""

    from open_energy_lab.control import RobustFCRPriceInputs

    values = authored_price_mapping(delivery_date)
    return RobustFCRPriceInputs(
        **values,
        energy_interval_refs=tuple(
            f"authored:{delivery_date.isoformat()}:day_ahead:{index}"
            for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"authored:{delivery_date.isoformat()}:fcr:{index}"
            for index in range(6)
        ),
    )


def build_authored_time_contract(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
) -> Any:
    """Build an ordinary 24/96/6 Feature 013 time contract."""

    from open_energy_lab.control import build_robust_fcr_time_contract

    return build_robust_fcr_time_contract(
        delivery_date=delivery_date,
        market_timezone=AUTHORED_MARKET_TIMEZONE,
    )


def authored_solve_policy_mapping(
    *,
    time_limit_seconds: float = 30.0,
    allow_feasible_incumbent_plan: bool = False,
) -> dict[str, object]:
    """Return the deterministic required-HiGHS policy for bounded cases."""

    return {
        "solver_name": "highs",
        "time_limit_seconds": float(time_limit_seconds),
        "threads": 1,
        "random_seed": 15,
        "primal_feasibility_tolerance": 1e-7,
        "dual_feasibility_tolerance": 1e-7,
        "mip_feasibility_tolerance": 1e-6,
        "relative_mip_gap": 1e-6,
        "objective_comparison_absolute_tolerance_eur": 1e-6,
        "objective_comparison_relative_tolerance": 1e-9,
        "allow_feasible_incumbent_plan": allow_feasible_incumbent_plan,
        "decision_canonicalization_id": "solver-output-kw-1e-9-half-even-v1",
    }


def build_authored_solve_policy(
    *,
    time_limit_seconds: float = 30.0,
    allow_feasible_incumbent_plan: bool = False,
) -> Any:
    """Build the bounded policy through Feature 013's public contract."""

    from open_energy_lab.control import RobustFCRSolvePolicy

    return RobustFCRSolvePolicy(
        **authored_solve_policy_mapping(
            time_limit_seconds=time_limit_seconds,
            allow_feasible_incumbent_plan=allow_feasible_incumbent_plan,
        )
    )


def authored_activation_values(
    *,
    sample_count: int,
    phase: int = 0,
) -> tuple[float, ...]:
    """Return a balanced deterministic signal without external data."""

    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    pattern = (0.0, 0.25, 0.5, 0.25, 0.0, -0.25, -0.5, -0.25)
    return tuple(pattern[(index + phase) % len(pattern)] for index in range(sample_count))


def build_authored_activation_trace(
    delivery_date: date = AUTHORED_DELIVERY_DATES[1],
    *,
    resolution: str = "PT15M",
    values: Sequence[float] | None = None,
) -> Any:
    """Build a complete authored trace through the public market importer."""

    from open_energy_lab.market import (
        ActivationImportRequest,
        import_regulation_activation_trace,
    )
    from open_energy_lab.market.time import parse_iso8601_duration

    time_contract = build_authored_time_contract(delivery_date)
    period = time_contract.delivery_period
    step = parse_iso8601_duration(resolution)
    duration = period.end_utc - period.start_utc
    count_float = duration / step
    if count_float != int(count_float):
        raise ValueError("resolution must exactly divide the ordinary delivery day")
    sample_count = int(count_float)
    activation_values = tuple(values) if values is not None else authored_activation_values(
        sample_count=sample_count,
        phase=(delivery_date - AUTHORED_DELIVERY_DATES[0]).days,
    )
    if len(activation_values) != sample_count:
        raise ValueError("activation values must exactly cover the delivery day")
    request = ActivationImportRequest(
        source_name="Feature 015 project-authored activation",
        source_locator="tests/fcr_rolling_case_utils.py",
        source_revision="sha256:" + fingerprint(list(activation_values)),
        source_timezone=AUTHORED_MARKET_TIMEZONE,
        requested_start_utc=period.start_utc,
        requested_end_utc=period.end_utc,
        source_resolution=resolution,
        source_value_kind="interval_average",
        source_sign_meaning="positive source activation means upward/discharge",
        normalization_rule={
            "conversion": "identity",
            "formula": "activation = source_value",
            "point_to_interval": "already_interval_average",
            "clip_min": -1.0,
            "clip_max": 1.0,
            "target_sign": "positive is upward/discharge",
        },
        redistribution_basis={
            "source": "project-authored deterministic input",
            "terms": "Apache-2.0",
            "attribution": "Open Energy Lab Feature 015 tests",
        },
    )
    samples = []
    cursor = period.start_utc
    for value in activation_values:
        next_cursor = cursor + step
        samples.append(
            {
                "start_utc": cursor,
                "end_utc": next_cursor,
                "value": float(value),
                "source_value": float(value),
                "source_unit": "dimensionless",
            }
        )
        cursor = next_cursor
    assert cursor == period.end_utc
    return import_regulation_activation_trace(
        request,
        samples,
        trace_id=f"feature-015-authored-{delivery_date.isoformat()}-activation-v1",
        created_at_utc=AUTHORED_ACTIVATION_CREATED_AT_UTC,
    )


def authored_date_window() -> tuple[date, ...]:
    """Return a detached copy of the ordered bounded authored dates."""

    return tuple(AUTHORED_DELIVERY_DATES)


__all__ = [
    "AUTHORED_ACTIVATION_CREATED_AT_UTC",
    "AUTHORED_DELIVERY_DATES",
    "AUTHORED_MARKET_TIMEZONE",
    "authored_activation_values",
    "authored_battery_mapping",
    "authored_date_window",
    "authored_price_mapping",
    "authored_solve_policy_mapping",
    "build_authored_activation_trace",
    "build_authored_battery",
    "build_authored_prices",
    "build_authored_solve_policy",
    "build_authored_time_contract",
    "fingerprint",
]
