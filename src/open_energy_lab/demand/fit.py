"""Demand-artifact fitting entry points."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ._aligned_history import normalize_aligned_training_history
from ._weather_response import fit_dual_output_weather_response
from .artifact import RESIDUAL_DAY_LIBRARY_KIND, DemandArtifact


FEATURE_NAME = "008-weather-demand-modeling"
DOUBLE_COUNTING_POLICY = "explicit_cooling_separate_from_non_thermal_electric"
LEGACY_CONCEPTUAL_EVIDENCE_PATHS = (
    "legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_1.ipynb",
    "legacy/fed_trpo/src/notebooks/ML_817_topic_I_lab_2.ipynb",
    "legacy/fed_trpo/src/notebooks/data_generation/naive_data_generation.ipynb",
)


def fit_demand_model(
    training_payload: dict[str, object],
    *,
    output_path: str | Path | None = None,
    residual_days: list[list[float]] | None = None,
    residual_days_provenance: dict[str, object] | None = None,
) -> DemandArtifact:
    """Fit and optionally persist a first-release weather-conditioned demand artifact.

    ``residual_days`` (one non-negative multiplier per local step per day, e.g.
    observed days divided by their expected profile) replaces the per-step
    Gaussian residual: sampling multiplies each day's expected profile by one
    whole library day. The artifact id gains ``:residual-days``.
    """

    aligned_history = normalize_aligned_training_history(training_payload)
    fitted_response = fit_dual_output_weather_response(aligned_history)
    created_at = datetime.now(tz=ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")

    provenance = dict(aligned_history.provenance)
    provenance.update(
        {
            "training_dataset_id": aligned_history.dataset_id,
            "legacy_evidence_paths": list(LEGACY_CONCEPTUAL_EVIDENCE_PATHS),
            "fit_notes": [
                "dual_output_local_civil_baseline",
                "cooling_history_required",
            ],
        }
    )

    library = None
    if residual_days is not None:
        library = {
            "model_kind": RESIDUAL_DAY_LIBRARY_KIND,
            "intervals_per_day": fitted_response.shared_residual_model.intervals_per_day,
            "days": [list(map(float, day)) for day in residual_days],
            "provenance": dict(residual_days_provenance or {}),
        }
    artifact = DemandArtifact(
        artifact_id=f"demand-artifact:{aligned_history.dataset_id}"
        + (":residual-days" if library is not None else ""),
        schema_version="v1",
        feature_name=FEATURE_NAME,
        created_at=created_at,
        timezone_name=aligned_history.timezone_name,
        time_basis=aligned_history.time_basis,
        timestep_hours=aligned_history.timestep_hours,
        required_weather_field_order=fitted_response.required_weather_field_order,
        training_record_summary={
            "dataset_id": aligned_history.dataset_id,
            "record_count": aligned_history.record_count,
            "first_timestamp_utc": aligned_history.timestamp_utc[0],
            "last_timestamp_utc": aligned_history.timestamp_utc[-1],
            "local_step_count": len(aligned_history.local_civil_step_labels),
        },
        non_thermal_electric_model=fitted_response.non_thermal_electric_model.to_dict(
            baseline_field_name="local_step_baseline_kw"
        ),
        cooling_demand_model=fitted_response.cooling_demand_model.to_dict(
            baseline_field_name="local_step_baseline_rt"
        ),
        shared_residual_model=fitted_response.shared_residual_model.to_dict(),
        double_counting_policy=DOUBLE_COUNTING_POLICY,
        provenance=provenance,
        supported_sampling_modes=("offline",),
        residual_day_library=library,
    )
    if output_path is not None:
        artifact.write_json(output_path)
    return artifact


__all__ = [
    "DOUBLE_COUNTING_POLICY",
    "FEATURE_NAME",
    "LEGACY_CONCEPTUAL_EVIDENCE_PATHS",
    "fit_demand_model",
]
