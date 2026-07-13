"""Unit contracts for planning-facing piecewise assembly helpers."""

from __future__ import annotations

import pytest

from open_energy_lab.planning.piecewise import (
    PiecewisePlanningTerms,
    build_piecewise_planning_terms,
)
from tests.integration.planning.fixture_utils import (
    TPM_ARTIFACT_FIXTURE_PATH,
    load_planning_fixture,
)


def test_build_piecewise_planning_terms_replays_committed_tpm_metadata() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    planning_terms = build_piecewise_planning_terms(
        artifact_fixture["approximation_metadata"],
        max_terms=2,
    )

    assert isinstance(planning_terms, PiecewisePlanningTerms)
    assert planning_terms.approximation_kind == "piecewise"
    assert planning_terms.leaf_encoding_mode == "histogram"
    assert planning_terms.sum_encoding_mode == "piecewise"
    assert planning_terms.breakpoint_policy["policy_name"] == "legacy-logspace-v1"
    assert planning_terms.mio_epsilon == pytest.approx(1e-6)
    assert planning_terms.fit_numeric_tolerance == pytest.approx(1e-9)
    assert planning_terms.query_numeric_tolerance == pytest.approx(1e-9)
    assert planning_terms.exp_breakpoints[-1] == pytest.approx(0.0)
    assert planning_terms.exp_values[-1] == pytest.approx(1.0)
    assert planning_terms.log_breakpoints[0] == pytest.approx(1.0)
    assert planning_terms.log_values[0] == pytest.approx(0.0)


def test_build_piecewise_planning_terms_preserves_reproducibility_metadata() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    first = build_piecewise_planning_terms(
        artifact_fixture["approximation_metadata"],
        max_terms=3,
    )
    second = build_piecewise_planning_terms(
        artifact_fixture["approximation_metadata"],
        max_terms=3,
    )

    assert first == second
    assert first.legacy_reference_paths == (
        "legacy/old_tpm/src_py/tpm/spn/main.py",
        "legacy/old_tpm/src_py/tpm/spn/encoding.py",
        "legacy/old_tpm/src_py/tpm/spn/utils_tangent.py",
        "legacy/old_tpm/src_py/utils/densities.py",
    )


def test_build_piecewise_planning_terms_rejects_invalid_max_terms() -> None:
    artifact_fixture = load_planning_fixture(TPM_ARTIFACT_FIXTURE_PATH)

    with pytest.raises(ValueError, match="max_terms"):
        build_piecewise_planning_terms(
            artifact_fixture["approximation_metadata"],
            max_terms=0,
        )
