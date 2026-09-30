"""Explicit full bounded Feature 015 native/source comparison research gate."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import pytest

from oel_validation.scripts.run_fcr_rolling_reference_benchmark import (
    FULL_HISTORY_REQUEST_SCHEMA_VERSION,
    FULL_HISTORY_SOURCE_DATE_LIST_SHA256,
    _load_full_history_request,
    run_bounded_reference_benchmark,
)
from examples.fcr_rolling_backtest.study_inputs import (
    BOUNDED_DATES,
    PROFILE_IDS,
    fingerprint,
)


pytestmark = pytest.mark.reference_benchmark

FIXTURE_PATH = Path(
    "tests/fixtures/fcr_rolling_backtest/"
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
)


def test_complete_five_profile_four_date_native_reference_comparison() -> None:
    report = run_bounded_reference_benchmark(
        fixture_path=FIXTURE_PATH,
        profile_ids=PROFILE_IDS,
        dates=BOUNDED_DATES,
        solver_name="highs",
        time_limit_seconds=60.0,
    )

    assert report["execution_mode"] == "explicit_bounded_reference_benchmark"
    assert tuple(report["profile_order"]) == PROFILE_IDS
    assert tuple(report["ordered_dates"]) == tuple(
        item.isoformat() for item in BOUNDED_DATES
    )
    assert report["backend_evidence"] == {
        "status": "required",
        "solver_name": "highs",
        "fallback_attempted": False,
    }
    assert len(report["profiles"]) == 5

    source_time_limit_dates = []
    native_statuses = Counter()
    comparison_outcomes = Counter()
    concise_profiles = []
    for expected_profile, profile_report in zip(
        PROFILE_IDS,
        report["profiles"],
        strict=True,
    ):
        assert profile_report["profile_id"] == expected_profile
        assert profile_report["status"] == "completed"
        assert profile_report["native_record_count"] == 4
        result = profile_report["result"]
        comparison = profile_report["comparison"]
        assert tuple(result["requested_dates"]) == tuple(
            item.isoformat() for item in BOUNDED_DATES
        )
        assert len(result["records"]) == 4
        assert len(comparison["date_summaries"]) == 4
        assert {
            item["delivery_date"] for item in comparison["field_results"]
        } == {item.isoformat() for item in BOUNDED_DATES}
        source_time_limit_dates.extend(profile_report["source_time_limit_dates"])
        native_statuses.update(
            {
                key: value
                for key, value in profile_report["native_status_counts"].items()
                if value
            }
        )
        comparison_outcomes.update(
            profile_report["source_comparison_outcome_counts"]
        )
        concise_profiles.append(
            {
                "profile_id": expected_profile,
                "completeness": result["completeness_status"],
                "status_counts": profile_report["native_status_counts"],
                "overall_compatibility": profile_report[
                    "overall_compatibility"
                ],
                "semantic_fingerprint": profile_report[
                    "native_semantic_fingerprint"
                ],
                "comparison_fingerprint": profile_report[
                    "comparison_fingerprint"
                ],
            }
        )

    assert source_time_limit_dates
    assert comparison_outcomes["unavailable"] > 0
    assert (
        comparison_outcomes["source_incumbent_equivalent"]
        + comparison_outcomes["incomplete_or_unfinalized"]
        + comparison_outcomes["mismatch"]
    ) > 0
    assert native_statuses["requested"] == 20
    print(
        "fcr_rolling_reference_benchmark="
        + json.dumps(
            {
                "fixture_fingerprint": report["fixture_fingerprint"],
                "source_time_limit_evidence_count": len(source_time_limit_dates),
                "comparison_outcomes": dict(sorted(comparison_outcomes.items())),
                "profiles": concise_profiles,
                "evidence_limits": report["evidence_limits"],
            },
            sort_keys=True,
        )
    )


def test_explicit_gurobi_unavailability_never_falls_back_to_highs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import oel_validation.scripts.run_fcr_rolling_reference_benchmark as benchmark

    monkeypatch.setattr(
        benchmark,
        "_gurobi_backend_evidence",
        lambda: {
            "status": "unavailable",
            "reason": "test license unavailable",
            "fallback_attempted": False,
        },
    )

    def forbidden_highs_fallback(*args: object, **kwargs: object) -> object:
        raise AssertionError("explicit Gurobi selection attempted a HiGHS solve")

    monkeypatch.setattr(
        benchmark,
        "run_rolling_fcr_study",
        forbidden_highs_fallback,
    )

    report = benchmark.run_bounded_reference_benchmark(
        fixture_path=FIXTURE_PATH,
        profile_ids=PROFILE_IDS,
        dates=BOUNDED_DATES,
        solver_name="gurobi",
        time_limit_seconds=1.0,
    )

    assert report["backend_evidence"]["status"] == "unavailable"
    assert report["backend_evidence"]["fallback_attempted"] is False
    assert {item["status"] for item in report["profiles"]} == {"unavailable"}
    assert all(
        item["reason_codes"] == ("optional_gurobi_backend_unavailable",)
        for item in report["profiles"]
    )


def test_full_history_request_pins_immutable_date_order_and_acceptance_policy(
    tmp_path: Path,
) -> None:
    excluded = (
        date(2020, 10, 25),
        date(2021, 3, 28),
        date(2021, 10, 31),
        date(2022, 3, 27),
        date(2022, 10, 30),
        date(2023, 3, 26),
        date(2023, 10, 29),
        date(2024, 3, 31),
    )
    first = date(2020, 7, 1)
    last = date(2024, 6, 30)
    calendar = tuple(
        first + timedelta(days=index)
        for index in range((last - first).days + 1)
    )
    ordered = tuple(item for item in calendar if item not in set(excluded))
    assert len(ordered) == 1453
    bundle = tmp_path / "full-history-data.json"
    bundle.write_text("{}\n", encoding="utf-8")
    bundle_digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    semantic = {
        "schema_version": FULL_HISTORY_REQUEST_SCHEMA_VERSION,
        "research_only": True,
        "release_gate": False,
        "profile_id": PROFILE_IDS[4],
        "state_carry_policy": "source_three_decimal",
        "ordered_dates": [item.isoformat() for item in ordered],
        "excluded_dates": [item.isoformat() for item in excluded],
        "source_date_list_sha256": FULL_HISTORY_SOURCE_DATE_LIST_SHA256,
        "acceptance_policy": {
            "kind": "assumed_accepted",
            "statement": "optimizer-selected bids are assumed accepted",
        },
        "data_bundle": {"sha256": bundle_digest},
    }
    request = {
        **semantic,
        "data_bundle": {"path": str(bundle), "sha256": bundle_digest},
        "request_fingerprint": fingerprint(semantic),
    }
    request_path = tmp_path / "full-history-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    loaded = _load_full_history_request(request_path)

    assert loaded["ordered_dates_parsed"] == ordered
    assert loaded["excluded_dates_parsed"] == excluded
    assert loaded["request_fingerprint"] == fingerprint(semantic)
    assert loaded["acceptance_policy"]["kind"] == "assumed_accepted"
