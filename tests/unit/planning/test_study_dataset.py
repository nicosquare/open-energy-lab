from __future__ import annotations

import json

import pytest

from open_energy_lab.planning.study_dataset import (
    PlanningStudyDatasetWriter,
    StudyDatasetIntegrityError,
    StudyDatasetValidationError,
    iter_study_rows,
    load_study_dataset_manifest,
)


COLUMNS = (
    "configuration_id",
    "sample_id",
    "battery_option_id",
    "solar_option_id",
    "shortfall_ratio",
    "adequacy_event",
)


def _rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "configuration_id": f"b{index // 2}__s{index % 2}",
            "sample_id": index,
            "battery_option_id": f"b{index // 2}",
            "solar_option_id": f"s{index % 2}",
            "shortfall_ratio": index / 10.0,
            "adequacy_event": int(index >= 2),
        }
        for index in range(4)
    )


@pytest.mark.parametrize("shard_format", ("jsonl", "parquet"))
def test_schema_v2_shards_round_trip_and_preserve_order(tmp_path, shard_format: str) -> None:
    writer = PlanningStudyDatasetWriter(
        output_dir=tmp_path / shard_format,
        dataset_id=f"dataset-{shard_format}",
        request_fingerprint="abc123",
        column_order=COLUMNS,
        shard_format=shard_format,
    )
    writer.write_shard(0, _rows()[:2])
    writer.write_shard(1, _rows()[2:])
    manifest = writer.finalize(metadata={"seed": 13})

    loaded = load_study_dataset_manifest(manifest.source_path)

    assert loaded.schema_version == "v2"
    assert loaded.row_count == 4
    assert tuple(iter_study_rows(loaded)) == _rows()
    assert all(shard.sha256 and shard.semantic_sha256 for shard in loaded.shards)


def test_jsonl_and_parquet_have_identical_semantic_digest(tmp_path) -> None:
    manifests = []
    for shard_format in ("jsonl", "parquet"):
        writer = PlanningStudyDatasetWriter(
            output_dir=tmp_path / shard_format,
            dataset_id=f"dataset-{shard_format}",
            request_fingerprint="same-request",
            column_order=COLUMNS,
            shard_format=shard_format,
        )
        writer.write_shard(0, _rows())
        manifests.append(writer.finalize())

    assert manifests[0].semantic_sha256 == manifests[1].semantic_sha256


def test_existing_matching_shard_is_reused_but_mismatch_is_rejected(tmp_path) -> None:
    writer = PlanningStudyDatasetWriter(
        output_dir=tmp_path,
        dataset_id="resume-dataset",
        request_fingerprint="request-a",
        column_order=COLUMNS,
        shard_format="jsonl",
    )
    first = writer.write_shard(0, _rows())
    repeated = writer.write_shard(0, _rows())
    assert repeated == first

    with pytest.raises(StudyDatasetIntegrityError, match="existing shard"):
        writer.write_shard(0, _rows()[:-1])


def test_corrupt_shard_fails_before_rows_are_returned(tmp_path) -> None:
    writer = PlanningStudyDatasetWriter(
        output_dir=tmp_path,
        dataset_id="corrupt-dataset",
        request_fingerprint="request-a",
        column_order=COLUMNS,
        shard_format="jsonl",
    )
    writer.write_shard(0, _rows())
    manifest = writer.finalize()
    shard_path = manifest.source_path.parent / manifest.shards[0].locator
    shard_path.write_text(json.dumps({"bad": True}) + "\n", encoding="utf-8")

    with pytest.raises(StudyDatasetIntegrityError, match="SHA-256"):
        tuple(iter_study_rows(load_study_dataset_manifest(manifest.source_path)))



@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("row_count",), "4"),
        (("created_at",), "2026-07-12T00:00:00"),
        (("shards", 0, "locator"), "../outside.jsonl"),
        (("shards", 0, "sha256"), "not-a-digest"),
    ],
)
def test_manifest_loading_rejects_coercible_or_unsafe_values(tmp_path, path, value) -> None:
    writer = PlanningStudyDatasetWriter(
        output_dir=tmp_path, dataset_id="d", request_fingerprint="abc", column_order=COLUMNS,
        shard_format="jsonl",
    )
    writer.write_shard(0, _rows())
    manifest = writer.finalize()
    payload = json.loads(manifest.source_path.read_text(encoding="utf-8"))
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(StudyDatasetValidationError, match=str(path[-1])):
        load_study_dataset_manifest(payload)
    assert manifest.to_dict()["created_at"] == manifest.created_at
