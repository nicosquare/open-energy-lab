"""Persisted TPM artifact contracts and offline loading helpers."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .features import TPMFeatureSpec, dump_feature_schema, load_feature_schema
from .piecewise import load_piecewise_metadata

FEATURE_NAME = "009-tpm-planning"
SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS = ("v1",)
TPM_ARTIFACT_REQUIRED_KEYS = (
    "artifact_id",
    "schema_version",
    "created_at",
    "dataset_reference",
    "feature_schema",
    "target_definition",
    "fit_configuration",
    "spn_payload",
    "spn_payload_format",
    "query_configuration",
    "approximation_metadata",
    "provenance",
)


class UnsupportedTPMArtifactVersionError(ValueError):
    """Raised when artifact loading sees an unsupported schema version."""


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
    spn_payload: object = None
    spn_payload_format: str = ""
    query_configuration: Mapping[str, object] = field(default_factory=dict)
    approximation_metadata: Mapping[str, object] = field(default_factory=dict)
    provenance: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version not in SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS:
            raise UnsupportedTPMArtifactVersionError(
                f"unsupported tpm artifact schema_version {self.schema_version!r}"
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
            "spn_payload": _serialize_spn_payload(self.spn_payload),
            "spn_payload_format": self.spn_payload_format,
            "query_configuration": dict(self.query_configuration),
            "approximation_metadata": dict(self.approximation_metadata),
            "provenance": dict(self.provenance),
        }

    def write_json(self, path: str | Path) -> Path:
        """Persist the artifact as a human-inspectable JSON file."""

        output_path = Path(path)
        output_path.write_text(
            json.dumps(self.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

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

        missing = [key for key in TPM_ARTIFACT_REQUIRED_KEYS if key not in data]
        if missing:
            raise ValueError(
                "TPM artifact is missing required keys: " + ", ".join(missing)
            )

        schema_version = str(data["schema_version"])
        if schema_version not in SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS:
            raise UnsupportedTPMArtifactVersionError(
                f"unsupported tpm artifact schema_version {schema_version!r}"
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

        spn_payload_format = str(data["spn_payload_format"])
        if not spn_payload_format:
            raise ValueError("spn_payload_format must be non-empty")
        spn_payload = _validate_spn_payload(
            data["spn_payload"],
            spn_payload_format=spn_payload_format,
        )

        query_configuration = _mapping(
            data["query_configuration"],
            field_name="query_configuration",
        )
        _validate_query_configuration(
            query_configuration,
            feature_schema=feature_schema,
        )

        approximation_metadata = _mapping(
            data["approximation_metadata"],
            field_name="approximation_metadata",
        )
        approximation_metadata = load_piecewise_metadata(approximation_metadata).to_dict()

        provenance = _mapping(data["provenance"], field_name="provenance")

        return cls(
            artifact_id=artifact_id,
            schema_version=schema_version,
            created_at=created_at,
            dataset_reference=dataset_reference,
            feature_schema=dump_feature_schema(feature_schema),
            target_definition=target_definition,
            fit_configuration=fit_configuration,
            spn_payload=spn_payload,
            spn_payload_format=spn_payload_format,
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
    else:
        raw_payload = json.loads(Path(source).read_text(encoding="utf-8"))

    return TPMArtifact.from_dict(raw_payload)


__all__ = [
    "FEATURE_NAME",
    "SUPPORTED_TPM_ARTIFACT_SCHEMA_VERSIONS",
    "TPM_ARTIFACT_REQUIRED_KEYS",
    "TPMArtifact",
    "UnsupportedTPMArtifactVersionError",
    "load_tpm_artifact",
]


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
    if not str(target_definition.get("supported_query_mode", "")):
        raise ValueError("target_definition.supported_query_mode must be non-empty")

    feature_by_name = {spec.feature_name: spec for spec in feature_schema}
    if target_name not in feature_by_name:
        raise ValueError(
            f"target_definition.target_name {target_name!r} is not present in feature_schema"
        )
    if feature_by_name[target_name].feature_role != "target":
        raise ValueError(
            f"feature_schema entry {target_name!r} must have feature_role 'target'"
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
    if spn_payload_format == "json-inline":
        if not isinstance(payload, Mapping):
            raise TypeError("spn_payload must be a mapping for spn_payload_format 'json-inline'")
        return {str(key): value for key, value in payload.items()}

    if spn_payload_format.endswith("-path") or spn_payload_format.endswith("-locator"):
        if isinstance(payload, str):
            if not payload:
                raise ValueError("spn_payload locator must be non-empty")
            return payload
        if isinstance(payload, Mapping):
            normalized = {str(key): value for key, value in payload.items()}
            locator = normalized.get("locator", normalized.get("path", ""))
            if not isinstance(locator, str) or not locator:
                raise ValueError("spn_payload locator payload must include a non-empty locator")
            return normalized
        raise TypeError(
            "spn_payload locator formats require a string payload or locator mapping"
        )

    return payload


def _serialize_spn_payload(payload: object) -> object:
    if isinstance(payload, Mapping):
        return {str(key): value for key, value in payload.items()}
    return payload
