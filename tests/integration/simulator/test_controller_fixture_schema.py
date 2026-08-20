"""Schema checks for controller-boundary simulator fixtures."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
from tests.integration.control.controller_fixture_utils import (
    COMMON_BATTERY_KEYS as CONTROLLER_PACK_COMMON_BATTERY_KEYS,
    COMMON_EXPECTED_PROPERTIES_KEYS as CONTROLLER_PACK_COMMON_EXPECTED_PROPERTIES_KEYS,
    COMMON_ORIGIN_KEYS as CONTROLLER_PACK_COMMON_ORIGIN_KEYS,
    COMMON_PRICING_KEYS as CONTROLLER_PACK_COMMON_PRICING_KEYS,
    COMMON_TOP_LEVEL_KEYS as CONTROLLER_PACK_COMMON_TOP_LEVEL_KEYS,
    CONTROLLER_PACK_FIXTURE_PATHS,
    LOAD_PV_SCENARIO_KEYS,
    load_all_controller_pack_fixtures,
)
from tests.integration.legacy_reference_utils import assert_legacy_reference_path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from controller_fixture_utils import (
    COMMON_BATTERY_KEYS,
    COMMON_CONTROLLER_STUB_KEYS,
    COMMON_EXPECTED_PROPERTIES_KEYS,
    COMMON_EXPECTED_TRACE_KEYS,
    COMMON_ORIGIN_KEYS,
    COMMON_PRICING_KEYS,
    COMMON_TOP_LEVEL_KEYS,
    CONTROLLER_ARBITRAGE_FIXTURE_PATH,
    CONTROLLER_BATTERY_LOAD_PV_FIXTURE_PATH,
    load_all_controller_fixtures,
)


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_controller_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_controller_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_data["status"] == "active"
    assert fixture_data["fixture_source"] == fixture_path.as_posix()
    assert fixture_data["controller_name"] == "sequence-controller"
    assert fixture_data["numeric_tolerance"] == pytest.approx(1e-6)

    origin = fixture_data["origin"]
    assert isinstance(origin, dict)
    missing_origin_keys = [key for key in COMMON_ORIGIN_KEYS if key not in origin]
    assert missing_origin_keys == []

    battery = fixture_data["battery"]
    assert isinstance(battery, dict)
    missing_battery_keys = [key for key in COMMON_BATTERY_KEYS if key not in battery]
    assert missing_battery_keys == []
    assert battery["name"] == "battery"

    pricing = fixture_data["pricing"]
    assert isinstance(pricing, dict)
    missing_pricing_keys = [key for key in COMMON_PRICING_KEYS if key not in pricing]
    assert missing_pricing_keys == []
    assert pricing["currency"] == "USD"
    assert pricing["time_alignment"] == "step-start"

    controller_stub = fixture_data["controller_stub"]
    assert isinstance(controller_stub, dict)
    missing_controller_stub_keys = [
        key for key in COMMON_CONTROLLER_STUB_KEYS if key not in controller_stub
    ]
    assert missing_controller_stub_keys == []
    assert controller_stub["kind"] == "deterministic-sequence"
    assert controller_stub["proposal_sign_convention"] == "positive-means-charge"
    assert controller_stub["requested_power_kw"] == [1.0, 0.0, -1.0]

    expected_properties = fixture_data["expected_properties"]
    assert isinstance(expected_properties, dict)
    missing_expected_properties_keys = [
        key for key in COMMON_EXPECTED_PROPERTIES_KEYS if key not in expected_properties
    ]
    assert missing_expected_properties_keys == []
    assert expected_properties == {
        "validates_controller_evaluation": True,
        "validates_preserved_explicit_dispatch_regression": False,
        "validates_preserved_price_threshold_regression": False,
        "validates_named_incomplete_context_rejection": False,
    }

    time_grid = fixture_data["time_grid"]
    assert isinstance(time_grid, dict)
    assert time_grid == {"num_steps": 3, "time_step_hours": 1.0}

    legacy_references = fixture_data["legacy_references"]
    assert isinstance(legacy_references, list)
    assert legacy_references != []
    for legacy_path in legacy_references:
        assert isinstance(legacy_path, str)
        assert legacy_path.startswith("legacy/")
        assert_legacy_reference_path(legacy_path)

    provenance_notes = fixture_data["provenance_notes"]
    assert isinstance(provenance_notes, list)
    assert provenance_notes != []
    assert all(isinstance(note, str) and note for note in provenance_notes)


@pytest.mark.parametrize(
    ("fixture_path", "scenario_kind", "scenario_keys", "trace_keys"),
    (
        (
            CONTROLLER_ARBITRAGE_FIXTURE_PATH,
            "ArbitrageScenario",
            (),
            COMMON_EXPECTED_TRACE_KEYS,
        ),
        (
            CONTROLLER_BATTERY_LOAD_PV_FIXTURE_PATH,
            "BatteryLoadPVScenario",
            ("load", "weather", "pv"),
            COMMON_EXPECTED_TRACE_KEYS
            + ("pv_generation_kw", "net_grid_power_kw", "net_grid_energy_kwh", "direction"),
        ),
    ),
)
def test_controller_fixture_scenario_specific_schema(
    fixture_path: Path,
    scenario_kind: str,
    scenario_keys: tuple[str, ...],
    trace_keys: tuple[str, ...],
) -> None:
    fixture_data = next(
        data for path, data in load_all_controller_fixtures() if path == fixture_path
    )

    assert fixture_data["scenario_kind"] == scenario_kind

    missing_scenario_keys = [key for key in scenario_keys if key not in fixture_data]
    assert missing_scenario_keys == []

    expected_trace = fixture_data["expected_trace"]
    assert isinstance(expected_trace, dict)
    missing_trace_keys = [key for key in trace_keys if key not in expected_trace]
    assert missing_trace_keys == []
    assert expected_trace["requested_power_kw"] == [1.0, 0.0, -1.0]
    assert expected_trace["realized_power_kw"] == [1.0, 0.0, -1.0]
    assert len(expected_trace["soc"]) == fixture_data["time_grid"]["num_steps"]
    assert len(expected_trace["step_settlement"]) == fixture_data["time_grid"]["num_steps"]
    assert isinstance(expected_trace["total_settlement"], float)
    assert expected_trace["constraint_events"] == []


def test_controller_battery_load_pv_fixture_preserves_weather_label_mappings() -> None:
    fixture_data = next(
        data
        for path, data in load_all_controller_fixtures()
        if path == CONTROLLER_BATTERY_LOAD_PV_FIXTURE_PATH
    )

    load_data = fixture_data["load"]
    assert load_data == {"name": "load", "demand_kw": [2.0, 1.5, 0.5]}

    weather = fixture_data["weather"]
    assert weather["timestamp_utc"]["tmy_label"] == "Date & time (UTC)"
    assert weather["timestamp_utc"]["values"] == [
        "2026-01-01T00:00:00Z",
        "2026-01-01T01:00:00Z",
        "2026-01-01T02:00:00Z",
    ]
    assert weather["dry_bulb_air_temperature_c"]["tmy_label"] == "T2m [°C]"
    assert weather["dry_bulb_air_temperature_c"]["values"] == [25.0, 26.0, 27.0]
    assert (
        weather["global_horizontal_irradiance_w_per_m2"]["tmy_label"] == "G(h) [W/m2]"
    )
    assert weather["global_horizontal_irradiance_w_per_m2"]["values"] == [0.0, 500.0, 1000.0]
    assert weather["deferred_tmy_fields"] == [
        {"field_name": "relative_humidity_pct", "tmy_label": "RH [%]"},
        {
            "field_name": "infrared_radiation_downwards_w_per_m2",
            "tmy_label": "IR(h) [W/m2]",
        },
        {"field_name": "windspeed_10m_m_per_s", "tmy_label": "WS10m [m/s]"},
        {"field_name": "wind_direction_10m_deg", "tmy_label": "WD10m [°]"},
        {"field_name": "surface_air_pressure_pa", "tmy_label": "SP [Pa]"},
    ]

    pv = fixture_data["pv"]
    assert pv["name"] == "pv"
    assert pv["rated_power_kw"] == pytest.approx(4.0)
    assert pv["temperature_coefficient_pct_per_c"] == pytest.approx(-0.4)
    assert pv["reference_irradiance_w_per_m2"] == pytest.approx(1000.0)
    assert pv["reference_temperature_c"] == pytest.approx(25.0)
    assert pv["derivation_name"] == "ghi-linear-temperature-adjusted"


@pytest.mark.parametrize(
    ("fixture_path", "fixture_data"),
    load_all_controller_pack_fixtures(),
    ids=lambda item: item.name if isinstance(item, Path) else repr(item),
)
def test_controller_pack_fixture_common_schema(
    fixture_path: Path,
    fixture_data: dict[str, object],
) -> None:
    missing_top_level_keys = [
        key for key in CONTROLLER_PACK_COMMON_TOP_LEVEL_KEYS if key not in fixture_data
    ]
    assert missing_top_level_keys == []
    assert fixture_path in CONTROLLER_PACK_FIXTURE_PATHS
    assert fixture_data["status"] in {"active", "scaffold"}
    assert fixture_data["fixture_source"] == fixture_path.as_posix()
    assert fixture_data["numeric_tolerance"] == pytest.approx(1e-6)
    assert fixture_data["config_reference"] in {
        "PriceThresholdConfig",
        "SocGuardrailConfig",
        "PVSelfConsumptionConfig",
    }

    origin = fixture_data["origin"]
    assert isinstance(origin, dict)
    missing_origin_keys = [
        key for key in CONTROLLER_PACK_COMMON_ORIGIN_KEYS if key not in origin
    ]
    assert missing_origin_keys == []
    assert origin["author"] == "OpenAI Codex"
    assert origin["seed"] is None

    battery = fixture_data["battery"]
    assert isinstance(battery, dict)
    missing_battery_keys = [
        key for key in CONTROLLER_PACK_COMMON_BATTERY_KEYS if key not in battery
    ]
    assert missing_battery_keys == []
    assert battery["name"] == "battery"

    pricing = fixture_data["pricing"]
    assert isinstance(pricing, dict)
    missing_pricing_keys = [
        key for key in CONTROLLER_PACK_COMMON_PRICING_KEYS if key not in pricing
    ]
    assert missing_pricing_keys == []
    assert pricing["currency"] == "USD"
    assert pricing["time_alignment"] == "step-start"

    expected_properties = fixture_data["expected_properties"]
    assert isinstance(expected_properties, dict)
    missing_expected_properties_keys = [
        key
        for key in CONTROLLER_PACK_COMMON_EXPECTED_PROPERTIES_KEYS
        if key not in expected_properties
    ]
    assert missing_expected_properties_keys == []
    assert expected_properties["validates_controller_evaluation"] is True
    assert expected_properties["validates_repeated_run_determinism"] is True
    assert expected_properties["validates_preserved_explicit_dispatch_regression"] is False
    assert expected_properties["validates_preserved_built_in_rule_regression"] is False

    time_grid = fixture_data["time_grid"]
    assert isinstance(time_grid, dict)
    assert time_grid == {"num_steps": 3, "time_step_hours": 1.0}

    planned_config = fixture_data["planned_config"]
    assert isinstance(planned_config, dict)
    assert planned_config != {}

    legacy_references = fixture_data["legacy_references"]
    assert isinstance(legacy_references, list)
    assert legacy_references != []
    for legacy_path in legacy_references:
        assert isinstance(legacy_path, str)
        assert legacy_path.startswith("legacy/")
        assert_legacy_reference_path(legacy_path)

    provenance_notes = fixture_data["provenance_notes"]
    assert isinstance(provenance_notes, list)
    assert provenance_notes != []
    assert all(isinstance(note, str) and note for note in provenance_notes)

    expected_trace = fixture_data["expected_trace"]
    assert isinstance(expected_trace, dict)


def test_price_threshold_controller_fixture_has_active_exact_trace() -> None:
    fixture_data = next(
        data
        for path, data in load_all_controller_pack_fixtures()
        if path == Path("tests/fixtures/simulator/price_threshold_controller_case.json")
    )

    assert fixture_data["status"] == "active"
    assert fixture_data["expected_trace"] == {
        "requested_power_kw": [5.0, 0.0, -5.0],
        "realized_power_kw": [5.0, 0.0, -5.0],
        "soc": [0.975, 0.975, 0.44868421052631574],
        "step_settlement": [-0.5, -0.0, 1.2],
        "total_settlement": 0.7,
        "constraint_events": [],
    }


def test_soc_guardrail_controller_fixture_has_active_exact_trace() -> None:
    fixture_data = next(
        data
        for path, data in load_all_controller_pack_fixtures()
        if path == Path("tests/fixtures/simulator/soc_guardrail_arbitrage_case.json")
    )

    assert fixture_data["status"] == "active"
    assert fixture_data["expected_trace"] == {
        "requested_power_kw": [5.0, 0.0, 0.0],
        "realized_power_kw": [5.0, 0.0, 0.0],
        "soc": [0.675, 0.675, 0.675],
        "step_settlement": [-0.5, -0.0, -0.0],
        "total_settlement": -0.5,
        "constraint_events": [],
    }


def test_pv_self_consumption_controller_fixture_has_active_exact_trace() -> None:
    fixture_data = next(
        data
        for path, data in load_all_controller_pack_fixtures()
        if path == Path("tests/fixtures/simulator/pv_self_consumption_case.json")
    )

    assert fixture_data["status"] == "active"
    assert fixture_data["expected_trace"] == {
        "requested_power_kw": [-2.0, 0.492, 3.468],
        "realized_power_kw": [-2.0, 0.492, 3.468],
        "soc": [0.2894736842105263, 0.33621368421052633, 0.6656736842105263],
        "pv_generation_kw": [0.0, 1.992, 3.968],
        "net_grid_power_kw": [0.0, 0.0, 0.0],
        "net_grid_energy_kwh": [0.0, 0.0, 0.0],
        "direction": ["neutral", "neutral", "neutral"],
        "step_settlement": [0.0, 0.0, 0.0],
        "total_settlement": 0.0,
        "constraint_events": [],
    }


@pytest.mark.parametrize(
    ("fixture_path", "scenario_kind", "scenario_keys", "planned_config_keys"),
    (
        (
            Path("tests/fixtures/simulator/price_threshold_controller_case.json"),
            "ArbitrageScenario",
            (),
            (
                "charge_below_import_price",
                "discharge_above_import_price",
                "charge_request_kw",
                "discharge_request_kw",
            ),
        ),
        (
            Path("tests/fixtures/simulator/soc_guardrail_arbitrage_case.json"),
            "ArbitrageScenario",
            (),
            (
                "target_min_soc",
                "target_max_soc",
                "charge_request_kw",
                "discharge_request_kw",
            ),
        ),
        (
            Path("tests/fixtures/simulator/pv_self_consumption_case.json"),
            "BatteryLoadPVScenario",
            LOAD_PV_SCENARIO_KEYS,
            (
                "reserve_min_soc",
                "reserve_max_soc",
                "charge_request_kw",
                "discharge_request_kw",
            ),
        ),
    ),
)
def test_controller_pack_fixture_scaffolds_match_planned_schema(
    fixture_path: Path,
    scenario_kind: str,
    scenario_keys: tuple[str, ...],
    planned_config_keys: tuple[str, ...],
) -> None:
    fixture_data = next(
        data for path, data in load_all_controller_pack_fixtures() if path == fixture_path
    )

    assert fixture_data["scenario_kind"] == scenario_kind
    missing_scenario_keys = [key for key in scenario_keys if key not in fixture_data]
    assert missing_scenario_keys == []
    assert tuple(fixture_data["planned_config"]) == planned_config_keys


def test_controller_pack_fixture_legacy_references_distinguish_pv_context_evidence() -> None:
    fixtures = dict(load_all_controller_pack_fixtures())

    price_threshold_legacy = fixtures[
        Path("tests/fixtures/simulator/price_threshold_controller_case.json")
    ]["legacy_references"]
    soc_guardrail_legacy = fixtures[
        Path("tests/fixtures/simulator/soc_guardrail_arbitrage_case.json")
    ]["legacy_references"]
    pv_self_consumption_legacy = fixtures[
        Path("tests/fixtures/simulator/pv_self_consumption_case.json")
    ]["legacy_references"]

    assert "legacy/fed_trpo/src/custom/building.py" not in price_threshold_legacy
    assert "legacy/fed_trpo/src/custom/building.py" not in soc_guardrail_legacy
    assert "legacy/old_tpm/src_py/simulator/common/specs.py" in pv_self_consumption_legacy
    assert "legacy/fed_trpo/src/custom/building.py" in pv_self_consumption_legacy
