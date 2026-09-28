"""TEMPORARY (consolidation A1): prove core helpers match the market copies.

Each market module's private helper is compared with the core helper bound to
the same error class, over a shared corpus of inputs. They must return the
same value (same type and repr) or raise the same exception type. Message
wording may differ, since A1 standardizes it.

This file is deleted once the market copies are removed, because then there is
nothing left to compare.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from functools import partial
import importlib
import math
from types import MappingProxyType

import pytest

from open_energy_lab.core import serialization, time as core_time, validation

M = "open_energy_lab.market."

SCALARS = [
    0, 1, -1, 2, 2.0, 0.5, -0.0, math.nan, math.inf, -math.inf, True, False, None,
    "", " ", "a", " a ", "0" * 64, "a" * 64, "A" * 64, "g" * 64, "a" * 63,
    b"x", [], (), {}, [1, 2], (1,), {"a": 1}, MappingProxyType({"b": 2}), object,
]
TIMES = SCALARS + [
    "2026-01-01T00:00:00Z",
    "2026-01-01T00:00:00+00:00",
    "2026-01-01T00:00:00.500000Z",
    "2026-01-01T01:00:00+01:00",
    "2026-01-01T00:00:00",
    datetime(2026, 1, 1, tzinfo=UTC),
    datetime(2026, 1, 1),
    datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
]
DOCUMENTS = [
    {"b": 1, "a": [1, 2.5, "é"]},
    MappingProxyType({"x": (1, MappingProxyType({"y": None}))}),
    {"n": math.nan},
    {"i": math.inf},
    {"s": {1, 2}},
    {"z": -0.0, 1: "int-key"},
    [1, (2, 3)],
    "text",
    None,
]

# (module, old helper, core helper, extra core kwargs, corpus)
CASES = [
    ("artifact", "_mapping", validation.mapping, {}, SCALARS),
    ("artifact", "_sequence", validation.sequence, {}, SCALARS),
    ("artifact", "_non_empty_string", validation.non_empty_str, {}, SCALARS),
    ("artifact", "_optional_string", validation.optional_str, {}, SCALARS),
    ("artifact", "_finite_number", validation.finite, {}, SCALARS),
    ("artifact", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("artifact", "_utc_timestamp", core_time.utc_timestamp_text, {}, TIMES),
    ("restoration_artifact", "_mapping", validation.mapping, {}, SCALARS),
    ("restoration_artifact", "_sequence", validation.sequence, {}, SCALARS),
    ("restoration_artifact", "_non_empty_string", validation.non_empty_str, {}, SCALARS),
    ("restoration_artifact", "_optional_string", validation.optional_str, {}, SCALARS),
    ("restoration_artifact", "_finite_number", validation.finite, {}, SCALARS),
    ("restoration_artifact", "_non_negative_int", validation.non_negative_int, {}, SCALARS),
    ("restoration_artifact", "_positive_int", validation.positive_int, {}, SCALARS),
    ("restoration_artifact", "_boolean", validation.boolean, {}, SCALARS),
    ("restoration_artifact", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("restoration_artifact", "_utc_timestamp", core_time.utc_timestamp_text, {}, TIMES),
    ("activation", "_mapping", validation.mapping, {}, SCALARS),
    ("activation", "_sequence", validation.sequence, {}, SCALARS),
    ("activation", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("activation", "_finite", validation.finite, {}, SCALARS),
    ("restoration_activation", "_mapping", validation.mapping, {}, SCALARS),
    ("restoration_activation", "_sequence", validation.sequence, {}, SCALARS),
    ("restoration_activation", "_non_empty", validation.non_empty_str, {}, SCALARS),
    ("restoration_activation", "_finite", validation.finite, {}, SCALARS),
    ("restoration_activation", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("restoration_activation", "_utc_timestamp", core_time.utc_timestamp_text, {}, TIMES),
    ("reference_fcr", "_mapping", validation.mapping, {}, SCALARS),
    ("reference_fcr", "_sequence", validation.sequence, {}, SCALARS),
    ("reference_fcr", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("reference_fcr", "_finite", validation.finite, {}, SCALARS),
    ("reference_fcr", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("entsoe", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("entsoe", "_require_utc_datetime", core_time.utc_datetime, {}, TIMES),
    ("rte", "_non_empty", validation.non_empty_str, {}, SCALARS),
    ("rte", "_utc", core_time.utc_datetime, {}, TIMES),
]

# (module, old serializer, error class name)
SERIALIZERS = [
    ("artifact", "canonical_json_bytes", "MarketArtifactValidationError"),
    ("restoration_artifact", "canonical_restoration_json_bytes", "RestorationArtifactValidationError"),
    ("activation", "_canonical_json", "ActivationValidationError"),
    ("reference_fcr", "canonical_reference_json_bytes", "ReferenceFCRValidationError"),
]


ERRORS = {
    "artifact": "MarketArtifactValidationError",
    "restoration_artifact": "RestorationArtifactValidationError",
    "activation": "ActivationValidationError",
    "restoration_activation": "RestorationActivationValidationError",
    "reference_fcr": "ReferenceFCRValidationError",
    "entsoe": "EntsoeRequestValidationError",
    "rte": "RTERequestValidationError",
}


def _error_class(module: object) -> type[Exception]:
    return getattr(module, ERRORS[module.__name__.rsplit(".", 1)[1]])


def _outcome(fn, *args):
    try:
        result = fn(*args)
    except Exception as exc:  # noqa: BLE001 - the exception type is the outcome
        return ("raise", type(exc))
    return ("ok", type(result), repr(result))


def _assert_same(old, new, args) -> None:
    assert _outcome(old, *args) == _outcome(new, *args), args


@pytest.mark.parametrize("module_name, old_name, core_fn, extra, corpus", CASES)
def test_validation_helper_matches_market_copy(module_name, old_name, core_fn, extra, corpus) -> None:
    module = importlib.import_module(M + module_name)
    old = getattr(module, old_name)
    new = partial(core_fn, error=_error_class(module), **extra)
    for value in corpus:
        _assert_same(partial(old, field_name="f"), partial(new, field_name="f"), (value,))


@pytest.mark.parametrize("module_name", ["artifact", "restoration_artifact", "restoration_activation"])
def test_require_fields_matches_market_copy(module_name) -> None:
    module = importlib.import_module(M + module_name)
    old = partial(module._required, field_name="f")
    new = partial(validation.require_fields, field_name="f", error=_error_class(module))
    for payload, names in [({"a": 1}, ["a"]), ({"a": 1}, ["a", "b", "c"]), ({}, [])]:
        _assert_same(old, new, (payload, names))


@pytest.mark.parametrize(
    "module_name, old_name",
    [("restoration_artifact", "_enum_value"), ("restoration_activation", "_enum"), ("rte", "_enum_value")],
)
def test_enum_helper_matches_market_copy(module_name, old_name) -> None:
    module = importlib.import_module(M + module_name)
    enum_type = importlib.import_module(M + "restoration_artifact").ObservationValueState
    old = partial(getattr(module, old_name), field_name="f")
    new = partial(validation.enum_member, field_name="f", error=_error_class(module))
    for value in ["VALUE", enum_type.SOURCE_NULL, "nope", None, 1]:
        _assert_same(old, new, (enum_type, value))


@pytest.mark.parametrize("module_name, old_name, error_name", SERIALIZERS)
def test_canonical_json_matches_market_copy(module_name, old_name, error_name) -> None:
    module = importlib.import_module(M + module_name)
    old = getattr(module, old_name)
    new = partial(serialization.canonical_json_bytes, error=getattr(module, error_name))
    for document in DOCUMENTS:
        _assert_same(old, new, (document,))


@pytest.mark.parametrize("module_name", ["artifact", "restoration_artifact", "activation"])
def test_freeze_matches_market_copy(module_name) -> None:
    old = importlib.import_module(M + module_name)._freeze
    for document in DOCUMENTS:
        _assert_same(old, serialization.freeze, (document,))


@pytest.mark.parametrize("module_name", ["artifact", "restoration_artifact", "activation", "reference_fcr"])
def test_thaw_matches_market_copy(module_name) -> None:
    old = importlib.import_module(M + module_name)._thaw
    for document in DOCUMENTS:
        _assert_same(old, serialization.thaw, (serialization.freeze(document),))


@pytest.mark.parametrize("module_name", ["artifact", "restoration_artifact", "activation"])
def test_manifest_json_matches_market_copy(module_name) -> None:
    module = importlib.import_module(M + module_name)
    error = _error_class(module)

    class Doc:
        def __init__(self, payload):
            self.payload = payload

        def to_dict(self):
            return self.payload

    for document in DOCUMENTS:
        _assert_same(
            lambda d: module._manifest_bytes(Doc(d)),
            lambda d: serialization.json_document_bytes(d, error=error),
            (document,),
        )


@pytest.mark.parametrize("module_name", ["activation", "entsoe"])
def test_format_utc_matches_market_copy(module_name) -> None:
    old = importlib.import_module(M + module_name)._format_utc
    for value in [datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1)))]:
        _assert_same(old, core_time.format_utc, (value,))


def test_reference_fingerprint_matches() -> None:
    module = importlib.import_module(M + "reference_fcr")
    for document in DOCUMENTS:
        _assert_same(
            module._fingerprint,
            partial(serialization.fingerprint, error=module.ReferenceFCRValidationError),
            (document,),
        )
