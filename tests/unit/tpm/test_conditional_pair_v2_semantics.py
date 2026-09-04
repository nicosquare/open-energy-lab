"""Focused conditional-pair-v2 semantic migration contracts."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from open_energy_lab.tpm.conditional import (
    CONDITIONAL_PAIR_COMPILER_VERSION,
    CONDITIONAL_PAIR_RECORD_KIND,
    CONDITIONAL_PAIR_SCHEMA_VERSION,
    load_conditional_pair,
)
from open_energy_lab.tpm.piecewise import (
    CONDITIONAL_GUARD_TRANSITION_WIDTH,
    PiecewiseBreakpointPolicy,
    build_logsumexp_piecewise_spec,
    evaluate_guarded_exponential,
    piecewise_linear_interpolate,
    resolve_guarded_exponential_spec,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("resolution", (5, 9, 17))
def test_v2_guard_has_zero_plateau_transition_and_unchanged_base(
    resolution: int,
) -> None:
    base = build_logsumexp_piecewise_spec(
        max_terms=2,
        breakpoint_policy=PiecewiseBreakpointPolicy(
            piecewise_breakpoint_count=resolution
        ),
    )
    resolved = resolve_guarded_exponential_spec(
        base_x_points=base["exp_x_points"],
        base_y_points=base["exp_y_points"],
    )
    cutoff = math.log(1e-3)
    transition_end = cutoff + CONDITIONAL_GUARD_TRANSITION_WIDTH
    base_at_end = piecewise_linear_interpolate(
        transition_end,
        x_points=base["exp_x_points"],
        y_points=base["exp_y_points"],
    )

    assert evaluate_guarded_exponential(cutoff - 1.0, configuration=resolved) == 0.0
    assert evaluate_guarded_exponential(cutoff, configuration=resolved) == 0.0
    assert evaluate_guarded_exponential(
        cutoff + 0.5e-3, configuration=resolved
    ) == pytest.approx(0.5 * base_at_end)
    assert evaluate_guarded_exponential(
        transition_end, configuration=resolved
    ) == pytest.approx(base_at_end)
    for x_value, y_value in zip(
        base["exp_x_points"], base["exp_y_points"], strict=True
    ):
        if x_value >= transition_end:
            assert evaluate_guarded_exponential(
                x_value, configuration=resolved
            ) == pytest.approx(y_value)


def test_v2_versions_are_explicit() -> None:
    assert CONDITIONAL_PAIR_RECORD_KIND == "conditional-pair-v2"
    assert CONDITIONAL_PAIR_SCHEMA_VERSION == "v2"
    assert CONDITIONAL_PAIR_COMPILER_VERSION == "conditional-mio-v2"


@pytest.mark.parametrize(
    "name", ("conditional_pair_max_v1.json", "conditional_pair_pwl_v1.json")
)
def test_v1_pair_requires_recompilation(name: str) -> None:
    path = REPOSITORY_ROOT / "tests" / "fixtures" / "tpm" / name
    with pytest.raises(ValueError, match="recompile the fitted artifact"):
        load_conditional_pair(path)
