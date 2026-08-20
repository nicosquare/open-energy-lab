"""Sharded schema-v2 planning-study dataset artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


STUDY_DATASET_SCHEMA_VERSION = "v2"
SUPPORTED_STUDY_DATASET_SHARD_FORMATS = ("jsonl", "parquet")


class StudyDatasetIntegrityError(ValueError):
    """Raised when a manifest or shard fails deterministic integrity checks."""


@dataclass(frozen=True, slots=True)
class StudyDatasetShard:
    shard_index: int
    locator: str
    shard_format: str
    row_count: int
    row_start: int
    row_stop: int
    sha256: str
    semantic_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "shard_index": self.shard_index,
            "locator": self.locator,
            "shard_format": self.shard_format,
            "row_count": self.row_count,
            "row_start": self.row_start,
            "row_stop": self.row_stop,
            "sha256": self.sha256,
            "semantic_sha256": self.semantic_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> StudyDatasetShard:
        return cls(
            shard_index=int(value["shard_index"]),
            locator=str(value["locator"]),
            shard_format=str(value["shard_format"]),
            row_count=int(value["row_count"]),
            row_start=int(value["row_start"]),
            row_stop=int(value["row_stop"]),
            sha256=str(value["sha256"]),
            semantic_sha256=str(value["semantic_sha256"]),
        )


@dataclass(frozen=True, slots=True)
class PlanningStudyDatasetManifest:
    dataset_id: str
    request_fingerprint: str
    column_order: tuple[str, ...]
    shard_format: str
    shards: tuple[StudyDatasetShard, ...]
    row_count: int
    semantic_sha256: str
    metadata: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = STUDY_DATASET_SCHEMA_VERSION
    created_at: str = ""
    source_path: Path = Path()

    def __post_init__(self) -> None:
        if self.schema_version != STUDY_DATASET_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported planning study dataset schema_version {self.schema_version!r}"
            )
        if not self.dataset_id or not self.request_fingerprint:
            raise ValueError("dataset_id and request_fingerprint must be non-empty")
        if not self.column_order or len(set(self.column_order)) != len(self.column_order):
            raise ValueError("column_order must be non-empty and unique")
        if self.shard_format not in SUPPORTED_STUDY_DATASET_SHARD_FORMATS:
            raise ValueError("unsupported study dataset shard_format")
        if self.row_count != sum(shard.row_count for shard in self.shards):
            raise ValueError("manifest row_count must equal the sum of shard row counts")
        if tuple(shard.shard_index for shard in self.shards) != tuple(range(len(self.shards))):
            raise ValueError("manifest shards must use contiguous ordered indices")

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset_id": self.dataset_id,
            "schema_version": self.schema_version,
            "created_at": self.created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "request_fingerprint": self.request_fingerprint,
            "column_order": list(self.column_order),
            "shard_format": self.shard_format,
            "row_count": self.row_count,
            "semantic_sha256": self.semantic_sha256,
            "shards": [shard.to_dict() for shard in self.shards],
            "metadata": dict(self.metadata),
        }


class PlanningStudyDatasetWriter:
    """Write deterministic shards and one atomic manifest."""

    def __init__(
        self,
        *,
        output_dir: str | Path,
        dataset_id: str,
        request_fingerprint: str,
        column_order: Sequence[str],
        shard_format: str = "parquet",
    ) -> None:
        self.output_dir = Path(output_dir)
        self.dataset_id = str(dataset_id)
        self.request_fingerprint = str(request_fingerprint)
        self.column_order = tuple(str(name) for name in column_order)
        self.shard_format = str(shard_format)
        if not self.dataset_id or not self.request_fingerprint:
            raise ValueError("dataset_id and request_fingerprint must be non-empty")
        if not self.column_order or len(set(self.column_order)) != len(self.column_order):
            raise ValueError("column_order must be non-empty and unique")
        if self.shard_format not in SUPPORTED_STUDY_DATASET_SHARD_FORMATS:
            raise ValueError(
                "shard_format must be one of "
                + ", ".join(SUPPORTED_STUDY_DATASET_SHARD_FORMATS)
            )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "shards").mkdir(parents=True, exist_ok=True)
        self._shards: dict[int, StudyDatasetShard] = {}
        self._validate_existing_manifest()

    @property
    def manifest_path(self) -> Path:
        return self.output_dir / "manifest.json"

    def _validate_existing_manifest(self) -> None:
        if not self.manifest_path.exists():
            return
        existing = load_study_dataset_manifest(self.manifest_path)
        expected = (
            existing.dataset_id == self.dataset_id
            and existing.request_fingerprint == self.request_fingerprint
            and existing.column_order == self.column_order
            and existing.shard_format == self.shard_format
        )
        if not expected:
            raise StudyDatasetIntegrityError(
                "existing manifest is incompatible with the requested study dataset"
            )
        self._shards = {shard.shard_index: shard for shard in existing.shards}

    def has_shard(self, shard_index: int) -> bool:
        """Return whether a verified finalized manifest already contains a shard."""

        shard = self._shards.get(shard_index)
        if shard is None:
            return False
        path = self.output_dir / shard.locator
        if not path.exists() or _file_hash(path) != shard.sha256:
            raise StudyDatasetIntegrityError(
                f"study dataset shard {shard.locator!r} failed SHA-256 verification"
            )
        return True

    def write_shard(
        self,
        shard_index: int,
        rows: Sequence[Mapping[str, object]],
    ) -> StudyDatasetShard:
        if isinstance(shard_index, bool) or shard_index < 0:
            raise ValueError("shard_index must be a non-negative integer")
        normalized_rows = tuple(self._normalize_row(row) for row in rows)
        if not normalized_rows:
            raise ValueError("study dataset shards must not be empty")
        suffix = "jsonl" if self.shard_format == "jsonl" else "parquet"
        locator = f"shards/{shard_index:06d}.{suffix}"
        path = self.output_dir / locator
        expected_semantic = _semantic_hash(normalized_rows, self.column_order)

        if path.exists():
            actual_rows = tuple(_read_rows(path, self.shard_format, self.column_order))
            actual_semantic = _semantic_hash(actual_rows, self.column_order)
            if actual_semantic != expected_semantic or actual_rows != normalized_rows:
                raise StudyDatasetIntegrityError(
                    f"existing shard {locator!r} does not match requested rows"
                )
        else:
            _atomic_write_rows(
                path,
                normalized_rows,
                shard_format=self.shard_format,
                column_order=self.column_order,
            )

        descriptor = StudyDatasetShard(
            shard_index=int(shard_index),
            locator=locator,
            shard_format=self.shard_format,
            row_count=len(normalized_rows),
            row_start=0,
            row_stop=len(normalized_rows),
            sha256=_file_hash(path),
            semantic_sha256=expected_semantic,
        )
        previous = self._shards.get(shard_index)
        if previous is not None and (
            previous.sha256 != descriptor.sha256
            or previous.semantic_sha256 != descriptor.semantic_sha256
            or previous.row_count != descriptor.row_count
        ):
            raise StudyDatasetIntegrityError(
                f"existing shard metadata for {locator!r} does not match requested rows"
            )
        self._shards[shard_index] = descriptor
        return descriptor

    def _normalize_row(self, row: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(row, Mapping):
            raise TypeError("every study dataset row must be a mapping")
        keys = tuple(str(key) for key in row)
        if keys != self.column_order:
            raise ValueError("study dataset row keys and order must match column_order")
        return {name: row[name] for name in self.column_order}

    def finalize(
        self,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> PlanningStudyDatasetManifest:
        if not self._shards:
            raise ValueError("cannot finalize a study dataset without shards")
        indices = tuple(sorted(self._shards))
        if indices != tuple(range(len(indices))):
            raise ValueError("study dataset shards must use contiguous indices from zero")
        ordered: list[StudyDatasetShard] = []
        offset = 0
        semantic = hashlib.sha256()
        for shard_index in indices:
            shard = self._shards[shard_index]
            path = self.output_dir / shard.locator
            if _file_hash(path) != shard.sha256:
                raise StudyDatasetIntegrityError(
                    f"study dataset shard {shard.locator!r} failed SHA-256 verification"
                )
            rows = tuple(_read_rows(path, shard.shard_format, self.column_order))
            if _semantic_hash(rows, self.column_order) != shard.semantic_sha256:
                raise StudyDatasetIntegrityError(
                    f"study dataset shard {shard.locator!r} failed semantic verification"
                )
            for row in rows:
                semantic.update(_canonical_row_bytes(row, self.column_order))
            ordered.append(
                replace(
                    shard,
                    row_start=offset,
                    row_stop=offset + shard.row_count,
                )
            )
            offset += shard.row_count
        manifest = PlanningStudyDatasetManifest(
            dataset_id=self.dataset_id,
            request_fingerprint=self.request_fingerprint,
            column_order=self.column_order,
            shard_format=self.shard_format,
            shards=tuple(ordered),
            row_count=offset,
            semantic_sha256=semantic.hexdigest(),
            metadata=dict(metadata or {}),
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            source_path=self.manifest_path,
        )
        _atomic_write_json(self.manifest_path, manifest.to_dict())
        return manifest


def load_study_dataset_manifest(
    source: str | Path | Mapping[str, Any],
) -> PlanningStudyDatasetManifest:
    if isinstance(source, Mapping):
        data = source
        source_path = Path()
    else:
        source_path = Path(source)
        data = json.loads(source_path.read_text(encoding="utf-8"))
    required = {
        "dataset_id",
        "schema_version",
        "created_at",
        "request_fingerprint",
        "column_order",
        "shard_format",
        "row_count",
        "semantic_sha256",
        "shards",
        "metadata",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError("study dataset manifest is missing: " + ", ".join(missing))
    return PlanningStudyDatasetManifest(
        dataset_id=str(data["dataset_id"]),
        schema_version=str(data["schema_version"]),
        created_at=str(data["created_at"]),
        request_fingerprint=str(data["request_fingerprint"]),
        column_order=tuple(str(name) for name in data["column_order"]),
        shard_format=str(data["shard_format"]),
        row_count=int(data["row_count"]),
        semantic_sha256=str(data["semantic_sha256"]),
        shards=tuple(StudyDatasetShard.from_dict(item) for item in data["shards"]),
        metadata=dict(data["metadata"]),
        source_path=source_path,
    )


def iter_study_rows(
    manifest: PlanningStudyDatasetManifest | str | Path,
) -> Iterator[dict[str, object]]:
    resolved = (
        manifest
        if isinstance(manifest, PlanningStudyDatasetManifest)
        else load_study_dataset_manifest(manifest)
    )
    if not resolved.source_path:
        raise ValueError("iterating study rows requires a file-backed manifest")
    root = resolved.source_path.parent
    semantic = hashlib.sha256()
    count = 0
    for shard in resolved.shards:
        path = root / shard.locator
        if _file_hash(path) != shard.sha256:
            raise StudyDatasetIntegrityError(
                f"study dataset shard {shard.locator!r} failed SHA-256 verification"
            )
        rows = tuple(_read_rows(path, shard.shard_format, resolved.column_order))
        if len(rows) != shard.row_count:
            raise StudyDatasetIntegrityError(
                f"study dataset shard {shard.locator!r} row count does not match manifest"
            )
        if _semantic_hash(rows, resolved.column_order) != shard.semantic_sha256:
            raise StudyDatasetIntegrityError(
                f"study dataset shard {shard.locator!r} failed semantic verification"
            )
        for row in rows:
            semantic.update(_canonical_row_bytes(row, resolved.column_order))
            count += 1
            yield row
    if count != resolved.row_count or semantic.hexdigest() != resolved.semantic_sha256:
        raise StudyDatasetIntegrityError("study dataset manifest semantic digest mismatch")


def _canonical_row_bytes(
    row: Mapping[str, object],
    column_order: Sequence[str],
) -> bytes:
    ordered_values = [row[name] for name in column_order]
    return (
        json.dumps(ordered_values, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _semantic_hash(rows: Iterable[Mapping[str, object]], column_order: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_canonical_row_bytes(row, column_order))
    return digest.hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_rows(
    path: Path,
    rows: Sequence[Mapping[str, object]],
    *,
    shard_format: str,
    column_order: Sequence[str],
) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        if shard_format == "jsonl":
            with temporary_path.open("w", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(
                        json.dumps(
                            {name: row[name] for name in column_order},
                            ensure_ascii=False,
                            allow_nan=False,
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
        else:
            import pyarrow as pa
            import pyarrow.parquet as pq

            table = pa.table(
                {name: [row[name] for row in rows] for name in column_order}
            )
            pq.write_table(table, temporary_path, compression="zstd")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    os.close(file_descriptor)
    temporary_path = Path(temporary_name)
    try:
        temporary_path.write_text(
            json.dumps(value, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _read_rows(
    path: Path,
    shard_format: str,
    column_order: Sequence[str],
) -> Iterator[dict[str, object]]:
    if shard_format == "jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                value = json.loads(line)
                yield {name: value[name] for name in column_order}
        return

    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=list(column_order))
    for value in table.to_pylist():
        yield {name: value[name] for name in column_order}


__all__ = [
    "PlanningStudyDatasetManifest",
    "PlanningStudyDatasetWriter",
    "STUDY_DATASET_SCHEMA_VERSION",
    "StudyDatasetIntegrityError",
    "StudyDatasetShard",
    "iter_study_rows",
    "load_study_dataset_manifest",
]
