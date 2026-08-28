"""Stage or verify reviewed conditional-MIO fixtures without silent repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from tempfile import TemporaryDirectory

from open_energy_lab.tpm import (
    TPMArtifactBuildRequest,
    TPMFeatureDomain,
    TPMFitConfig,
    detect_spflow_backend_capabilities,
    fit_tpm_artifact_from_rows,
    load_tpm_artifact,
)
from open_energy_lab.tpm.artifact import write_tpm_sidecar
from open_energy_lab.tpm.optional_spflow import load_spflow_payload
from open_energy_lab.tpm.query import reduce_spflow_log_likelihood


EXAMPLE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXAMPLE_DIRECTORY.parent.parent
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "tests" / "fixtures" / "tpm"
SOURCE_PATH = FIXTURE_DIRECTORY / "conditional_mio_embedding_v1.json"
ARTIFACT_PATH = FIXTURE_DIRECTORY / "tpm_artifact_conditional_mio_v3.json"
SIDECAR_PATH = (
    FIXTURE_DIRECTORY
    / "sidecars"
    / "tpm_artifact_conditional_mio_v3.spn_payload.pkl"
)
FIXED_FIXTURE_TIMESTAMP = "2026-08-28T00:00:00Z"
STAGING_COMMAND = (
    "uv run --offline --locked --no-sync python "
    "examples/tpm_planning/run_conditional_mio_embedding.py "
    "--stage-fixtures <fresh-directory>"
)
VERIFICATION_COMMAND = (
    "uv run --offline --locked --no-sync python "
    "examples/tpm_planning/run_conditional_mio_embedding.py --verify-fixtures"
)


def _load_source() -> dict[str, object]:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("conditional-MIO source fixture must be a JSON object")
    return payload


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): item for key, item in value.items()}


def _rows(source: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    values = source.get("physical_training_rows")
    if not isinstance(values, list) or not values:
        raise ValueError("source fixture requires physical_training_rows")
    if any(not isinstance(row, Mapping) for row in values):
        raise TypeError("physical_training_rows must contain only mappings")
    return tuple(dict(row) for row in values)


def _feature_domains(
    source: Mapping[str, object],
) -> dict[str, TPMFeatureDomain]:
    declarations = _mapping(
        source.get("feature_declarations"), field_name="feature_declarations"
    )
    return {
        name: TPMFeatureDomain.from_dict(
            {
                "feature_name": name,
                **_mapping(declaration, field_name=f"feature_declarations.{name}"),
            }
        )
        for raw_name, declaration in declarations.items()
        for name in (str(raw_name),)
    }


def _fit_to_path(output_path: Path):
    source = _load_source()
    fit_case = _mapping(source.get("fit_case"), field_name="fit_case")
    return fit_tpm_artifact_from_rows(
        _rows(source),
        build_request=TPMArtifactBuildRequest(
            artifact_id=str(fit_case["artifact_id"]),
            dataset_reference=str(fit_case["dataset_reference"]),
            decision_features=tuple(str(name) for name in fit_case["decision_features"]),
            target_name=str(fit_case["target_name"]),
            event_target_name=str(fit_case["event_target_name"]),
            feature_domains=_feature_domains(source),
            provenance={
                "author": "OpenAI Codex",
                "origin": (
                    "Real current-SPFlow fit from the reviewed nonuniform "
                    "conditional-MIO physical rows"
                ),
                "source_fixture": str(SOURCE_PATH.relative_to(REPOSITORY_ROOT)),
                "source_fixture_sha256": _sha256(SOURCE_PATH),
                "staging_command": STAGING_COMMAND,
                "verification_command": VERIFICATION_COMMAND,
                "refresh_policy": (
                    "Stage exactly once in a fresh directory after an intentional "
                    "reviewed input change; do not retry or adapt after inspecting output."
                ),
                "retry_policy": "none",
                "legacy_evidence_paths": [],
            },
        ),
        output_path=output_path,
        fit_config=TPMFitConfig(
            training_random_seed=int(fit_case["training_random_seed"]),
            spn_payload_format="spflow-model-sidecar",
            learn_mspn_kwargs=_mapping(
                fit_case["learn_spn_options"], field_name="learn_spn_options"
            ),
            notes=("conditional-mio-embedding-v1", "offline-cpu-current-spflow"),
        ),
    )


def _fixture_payload(artifact) -> dict[str, object]:
    payload = artifact.to_dict()
    payload["created_at"] = FIXED_FIXTURE_TIMESTAMP
    payload["spn_payload"] = {
        **payload["spn_payload"],
        "locator": "sidecars/tpm_artifact_conditional_mio_v3.spn_payload.pkl",
    }
    provenance = dict(payload["provenance"])
    provenance.update(
        {
            "artifact_schema_version": artifact.schema_version,
            "backend_generation": artifact.backend_generation,
            "backend_api_version": artifact.backend_api_version,
            "sidecar_sha256": artifact.payload_hash,
            "python_version": sys.version.split()[0],
            "torch_version": artifact.fit_configuration[
                "determinism_configuration"
            ]["torch_version"],
            "torch_device": "cpu",
            "network_required": False,
            "commercial_solver_required": False,
        }
    )
    payload["provenance"] = provenance
    return {
        "fixture_name": "tpm_artifact_conditional_mio_v3",
        "fixture_status": "active-source-artifact",
        "purpose": (
            "Real current-SPFlow schema-v3 source artifact for feature 016 "
            "conditional numerator/denominator compilation."
        ),
        "spec_feature": "016-conditional-mio-embedding",
        "notes": [
            "The source rows are deliberately nonuniform in the retained decision x.",
            "This artifact is fitted evidence; final max/PWL pair fixtures are published only after mixed symbolic attachment support exists.",
            "Verification refits and compares semantic values; it does not require pickle-byte identity.",
        ],
        **payload,
    }


def _write_json_new(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    with path.open("xb") as output:
        output.write(serialized)
        output.flush()


def stage_fixtures(staging_directory: Path) -> dict[str, object]:
    """Create the reviewed source artifact and sidecar in one fresh directory."""

    destination = Path(staging_directory).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    staged_manifest = destination / ARTIFACT_PATH.name
    staged_sidecar = destination / "sidecars" / SIDECAR_PATH.name
    with TemporaryDirectory(prefix="oel-conditional-mio-stage-", dir="/tmp") as raw:
        artifact = _fit_to_path(Path(raw) / ARTIFACT_PATH.name)
        _, digest = write_tpm_sidecar(staged_sidecar, artifact.sidecar_path.read_bytes())
        if digest != artifact.payload_hash:
            raise AssertionError("staged sidecar digest differs from the fitted artifact")
        _write_json_new(staged_manifest, _fixture_payload(artifact))
    loaded = load_tpm_artifact(staged_manifest)
    return {
        "mode": "stage_fixtures",
        "staging_directory": str(destination),
        "manifest": str(staged_manifest),
        "sidecar": str(staged_sidecar),
        "manifest_sha256": _sha256(staged_manifest),
        "sidecar_sha256": _sha256(staged_sidecar),
        "artifact_id": loaded.artifact_id,
        "schema_version": loaded.schema_version,
        "backend_api_version": loaded.backend_api_version,
        "published_pairs": [],
    }


def _native_evidence(artifact) -> tuple[dict[str, object], ...]:
    import torch

    source = _load_source()
    feature_specs = artifact.feature_specs
    feature_by_name = {spec.feature_name: spec for spec in feature_specs}
    feature_indices = {
        spec.feature_name: index for index, spec in enumerate(feature_specs)
    }
    event_name = str(artifact.target_definition["event_target_name"])
    fit_case = _mapping(source["fit_case"], field_name="fit_case")
    runtime = load_spflow_payload(artifact)
    if runtime is None or runtime.get("query_strategy") != "spflow":
        raise RuntimeError("fixture verification requires a real current-SPFlow sidecar")
    model = runtime.get("model")
    if model is None:
        raise RuntimeError("current-SPFlow sidecar does not contain a fitted model")
    evidence = []
    for raw_case in source["representative_assignments"]:
        case = _mapping(raw_case, field_name="representative_assignment")
        assignments = _mapping(case["values"], field_name="values")
        denominator_input = torch.full(
            (1, len(feature_specs)), torch.nan, dtype=torch.float64, device="cpu"
        )
        for name, value in assignments.items():
            denominator_input[0, feature_indices[name]] = feature_by_name[
                name
            ].normalize_value(value)
        denominator = reduce_spflow_log_likelihood(
            model.log_likelihood(denominator_input)
        )
        numerator_input = denominator_input.clone()
        numerator_input[0, feature_indices[event_name]] = feature_by_name[
            event_name
        ].normalize_value(fit_case["event_value"])
        numerator = reduce_spflow_log_likelihood(model.log_likelihood(numerator_input))
        conditional_log_risk = numerator - denominator
        evidence.append(
            {
                "case_name": case["case_name"],
                "assignments": assignments,
                "numerator_log": numerator,
                "denominator_log": denominator,
                "conditional_log_risk": conditional_log_risk,
                "conditional_probability": math.exp(conditional_log_risk),
                "event_value": fit_case["event_value"],
            }
        )
    return tuple(evidence)


def _semantic_projection(artifact) -> dict[str, object]:
    return {
        "artifact_id": artifact.artifact_id,
        "schema_version": artifact.schema_version,
        "backend_generation": artifact.backend_generation,
        "backend_api_version": artifact.backend_api_version,
        "feature_schema": [
            spec.to_dict(schema_version="v3") for spec in artifact.feature_specs
        ],
        "fit_options": dict(artifact.fit_configuration["learn_mspn_kwargs"]),
        "fit_summary": dict(artifact.fit_configuration["fit_summary"]),
        "native_evidence": _native_evidence(artifact),
    }


def verify_fixtures() -> dict[str, object]:
    """Verify committed source evidence without rewriting or repairing it."""

    source_before = SOURCE_PATH.read_bytes()
    manifest_before = ARTIFACT_PATH.read_bytes()
    sidecar_before = SIDECAR_PATH.read_bytes()
    committed = load_tpm_artifact(ARTIFACT_PATH)
    if committed.provenance.get("source_fixture_sha256") != _sha256(SOURCE_PATH):
        raise AssertionError("committed artifact source digest is stale")
    committed_semantics = _semantic_projection(committed)
    with TemporaryDirectory(prefix="oel-conditional-mio-verify-", dir="/tmp") as raw:
        fresh = _fit_to_path(Path(raw) / ARTIFACT_PATH.name)
        fresh_semantics = _semantic_projection(fresh)
    _assert_nested_close(
        committed_semantics,
        fresh_semantics,
        path="conditional_mio_source_artifact",
        tolerance=1e-9,
    )
    if SOURCE_PATH.read_bytes() != source_before:
        raise AssertionError("source fixture changed during verification")
    if ARTIFACT_PATH.read_bytes() != manifest_before:
        raise AssertionError("artifact manifest changed during verification")
    if SIDECAR_PATH.read_bytes() != sidecar_before:
        raise AssertionError("artifact sidecar changed during verification")
    capabilities = detect_spflow_backend_capabilities()
    return {
        "mode": "verify_fixtures",
        "artifact_id": committed.artifact_id,
        "manifest_sha256": _sha256(ARTIFACT_PATH),
        "sidecar_sha256": _sha256(SIDECAR_PATH),
        "source_sha256": _sha256(SOURCE_PATH),
        "backend_generation": committed.backend_generation,
        "backend_api_version": committed.backend_api_version,
        "adapter_name": capabilities["backend_adapter_name"],
        "semantic_refit_verified": True,
        "committed_bytes_unchanged": True,
        "cpu_only": True,
    }


def _assert_nested_close(
    actual: object,
    expected: object,
    *,
    path: str,
    tolerance: float,
) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        if actual.keys() != expected.keys():
            raise AssertionError(f"{path} keys differ")
        for key in actual:
            _assert_nested_close(
                actual[key],
                expected[key],
                path=f"{path}.{key}",
                tolerance=tolerance,
            )
        return
    if (
        isinstance(actual, Sequence)
        and isinstance(expected, Sequence)
        and not isinstance(actual, str | bytes)
        and not isinstance(expected, str | bytes)
    ):
        if len(actual) != len(expected):
            raise AssertionError(f"{path} lengths differ")
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            _assert_nested_close(
                left,
                right,
                path=f"{path}[{index}]",
                tolerance=tolerance,
            )
        return
    if (
        isinstance(actual, Real)
        and not isinstance(actual, bool)
        and isinstance(expected, Real)
        and not isinstance(expected, bool)
    ):
        if not math.isclose(float(actual), float(expected), abs_tol=tolerance, rel_tol=0.0):
            raise AssertionError(f"{path} differs: {actual!r} != {expected!r}")
        return
    if actual != expected:
        raise AssertionError(f"{path} differs: {actual!r} != {expected!r}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage or verify conditional-MIO current-SPFlow fixtures."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--stage-fixtures",
        type=Path,
        metavar="FRESH_DIRECTORY",
        help="create only the source artifact and sidecar in a new directory",
    )
    mode.add_argument(
        "--verify-fixtures",
        action="store_true",
        help="read and refit committed source evidence without rewriting it",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = (
        stage_fixtures(args.stage_fixtures)
        if args.stage_fixtures is not None
        else verify_fixtures()
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
