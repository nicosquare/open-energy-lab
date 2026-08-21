"""Contract tests for canonical market intervals and exact multi-rate grids."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta, timezone
import importlib
from types import ModuleType
from typing import Any

import pytest


PARIS = "Europe/Paris"


def _time_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.market.time")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.market.time is not implemented; T009 must provide "
            "the canonical time contract",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _time_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.market.time.{name} is not implemented",
            pytrace=False,
        )


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise AssertionError(f"expected datetime-compatible value, got {value!r}")


def _iso(value: object) -> str:
    instant = _as_datetime(value)
    if instant.tzinfo == UTC:
        return instant.isoformat().replace("+00:00", "Z")
    return instant.isoformat()


def test_canonical_interval_requires_aware_ordered_utc_half_open_bounds() -> None:
    canonical_interval = _require("canonical_interval")
    start = datetime(2022, 8, 18, 22, tzinfo=UTC)
    end = start + timedelta(hours=1)

    interval = canonical_interval(start, end, market_timezone=PARIS)

    assert _as_datetime(interval.start_utc) == start
    assert _as_datetime(interval.end_utc) == end
    assert interval.interval_convention == "start-inclusive/end-exclusive"
    assert interval.market_timezone == PARIS


@pytest.mark.parametrize(
    ("start", "end", "expected_message"),
    [
        (
            datetime(2022, 8, 18, 22),
            datetime(2022, 8, 18, 23, tzinfo=UTC),
            "aware.*UTC|UTC.*aware",
        ),
        (
            datetime(2022, 8, 18, 22, tzinfo=UTC),
            datetime(2022, 8, 18, 23),
            "aware.*UTC|UTC.*aware",
        ),
        (
            datetime(2022, 8, 19, 0, tzinfo=timezone(timedelta(hours=2))),
            datetime(2022, 8, 19, 1, tzinfo=timezone(timedelta(hours=2))),
            "UTC",
        ),
        (
            datetime(2022, 8, 18, 22, tzinfo=UTC),
            datetime(2022, 8, 18, 22, tzinfo=UTC),
            "start.*before.*end|positive",
        ),
        (
            datetime(2022, 8, 18, 23, tzinfo=UTC),
            datetime(2022, 8, 18, 22, tzinfo=UTC),
            "start.*before.*end|positive",
        ),
    ],
)
def test_canonical_interval_rejects_ambiguous_or_non_half_open_bounds(
    start: datetime,
    end: datetime,
    expected_message: str,
) -> None:
    canonical_interval = _require("canonical_interval")
    error_type = _require("MarketTimeValidationError")

    with pytest.raises(error_type, match=expected_message):
        canonical_interval(start, end, market_timezone=PARIS)


def test_canonical_interval_preserves_paris_labels_offsets_and_dst_folds() -> None:
    canonical_interval = _require("canonical_interval")

    summer = canonical_interval(
        datetime(2022, 8, 18, 22, tzinfo=UTC),
        datetime(2022, 8, 18, 23, tzinfo=UTC),
        market_timezone=PARIS,
    )
    repeated_hour = canonical_interval(
        datetime(2022, 10, 30, 0, tzinfo=UTC),
        datetime(2022, 10, 30, 1, tzinfo=UTC),
        market_timezone=PARIS,
    )

    assert _iso(summer.local_start) == "2022-08-19T00:00:00+02:00"
    assert _iso(summer.local_end) == "2022-08-19T01:00:00+02:00"
    assert summer.start_utc_offset_seconds == 7200
    assert summer.end_utc_offset_seconds == 7200
    assert summer.start_fold == 0
    assert summer.end_fold == 0

    assert _iso(repeated_hour.local_start) == "2022-10-30T02:00:00+02:00"
    assert _iso(repeated_hour.local_end) == "2022-10-30T02:00:00+01:00"
    assert repeated_hour.start_utc_offset_seconds == 7200
    assert repeated_hour.end_utc_offset_seconds == 3600
    assert repeated_hour.start_fold == 0
    assert repeated_hour.end_fold == 1

    persisted = repeated_hour.to_dict()
    assert persisted["start_utc"] == "2022-10-30T00:00:00Z"
    assert persisted["end_utc"] == "2022-10-30T01:00:00Z"
    assert persisted["local_start"] == "2022-10-30T02:00:00+02:00"
    assert persisted["local_end"] == "2022-10-30T02:00:00+01:00"
    assert persisted["start_fold"] == 0
    assert persisted["end_fold"] == 1


@pytest.mark.parametrize(
    ("local_day", "expected_count", "expected_start", "expected_end"),
    [
        (
            date(2022, 3, 27),
            23,
            "2022-03-26T23:00:00Z",
            "2022-03-27T22:00:00Z",
        ),
        (
            date(2022, 10, 30),
            25,
            "2022-10-29T22:00:00Z",
            "2022-10-30T23:00:00Z",
        ),
    ],
)
def test_local_delivery_days_preserve_23_and_25_hour_utc_coverage(
    local_day: date,
    expected_count: int,
    expected_start: str,
    expected_end: str,
) -> None:
    build_local_delivery_day = _require("build_local_delivery_day")

    intervals = build_local_delivery_day(
        local_day,
        resolution="PT1H",
        market_timezone=PARIS,
    )

    assert len(intervals) == expected_count
    assert _iso(intervals[0].start_utc) == expected_start
    assert _iso(intervals[-1].end_utc) == expected_end
    assert all(
        _as_datetime(previous.end_utc) == _as_datetime(current.start_utc)
        for previous, current in zip(intervals, intervals[1:])
    )
    assert all(
        _as_datetime(interval.end_utc) - _as_datetime(interval.start_utc)
        == timedelta(hours=1)
        for interval in intervals
    )

    local_starts = [_iso(interval.local_start) for interval in intervals]
    if expected_count == 23:
        assert not any(label.startswith("2022-03-27T02:00:00") for label in local_starts)
    else:
        repeated = [
            interval
            for interval in intervals
            if _iso(interval.local_start).startswith("2022-10-30T02:00:00")
        ]
        assert len(repeated) == 2
        assert [interval.start_fold for interval in repeated] == [0, 1]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PT10S", timedelta(seconds=10)),
        ("PT15M", timedelta(minutes=15)),
        ("PT1H", timedelta(hours=1)),
        ("PT4H", timedelta(hours=4)),
    ],
)
def test_resolution_parser_accepts_the_exact_reference_grid(
    value: str,
    expected: timedelta,
) -> None:
    parse_iso8601_duration = _require("parse_iso8601_duration")

    assert parse_iso8601_duration(value) == expected


@pytest.mark.parametrize("value", ["", "PT0S", "PT90X", "1H", "P1M"])
def test_resolution_parser_rejects_empty_zero_or_non_fixed_durations(value: str) -> None:
    parse_iso8601_duration = _require("parse_iso8601_duration")
    error_type = _require("MarketTimeValidationError")

    with pytest.raises(error_type, match="duration|resolution|ISO"):
        parse_iso8601_duration(value)


def test_multi_rate_index_maps_every_activation_interval_exactly_once() -> None:
    build_multi_rate_index = _require("build_multi_rate_index")
    start = datetime(2022, 8, 18, 22, tzinfo=UTC)
    end = start + timedelta(hours=4)

    index = build_multi_rate_index(
        start,
        end,
        activation_resolution="PT10S",
        checkpoint_resolution="PT15M",
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone=PARIS,
    )

    assert len(index.activation_intervals) == 1440
    assert len(index.checkpoint_intervals) == 16
    assert len(index.energy_intervals) == 4
    assert len(index.fcr_intervals) == 1

    assert len(index.activation_to_checkpoint) == 1440
    assert len(index.activation_to_energy) == 1440
    assert len(index.activation_to_fcr) == 1440
    assert Counter(index.activation_to_checkpoint) == Counter({i: 90 for i in range(16)})
    assert Counter(index.activation_to_energy) == Counter({i: 360 for i in range(4)})
    assert Counter(index.activation_to_fcr) == Counter({0: 1440})

    assert index.activation_to_checkpoint[0] == 0
    assert index.activation_to_checkpoint[-1] == 15
    assert index.activation_to_energy[0] == 0
    assert index.activation_to_energy[-1] == 3
    assert index.activation_to_fcr[0] == index.activation_to_fcr[-1] == 0
    assert _as_datetime(index.activation_intervals[0].start_utc) == start
    assert _as_datetime(index.activation_intervals[-1].end_utc) == end


@pytest.mark.parametrize(
    ("start_offset", "end_offset", "checkpoint_resolution", "expected_message"),
    [
        (timedelta(0), timedelta(hours=4), "PT17M", "divide|divisib|exact"),
        (timedelta(0), timedelta(hours=3), "PT15M", "complete|PT4H|block"),
        (
            timedelta(minutes=5),
            timedelta(hours=4, minutes=5),
            "PT15M",
            "boundary|align",
        ),
    ],
)
def test_multi_rate_index_rejects_inexact_divisibility_or_partial_blocks(
    start_offset: timedelta,
    end_offset: timedelta,
    checkpoint_resolution: str,
    expected_message: str,
) -> None:
    build_multi_rate_index = _require("build_multi_rate_index")
    error_type = _require("MarketTimeValidationError")
    anchor = datetime(2022, 8, 18, 22, tzinfo=UTC)

    with pytest.raises(error_type, match=expected_message):
        build_multi_rate_index(
            anchor + start_offset,
            anchor + end_offset,
            activation_resolution="PT10S",
            checkpoint_resolution=checkpoint_resolution,
            energy_resolution="PT1H",
            fcr_resolution="PT4H",
            market_timezone=PARIS,
        )
