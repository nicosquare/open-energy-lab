"""Regenerate or verify the real-SPFlow declared-domain v3 fixture offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from tempfile import TemporaryDirectory

from tpm import (
    TPMArtifactBuildRequest,
    TPMFeatureDomain,
    TPMFitConfig,
    TPMQueryRequest,
    detect_spflow_backend_capabilities,
    fit_tpm_artifact_from_rows,
    load_tpm_artifact,
    query_tpm_artifact,
)
from tpm.artifact import write_tpm_sidecar


EXAMPLE_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = EXAMPLE_DIRECTORY.parent.parent
FIXTURE_DIRECTORY = REPOSITORY_ROOT / "tests" / "fixtures" / "tpm"
INPUT_FIXTURE_PATH = FIXTURE_DIRECTORY / "declared_feature_domains_v1.json"
ARTIFACT_FIXTURE_PATH = FIXTURE_DIRECTORY / "tpm_artifact_domains_v3.json"
SIDECAR_FIXTURE_PATH = (
    FIXTURE_DIRECTORY / "sidecars" / "tpm_artifact_domains_v3.spn_payload.pkl"
)
FIXED_FIXTURE_TIMESTAMP = "2026-08-27T00:00:00Z"
GENERATION_COMMAND = (
    "uv run --locked --no-sync python "
    "examples/tpm_planning/run_declared_domains_pipeline.py --regenerate-fixture"
)
VERIFICATION_COMMAND = (
    "uv run --locked --no-sync python "
    "examples/tpm_planning/run_declared_domains_pipeline.py --verify-fixture"
)


def _load_input() -> dict[str, object]:
    payload = json.loads(INPUT_FIXTURE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("declared-domain input fixture must be a JSON object")
    return payload


def _feature_domains(payload: Mapping[str, object]) -> dict[str, TPMFeatureDomain]:
    declarations = payload.get("feature_declarations")
    if not isinstance(declarations, Mapping):
        raise TypeError("input fixture must contain feature_declarations")
    return {
        str(feature_name): TPMFeatureDomain.from_dict(
            {
                "feature_name": str(feature_name),
                **_mapping(declaration, field_name=str(feature_name)),
            }
        )
        for feature_name, declaration in declarations.items()
    }


def _training_rows(payload: Mapping[str, object]) -> tuple[dict[str, object], ...]:
    rows = payload.get("physical_training_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("input fixture must contain physical_training_rows")
    if any(not isinstance(row, Mapping) for row in rows):
        raise TypeError("physical_training_rows must contain only mappings")
    return tuple(dict(row) for row in rows)


def _fit_to_path(output_path: Path):
    payload = _load_input()
    fit_case = _mapping(payload.get("fit_case"), field_name="fit_case")
    return fit_tpm_artifact_from_rows(
        _training_rows(payload),
        build_request=TPMArtifactBuildRequest(
            artifact_id=str(fit_case["artifact_id"]),
            dataset_reference=str(fit_case["dataset_reference"]),
            decision_features=tuple(str(name) for name in fit_case["decision_features"]),
            target_name=str(fit_case["target_name"]),
            event_target_name=str(fit_case["event_target_name"]),
            target_threshold=float(fit_case["target_threshold"]),
            feature_domains=_feature_domains(payload),
            provenance={
                "author": "OpenAI Codex",
                "origin": (
                    "Real current-SPFlow fit from the reviewable U-Bounds "
                    "physical input fixture"
                ),
                "source_fixture": str(INPUT_FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
                "source_fixture_sha256": _sha256(INPUT_FIXTURE_PATH),
                "generation_command": GENERATION_COMMAND,
                "verification_command": VERIFICATION_COMMAND,
                "refresh_policy": (
                    "Regenerate only after intentional changes to declared-domain "
                    "semantics, physical rows, the fit contract, or required backend."
                ),
                "legacy_evidence_paths": [],
            },
        ),
        output_path=output_path,
        fit_config=TPMFitConfig(
            training_random_seed=int(fit_case["training_random_seed"]),
            spn_payload_format="spflow-model-sidecar",
            notes=(
                "declared-feature-domains-v1",
                "offline-cpu-current-spflow",
            ),
        ),
    )


def _semantic_evidence(artifact) -> dict[str, object]:
    payload = _load_input()
    tolerances = _mapping(
        payload.get("assertion_tolerances"),
        field_name="assertion_tolerances",
    )
    feature_semantics = {
        spec.feature_name: {
            "mathematical_domain": spec.mathematical_domain.to_dict(),
            "training_support": spec.training_support.to_dict(),
            "normalization": spec.normalization.to_dict(),
        }
        for spec in artifact.feature_specs
    }
    feature_by_name = {
        spec.feature_name: spec for spec in artifact.feature_specs
    }
    probe_results: list[dict[str, object]] = []
    for raw_probe in payload["query_probes"]:
        probe = _mapping(raw_probe, field_name="query_probe")
        feature_name = str(probe["feature_name"])
        physical_value = probe["physical_value"]
        spec = feature_by_name[feature_name]
        try:
            model_coordinate = spec.normalize_value(physical_value)
        except (TypeError, ValueError):
            membership = False
            model_coordinate = None
        else:
            membership = True
        expected_membership = bool(probe["expected_domain_membership"])
        if membership != expected_membership:
            raise AssertionError(
                f"probe {probe['probe_name']!r} membership differs from declaration"
            )
        if "expected_model_coordinate" in probe and not math.isclose(
            float(model_coordinate),
            float(probe["expected_model_coordinate"]),
            abs_tol=float(tolerances["model_coordinate"]),
            rel_tol=0.0,
        ):
            raise AssertionError(
                f"probe {probe['probe_name']!r} model coordinate differs"
            )
        probe_results.append(
            {
                "probe_name": probe["probe_name"],
                "feature_name": feature_name,
                "physical_value": physical_value,
                "domain_membership": membership,
                "model_coordinate": model_coordinate,
            }
        )

    query_cases = (
        {
            "case_name": "lower-endpoint-outside-training-support",
            "x": 40.0,
            "activation": "off",
            "service_tier": "economy",
        },
        {
            "case_name": "upper-endpoint-outside-training-support",
            "x": 160.0,
            "activation": "on",
            "service_tier": "standard",
        },
        {
            "case_name": "declared-unobserved-category",
            "x": 100.0,
            "activation": "on",
            "service_tier": "priority",
        },
    )
    native_queries: list[dict[str, object]] = []
    for query_case in query_cases:
        assignments = {
            key: value for key, value in query_case.items() if key != "case_name"
        }
        result = query_tpm_artifact(
            artifact,
            TPMQueryRequest(decision_assignments=assignments),
        )
        native_queries.append(
            {
                "case_name": query_case["case_name"],
                "decision_assignments": assignments,
                "source": result["source"],
                "conditional_probability": result["conditional_probability"],
            }
        )

    return {
        "source_fixture_sha256": _sha256(INPUT_FIXTURE_PATH),
        "domain_membership_policy": tolerances["domain_membership"],
        "model_coordinate_tolerance": tolerances["model_coordinate"],
        "native_probability_tolerance": tolerances["native_probability"],
        "feature_semantics": feature_semantics,
        "probe_results": probe_results,
        "native_queries": native_queries,
    }


def _fixture_payload(artifact, evidence: Mapping[str, object]) -> dict[str, object]:
    artifact_payload = artifact.to_dict()
    artifact_payload["created_at"] = FIXED_FIXTURE_TIMESTAMP
    artifact_payload["spn_payload"] = {
        **artifact_payload["spn_payload"],
        "locator": "sidecars/tpm_artifact_domains_v3.spn_payload.pkl",
    }
    capabilities = detect_spflow_backend_capabilities()
    provenance = dict(artifact_payload["provenance"])
    provenance.update(
        {
            "random_seed": artifact.fit_configuration["training_random_seed"],
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
    artifact_payload["provenance"] = provenance
    return {
        "fixture_name": "tpm_artifact_domains_v3",
        "fixture_status": "active",
        "purpose": (
            "Real current-SPFlow schema-v3 evidence for declared mathematical "
            "domains, physical training support, normalization, reload, and queries."
        ),
        "spec_feature": "014-declared-feature-domains",
        "provenance": provenance,
        "planned_contracts": [
            "specs/014-declared-feature-domains/contracts/feature-domain-contract.md",
            (
                "specs/014-declared-feature-domains/contracts/"
                "training-normalization-query-contract.md"
            ),
            "specs/014-declared-feature-domains/contracts/validation-contract.md",
        ],
        "notes": [
            (
                "The source fixture contains reviewable physical inputs; this "
                "fixture contains fitted output."
            ),
            (
                "Domain membership is exact; recorded tolerances apply only to "
                "coordinate and probability comparisons."
            ),
            "Verification compares semantic and numeric evidence, not pickle-byte identity.",
        ],
        "declared_domain_evidence": dict(evidence),
        **artifact_payload,
    }


def regenerate_fixture() -> dict[str, object]:
    """Replace the committed schema-v3 manifest and real-SPFlow sidecar."""

    with TemporaryDirectory(prefix="oel-declared-domains-", dir="/tmp") as directory:
        artifact = _fit_to_path(Path(directory) / "tpm_artifact_domains_v3.json")
        evidence = _semantic_evidence(artifact)
        sidecar_bytes = artifact.sidecar_path.read_bytes()
        _, digest = write_tpm_sidecar(SIDECAR_FIXTURE_PATH, sidecar_bytes)
        if digest != artifact.payload_hash:
            raise AssertionError("copied sidecar digest differs from fitted artifact")
        _write_json_atomic(
            ARTIFACT_FIXTURE_PATH,
            _fixture_payload(artifact, evidence),
        )
    loaded = load_tpm_artifact(ARTIFACT_FIXTURE_PATH)
    return {
        "mode": "regenerate_fixture",
        "manifest_path": str(ARTIFACT_FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
        "sidecar_path": str(SIDECAR_FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
        "payload_hash": loaded.payload_hash,
        "schema_version": loaded.schema_version,
        "backend_api_version": loaded.backend_api_version,
    }


def verify_fixture() -> dict[str, object]:
    """Refit offline and compare persisted declared-domain semantic evidence."""

    committed_payload = json.loads(ARTIFACT_FIXTURE_PATH.read_text(encoding="utf-8"))
    committed = load_tpm_artifact(ARTIFACT_FIXTURE_PATH)
    committed_evidence = committed_payload["declared_domain_evidence"]
    recomputed_committed_evidence = _semantic_evidence(committed)
    _assert_nested_close(
        committed_evidence,
        recomputed_committed_evidence,
        path="committed_evidence",
        tolerance=float(committed_evidence["native_probability_tolerance"]),
    )

    with TemporaryDirectory(prefix="oel-declared-domains-verify-", dir="/tmp") as directory:
        fresh = _fit_to_path(Path(directory) / "tpm_artifact_domains_v3.json")
        fresh_evidence = _semantic_evidence(fresh)

    _assert_nested_close(
        committed_evidence,
        fresh_evidence,
        path="fresh_evidence",
        tolerance=float(committed_evidence["native_probability_tolerance"]),
    )
    _assert_nested_close(
        committed.fit_configuration["fit_summary"],
        fresh.fit_configuration["fit_summary"],
        path="fit_summary",
        tolerance=float(committed_evidence["native_probability_tolerance"]),
    )
    return {
        "mode": "verify_fixture",
        "manifest_path": str(ARTIFACT_FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
        "sidecar_path": str(SIDECAR_FIXTURE_PATH.relative_to(REPOSITORY_ROOT)),
        "payload_hash": committed.payload_hash,
        "semantic_evidence_repeatable": True,
        "fit_summary_repeatable": True,
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
        for index, (actual_item, expected_item) in enumerate(
            zip(actual, expected, strict=True)
        ):
            _assert_nested_close(
                actual_item,
                expected_item,
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
        if not math.isclose(
            float(actual),
            float(expected),
            abs_tol=tolerance,
            rel_tol=0.0,
        ):
            raise AssertionError(f"{path} differs: {actual!r} != {expected!r}")
        return
    if actual != expected:
        raise AssertionError(f"{path} differs: {actual!r} != {expected!r}")


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping")
    return {str(key): inner for key, inner in value.items()}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".stage",
        delete=False,
    ) as staging_file:
        staging_path = Path(staging_file.name)
        staging_file.write(serialized)
    os.replace(staging_path, path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate or verify real declared-domain SPFlow evidence."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--regenerate-fixture", action="store_true")
    mode.add_argument("--verify-fixture", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = regenerate_fixture() if args.regenerate_fixture else verify_fixture()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
