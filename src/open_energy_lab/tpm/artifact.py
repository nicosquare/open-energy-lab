"""Persisted TPM artifact contracts and offline loading helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .features import TPMFeatureSpec, dump_feature_schema, load_feature_schema
from .piecewise import load_piecewise_metadata

FEATURE_NAME = "009-tpm-planning"
SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS = ("v2",)
SUPPORTED_TPM_EXECUTION_MODES = ("production", "fixture_replay")
TPM_ARTIFACT_REQUIRED_KEYS = (
    "artifact_id",
    "schema_version",
    "created_at",
    "dataset_reference",
    "feature_schema",
    "target_definition",
    "fit_configuration",
    "backend_generation",
    "backend_api_version",
    "execution_mode",
    "spn_payload",
    "spn_payload_format",
    "payload_hash",
    "query_configuration",
    "approximation_metadata",
    "provenance",
)


class UnsupportedTPMArtifactVersionError(ValueError):
    """Raised when artifact loading sees an unsupported schema version."""


class LegacyTPMArtifactVersionError(UnsupportedTPMArtifactVersionError):
    """Raised when a schema-v1 artifact must be rebuilt with current SPFlow."""


class TPMArtifactIntegrityError(ValueError):
    """Raised when a schema-v2 model sidecar is absent or fails verification."""


@dataclass(frozen=True, slots=True)
class TPMArtifact:
    """Import-light persisted TPM artifact contract."""

    artifact_id: str
    schema_version: str
    created_at: str = ""
    dataset_reference: str = ""
    feature_schema: tuple[Mapping[str, object], ...] = field(default_factory=tuple)
    target_definition: Mapping[str, object] = field(default_factory=dict)
    fit_configuration: Mapping[str, object] = field(default_factory=dict)
    backend_generation: str = ""
    backend_api_version: str = ""
    execution_mode: str = "production"
    spn_payload: object = None
    spn_payload_format: str = ""
    payload_hash: str = ""
    query_configuration: Mapping[str, object] = field(default_factory=dict)
    approximation_metadata: Mapping[str, object] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)
    source_path: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schema_version",
            _validate_schema_version(self.schema_version),
        )
        object.__setattr__(
            self,
            "backend_generation",
            _validate_non_empty_string(
                self.backend_generation,
                field_name="backend_generation",
            ),
        )
        object.__setattr__(
            self,
            "backend_api_version",
            _validate_non_empty_string(
                self.backend_api_version,
                field_name="backend_api_version",
            ),
        )
        object.__setattr__(
            self,
            "execution_mode",
            _validate_execution_mode(self.execution_mode),
        )
        object.__setattr__(
            self,
            "payload_hash",
            _validate_payload_hash(self.payload_hash),
        )
        object.__setattr__(
            self,
            "spn_payload_format",
            _validate_non_empty_string(
                self.spn_payload_format,
                field_name="spn_payload_format",
            ),
        )
        object.__setattr__(
            self,
            "spn_payload",
            _validate_spn_payload(
                self.spn_payload,
                spn_payload_format=self.spn_payload_format,
            ),
        )

    @property
    def feature_specs(self) -> tuple[TPMFeatureSpec, ...]:
        """Load the persisted feature schema into validated feature specs."""

        return load_feature_schema(self.feature_schema)

    def to_dict(self) -> dict[str, object]:
        """Serialize the TPM artifact into its persisted JSON shape."""

        return {
            "artifact_id": self.artifact_id,
            "schema_version": self.schema_version,
            "created_at": _persisted_created_at(self.created_at),
            "dataset_reference": self.dataset_reference,
            "feature_schema": list(dump_feature_schema(self.feature_specs)),
            "target_definition": dict(self.target_definition),
            "fit_configuration": dict(self.fit_configuration),
            "backend_generation": self.backend_generation,
            "backend_api_version": self.backend_api_version,
            "execution_mode": self.execution_mode,
            "spn_payload": _serialize_spn_payload(self.spn_payload),
            "spn_payload_format": self.spn_payload_format,
            "payload_hash": self.payload_hash,
            "query_configuration": dict(self.query_configuration),
            "approximation_metadata": dict(self.approximation_metadata),
            "provenance": dict(self.provenance),
        }

    def write_json(self, path: str | Path) -> Path:
        """Atomically persist the artifact as human-inspectable JSON."""

        output_path = Path(path)
        _atomic_write_bytes(
            output_path,
            (json.dumps(self.to_dict(), indent=2) + "\n").encode("utf-8"),
        )
        return output_path

    @property
    def payload_locator(self) -> str:
        """Return the validated project-relative model-sidecar locator."""

        return _payload_locator(self.spn_payload)

    @property
    def sidecar_path(self) -> Path:
        """Resolve the model sidecar against the manifest location when known."""

        locator_path = Path(self.payload_locator)
        if not self.source_path:
            return locator_path
        artifact_directory = Path(self.source_path).resolve().parent
        resolved_path = (artifact_directory / locator_path).resolve()
        try:
            resolved_path.relative_to(artifact_directory)
        except ValueError as exc:
            raise TPMArtifactIntegrityError(
                "TPM artifact sidecar resolves outside the artifact directory"
            ) from exc
        return resolved_path

    def validate_feature_assignments(self, assignments: Mapping[str, object]) -> None:
        """Validate concrete feature assignments against the artifact schema."""

        if not isinstance(assignments, Mapping):
            raise TypeError("feature assignments must be a mapping")

        feature_by_name = {spec.feature_name: spec for spec in self.feature_specs}
        for feature_name, value in assignments.items():
            if feature_name not in feature_by_name:
                raise ValueError(f"unknown TPM feature assignment {feature_name!r}")
            feature_by_name[feature_name].validate_value(value)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TPMArtifact:
        """Construct a validated artifact from one decoded JSON payload."""

        if "schema_version" not in data:
            raise ValueError("TPM artifact is missing required keys: schema_version")
        schema_version = str(data["schema_version"])
        _validate_schema_version(schema_version)

        missing = [key for key in TPM_ARTIFACT_REQUIRED_KEYS if key not in data]
        if missing:
            raise ValueError(
                "TPM artifact is missing required keys: " + ", ".join(missing)
            )

        artifact_id = str(data["artifact_id"])
        if not artifact_id:
            raise ValueError("artifact_id must be non-empty")

        created_at = str(data["created_at"])
        _validate_timestamp(created_at, field_name="created_at")

        dataset_reference = str(data["dataset_reference"])
        if not dataset_reference:
            raise ValueError("dataset_reference must be non-empty")

        feature_schema = load_feature_schema(_sequence_of_mappings(data["feature_schema"]))
        if not feature_schema:
            raise ValueError("feature_schema must not be empty")

        target_definition = _mapping(data["target_definition"], field_name="target_definition")
        _validate_target_definition(target_definition, feature_schema=feature_schema)

        fit_configuration = _mapping(
            data["fit_configuration"],
            field_name="fit_configuration",
        )
        backend_name = str(fit_configuration.get("backend_name", ""))
        if not backend_name:
            raise ValueError("fit_configuration.backend_name must be non-empty")

        backend_generation = _validate_non_empty_string(
            data["backend_generation"],
            field_name="backend_generation",
        )
        backend_api_version = _validate_non_empty_string(
            data["backend_api_version"],
            field_name="backend_api_version",
        )
        execution_mode = _validate_execution_mode(data["execution_mode"])

        spn_payload_format = _validate_non_empty_string(
            data["spn_payload_format"],
            field_name="spn_payload_format",
        )
        spn_payload = _validate_spn_payload(
            data["spn_payload"],
            spn_payload_format=spn_payload_format,
        )
        payload_hash = _validate_payload_hash(data["payload_hash"])

        query_configuration = _mapping(
            data["query_configuration"],
            field_name="query_configuration",
        )
        _validate_query_configuration(
            query_configuration,
            feature_schema=feature_schema,
        )

        raw_approximation_metadata = _mapping(
            data["approximation_metadata"],
            field_name="approximation_metadata",
        )
        approximation_metadata = {
            **raw_approximation_metadata,
            **load_piecewise_metadata(raw_approximation_metadata).to_dict(),
        }

        provenance = _mapping(data["provenance"], field_name="provenance")

        return cls(
            artifact_id=artifact_id,
            schema_version=schema_version,
            created_at=created_at,
            dataset_reference=dataset_reference,
            feature_schema=dump_feature_schema(feature_schema),
            target_definition=target_definition,
            fit_configuration=fit_configuration,
            backend_generation=backend_generation,
            backend_api_version=backend_api_version,
            execution_mode=execution_mode,
            spn_payload=spn_payload,
            spn_payload_format=spn_payload_format,
            payload_hash=payload_hash,
            query_configuration={
                "supported_output_modes": list(
                    _string_sequence(
                        query_configuration["supported_output_modes"],
                        field_name="query_configuration.supported_output_modes",
                    )
                ),
                "required_decision_features": list(
                    _string_sequence(
                        query_configuration["required_decision_features"],
                        field_name="query_configuration.required_decision_features",
                    )
                ),
                **{
                    key: value
                    for key, value in query_configuration.items()
                    if key
                    not in {
                        "supported_output_modes",
                        "required_decision_features",
                    }
                },
            },
            approximation_metadata=approximation_metadata,
            provenance=provenance,
        )


def load_tpm_artifact(source: str | Path | Mapping[str, Any]) -> TPMArtifact:
    """Load and validate a persisted TPM artifact."""

    if isinstance(source, Mapping):
        raw_payload = source
        source_path = ""
    else:
        path = Path(source)
        raw_payload = json.loads(path.read_text(encoding="utf-8"))
        source_path = path.as_posix()

    artifact = TPMArtifact.from_dict(raw_payload)
    if not source_path:
        return artifact
    artifact = replace(artifact, source_path=source_path)
    _verify_sidecar_integrity(artifact)
    return artifact


def write_tpm_sidecar(
    path: str | Path,
    payload: bytes | bytearray | memoryview,
) -> tuple[Path, str]:
    """Atomically write sidecar bytes and return their persisted SHA-256 digest."""

    if not isinstance(payload, bytes | bytearray | memoryview):
        raise TypeError("TPM sidecar payload must be bytes-like")
    normalized_payload = bytes(payload)
    output_path = Path(path)
    _atomic_write_bytes(output_path, normalized_payload)
    return output_path, hashlib.sha256(normalized_payload).hexdigest()


__all__ = [
    "FEATURE_NAME",
    "LegacyTPMArtifactVersionError",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "SUPPORTED_TPM_EXECUTION_MODES",
    "TPM_ARTIFACT_REQUIRED_KEYS",
    "TPMArtifact",
    "TPMArtifactIntegrityError",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
    "write_tpm_sidecar",
]


def _validate_schema_version(schema_version: object) -> str:
    normalized_version = str(schema_version)
    if normalized_version == "v1":
        raise LegacyTPMArtifactVersionError(
            "legacy TPM artifact schema_version 'v1' is incompatible with the "
            "current SPFlow backend; refit the source planning dataset to create "
            "a schema-v2 artifact"
        )
    if normalized_version not in SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS:
        raise UnsupportedTPMArtifactVersionError(
            f"unsupported tpm artifact schema_version {normalized_version!r}"
        )
    return normalized_version


def _validate_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    normalized_value = value.strip()
    return normalized_value


def _validate_execution_mode(value: object) -> str:
    execution_mode = str(value)
    if execution_mode not in SUPPORTED_TPM_EXECUTION_MODES:
        raise ValueError(
            "execution_mode must be one of "
            f"{SUPPORTED_TPM_EXECUTION_MODES!r}; got {execution_mode!r}"
        )
    return execution_mode


def _validate_payload_hash(value: object) -> str:
    payload_hash = str(value).lower()
    if len(payload_hash) != 64 or any(
        character not in "0123456789abcdef" for character in payload_hash
    ):
        raise ValueError("payload_hash must be a 64-character SHA-256 hex digest")
    return payload_hash


def _payload_locator(payload: object) -> str:
    if not isinstance(payload, Mapping):
        raise TypeError("schema-v2 spn_payload must be a sidecar locator mapping")
    locator = payload.get("locator")
    if not isinstance(locator, str) or not locator or locator != locator.strip():
        raise ValueError(
            "schema-v2 spn_payload locator must be a non-empty project-relative path"
        )
    if "\\" in locator or "://" in locator:
        raise ValueError(
            "schema-v2 spn_payload locator must be a project-relative POSIX path"
        )
    locator_path = Path(locator)
    if (
        locator_path.is_absolute()
        or locator_path == Path(".")
        or ".." in locator_path.parts
    ):
        raise ValueError(
            "schema-v2 spn_payload locator must be project-relative and remain "
            "inside the artifact directory"
        )
    return locator_path.as_posix()


def _verify_sidecar_integrity(artifact: TPMArtifact) -> None:
    sidecar_path = artifact.sidecar_path
    if not sidecar_path.is_file():
        raise TPMArtifactIntegrityError(
            "TPM artifact sidecar is missing for spn_payload locator "
            f"{artifact.payload_locator!r}"
        )

    digest = hashlib.sha256()
    with sidecar_path.open("rb") as sidecar_file:
        for chunk in iter(lambda: sidecar_file.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_hash = digest.hexdigest()
    if actual_hash != artifact.payload_hash:
        raise TPMArtifactIntegrityError(
            "TPM artifact sidecar SHA-256 integrity check failed for "
            f"{artifact.payload_locator!r}: expected {artifact.payload_hash}, "
            f"got {actual_hash}"
        )


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): inner_value for key, inner_value in value.items()}


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if isinstance(value, Mapping) or not isinstance(value, tuple | list):
        raise TypeError("feature_schema must be a sequence of mappings")
    items = tuple(value)
    if any(not isinstance(item, Mapping) for item in items):
        raise TypeError("feature_schema must contain only mappings")
    return items


def _string_sequence(value: object, *, field_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, tuple | list):
        raise TypeError(f"{field_name} must be a sequence of strings")
    normalized = tuple(str(item) for item in value)
    if any(not item for item in normalized):
        raise ValueError(f"{field_name} must not contain empty strings")
    return normalized


def _validate_timestamp(value: object, *, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty ISO-8601 timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid ISO-8601 timestamp") from exc


def _persisted_created_at(created_at: str) -> str:
    if created_at:
        _validate_timestamp(created_at, field_name="created_at")
        return created_at
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_target_definition(
    target_definition: Mapping[str, object],
    *,
    feature_schema: tuple[TPMFeatureSpec, ...],
) -> None:
    target_name = str(target_definition.get("target_name", ""))
    if not target_name:
        raise ValueError("target_definition.target_name must be non-empty")
    event_target_name = str(target_definition.get("event_target_name", ""))
    if not event_target_name:
        raise ValueError("target_definition.event_target_name must be non-empty")
    if not str(target_definition.get("supported_query_mode", "")):
        raise ValueError("target_definition.supported_query_mode must be non-empty")

    feature_by_name = {spec.feature_name: spec for spec in feature_schema}
    if target_name not in feature_by_name:
        raise ValueError(
            f"target_definition.target_name {target_name!r} is not present in feature_schema"
        )
    if feature_by_name[target_name].feature_role not in {"metric_target", "target"}:
        raise ValueError(
            f"feature_schema entry {target_name!r} must have feature_role "
            "'metric_target' or 'target'"
        )
    if event_target_name not in feature_by_name:
        raise ValueError(
            "target_definition.event_target_name "
            f"{event_target_name!r} is not present in feature_schema"
        )
    if feature_by_name[event_target_name].feature_role != "target":
        raise ValueError(
            f"feature_schema entry {event_target_name!r} must have feature_role 'target'"
        )


def _validate_query_configuration(
    query_configuration: Mapping[str, object],
    *,
    feature_schema: tuple[TPMFeatureSpec, ...],
) -> None:
    supported_output_modes = _string_sequence(
        query_configuration.get("supported_output_modes"),
        field_name="query_configuration.supported_output_modes",
    )
    if not supported_output_modes:
        raise ValueError("query_configuration.supported_output_modes must not be empty")

    required_decision_features = _string_sequence(
        query_configuration.get("required_decision_features"),
        field_name="query_configuration.required_decision_features",
    )

    feature_by_name = {spec.feature_name: spec for spec in feature_schema}
    for feature_name in required_decision_features:
        if feature_name not in feature_by_name:
            raise ValueError(
                "query_configuration.required_decision_features references unknown "
                f"feature {feature_name!r}"
            )
        spec = feature_by_name[feature_name]
        if not spec.modifiable:
            raise ValueError(
                "query_configuration.required_decision_features must reference "
                f"modifiable features, found {feature_name!r}"
            )


def _validate_spn_payload(
    payload: object,
    *,
    spn_payload_format: str,
) -> object:
    if not spn_payload_format:
        raise ValueError("spn_payload_format must be non-empty")
    if spn_payload_format == "json-inline":
        raise ValueError(
            "schema-v2 spn_payload_format must describe a model sidecar, not json-inline"
        )
    if not isinstance(payload, Mapping):
        raise TypeError("schema-v2 spn_payload must be a sidecar locator mapping")

    normalized = {str(key): value for key, value in payload.items()}
    normalized["locator"] = _payload_locator(normalized)
    serialization = normalized.get("serialization")
    if not isinstance(serialization, str) or not serialization.strip():
        raise ValueError(
            "schema-v2 spn_payload must include a non-empty serialization"
        )
    normalized["serialization"] = serialization.strip()
    return normalized


def _serialize_spn_payload(payload: object) -> object:
    if isinstance(payload, Mapping):
        return {str(key): value for key, value in payload.items()}
    return payload
