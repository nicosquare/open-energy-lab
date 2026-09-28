"""TEMPORARY (consolidation A1): prove core helpers match the control copies.

Same method as the market (1319b4e) and simulator (28d7d8c) checks: each
private helper is compared with the core helper bound to the same error
class, over a shared corpus. They must return the same value (same type and
repr) or raise the same exception type; message wording may differ. Also
covers ``market.reference_fcr._integer``.

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

C = "open_energy_lab.control."


class Kind(str, Enum):
    A = "a"


SCALARS = [
    0, 1, -1, 2, 3, 2.0, 0.5, -0.5, -0.0, 1e-300, math.nan, math.inf, -math.inf, True,
    False, None, "", " ", "a", " a ", "0" * 64, "a" * 64, "A" * 64, "g" * 64, "a" * 63,
    b"x", [], (), {}, [1, 2], (1,), {"a": 1}, MappingProxyType({"b": 2}), object,
]
TIMES = SCALARS + [
    datetime(2026, 1, 1, tzinfo=UTC),
    datetime(2026, 1, 1, 12, 30, tzinfo=UTC),
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

ROBUST = "RobustFCRValidationError"
ROLLING = "RollingFCRValidationError"
ERRORS = {
    "fcr_bid_plan": "FCRBidPlanValidationError",
    "restoration_service": "RestorationControlValidationError",
    "stacked_service": "StackedBaselineValidationError",
    "robust_fcr_bidding": ROBUST,
    "robust_fcr_reference": ROBUST,
    "fcr_rolling_backtest": ROLLING,
    "robust_fcr_rolling": ROLLING,
    "fcr_rolling_reference": ROLLING,
}
NZ = {"normalize_zero": True}

# (module, old helper, core helper, extra core kwargs, corpus, error-class override)
CASES = [
    ("fcr_bid_plan", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS, None),
    ("fcr_bid_plan", "_finite", validation.finite, {}, SCALARS, None),
    ("fcr_bid_plan", "_sha256", validation.sha256_digest, {}, SCALARS, None),
    ("fcr_bid_plan", "_utc", core_time.utc_datetime, {}, TIMES, None),
    ("stacked_service", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS, None),
    ("stacked_service", "_finite", validation.finite, {}, SCALARS, None),
    ("restoration_service", "_non_empty", validation.non_empty_str, {}, SCALARS, None),
    ("restoration_service", "_finite", validation.finite, {}, SCALARS, None),
    ("restoration_service", "_non_negative", validation.non_negative, {}, SCALARS, None),
    ("restoration_service", "_positive", validation.positive, {}, SCALARS, None),
    ("restoration_service", "_mapping", validation.mapping, {}, SCALARS, None),
    ("restoration_service", "_sequence", validation.sequence, {}, SCALARS, None),
    ("robust_fcr_bidding", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS, None),
    ("robust_fcr_bidding", "_finite", validation.finite, NZ, SCALARS, None),
    ("robust_fcr_bidding", "_positive", validation.positive, NZ, SCALARS, None),
    ("robust_fcr_bidding", "_non_negative", validation.non_negative, NZ, SCALARS, None),
    ("robust_fcr_bidding", "_sha256", validation.sha256_digest, {}, SCALARS, None),
    ("robust_fcr_bidding", "_utc", core_time.utc_datetime, {}, TIMES, None),
    ("robust_fcr_reference", "_mapping", validation.mapping, {}, SCALARS, None),
    ("fcr_rolling_backtest", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS, None),
    ("fcr_rolling_backtest", "_finite", validation.finite, NZ, SCALARS, None),
    ("fcr_rolling_backtest", "_positive", validation.positive, NZ, SCALARS, None),
    ("fcr_rolling_backtest", "_utc", core_time.utc_datetime, {}, TIMES, None),
    ("fcr_rolling_backtest", "_sha", validation.sha256_digest, {}, SCALARS, None),
    ("robust_fcr_rolling", "_non_empty", validation.non_empty_str, {"strip": True}, SCALARS, None),
    ("robust_fcr_rolling", "_finite", validation.finite, NZ, SCALARS, None),
    ("robust_fcr_rolling", "_utc", core_time.utc_datetime, {}, TIMES, None),
    ("robust_fcr_rolling", "_sha", validation.sha256_digest, {}, SCALARS, None),
    ("fcr_rolling_reference", "_finite", validation.finite, NZ, SCALARS, None),
    ("fcr_rolling_reference", "_non_negative", validation.non_negative, NZ, SCALARS, None),
    ("fcr_rolling_reference", "_sha", validation.sha256_digest, {}, SCALARS, ROBUST),
]


def _module(name: str):
    return importlib.import_module(C + name)


def _error(name: str, override: str | None = None) -> type[Exception]:
    if override:
        return getattr(_module("robust_fcr_bidding"), override)
    return getattr(_module(name), ERRORS[name])


def _has_enum(value) -> bool:
    if isinstance(value, Enum):
        return True
    if isinstance(value, dict | MappingProxyType):
        return any(_has_enum(inner) for inner in value.values())
    if isinstance(value, list | tuple):
        return any(_has_enum(inner) for inner in value)
    return False



def _outcome(fn, *args, **kwargs):
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the exception type is the outcome
        return ("raise", type(exc))
    return ("ok", type(result), repr(result))


def _assert_same(old, new, args, kwargs=None) -> None:
    kwargs = kwargs or {}
    assert _outcome(old, *args, **kwargs) == _outcome(new, *args, **kwargs), (args, kwargs)


@pytest.mark.parametrize("module_name, old_name, core_fn, extra, corpus, override", CASES)
def test_validation_helper_matches_control_copy(module_name, old_name, core_fn, extra, corpus, override) -> None:
    old = partial(getattr(_module(module_name), old_name), field_name="f")
    new = partial(core_fn, field_name="f", error=_error(module_name, override), **extra)
    for value in corpus:
        _assert_same(old, new, (value,))


@pytest.mark.parametrize(
    "module_path, old_name, error_name, default_minimum",
    [
        (C + "robust_fcr_bidding", "_integer", ROBUST, None),
        (C + "fcr_rolling_reference", "_integer", ROLLING, 0),
        ("open_energy_lab.market.reference_fcr", "_integer", "ReferenceFCRValidationError", 0),
    ],
)
def test_integer_matches_copy(module_path, old_name, error_name, default_minimum) -> None:
    module = importlib.import_module(module_path)
    old = partial(getattr(module, old_name), field_name="f")
    new = partial(validation.integer, field_name="f", error=getattr(module, error_name), minimum=default_minimum)
    for value in SCALARS:
        _assert_same(old, new, (value,))
        for minimum in (0, 1, 3):
            _assert_same(old, new, (value,), {"minimum": minimum})


@pytest.mark.parametrize("module_name", ["robust_fcr_rolling", "fcr_rolling_backtest"])
def test_utc_text_matches_format_utc(module_name) -> None:
    old = _module(module_name)._utc_text
    for value in TIMES:
        if isinstance(value, datetime) and value.tzinfo is not None:
            _assert_same(old, core_time.format_utc, (value,))


def test_robust_utc_text_validates_then_formats() -> None:
    module = _module("robust_fcr_bidding")

    def new(value):
        return core_time.format_utc(
            core_time.utc_datetime(value, field_name="datetime", error=module.RobustFCRValidationError)
        )

    for value in TIMES:
        _assert_same(module._utc_text, new, (value,))


def test_fcr_bid_plan_serialization_matches_core() -> None:
    module = _module("fcr_bid_plan")
    error = module.FCRBidPlanValidationError
    for document in DOCUMENTS:
        frozen = serialization.freeze(document)
        if _has_enum(frozen):
            # Known difference: the old copy leaves Enum members as-is, core.thaw
            # returns their values. Canonical bytes are identical (checked below).
            assert module._thaw(frozen)["k"] is Kind.A and serialization.thaw(frozen)["k"] == "a"
        else:
            _assert_same(module._thaw, serialization.thaw, (frozen,))
        _assert_same(module._canonical_json, partial(serialization.canonical_json_bytes, error=error), (document,))
        _assert_same(module._fingerprint, partial(serialization.fingerprint, error=error), (document,))


def test_stacked_service_serialization_matches_core_where_old_accepted() -> None:
    """Known difference: the old copy never thawed its input.

    For every input the old copy accepted, core returns the same bytes and
    fingerprint. Core additionally accepts inputs the old copy rejected
    (read-only mappings, non-string keys), because core.thaw normalizes them.
    """

    module = _module("stacked_service")
    error = module.StackedBaselineValidationError
    new_json = partial(serialization.canonical_json_bytes, error=error)
    new_fp = partial(serialization.fingerprint, error=error)
    widened = 0
    for document in DOCUMENTS:
        old_outcome = _outcome(module._canonical_json, document)
        if old_outcome[0] == "raise" and _outcome(new_json, document)[0] == "ok":
            widened += 1
            continue
        _assert_same(module._canonical_json, new_json, (document,))
        _assert_same(module._fingerprint, new_fp, (document,))
    assert widened == 2  # the MappingProxyType document and the int-key document


def test_restoration_service_serialization_matches_core() -> None:
    module = _module("restoration_service")
    error = module.RestorationControlValidationError
    for document in DOCUMENTS:
        _assert_same(module._freeze, serialization.freeze, (document,))
        _assert_same(module._fingerprint, partial(serialization.fingerprint, error=error), (document,))
