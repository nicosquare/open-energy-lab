"""TEMPORARY (consolidation A1): prove core helpers match the simulator copies.

Same method as the market check at 1319b4e: each private helper is compared
with the core helper bound to the same error class, over a shared corpus. They
must return the same value (same type and repr) or raise the same exception
type; message wording may differ. Also covers ``market.reference_fcr._freeze``,
which moves onto ``freeze(sort_keys=True)`` in this change.

Deleted once the copies are removed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from functools import partial
import importlib
import math
from types import MappingProxyType

import pytest

from open_energy_lab.core import serialization, time as core_time, validation

S = "open_energy_lab.simulator."


class Kind(str, Enum):
    A = "a"


SCALARS = [
    0, 1, -1, 2, 2.0, 0.5, -0.5, -0.0, 1e-300, math.nan, math.inf, -math.inf, True, False,
    None, "", " ", "a", " a ", "0" * 64, "a" * 64, "A" * 64, "g" * 64, "a" * 63, b"x",
    [], (), {}, [1, 2], (1,), {"a": 1}, MappingProxyType({"b": 2}), object,
]
TIMES = SCALARS + [
    datetime(2026, 1, 1, tzinfo=UTC),
    datetime(2026, 1, 1),
    datetime(2026, 1, 1, 1, tzinfo=timezone(timedelta(hours=1))),
    "2026-01-01T00:00:00Z",
]
DOCUMENTS = [
    {"b": 1, "a": [1, 2.5, "é"]},
    MappingProxyType({"x": (1, MappingProxyType({"y": None}))}),
    {"z": {"d": 1, "c": [{"f": 2, "e": 3}]}, "a": 0},
    {"n": math.nan},
    {"i": math.inf},
    {"s": {1, 2}},
    {"z": -0.0, 1: "int-key"},
    {"k": Kind.A, "t": (Kind.A,)},
    [1, (2, 3)],
    "text",
    None,
]

ERRORS = {
    "fcr_bid_evaluation": "FCRBidEvaluationValidationError",
    "fcr_rolling_evaluation": "FCRBidEvaluationValidationError",
    "fcr_settlement": "FCRSettlementValidationError",
    "stacked_service": "StackedServiceValidationError",
    "restoration_service": "RestorationReplayValidationError",
    "restoration_settlement": "RestorationSettlementValidationError",
}

# (module, old helper, core helper, extra core kwargs, corpus)
CASES = [
    ("fcr_bid_evaluation", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("fcr_bid_evaluation", "_finite", validation.finite, {}, SCALARS),
    ("fcr_bid_evaluation", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("fcr_rolling_evaluation", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("fcr_rolling_evaluation", "_finite", validation.finite, {"normalize_zero": True}, SCALARS),
    ("fcr_rolling_evaluation", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("fcr_settlement", "_finite", validation.finite, {}, SCALARS),
    ("fcr_settlement", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("stacked_service", "_finite", validation.finite, {}, SCALARS),
    ("stacked_service", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("stacked_service", "_utc", core_time.utc_datetime, {}, TIMES),
    ("stacked_service", "_mapping", validation.mapping, {}, SCALARS),
    ("stacked_service", "_sequence", validation.sequence, {}, SCALARS),
    ("restoration_service", "_non_empty", validation.non_empty_str, {}, SCALARS),
    ("restoration_service", "_finite", validation.finite, {}, SCALARS),
    ("restoration_service", "_positive", validation.positive, {}, SCALARS),
    ("restoration_service", "_non_negative", validation.non_negative, {}, SCALARS),
    ("restoration_service", "_sha256", validation.sha256_digest, {}, SCALARS),
    ("restoration_service", "_mapping", validation.mapping, {}, SCALARS),
    ("restoration_settlement", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS),
    ("restoration_settlement", "_finite", validation.finite, {}, SCALARS),
    ("restoration_settlement", "_positive", validation.positive, {}, SCALARS),
    ("restoration_settlement", "_non_negative", validation.non_negative, {}, SCALARS),
    ("restoration_settlement", "_sha256", validation.sha256_digest, {}, SCALARS),
]


def _module(name: str):
    return importlib.import_module(S + name)


def _error(name: str) -> type[Exception]:
    return getattr(_module(name), ERRORS[name])


def _outcome(fn, *args):
    try:
        result = fn(*args)
    except Exception as exc:  # noqa: BLE001 - the exception type is the outcome
        return ("raise", type(exc))
    return ("ok", type(result), repr(result))


def _assert_same(old, new, args) -> None:
    assert _outcome(old, *args) == _outcome(new, *args), args


@pytest.mark.parametrize("module_name, old_name, core_fn, extra, corpus", CASES)
def test_validation_helper_matches_simulator_copy(module_name, old_name, core_fn, extra, corpus) -> None:
    old = partial(getattr(_module(module_name), old_name), field_name="f")
    new = partial(core_fn, field_name="f", error=_error(module_name), **extra)
    for value in corpus:
        _assert_same(old, new, (value,))


@pytest.mark.parametrize("module_name", ["restoration_service", "restoration_settlement"])
def test_product_matches_enum_member(module_name) -> None:
    module = _module(module_name)
    new = partial(
        validation.enum_member, module.RestorationProduct, field_name="product", error=_error(module_name)
    )
    for value in ["AFRR", "MFRR", module.RestorationProduct.AFRR, "afrr", None, 1]:
        _assert_same(module._product, new, (value,))


@pytest.mark.parametrize("module_name", ["fcr_bid_evaluation", "fcr_rolling_evaluation", "stacked_service"])
def test_thaw_matches_simulator_copy(module_name) -> None:
    old = _module(module_name)._thaw
    for document in DOCUMENTS:
        frozen = serialization.freeze(document)
        if any(isinstance(v, Kind) for v in _leaves(frozen)):
            continue  # these copies predate Enum support; see test_plain_matches_thaw
        _assert_same(old, serialization.thaw, (frozen,))


@pytest.mark.parametrize("module_name", ["restoration_service", "restoration_settlement"])
def test_plain_matches_thaw(module_name) -> None:
    old = _module(module_name)._plain
    for document in DOCUMENTS:
        _assert_same(old, serialization.thaw, (serialization.freeze(document),))


@pytest.mark.parametrize(
    "module_name, sort_keys",
    [
        ("fcr_bid_evaluation", True),
        ("fcr_rolling_evaluation", True),
        ("stacked_service", False),
    ],
)
def test_freeze_matches_simulator_copy(module_name, sort_keys) -> None:
    old = _module(module_name)._freeze
    new = partial(serialization.freeze, sort_keys=sort_keys)
    for document in DOCUMENTS:
        _assert_same(old, new, (document,))


def test_reference_fcr_freeze_matches_sorted_freeze() -> None:
    old = importlib.import_module("open_energy_lab.market.reference_fcr")._freeze
    new = partial(serialization.freeze, sort_keys=True)
    for document in DOCUMENTS:
        _assert_same(old, new, (document,))


@pytest.mark.parametrize(
    "module_name, old_name",
    [("fcr_bid_evaluation", "canonical_json_bytes"), ("stacked_service", "_canonical_json")],
)
def test_canonical_json_matches_simulator_copy(module_name, old_name) -> None:
    old = getattr(_module(module_name), old_name)
    new = partial(serialization.canonical_json_bytes, error=_error(module_name))
    for document in DOCUMENTS:
        _assert_same(old, new, (document,))


@pytest.mark.parametrize(
    "module_name",
    ["fcr_bid_evaluation", "fcr_rolling_evaluation", "stacked_service", "restoration_service", "restoration_settlement"],
)
def test_fingerprint_matches_simulator_copy(module_name) -> None:
    old = _module(module_name)._fingerprint
    new = partial(serialization.fingerprint, error=_error(module_name))
    for document in DOCUMENTS:
        _assert_same(old, new, (document,))


def _leaves(value):
    if isinstance(value, MappingProxyType | dict):
        for inner in value.values():
            yield from _leaves(inner)
    elif isinstance(value, tuple | list):
        for inner in value:
            yield from _leaves(inner)
    else:
        yield value
