"""Persisted-output normalization and validation for visualization fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import isclose


DEFAULT_ABSOLUTE_TOLERANCE = 1e-6
SUPPORTED_PERSISTED_SCENARIO_KINDS = (
    "ArbitrageScenario",
    "BatteryLoadPVScenario",
)
REQUIRED_PERSISTED_OUTPUT_KEYS = (
    "scenario_id",
    "scenario_kind",
    "time_step_hours",
    "realized_power_kw",
    "step_settlement",
    "trace_payload",
    "summary_payload",
    "provenance_notes",
)
OPTIONAL_PERSISTED_OUTPUT_KEYS = ("requested_power_kw",)
_ALLOWED_PERSISTED_OUTPUT_KEYS = (
    set(REQUIRED_PERSISTED_OUTPUT_KEYS) | set(OPTIONAL_PERSISTED_OUTPUT_KEYS)
)
_TRACE_PAYLOAD_KEYS = {"series", "available_sections"}
_SERIES_REQUIRED_KEYS = {"values", "units", "source_field"}
_SERIES_OPTIONAL_KEYS = {"display_category", "optional", "step_labels"}
_SUMMARY_REQUIRED_KEYS = {"value", "units", "source_field", "display_group"}
_SECTION_REQUIREMENTS = {
    "ArbitrageScenario": {
        "battery": True,
        "dispatch": True,
        "pricing": True,
        "settlement": True,
        "load": False,
        "pv": False,
        "net_grid": False,
        "weather": False,
    },
    "BatteryLoadPVScenario": {
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


def _require_non_empty_text(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or value == "":
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_numeric_scalar(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def _require_positive_scalar(value: object, *, field_name: str) -> float:
    normalized = _require_numeric_scalar(value, field_name=field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return normalized


def _require_mapping(value: object, *, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return value


def _normalize_text_sequence(
    value: object,
    *,
    field_name: str,
    allow_empty: bool = False,
) -> list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of strings")

    normalized: list[str] = []
    for item in value:
        text = _require_non_empty_text(item, field_name=field_name)
        normalized.append(text)

    if not allow_empty and not normalized:
        raise ValueError(f"{field_name} must not be empty")
    return normalized


def _normalize_series_values(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> list[float] | list[str]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence")

    if len(value) != expected_length:
        raise ValueError(f"{field_name} must have length {expected_length}")
    if expected_length == 0:
        raise ValueError(f"{field_name} must not be empty")

    normalized_numeric: list[float] = []
    normalized_text: list[str] = []
    value_kind: str | None = None

    for item in value:
        if isinstance(item, bool):
            raise TypeError(f"{field_name} values must not be boolean")
        if isinstance(item, (int, float)):
            if value_kind == "text":
                raise TypeError(f"{field_name} must not mix numeric and text values")
            value_kind = "numeric"
            normalized_numeric.append(float(item))
            continue
        if isinstance(item, str):
            if item == "":
                raise ValueError(f"{field_name} text values must be non-empty")
            if value_kind == "numeric":
                raise TypeError(f"{field_name} must not mix numeric and text values")
            value_kind = "text"
            normalized_text.append(item)
            continue
        raise TypeError(f"{field_name} values must be numeric or text")

    if value_kind == "numeric":
        return normalized_numeric
    if value_kind == "text":
        return normalized_text
    raise ValueError(f"{field_name} must not be empty")


def _normalize_numeric_series(
    value: object,
    *,
    field_name: str,
    expected_length: int,
) -> list[float]:
    normalized = _normalize_series_values(
        value,
        field_name=field_name,
        expected_length=expected_length,
    )
    if not normalized or not isinstance(normalized[0], float):
        raise TypeError(f"{field_name} must be numeric")
    return normalized


def _normalize_available_sections(
    value: object,
    *,
    scenario_kind: str,
) -> dict[str, bool]:
    mapping = _require_mapping(value, field_name="trace_payload.available_sections")
    required_sections = _SECTION_REQUIREMENTS[scenario_kind]

    unexpected_sections = sorted(set(mapping) - set(required_sections))
    missing_sections = sorted(set(required_sections) - set(mapping))
    if unexpected_sections:
        raise ValueError(
            "trace_payload.available_sections contains unsupported sections: "
            f"{unexpected_sections}"
        )
    if missing_sections:
        raise ValueError(
            "trace_payload.available_sections is missing required sections: "
            f"{missing_sections}"
        )

    normalized: dict[str, bool] = {}
    for section_name, expected_value in required_sections.items():
        actual_value = mapping[section_name]
        if not isinstance(actual_value, bool):
            raise TypeError(
                "trace_payload.available_sections values must be booleans"
            )
        if actual_value is not expected_value:
            raise ValueError(
                "trace_payload.available_sections must explicitly preserve "
                f"{section_name}={expected_value!r} for {scenario_kind}"
            )
        normalized[section_name] = actual_value
    return normalized


def _normalize_trace_payload(
    value: object,
    *,
    scenario_kind: str,
    step_count: int,
) -> dict[str, object]:
    mapping = _require_mapping(value, field_name="trace_payload")
    unexpected_keys = sorted(set(mapping) - _TRACE_PAYLOAD_KEYS)
    missing_keys = sorted(_TRACE_PAYLOAD_KEYS - set(mapping))
    if unexpected_keys:
        raise ValueError(f"trace_payload contains unsupported keys: {unexpected_keys}")
    if missing_keys:
        raise ValueError(f"trace_payload is missing required keys: {missing_keys}")

    series_mapping = _require_mapping(mapping["series"], field_name="trace_payload.series")
    if not series_mapping:
        raise ValueError("trace_payload.series must not be empty")

    normalized_series: dict[str, dict[str, object]] = {}
    for series_name, series_value in series_mapping.items():
        normalized_series_name = _require_non_empty_text(
            series_name,
            field_name="trace_payload.series key",
        )
        series_payload = _require_mapping(
            series_value,
            field_name=f"trace_payload.series[{normalized_series_name!r}]",
        )
        unexpected_series_keys = sorted(
            set(series_payload) - (_SERIES_REQUIRED_KEYS | _SERIES_OPTIONAL_KEYS)
        )
        missing_series_keys = sorted(_SERIES_REQUIRED_KEYS - set(series_payload))
        if unexpected_series_keys:
            raise ValueError(
                "trace_payload.series "
                f"{normalized_series_name!r} contains unsupported keys: "
                f"{unexpected_series_keys}"
            )
        if missing_series_keys:
            raise ValueError(
                "trace_payload.series "
                f"{normalized_series_name!r} is missing required keys: "
                f"{missing_series_keys}"
            )

        normalized_series_payload: dict[str, object] = {
            "values": _normalize_series_values(
                series_payload["values"],
                field_name=f"trace_payload.series[{normalized_series_name!r}].values",
                expected_length=step_count,
            ),
            "units": _require_non_empty_text(
                series_payload["units"],
                field_name=f"trace_payload.series[{normalized_series_name!r}].units",
            ),
            "source_field": _require_non_empty_text(
                series_payload["source_field"],
                field_name=(
                    f"trace_payload.series[{normalized_series_name!r}].source_field"
                ),
            ),
            "optional": bool(series_payload.get("optional", False)),
        }

        if "display_category" in series_payload:
            normalized_series_payload["display_category"] = _require_non_empty_text(
                series_payload["display_category"],
                field_name=(
                    f"trace_payload.series[{normalized_series_name!r}].display_category"
                ),
            )
        if "step_labels" in series_payload:
            normalized_step_labels = _normalize_text_sequence(
                series_payload["step_labels"],
                field_name=(
                    f"trace_payload.series[{normalized_series_name!r}].step_labels"
                ),
                allow_empty=False,
            )
            if len(normalized_step_labels) != step_count:
                raise ValueError(
                    "trace_payload.series "
                    f"{normalized_series_name!r} step_labels must have length {step_count}"
                )
            normalized_series_payload["step_labels"] = normalized_step_labels
        normalized_series[normalized_series_name] = normalized_series_payload

    return {
        "series": normalized_series,
        "available_sections": _normalize_available_sections(
            mapping["available_sections"],
            scenario_kind=scenario_kind,
        ),
    }


def _normalize_summary_payload(
    value: object,
    *,
    step_settlement: list[float],
) -> dict[str, dict[str, object]]:
    mapping = _require_mapping(value, field_name="summary_payload")
    if not mapping:
        raise ValueError("summary_payload must not be empty")

    normalized: dict[str, dict[str, object]] = {}
    for summary_name, summary_value in mapping.items():
        normalized_summary_name = _require_non_empty_text(
            summary_name,
            field_name="summary_payload key",
        )
        summary_payload = _require_mapping(
            summary_value,
            field_name=f"summary_payload[{normalized_summary_name!r}]",
        )
        unexpected_keys = sorted(set(summary_payload) - _SUMMARY_REQUIRED_KEYS)
        missing_keys = sorted(_SUMMARY_REQUIRED_KEYS - set(summary_payload))
        if unexpected_keys:
            raise ValueError(
                "summary_payload "
                f"{normalized_summary_name!r} contains unsupported keys: "
                f"{unexpected_keys}"
            )
        if missing_keys:
            raise ValueError(
                "summary_payload "
                f"{normalized_summary_name!r} is missing required keys: "
                f"{missing_keys}"
            )

        normalized[normalized_summary_name] = {
            "value": _require_numeric_scalar(
                summary_payload["value"],
                field_name=f"summary_payload[{normalized_summary_name!r}].value",
            ),
            "units": _require_non_empty_text(
                summary_payload["units"],
                field_name=f"summary_payload[{normalized_summary_name!r}].units",
            ),
            "source_field": _require_non_empty_text(
                summary_payload["source_field"],
                field_name=f"summary_payload[{normalized_summary_name!r}].source_field",
            ),
            "display_group": _require_non_empty_text(
                summary_payload["display_group"],
                field_name=f"summary_payload[{normalized_summary_name!r}].display_group",
            ),
        }

    total_settlement = normalized.get("total_settlement")
    if total_settlement is None:
        raise ValueError("summary_payload must contain 'total_settlement'")
    if not isclose(
        total_settlement["value"],
        sum(step_settlement),
        abs_tol=DEFAULT_ABSOLUTE_TOLERANCE,
    ):
        raise ValueError(
            "summary_payload['total_settlement'] must match the summed step_settlement"
        )
    return normalized


def normalize_persisted_output(value: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize one supported persisted visualization payload."""

    mapping = _require_mapping(value, field_name="persisted_output")
    missing_keys = sorted(set(REQUIRED_PERSISTED_OUTPUT_KEYS) - set(mapping))
    unexpected_keys = sorted(set(mapping) - _ALLOWED_PERSISTED_OUTPUT_KEYS)
    if missing_keys:
        raise ValueError(f"persisted_output is missing required keys: {missing_keys}")
    if unexpected_keys:
        raise ValueError(f"persisted_output contains unsupported keys: {unexpected_keys}")

    scenario_kind = _require_non_empty_text(
        mapping["scenario_kind"],
        field_name="scenario_kind",
    )
    if scenario_kind not in SUPPORTED_PERSISTED_SCENARIO_KINDS:
        raise ValueError(
            f"scenario_kind must be one of {SUPPORTED_PERSISTED_SCENARIO_KINDS!r}"
        )

    normalized_realized_power_kw = _normalize_numeric_series(
        mapping["realized_power_kw"],
        field_name="realized_power_kw",
        expected_length=len(mapping["realized_power_kw"]),
    )
    step_count = len(normalized_realized_power_kw)
    normalized_step_settlement = _normalize_numeric_series(
        mapping["step_settlement"],
        field_name="step_settlement",
        expected_length=step_count,
    )

    normalized: dict[str, object] = {
        "scenario_id": _require_non_empty_text(
            mapping["scenario_id"],
            field_name="scenario_id",
        ),
        "scenario_kind": scenario_kind,
        "time_step_hours": _require_positive_scalar(
            mapping["time_step_hours"],
            field_name="time_step_hours",
        ),
        "realized_power_kw": normalized_realized_power_kw,
        "step_settlement": normalized_step_settlement,
        "trace_payload": _normalize_trace_payload(
            mapping["trace_payload"],
            scenario_kind=scenario_kind,
            step_count=step_count,
        ),
        "summary_payload": _normalize_summary_payload(
            mapping["summary_payload"],
            step_settlement=normalized_step_settlement,
        ),
        "provenance_notes": _normalize_text_sequence(
            mapping["provenance_notes"],
            field_name="provenance_notes",
        ),
    }

    if "requested_power_kw" in mapping:
        normalized["requested_power_kw"] = _normalize_numeric_series(
            mapping["requested_power_kw"],
            field_name="requested_power_kw",
            expected_length=step_count,
        )

    return normalized


def validate_persisted_output(value: Mapping[str, object]) -> None:
    """Fail fast when a persisted visualization payload violates the schema."""

    normalize_persisted_output(value)


def load_persisted_run_output(value: Mapping[str, object]) -> dict[str, object]:
    """Normalize one supported persisted output mapping for later inspection work."""

    return normalize_persisted_output(value)


__all__ = [
    "DEFAULT_ABSOLUTE_TOLERANCE",
    "REQUIRED_PERSISTED_OUTPUT_KEYS",
    "SUPPORTED_PERSISTED_SCENARIO_KINDS",
    "load_persisted_run_output",
    "normalize_persisted_output",
    "validate_persisted_output",
]
