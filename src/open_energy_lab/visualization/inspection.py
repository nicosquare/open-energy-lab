"""Stable inspection builders for supported deterministic visualization inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ._persistence import load_persisted_run_output


_ARBITRAGE_SCENARIO_KIND = "ArbitrageScenario"
_BATTERY_LOAD_PV_SCENARIO_KIND = "BatteryLoadPVScenario"
_STABLE_MATURITY = "stable"
_AVAILABLE_SECTIONS_BY_SCENARIO_KIND = {
    _ARBITRAGE_SCENARIO_KIND: {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": False,
        "pv": False,
        "net_grid": False,
        "weather": False,
    },
    _BATTERY_LOAD_PV_SCENARIO_KIND: {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": True,
        "pv": True,
        "net_grid": True,
        "weather": True,
    },
}


def _is_persisted_output_candidate(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required_keys = {
        "scenario_id",
        "scenario_kind",
        "trace_payload",
        "summary_payload",
        "realized_power_kw",
        "step_settlement",
    }
    return required_keys.issubset(value)


def _is_inspection_view(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    required_keys = {
        "scenario_id",
        "scenario_kind",
        "trace_series",
        "summary_outcomes",
        "available_sections",
        "source_kind",
    }
    return required_keys.issubset(value)


def _is_controller_evaluation_result(value: object) -> bool:
    return all(
        hasattr(value, attribute_name)
        for attribute_name in (
            "scenario_id",
            "scenario_kind",
            "step_records",
            "requested_power_kw",
            "realized_power_kw",
            "underlying_trace",
        )
    )


def _coerce_step_labels(
    *,
    step_count: int,
    provided_labels: Sequence[str] | None = None,
) -> list[str]:
    if provided_labels is not None:
        labels = [str(label) for label in provided_labels]
        if len(labels) != step_count:
            raise ValueError(f"step_labels must have length {step_count}")
        return labels
    return [f"step-{index}" for index in range(step_count)]


def _series_entry(
    *,
    series_name: str,
    values: Sequence[float] | Sequence[str],
    units: str,
    source_field: str,
    display_category: str,
    step_labels: Sequence[str],
    optional: bool = False,
) -> dict[str, object]:
    return {
        "series_name": series_name,
        "values": list(values),
        "units": units,
        "source_field": source_field,
        "display_category": display_category,
        "step_labels": list(step_labels),
        "optional": optional,
    }


def _summary_entry(
    *,
    summary_name: str,
    value: float,
    units: str,
    source_field: str,
    display_group: str,
) -> dict[str, object]:
    return {
        "summary_name": summary_name,
        "value": float(value),
        "units": units,
        "source_field": source_field,
        "display_group": display_group,
    }


def _build_view_from_persisted_output(
    persisted_output: Mapping[str, object],
) -> dict[str, object]:
    normalized_output = load_persisted_run_output(persisted_output)
    trace_payload = normalized_output["trace_payload"]
    summary_payload = normalized_output["summary_payload"]

    series_entries = []
    for series_name, payload in trace_payload["series"].items():
        step_labels = payload.get("step_labels")
        if step_labels is None:
            step_labels = _coerce_step_labels(step_count=len(payload["values"]))
        series_entries.append(
            _series_entry(
                series_name=series_name,
                values=payload["values"],
                units=payload["units"],
                source_field=payload["source_field"],
                display_category=payload.get("display_category", "trace"),
                step_labels=step_labels,
                optional=bool(payload.get("optional", False)),
            )
        )

    summary_entries = [
        _summary_entry(
            summary_name=summary_name,
            value=payload["value"],
            units=payload["units"],
            source_field=payload["source_field"],
            display_group=payload["display_group"],
        )
        for summary_name, payload in summary_payload.items()
    ]

    return {
        "scenario_id": normalized_output["scenario_id"],
        "scenario_kind": normalized_output["scenario_kind"],
        "trace_series": series_entries,
        "summary_outcomes": summary_entries,
        "available_sections": dict(trace_payload["available_sections"]),
        "maturity": _STABLE_MATURITY,
        "source_kind": "persisted_output",
    }


def _require_supported_scenario_kind(scenario_kind: str) -> None:
    if scenario_kind not in _AVAILABLE_SECTIONS_BY_SCENARIO_KIND:
        raise NotImplementedError(
            "build_inspection_view supports ArbitrageScenario and "
            "BatteryLoadPVScenario inputs in the current MVP"
        )


def _require_series_length(
    values: Sequence[object],
    *,
    expected_length: int,
    field_name: str,
) -> None:
    if len(values) != expected_length:
        raise ValueError(f"{field_name} must align to the trace length {expected_length}")


def _require_weather_step_labels(weather: object, *, step_count: int) -> list[str]:
    timestamp_utc = getattr(weather, "timestamp_utc", None)
    if timestamp_utc is None:
        raise ValueError("scenario.weather.timestamp_utc is required for inspection")
    _require_series_length(
        timestamp_utc,
        expected_length=step_count,
        field_name="scenario.weather.timestamp_utc",
    )
    return [str(value) for value in timestamp_utc]


def _require_numeric_weather_series(
    weather: object,
    *,
    field_name: str,
    step_count: int,
) -> list[float]:
    values = getattr(weather, field_name, None)
    if values is None:
        raise ValueError(f"scenario.weather.{field_name} is required for inspection")
    _require_series_length(
        values,
        expected_length=step_count,
        field_name=f"scenario.weather.{field_name}",
    )
    return [float(value) for value in values]


def _build_summary_outcomes(*, total_settlement: float) -> list[dict[str, object]]:
    return [
        _summary_entry(
            summary_name="total_settlement",
            value=total_settlement,
            units="usd",
            source_field="total_settlement",
            display_group="settlement",
        )
    ]


def _build_arbitrage_trace_series(
    *,
    trace: object,
    import_prices: Sequence[float],
    step_labels: Sequence[str],
    battery_soc_source_field: str,
) -> list[dict[str, object]]:
    return [
        _series_entry(
            series_name="battery_soc",
            values=[state.soc for state in trace.states],
            units="fraction",
            source_field=battery_soc_source_field,
            display_category="battery",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="requested_power_kw",
            values=trace.requested_power_kw,
            units="kw",
            source_field="requested_power_kw",
            display_category="dispatch",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="realized_power_kw",
            values=trace.realized_power_kw,
            units="kw",
            source_field="realized_power_kw",
            display_category="dispatch",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="import_price",
            values=import_prices,
            units="usd_per_kwh",
            source_field="price_signal.import_prices",
            display_category="pricing",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="step_settlement",
            values=trace.step_settlement,
            units="usd",
            source_field="step_settlement",
            display_category="settlement",
            step_labels=step_labels,
        ),
    ]


def _build_battery_load_pv_trace_series(
    *,
    trace: object,
    import_prices: Sequence[float],
    timestamp_utc: Sequence[str],
    dry_bulb_air_temperature_c: Sequence[float],
    global_horizontal_irradiance_w_per_m2: Sequence[float],
    battery_soc_source_field: str,
) -> list[dict[str, object]]:
    return [
        _series_entry(
            series_name="battery_soc",
            values=[state.soc for state in trace.states],
            units="fraction",
            source_field=battery_soc_source_field,
            display_category="battery",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="requested_power_kw",
            values=trace.requested_power_kw,
            units="kw",
            source_field="requested_power_kw",
            display_category="dispatch",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="realized_power_kw",
            values=trace.realized_power_kw,
            units="kw",
            source_field="realized_power_kw",
            display_category="dispatch",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="load_kw",
            values=trace.load_kw,
            units="kw",
            source_field="load.demand_kw",
            display_category="load",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="pv_generation_kw",
            values=trace.pv_generation_kw,
            units="kw",
            source_field="pv_generation_kw",
            display_category="pv",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="net_grid_power_kw",
            values=trace.net_grid_power_kw,
            units="kw",
            source_field="net_grid_power_kw",
            display_category="net_grid",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="net_grid_energy_kwh",
            values=trace.net_grid_energy_kwh,
            units="kwh",
            source_field="net_grid_energy_kwh",
            display_category="net_grid",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="direction",
            values=trace.direction,
            units="label",
            source_field="direction",
            display_category="net_grid",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="import_price",
            values=import_prices,
            units="usd_per_kwh",
            source_field="price_signal.import_prices",
            display_category="pricing",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="step_settlement",
            values=trace.step_settlement,
            units="usd",
            source_field="step_settlement",
            display_category="settlement",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="timestamp_utc",
            values=timestamp_utc,
            units="iso8601",
            source_field="weather.timestamp_utc",
            display_category="weather",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="dry_bulb_air_temperature_c",
            values=dry_bulb_air_temperature_c,
            units="celsius",
            source_field="weather.dry_bulb_air_temperature_c",
            display_category="weather",
            step_labels=timestamp_utc,
        ),
        _series_entry(
            series_name="global_horizontal_irradiance_w_per_m2",
            values=global_horizontal_irradiance_w_per_m2,
            units="w_per_m2",
            source_field="weather.global_horizontal_irradiance_w_per_m2",
            display_category="weather",
            step_labels=timestamp_utc,
        ),
    ]


def _build_view_from_simulation_trace(
    trace: object,
    *,
    scenario: object,
) -> dict[str, object]:
    scenario_kind = type(scenario).__name__
    _require_supported_scenario_kind(scenario_kind)

    step_count = len(trace.realized_power_kw)
    if len(trace.requested_power_kw) != step_count:
        raise ValueError("trace requested_power_kw and realized_power_kw must align")
    if len(trace.step_settlement) != step_count:
        raise ValueError("trace step_settlement must align to the trace length")

    price_signal = getattr(scenario, "price_signal", None)
    import_prices = getattr(price_signal, "import_prices", None)
    if import_prices is None:
        raise ValueError("scenario.price_signal.import_prices is required for inspection")
    _require_series_length(
        import_prices,
        expected_length=step_count,
        field_name="scenario.price_signal.import_prices",
    )

    if scenario_kind == _ARBITRAGE_SCENARIO_KIND:
        scenario_labels = getattr(getattr(scenario, "time_grid", None), "step_labels", None)
        step_labels = _coerce_step_labels(step_count=step_count, provided_labels=scenario_labels)
        trace_series = _build_arbitrage_trace_series(
            trace=trace,
            import_prices=import_prices,
            step_labels=step_labels,
            battery_soc_source_field="states.soc",
        )
    else:
        _require_series_length(trace.load_kw, expected_length=step_count, field_name="trace.load_kw")
        _require_series_length(
            trace.pv_generation_kw,
            expected_length=step_count,
            field_name="trace.pv_generation_kw",
        )
        _require_series_length(
            trace.net_grid_power_kw,
            expected_length=step_count,
            field_name="trace.net_grid_power_kw",
        )
        _require_series_length(
            trace.net_grid_energy_kwh,
            expected_length=step_count,
            field_name="trace.net_grid_energy_kwh",
        )
        _require_series_length(
            trace.direction,
            expected_length=step_count,
            field_name="trace.direction",
        )
        weather = getattr(scenario, "weather", None)
        if weather is None:
            raise ValueError("BatteryLoadPVScenario inspection requires weather context")
        timestamp_utc = _require_weather_step_labels(weather, step_count=step_count)
        dry_bulb_air_temperature_c = _require_numeric_weather_series(
            weather,
            field_name="dry_bulb_air_temperature_c",
            step_count=step_count,
        )
        global_horizontal_irradiance_w_per_m2 = _require_numeric_weather_series(
            weather,
            field_name="global_horizontal_irradiance_w_per_m2",
            step_count=step_count,
        )
        trace_series = _build_battery_load_pv_trace_series(
            trace=trace,
            import_prices=import_prices,
            timestamp_utc=timestamp_utc,
            dry_bulb_air_temperature_c=dry_bulb_air_temperature_c,
            global_horizontal_irradiance_w_per_m2=global_horizontal_irradiance_w_per_m2,
            battery_soc_source_field="states.soc",
        )

    return {
        "scenario_id": scenario.scenario_id,
        "scenario_kind": scenario_kind,
        "trace_series": trace_series,
        "summary_outcomes": _build_summary_outcomes(total_settlement=trace.total_settlement),
        "available_sections": dict(_AVAILABLE_SECTIONS_BY_SCENARIO_KIND[scenario_kind]),
        "maturity": _STABLE_MATURITY,
        "source_kind": "simulation_trace",
    }


def _build_view_from_controller_result(result: object) -> dict[str, object]:
    scenario_kind = getattr(result, "scenario_kind")
    _require_supported_scenario_kind(scenario_kind)

    if getattr(result, "rejection", None) is not None:
        raise ValueError("controller evaluation must succeed before it can be inspected")

    trace = getattr(result, "underlying_trace", None)
    if trace is None:
        raise ValueError("controller evaluation is missing underlying_trace")

    step_records = list(getattr(result, "step_records"))
    step_count = len(step_records)
    if step_count == 0:
        raise ValueError("controller evaluation must include step_records")

    step_labels = _coerce_step_labels(step_count=step_count)
    import_prices = [record.context.price_input.import_price for record in step_records]

    if scenario_kind == _ARBITRAGE_SCENARIO_KIND:
        trace_series = _build_arbitrage_trace_series(
            trace=trace,
            import_prices=import_prices,
            step_labels=step_labels,
            battery_soc_source_field="underlying_trace.states.soc",
        )
    else:
        source_scenario = getattr(result, "source_scenario", None)
        if source_scenario is None:
            raise ValueError(
                "BatteryLoadPVScenario controller inspection requires source_scenario"
            )
        _require_series_length(trace.load_kw, expected_length=step_count, field_name="trace.load_kw")
        _require_series_length(
            trace.pv_generation_kw,
            expected_length=step_count,
            field_name="trace.pv_generation_kw",
        )
        _require_series_length(
            trace.net_grid_power_kw,
            expected_length=step_count,
            field_name="trace.net_grid_power_kw",
        )
        _require_series_length(
            trace.net_grid_energy_kwh,
            expected_length=step_count,
            field_name="trace.net_grid_energy_kwh",
        )
        _require_series_length(
            trace.direction,
            expected_length=step_count,
            field_name="trace.direction",
        )
        weather = getattr(source_scenario, "weather", None)
        if weather is None:
            raise ValueError(
                "BatteryLoadPVScenario controller inspection requires weather context"
            )
        timestamp_utc = _require_weather_step_labels(weather, step_count=step_count)
        dry_bulb_air_temperature_c = _require_numeric_weather_series(
            weather,
            field_name="dry_bulb_air_temperature_c",
            step_count=step_count,
        )
        global_horizontal_irradiance_w_per_m2 = _require_numeric_weather_series(
            weather,
            field_name="global_horizontal_irradiance_w_per_m2",
            step_count=step_count,
        )
        trace_series = _build_battery_load_pv_trace_series(
            trace=trace,
            import_prices=import_prices,
            timestamp_utc=timestamp_utc,
            dry_bulb_air_temperature_c=dry_bulb_air_temperature_c,
            global_horizontal_irradiance_w_per_m2=global_horizontal_irradiance_w_per_m2,
            battery_soc_source_field="underlying_trace.states.soc",
        )

    return {
        "scenario_id": result.scenario_id,
        "scenario_kind": scenario_kind,
        "trace_series": trace_series,
        "summary_outcomes": _build_summary_outcomes(total_settlement=result.total_settlement),
        "available_sections": dict(_AVAILABLE_SECTIONS_BY_SCENARIO_KIND[scenario_kind]),
        "maturity": _STABLE_MATURITY,
        "source_kind": "controller_evaluation",
    }


def build_inspection_view(
    value: object,
    *,
    scenario: object | None = None,
) -> dict[str, object]:
    """Build one stable inspection view from a supported deterministic input."""

    if _is_inspection_view(value):
        return {
            "scenario_id": value["scenario_id"],
            "scenario_kind": value["scenario_kind"],
            "trace_series": [dict(series) for series in value["trace_series"]],
            "summary_outcomes": [dict(item) for item in value["summary_outcomes"]],
            "available_sections": dict(value["available_sections"]),
            "maturity": value.get("maturity", _STABLE_MATURITY),
            "source_kind": value["source_kind"],
        }

    if _is_persisted_output_candidate(value):
        return _build_view_from_persisted_output(value)

    if _is_controller_evaluation_result(value):
        return _build_view_from_controller_result(value)

    if scenario is None:
        raise TypeError(
            "build_inspection_view requires a scenario for direct simulation traces"
        )
    return _build_view_from_simulation_trace(value, scenario=scenario)


def summarize_inspection_view(
    value: object,
    *,
    scenario: object | None = None,
) -> dict[str, object]:
    """Extract the stable summary/reporting surface from an inspection view."""

    view = build_inspection_view(value, scenario=scenario)
    return {
        "scenario_id": view["scenario_id"],
        "scenario_kind": view["scenario_kind"],
        "summary_outcomes": [dict(item) for item in view["summary_outcomes"]],
        "available_sections": dict(view["available_sections"]),
        "source_kind": view["source_kind"],
        "maturity": view["maturity"],
    }


__all__ = ["build_inspection_view", "summarize_inspection_view"]
