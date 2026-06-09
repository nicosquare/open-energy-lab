"""Shared helpers for native controller-pack integration fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_DIR = Path("tests/fixtures/simulator")
PRICE_THRESHOLD_CONTROLLER_FIXTURE_PATH = (
    FIXTURE_DIR / "price_threshold_controller_case.json"
)
SOC_GUARDRAIL_ARBITRAGE_FIXTURE_PATH = (
    FIXTURE_DIR / "soc_guardrail_arbitrage_case.json"
)
PV_SELF_CONSUMPTION_FIXTURE_PATH = FIXTURE_DIR / "pv_self_consumption_case.json"
CONTROLLER_PACK_FIXTURE_PATHS = (
    PRICE_THRESHOLD_CONTROLLER_FIXTURE_PATH,
    SOC_GUARDRAIL_ARBITRAGE_FIXTURE_PATH,
    PV_SELF_CONSUMPTION_FIXTURE_PATH,
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
    "config_reference",
    "planned_config",
    "time_grid",
    "battery",
    "pricing",
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

COMMON_EXPECTED_PROPERTIES_KEYS = (
    "validates_controller_evaluation",
    "validates_repeated_run_determinism",
    "validates_preserved_explicit_dispatch_regression",
    "validates_preserved_built_in_rule_regression",
)

LOAD_PV_SCENARIO_KEYS = ("load", "weather", "pv")


def load_controller_pack_fixture(path: Path) -> dict[str, Any]:
    """Load one native controller-pack fixture from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_all_controller_pack_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    """Load every committed native controller-pack fixture scaffold."""

    return [
        (path, load_controller_pack_fixture(path))
        for path in CONTROLLER_PACK_FIXTURE_PATHS
    ]


def load_controller_pack_fixture_by_name(controller_name: str) -> tuple[Path, dict[str, Any]]:
    """Load one native controller-pack fixture by controller class name."""

    for path, fixture_data in load_all_controller_pack_fixtures():
        if fixture_data["controller_name"] == controller_name:
            return path, fixture_data

    raise KeyError(f"unknown controller-pack fixture for {controller_name!r}")
