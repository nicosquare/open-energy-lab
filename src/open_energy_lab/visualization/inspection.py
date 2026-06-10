"""Stable inspection builders for supported deterministic visualization inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ._persistence import load_persisted_run_output


_ARBITRAGE_SCENARIO_KIND = "ArbitrageScenario"
_STABLE_MATURITY = "stable"
_ARBITRAGE_AVAILABLE_SECTIONS = {
    "battery": True,
    "dispatch": True,
    "pricing": True,
    "settlement": True,
    "load": False,
    "pv": False,
    "net_grid": False,
    "weather": False,
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


def _require_arbitrage_scenario_kind(scenario_kind: str) -> None:
    if scenario_kind != _ARBITRAGE_SCENARIO_KIND:
        raise NotImplementedError(
            "build_inspection_view currently supports ArbitrageScenario inputs for US1"
        )


def _build_view_from_simulation_trace(
    trace: object,
    *,
    scenario: object,
) -> dict[str, object]:
    scenario_kind = type(scenario).__name__
    _require_arbitrage_scenario_kind(scenario_kind)

    step_count = len(trace.realized_power_kw)
    if len(trace.requested_power_kw) != step_count:
        raise ValueError("trace requested_power_kw and realized_power_kw must align")

    scenario_labels = getattr(getattr(scenario, "time_grid", None), "step_labels", None)
    step_labels = _coerce_step_labels(step_count=step_count, provided_labels=scenario_labels)
    price_signal = getattr(scenario, "price_signal", None)
    import_prices = getattr(price_signal, "import_prices", None)
    if import_prices is None:
        raise ValueError("scenario.price_signal.import_prices is required for inspection")
    if len(import_prices) != step_count:
        raise ValueError("scenario import_prices must align to the trace length")

    trace_series = [
        _series_entry(
            series_name="battery_soc",
            values=[state.soc for state in trace.states],
            units="fraction",
            source_field="states.soc",
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

    return {
        "scenario_id": scenario.scenario_id,
        "scenario_kind": scenario_kind,
        "trace_series": trace_series,
        "summary_outcomes": [
            _summary_entry(
                summary_name="total_settlement",
                value=trace.total_settlement,
                units="usd",
                source_field="total_settlement",
                display_group="settlement",
            )
        ],
        "available_sections": dict(_ARBITRAGE_AVAILABLE_SECTIONS),
        "maturity": _STABLE_MATURITY,
        "source_kind": "simulation_trace",
    }


def _build_view_from_controller_result(result: object) -> dict[str, object]:
    scenario_kind = getattr(result, "scenario_kind")
    _require_arbitrage_scenario_kind(scenario_kind)

    if getattr(result, "rejection", None) is not None:
        raise ValueError("controller evaluation must succeed before it can be inspected")

    trace = getattr(result, "underlying_trace", None)
    if trace is None:
        raise ValueError("controller evaluation is missing underlying_trace")

    step_records = list(getattr(result, "step_records"))
    step_count = len(step_records)
    if step_count == 0:
        raise ValueError("controller evaluation must include step_records")

    import_prices = [record.context.price_input.import_price for record in step_records]
    step_labels = _coerce_step_labels(step_count=step_count)

    trace_series = [
        _series_entry(
            series_name="battery_soc",
            values=[state.soc for state in trace.states],
            units="fraction",
            source_field="underlying_trace.states.soc",
            display_category="battery",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="requested_power_kw",
            values=result.requested_power_kw,
            units="kw",
            source_field="requested_power_kw",
            display_category="dispatch",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="realized_power_kw",
            values=result.realized_power_kw,
            units="kw",
            source_field="realized_power_kw",
            display_category="dispatch",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="import_price",
            values=import_prices,
            units="usd_per_kwh",
            source_field="step_records.context.price_input.import_price",
            display_category="pricing",
            step_labels=step_labels,
        ),
        _series_entry(
            series_name="step_settlement",
            values=[record.step_settlement for record in step_records],
            units="usd",
            source_field="step_records.step_settlement",
            display_category="settlement",
            step_labels=step_labels,
        ),
    ]

    return {
        "scenario_id": result.scenario_id,
        "scenario_kind": scenario_kind,
        "trace_series": trace_series,
        "summary_outcomes": [
            _summary_entry(
                summary_name="total_settlement",
                value=result.total_settlement,
                units="usd",
                source_field="total_settlement",
                display_group="settlement",
            )
        ],
        "available_sections": dict(_ARBITRAGE_AVAILABLE_SECTIONS),
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
