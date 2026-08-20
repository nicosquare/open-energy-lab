"""Unit contracts for canonical TPM piecewise metadata and helpers."""

from __future__ import annotations

import math

import pytest

from open_energy_lab.tpm.piecewise import (
    CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS,
    DEFAULT_QUERY_NUMERIC_TOLERANCE,
    PiecewiseBreakpointPolicy,
    approximate_exponential,
    approximate_log,
    build_histogram_piecewise_points,
    build_logsumexp_piecewise_spec,
    build_piecewise_metadata,
    load_piecewise_metadata,
    resolve_query_numeric_tolerance,
)


def test_build_piecewise_metadata_preserves_canonical_contract() -> None:
    metadata = build_piecewise_metadata(fit_numeric_tolerance=1e-6)

    assert metadata.approximation_kind == "piecewise"
    assert metadata.leaf_encoding_mode == "histogram"
    assert metadata.sum_encoding_mode == "piecewise"
    assert metadata.breakpoint_policy.policy_name == "legacy-logspace-v1"
    assert metadata.fit_numeric_tolerance == pytest.approx(1e-6)
    assert metadata.query_numeric_tolerance == pytest.approx(DEFAULT_QUERY_NUMERIC_TOLERANCE)
    assert metadata.legacy_reference_paths == CANONICAL_PIECEWISE_LEGACY_REFERENCE_PATHS


def test_load_piecewise_metadata_accepts_max_sum_encoding() -> None:
    metadata = load_piecewise_metadata(
        {
            "approximation_kind": "piecewise",
            "sum_encoding_mode": "max",
        }
    )

    assert metadata.sum_encoding_mode == "max"


def test_load_piecewise_metadata_rejects_non_canonical_lower_tangent_sum_encoding() -> None:
    with pytest.raises(ValueError, match="lower_tangent"):
        load_piecewise_metadata(
            {
                "approximation_kind": "piecewise",
                "sum_encoding_mode": "lower_tangent",
            }
        )


def test_build_histogram_piecewise_points_matches_legacy_endpoint_doubling() -> None:
    breakpoints, values = build_histogram_piecewise_points(
        breaks=(0.0, 1.0, 3.0),
        values=(0.2, 0.5),
    )

    assert breakpoints == (0.0, 1.0, 1.0, 3.0)
    assert values == (0.2, 0.2, 0.5, 0.5)


def test_logsumexp_piecewise_spec_replays_legacy_logspace_breakpoint_policy() -> None:
    policy = PiecewiseBreakpointPolicy(piecewise_breakpoint_count=5, exp_probability_floor=1e-3)
    spec = build_logsumexp_piecewise_spec(max_terms=4, breakpoint_policy=policy)

    assert spec["exp_x_points"][0] == pytest.approx(math.log(1e-3))
    assert spec["exp_x_points"][-1] == pytest.approx(0.0)
    assert spec["log_x_points"][0] == pytest.approx(1.0)
    assert spec["log_x_points"][-1] == pytest.approx(4.0)
    assert spec["exp_y_points"][-1] == pytest.approx(1.0)
    assert spec["log_y_points"][0] == pytest.approx(0.0)


def test_piecewise_approximation_helpers_match_legacy_boundary_behavior() -> None:
    policy = PiecewiseBreakpointPolicy(piecewise_breakpoint_count=5, exp_probability_floor=1e-3)

    assert approximate_exponential(0.0, breakpoint_policy=policy) == pytest.approx(1.0)
    assert approximate_exponential(math.log(1e-3) - 1.0, breakpoint_policy=policy) == 0.0
    assert approximate_log(1.0, max_terms=4, breakpoint_policy=policy) == pytest.approx(0.0)


def test_resolve_query_numeric_tolerance_prefers_piecewise_query_tolerance() -> None:
    metadata = build_piecewise_metadata(
        fit_numeric_tolerance=1e-6,
        query_numeric_tolerance=1e-4,
    ).to_dict()

    assert resolve_query_numeric_tolerance(metadata) == pytest.approx(1e-4)
