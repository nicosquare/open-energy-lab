from __future__ import annotations

from pathlib import Path

import pytest

from oel_validation.scripts.run_fcr_bid_reference_parity import (
    DEFAULT_FIXTURE,
    build_reference_request,
)
from open_energy_lab.simulator import (
    evaluate_fixed_fcr_bid,
)
from oel_validation.fcr_bid_evaluation import compare_reference_evaluation


DEFAULT_ACTIVATION_PATH = Path(
    "artifacts/reference/robust_storage_bidding/regulation_signal.csv"
)


pytestmark = pytest.mark.external_reference_data


def _installed_request(activation_path: Path = DEFAULT_ACTIVATION_PATH):
    if not activation_path.is_file():
        pytest.skip(
            "external reference activation is not installed at "
            f"{activation_path}; follow "
            "tests/fixtures/fcr_bid_evaluation/README.md and rerun this explicitly"
        )
    return build_reference_request(
        fixture_path=DEFAULT_FIXTURE,
        activation_path=activation_path,
    )


def test_absent_external_data_skip_is_actionable(tmp_path: Path) -> None:
    missing = tmp_path / "misplaced" / "regulation_signal.csv"

    with pytest.raises(pytest.skip.Exception) as exc_info:
        _installed_request(missing)

    message = str(exc_info.value)
    assert missing.as_posix() in message
    assert "tests/fixtures/fcr_bid_evaluation/README.md" in message
    assert "rerun this explicitly" in message


def test_complete_2023_06_18_reference_aggregate_parity() -> None:
    request = _installed_request()

    first = evaluate_fixed_fcr_bid(request)
    repeated = evaluate_fixed_fcr_bid(request)
    comparison = compare_reference_evaluation(request, first)

    assert first.status == "settled"
    assert len(request.energy_schedule.intervals) == 24
    assert len(request.fcr_schedule.intervals) == 6
    assert len(request.time_contract.index.checkpoint_intervals) == 96
    assert len(request.activation_trace.samples) == 8640
    assert first.physical_metrics["interval_counts"] == {
        "activation": 8640,
        "checkpoint": 96,
        "energy": 24,
        "fcr": 6,
    }
    assert first.physical_metrics["saturation_event_count"] == 0
    assert comparison.overall_status in {"exact", "source_precision_compatible"}
    assert all(
        item.status in {"exact", "source_precision_compatible", "unavailable"}
        for item in comparison.fields
    )
    assert not any(item.status == "mismatch" for item in comparison.fields)
    statuses = {item.field_id: item.status for item in comparison.fields}
    assert statuses["settlement.day_ahead_revenue_eur"] == (
        "source_precision_compatible"
    )
    assert statuses["physical.terminal_stored_energy_kwh"] == (
        "source_precision_compatible"
    )
    assert statuses["physical.minimum_stored_energy_kwh"] == (
        "source_precision_compatible"
    )
    assert first.canonical_bytes() == repeated.canonical_bytes()


def test_reference_fixture_refuses_unsupported_stepwise_claims() -> None:
    request = _installed_request()
    report = evaluate_fixed_fcr_bid(request)

    comparison = compare_reference_evaluation(
        request,
        report,
        requested_field_ids=(
            "physical.detailed_trace",
            "physical.directional_fcr_energy",
            "physical.tracking_error",
            "physical.throughput_kwh",
        ),
    )

    assert comparison.overall_status == "unavailable"
    assert all(item.status == "unavailable" for item in comparison.fields)
