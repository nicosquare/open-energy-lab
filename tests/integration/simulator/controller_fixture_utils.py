"""Shared helpers for controller-boundary integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/simulator")
CONTROLLER_ARBITRAGE_FIXTURE_PATH = FIXTURE_DIR / "controller_arbitrage_case.json"
CONTROLLER_BATTERY_LOAD_PV_FIXTURE_PATH = (
    FIXTURE_DIR / "controller_battery_load_pv_case.json"
)
CONTROLLER_FIXTURE_PATHS = (
    CONTROLLER_ARBITRAGE_FIXTURE_PATH,
    CONTROLLER_BATTERY_LOAD_PV_FIXTURE_PATH,
)

COMMON_TOP_LEVEL_KEYS = (
    "case_id",
    "status",
    "purpose",
    "origin",
    "legacy_references",
    "scenario_kind",
    "controller_name",
    "fixture_source",
    "time_grid",
    "battery",
    "pricing",
    "controller_stub",
    "expected_properties",
    "expected_trace",
    "numeric_tolerance",
    "provenance_notes",
)

COMMON_ORIGIN_KEYS = (
    "author",
    "construction",
    "seed",
    "generation_command",
    "refresh_policy",
)

COMMON_BATTERY_KEYS = (
    "name",
    "capacity_kwh",
    "max_charge_kw",
    "max_discharge_kw",
    "charge_efficiency",
    "discharge_efficiency",
    "initial_soc",
    "min_soc",
    "max_soc",
)

COMMON_PRICING_KEYS = (
    "currency",
    "unit_rate_name",
    "import_prices",
    "export_price_ratio",
    "interpretation",
    "time_alignment",
)

COMMON_CONTROLLER_STUB_KEYS = (
    "kind",
    "proposal_sign_convention",
    "requested_power_kw",
)

COMMON_EXPECTED_PROPERTIES_KEYS = (
    "validates_controller_evaluation",
    "validates_preserved_explicit_dispatch_regression",
    "validates_preserved_price_threshold_regression",
    "validates_named_incomplete_context_rejection",
)

COMMON_EXPECTED_TRACE_KEYS = (
    "requested_power_kw",
    "realized_power_kw",
    "soc",
    "step_settlement",
    "total_settlement",
    "constraint_events",
)


def load_controller_fixture(path: Path) -> dict[str, Any]:
    """Load one controller-boundary fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_controller_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed controller-boundary fixture."""

    return [(path, load_controller_fixture(path)) for path in CONTROLLER_FIXTURE_PATHS]
