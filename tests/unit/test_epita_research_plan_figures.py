"""Contract tests for the standalone EPITA proposal figure generator."""

from __future__ import annotations

from pathlib import Path

import pytest

from examples.epita_research_plan.generate_figures import (
    DEMONSTRATION_MAP_FILENAME,
    OUTPUT_FILENAME,
    build_research_backbone_data,
    render_demonstration_map_figure,
    render_research_backbone_figure,
)


def test_research_backbone_data_uses_reviewed_and_deployable_evidence() -> None:
    data = build_research_backbone_data()

    assert data.case_names == ("lower-boundary", "interior", "upper-boundary")
    assert tuple(name for name, _ in data.compiled_probabilities_by_encoding) == (
        "MAX",
        "PWL",
    )
    assert len(data.tpm_evidence_ids) == 2
    assert len(set(data.tpm_evidence_ids)) == 2
    assert len(data.energy_baseline_kw) == 24
    assert len(data.reserve_by_hour_kw) == 24
    assert data.reserve_by_hour_kw[8:] == pytest.approx((3.636363636,) * 16)
    assert len(data.robust_result_fingerprint) == 64


def test_research_backbone_pdf_is_written_to_explicit_destination(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    data = build_research_backbone_data()
    destination = render_research_backbone_figure(
        data,
        tmp_path / OUTPUT_FILENAME,
    )

    assert destination == tmp_path / OUTPUT_FILENAME
    assert destination.read_bytes().startswith(b"%PDF")
    assert destination.stat().st_size > 10_000


def test_demonstration_map_pdf_is_written_to_explicit_destination(
    tmp_path: Path,
) -> None:
    pytest.importorskip("matplotlib")
    destination = render_demonstration_map_figure(
        tmp_path / DEMONSTRATION_MAP_FILENAME,
    )

    assert destination == tmp_path / DEMONSTRATION_MAP_FILENAME
    assert destination.read_bytes().startswith(b"%PDF")
    assert destination.stat().st_size > 10_000
