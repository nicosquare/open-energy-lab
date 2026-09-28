"""Behavior of the shared validation, serialization, and time helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
import json
import math
from pathlib import Path
from types import MappingProxyType

import pytest

from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import (
    canonical_json_bytes,
    fingerprint,
    freeze,
    json_document_bytes,
    thaw,
    write_bytes_atomically,
)
from open_energy_lab.core.time import format_utc, utc_datetime, utc_timestamp_text
from open_energy_lab.core.validation import (
    enum_member,
    finite,
    mapping,
    non_empty_str,
    non_negative,
    non_negative_int,
    positive,
    positive_int,
    require_fields,
    sequence,
    sha256_digest,
)


class CustomError(ValueError):
    pass


class Color(str, Enum):
    RED = "red"


def test_checks_raise_the_bound_error_type() -> None:
    with pytest.raises(CustomError, match="x must be a finite number"):
        finite("1", field_name="x", error=CustomError)
    with pytest.raises(ValidationError):
        finite(math.nan, field_name="x")


@pytest.mark.parametrize("value", [True, "1", None, math.inf, -math.inf, math.nan])
def test_finite_rejects_non_finite_and_bool(value: object) -> None:
    with pytest.raises(ValidationError):
        finite(value, field_name="x")


def test_finite_normalizes_negative_zero_only_on_request() -> None:
    assert math.copysign(1.0, finite(-0.0, field_name="x")) == -1.0
    assert math.copysign(1.0, finite(-0.0, field_name="x", normalize_zero=True)) == 1.0
    assert finite(3, field_name="x") == 3.0


def test_signed_float_checks() -> None:
    assert positive(2, field_name="x") == 2.0
    assert non_negative(0, field_name="x") == 0.0
    for check, value in ((positive, 0.0), (positive, -1), (non_negative, -0.5), (non_negative, True)):
        with pytest.raises(ValidationError):
            check(value, field_name="x")


def test_non_empty_str_strip_option() -> None:
    assert non_empty_str(" ", field_name="x") == " "
    with pytest.raises(ValidationError):
        non_empty_str(" ", field_name="x", strip=True)
    with pytest.raises(ValidationError):
        non_empty_str("", field_name="x")


def test_integer_checks_are_strict() -> None:
    assert non_negative_int(0, field_name="x") == 0
    assert positive_int(2, field_name="x") == 2
    for value in (True, 2.0, -1, "2"):
        with pytest.raises(ValidationError):
            positive_int(value, field_name="x")
    with pytest.raises(ValidationError):
        positive_int(0, field_name="x")


def test_container_checks() -> None:
    assert mapping(MappingProxyType({1: "a"}), field_name="x") == {"1": "a"}
    assert sequence((1, 2), field_name="x") == [1, 2]
    with pytest.raises(ValidationError):
        sequence("ab", field_name="x")
    with pytest.raises(ValidationError, match="missing required fields: b"):
        require_fields({"a": 1}, ["a", "b"], field_name="x")


def test_sha256_and_enum() -> None:
    assert sha256_digest("a" * 64, field_name="x") == "a" * 64
    with pytest.raises(ValidationError):
        sha256_digest("A" * 64, field_name="x")
    assert enum_member(Color, "red", field_name="x") is Color.RED
    with pytest.raises(ValidationError, match="must be one of: red"):
        enum_member(Color, "blue", field_name="x")


def test_freeze_thaw_round_trip() -> None:
    frozen = freeze({"a": [1, {"b": (2, 3)}]})
    assert isinstance(frozen, MappingProxyType)
    assert frozen["a"][1]["b"] == (2, 3)
    assert thaw(frozen) == {"a": [1, {"b": [2, 3]}]}
    assert thaw({"c": Color.RED}) == {"c": "red"}
    assert list(freeze({"b": 1, "a": {"d": 2, "c": 3}}, sort_keys=True)) == ["a", "b"]
    assert list(freeze({"b": 1, "a": {"d": 2, "c": 3}}, sort_keys=True)["a"]) == ["c", "d"]
    assert list(freeze({"b": 1, "a": 2})) == ["b", "a"]


def test_canonical_json_is_compact_sorted_and_finite() -> None:
    assert canonical_json_bytes(freeze({"b": 1, "a": ("é",)})) == '{"a":["é"],"b":1}'.encode()
    with pytest.raises(CustomError):
        canonical_json_bytes({"a": math.nan}, error=CustomError)
    assert fingerprint({"a": 1}) == fingerprint(MappingProxyType({"a": 1}))


def test_json_document_bytes_is_indented_with_trailing_newline() -> None:
    data = json_document_bytes({"b": 1, "a": 2})
    assert data.endswith(b"\n")
    assert json.loads(data) == {"a": 2, "b": 1}
    assert data.index(b'"a"') < data.index(b'"b"')


def test_write_bytes_atomically(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    write_bytes_atomically(target, b"one")
    write_bytes_atomically(target, b"two")
    assert target.read_bytes() == b"two"
    with pytest.raises(FileExistsError):
        write_bytes_atomically(target, b"three", fail_if_exists=True)
    assert target.read_bytes() == b"two"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.json"]


def test_utc_helpers() -> None:
    moment = datetime(2026, 1, 1, tzinfo=UTC)
    assert format_utc(moment) == "2026-01-01T00:00:00Z"
    assert utc_datetime(moment, field_name="x") == moment
    assert utc_timestamp_text("2026-01-01T00:00:00+00:00", field_name="x") == "2026-01-01T00:00:00Z"
    for value in (datetime(2026, 1, 1), moment.astimezone(timezone(timedelta(hours=1)))):
        with pytest.raises(ValidationError):
            utc_datetime(value, field_name="x")
    for text in ("2026-01-01T00:00:00", "2026-01-01T01:00:00+01:00", "nope", ""):
        with pytest.raises(ValidationError):
            utc_timestamp_text(text, field_name="x")
