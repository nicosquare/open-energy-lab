"""Optional empirical residual days replace per-step Gaussian demand residuals."""

from __future__ import annotations

from dataclasses import replace

import pytest

from open_energy_lab.demand import DemandSamplingRequest, sample_demand_family
from open_energy_lab.demand.artifact import DemandArtifact, DemandArtifactValidationError
from open_energy_lab.demand.fit import fit_demand_model
from tests.integration.demand.fixture_utils import ALIGNED_TRAINING_FIXTURE_PATH, load_demand_fixture
from tests.unit.demand.test_sampling_family import (
    _load_supported_demand_artifact,
    _sample_supported_weather_family,
)


def _library(days):
    return {"model_kind": "multiplicative-residual-days", "intervals_per_day": 1, "days": days}


def _sample(artifact):
    weather = _sample_supported_weather_family()
    request = DemandSamplingRequest(
        weather_family_reference=weather, num_steps=7, scenario_count=4, paired_family_seed=23
    )
    family = sample_demand_family(artifact, request=request)
    return [value for trace in family.sampled_traces for value in trace.non_thermal_electric_demand_kw]


def test_library_days_multiply_the_expected_profile():
    artifact = _load_supported_demand_artifact()
    expected = _sample(replace(artifact, residual_day_library=_library([[1.0]])))
    scaled = _sample(replace(artifact, residual_day_library=_library([[2.0], [0.5]])))

    ratios = {round(s / e, 9) for s, e in zip(scaled, expected) if e > 0}
    assert ratios == {2.0, 0.5}


def test_library_is_validated_and_serialized_only_when_present():
    artifact = _load_supported_demand_artifact()
    assert "residual_day_library" not in artifact.to_dict()
    with pytest.raises(DemandArtifactValidationError, match="intervals_per_day non-negative"):
        replace(artifact, residual_day_library=_library([[1.0, 1.0]]))
    with pytest.raises(DemandArtifactValidationError, match="model_kind"):
        replace(artifact, residual_day_library={**_library([[1.0]]), "model_kind": "other"})


def test_fit_stores_the_library_and_marks_the_artifact_id():
    payload = load_demand_fixture(ALIGNED_TRAINING_FIXTURE_PATH)
    plain = fit_demand_model(payload)
    with_days = fit_demand_model(payload, residual_days=[[1.2], [0.8]], residual_days_provenance={"source": "test"})

    assert with_days.artifact_id == plain.artifact_id + ":residual-days"
    reloaded = DemandArtifact.from_dict(with_days.to_dict())
    assert reloaded.residual_day_library["days"] == [[1.2], [0.8]]
    assert reloaded.residual_day_library["provenance"] == {"source": "test"}
