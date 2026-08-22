"""Contracts for source-independent regulation activation artifacts."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import importlib
import json
import math
import os
from pathlib import Path
import socket
from types import ModuleType
from typing import Any

import pytest


SCHEMA_VERSION = "oel.regulation-activation.v1"
PERIOD_START = datetime(2022, 8, 18, 22, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(hours=1)


def _activation_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.market.activation")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.market.activation is not implemented; T027 must "
            "provide the activation artifact contract",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _activation_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.market.activation.{name} is not implemented",
            pytrace=False,
        )


def _identity_normalization() -> dict[str, object]:
    return {
        "conversion": "identity",
        "formula": "activation",
        "point_to_interval": "already_interval_average",
        "clip_min": -1.0,
        "clip_max": 1.0,
        "target_sign": "positive is upward/discharge",
    }


def _frequency_normalization() -> dict[str, object]:
    return {
        "conversion": "clip_linear_frequency_droop",
        "formula": "clip((50.0 - frequency_hz) / 0.2, -1, 1)",
        "point_to_interval": "instantaneous_left_hold",
        "nominal_frequency_hz": 50.0,
        "full_activation_deviation_hz": 0.2,
        "clip_min": -1.0,
        "clip_max": 1.0,
        "target_sign": "positive is upward/discharge",
    }


def _request(
    *,
    source_value_kind: str = "interval_average",
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
    resolution: str = "PT15M",
    normalization_rule: dict[str, object] | None = None,
    source_timezone: str = "Europe/Paris",
    source_document_type: str | None = None,
    command_semantics_proof: dict[str, object] | None = None,
):
    request_type = _require("ActivationImportRequest")
    return request_type(
        source_name="Synthetic France activation",
        source_locator="fixtures/synthetic-activation.csv",
        source_revision="sha256:" + "a" * 64,
        source_timezone=source_timezone,
        requested_start_utc=start,
        requested_end_utc=end,
        source_resolution=resolution,
        source_value_kind=source_value_kind,
        source_sign_meaning=(
            "positive source activation means upward/discharge"
            if source_value_kind == "interval_average"
            else "lower frequency means upward/discharge after normalization"
        ),
        normalization_rule=(
            normalization_rule
            if normalization_rule is not None
            else (
                _identity_normalization()
                if source_value_kind == "interval_average"
                else _frequency_normalization()
            )
        ),
        redistribution_basis={
            "source": "project-authored synthetic input",
            "terms": "Apache-2.0",
            "attribution": "Open Energy Lab tests",
        },
        source_document_type=source_document_type,
        command_semantics_proof=command_semantics_proof,
    )


def _interval_inputs() -> list[dict[str, object]]:
    values = (-1.0, -0.25, 0.5, 1.0)
    return [
        {
            "start_utc": PERIOD_START + timedelta(minutes=15 * index),
            "end_utc": PERIOD_START + timedelta(minutes=15 * (index + 1)),
            "value": value,
            "source_value": value,
            "source_unit": "dimensionless",
        }
        for index, value in enumerate(values)
    ]


def _import_trace(
    request: object | None = None,
    samples: list[dict[str, object]] | None = None,
    *,
    trace_id: str = "activation-unit-v1",
    created_at_utc: datetime = datetime(2026, 8, 21, 12, tzinfo=UTC),
):
    operation = _require("import_regulation_activation_trace")
    return operation(
        _request() if request is None else request,
        _interval_inputs() if samples is None else samples,
        trace_id=trace_id,
        created_at_utc=created_at_utc,
    )


def test_interval_average_import_preserves_explicit_bounds_and_values() -> None:
    trace = _import_trace()

    assert trace.schema_version == SCHEMA_VERSION
    assert trace.resolution == "PT15M"
    assert trace.value_semantics == "interval-average normalized FCR activation"
    assert trace.sign_semantics == "positive is upward/discharge"
    assert trace.covered_period.start_utc == PERIOD_START
    assert trace.covered_period.end_utc == PERIOD_END
    assert [sample.activation for sample in trace.samples] == [-1.0, -0.25, 0.5, 1.0]
    assert [sample.source_value for sample in trace.samples] == [-1.0, -0.25, 0.5, 1.0]
    assert all(sample.conversion_ref is None for sample in trace.samples)
    assert trace.normalization["point_to_interval"] == "already_interval_average"


def test_instantaneous_points_use_declared_left_hold_and_frequency_droop() -> None:
    start = datetime(2022, 8, 18, 22, tzinfo=UTC)
    end = start + timedelta(seconds=30)
    request = _request(
        source_value_kind="instantaneous_left_hold",
        start=start,
        end=end,
        resolution="PT10S",
    )
    points = [
        {
            "timestamp": datetime(2022, 8, 19, 0, 0, 0),
            "value": 49.8,
            "source_unit": "Hz",
        },
        {
            "timestamp": datetime(2022, 8, 19, 0, 0, 10),
            "value": 50.0,
            "source_unit": "Hz",
        },
        {
            "timestamp": datetime(2022, 8, 19, 0, 0, 20),
            "value": 50.1,
            "source_unit": "Hz",
        },
    ]

    trace = _import_trace(request, points)

    assert trace.resolution == "PT10S"
    assert [sample.activation for sample in trace.samples] == pytest.approx(
        [1.0, 0.0, -0.5]
    )
    assert [sample.interval.start_utc for sample in trace.samples] == [
        start,
        start + timedelta(seconds=10),
        start + timedelta(seconds=20),
    ]
    assert all(sample.interval.end_utc - sample.interval.start_utc == timedelta(seconds=10) for sample in trace.samples)
    assert all(sample.conversion_ref == "frequency-droop-left-hold-v1" for sample in trace.samples)
    assert trace.source["timezone"] == "Europe/Paris"
    assert trace.normalization["formula"] == (
        "clip((50.0 - frequency_hz) / 0.2, -1, 1)"
    )


def test_trace_and_samples_are_immutable_and_serializable() -> None:
    trace = _import_trace()
    payload = trace.to_dict()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["samples"][0]["interval"]["interval_convention"] == (
        "start-inclusive/end-exclusive"
    )
    assert json.loads(json.dumps(payload, allow_nan=False))["trace_id"] == trace.trace_id
    with pytest.raises(FrozenInstanceError):
        trace.trace_id = "mutated"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        trace.samples[0].activation = 0.0  # type: ignore[misc]


def test_content_and_artifact_fingerprints_have_distinct_stability_rules() -> None:
    first = _import_trace()
    second = _import_trace(
        trace_id="activation-unit-copy",
        created_at_utc=datetime(2026, 8, 22, 12, tzinfo=UTC),
    )
    changed_samples = _interval_inputs()
    changed_samples[1]["value"] = -0.2
    changed_samples[1]["source_value"] = -0.2
    changed = _import_trace(samples=changed_samples)

    assert first.content_fingerprint == second.content_fingerprint
    assert first.artifact_fingerprint != second.artifact_fingerprint
    assert changed.content_fingerprint != first.content_fingerprint
    assert changed.artifact_fingerprint != first.artifact_fingerprint
    assert len(first.content_fingerprint) == 64
    assert len(first.artifact_fingerprint) == 64


def test_fingerprinted_write_reloads_offline_without_environment_or_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_trace = _require("write_regulation_activation_trace")
    load_trace = _require("load_regulation_activation_trace")
    trace = _import_trace()

    path = write_trace(trace, destination_dir=tmp_path)
    original_bytes = path.read_bytes()

    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("activation artifact load attempted network access")

    class GuardedEnvironment(dict[str, str]):
        def get(self, key: str, default: object = None) -> object:
            if "TOKEN" in key or "CREDENTIAL" in key:
                raise AssertionError("activation artifact load inspected credentials")
            return super().get(key, default)

    monkeypatch.setattr(socket, "socket", _network_forbidden)
    monkeypatch.setattr(os, "environ", GuardedEnvironment(os.environ))

    loaded = load_trace(path)
    reused = write_trace(trace, destination_dir=tmp_path)

    assert trace.artifact_fingerprint in path.name
    assert loaded.to_dict() == trace.to_dict()
    assert reused == path
    assert reused.read_bytes() == original_bytes


def test_load_rejects_unknown_schema_before_values_are_exposed(tmp_path: Path) -> None:
    load_trace = _require("load_regulation_activation_trace")
    error_type = _require("UnsupportedActivationSchemaError")
    payload = _import_trace().to_dict()
    payload["schema_version"] = "oel.regulation-activation.v999"
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(error_type, match="schema|version|v999"):
        load_trace(path)


@pytest.mark.parametrize("fingerprint_field", ["content_fingerprint", "artifact_fingerprint"])
def test_load_rejects_fingerprint_tampering(
    tmp_path: Path,
    fingerprint_field: str,
) -> None:
    load_trace = _require("load_regulation_activation_trace")
    integrity_error = _require("ActivationIntegrityError")
    payload = _import_trace().to_dict()
    payload[fingerprint_field] = "0" * 64
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(integrity_error, match="fingerprint|integrity|mismatch"):
        load_trace(path)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda items: items.__setitem__(
                1,
                {
                    **items[1],
                    "start_utc": PERIOD_START + timedelta(minutes=20),
                },
            ),
            "gap",
        ),
        (
            lambda items: items.__setitem__(1, dict(items[0])),
            "duplicate|overlap",
        ),
        (
            lambda items: items.__setitem__(
                1,
                {
                    **items[1],
                    "start_utc": PERIOD_START + timedelta(minutes=10),
                },
            ),
            "overlap",
        ),
    ],
)
def test_interval_inputs_reject_gaps_duplicates_and_overlaps(
    mutator: Any,
    message: str,
) -> None:
    validation_error = _require("ActivationValidationError")
    samples = _interval_inputs()
    mutator(samples)

    with pytest.raises(validation_error, match=message):
        _import_trace(samples=samples)


def test_left_hold_points_reject_duplicate_and_non_resolution_timestamps() -> None:
    validation_error = _require("ActivationValidationError")
    start = PERIOD_START
    request = _request(
        source_value_kind="instantaneous_left_hold",
        start=start,
        end=start + timedelta(seconds=30),
        resolution="PT10S",
    )
    base = datetime(2022, 8, 19, 0, 0)
    duplicate = [
        {"timestamp": base, "value": 50.0, "source_unit": "Hz"},
        {"timestamp": base, "value": 50.0, "source_unit": "Hz"},
        {"timestamp": base + timedelta(seconds=20), "value": 50.0, "source_unit": "Hz"},
    ]
    gap = [
        {"timestamp": base, "value": 50.0, "source_unit": "Hz"},
        {"timestamp": base + timedelta(seconds=11), "value": 50.0, "source_unit": "Hz"},
        {"timestamp": base + timedelta(seconds=20), "value": 50.0, "source_unit": "Hz"},
    ]

    with pytest.raises(validation_error, match="duplicate|unique"):
        _import_trace(request, duplicate)
    with pytest.raises(validation_error, match="gap|resolution|timestamp"):
        _import_trace(request, gap)


def test_naive_ambiguous_paris_timestamp_requires_explicit_fold() -> None:
    validation_error = _require("ActivationValidationError")
    start = datetime(2022, 10, 30, 0, tzinfo=UTC)
    request = _request(
        source_value_kind="instantaneous_left_hold",
        start=start,
        end=start + timedelta(seconds=10),
        resolution="PT10S",
    )
    points = [
        {
            "timestamp": datetime(2022, 10, 30, 2, 30),
            "value": 50.0,
            "source_unit": "Hz",
        }
    ]

    with pytest.raises(validation_error, match="ambiguous|fold|timezone"):
        _import_trace(request, points)


@pytest.mark.parametrize("bad_value", [math.nan, math.inf, -math.inf])
def test_nonfinite_source_and_activation_values_are_rejected(bad_value: float) -> None:
    validation_error = _require("ActivationValidationError")
    samples = _interval_inputs()
    samples[0]["value"] = bad_value

    with pytest.raises(validation_error, match="finite"):
        _import_trace(samples=samples)


@pytest.mark.parametrize("bad_value", [-1.000001, 1.000001])
def test_interval_average_activation_must_remain_inside_closed_range(
    bad_value: float,
) -> None:
    validation_error = _require("ActivationValidationError")
    samples = _interval_inputs()
    samples[0]["value"] = bad_value

    with pytest.raises(validation_error, match=r"range|\[-1.*1\]"):
        _import_trace(samples=samples)


@pytest.mark.parametrize(
    "source_value_kind",
    ["instantaneous_right_hold", "linear_interpolation", "inferred_from_shape"],
)
def test_unsupported_point_to_interval_semantics_are_rejected(
    source_value_kind: str,
) -> None:
    validation_error = _require("ActivationValidationError")

    with pytest.raises(validation_error, match="value kind|semantics|unsupported"):
        _request(source_value_kind=source_value_kind)


def test_declared_mode_and_normalization_conversion_must_agree() -> None:
    validation_error = _require("ActivationValidationError")
    request = _request(
        source_value_kind="interval_average",
        normalization_rule=_frequency_normalization(),
    )

    with pytest.raises(validation_error, match="normalization|conversion|mode"):
        _import_trace(request)


@pytest.mark.parametrize("document_type", ["A83", "A84"])
def test_unproven_balancing_documents_cannot_be_activation_traces(
    document_type: str,
) -> None:
    validation_error = _require("ActivationValidationError")

    with pytest.raises(validation_error, match="A83|A84|proof|activation"):
        _request(source_document_type=document_type)


def test_declared_resolution_must_match_every_canonical_interval() -> None:
    validation_error = _require("ActivationValidationError")
    samples = _interval_inputs()
    samples[0]["end_utc"] = PERIOD_START + timedelta(minutes=10)

    with pytest.raises(validation_error, match="resolution|duration|gap"):
        _import_trace(samples=samples)


def test_trace_from_dict_rejects_nonfinite_json_even_if_decoder_allows_it() -> None:
    trace_type = _require("RegulationActivationTrace")
    validation_error = _require("ActivationValidationError")
    payload = deepcopy(_import_trace().to_dict())
    payload["samples"][0]["activation"] = math.nan

    with pytest.raises(validation_error, match="finite"):
        trace_type.from_dict(payload)
