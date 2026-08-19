from __future__ import annotations

import argparse
import json
import math
import os
import tempfile
from collections.abc import Mapping, Sequence
from numbers import Real
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from open_energy_lab.tpm import (
    TPMArtifactBuildRequest,
    TPMFitConfig,
    TPMQueryRequest,
    compile_spflow_model_to_mio,
    detect_spflow_backend_capabilities,
    evaluate_compiled_spflow_probability,
    fit_tpm_artifact_from_rows,
    load_tpm_artifact,
    query_tpm_artifact,
)
from open_energy_lab.tpm.optional_spflow import load_spflow_payload


EXAMPLE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_ROOT.parent.parent
OUTPUT_ROOT = REPO_ROOT / "tmp" / "open-energy-lab-pipeline-real-backends"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "tpm"
PRODUCTION_FIXTURE_PATH = FIXTURE_ROOT / "tpm_artifact_spflow_v1.json"
PRODUCTION_SIDECAR_STAGE_PATH = (
    FIXTURE_ROOT / "sidecars" / "tpm_artifact_spflow_v1.json"
)
PRODUCTION_SIDECAR_PATH = (
    FIXTURE_ROOT / "sidecars" / "tpm_artifact_spflow_v1.spn_payload.pkl"
)

CANONICAL_SEED = 13
CANONICAL_BREAKPOINT_COUNT = 5
MIO_EPSILON = 1e-6
REPEATABILITY_TOLERANCE = 1e-9
PARITY_TOLERANCE = 1e-6
FIXED_FIXTURE_TIMESTAMP = "2026-08-19T00:00:00Z"
GENERATION_COMMAND = (
    "uv run python examples/tpm_planning/run_generic_rows_pipeline.py "
    "--regenerate-fixture"
)
VERIFICATION_COMMAND = (
    "uv run python examples/tpm_planning/run_generic_rows_pipeline.py "
    "--verify-fixture"
)
LEGACY_EVIDENCE_PATHS = (
    "legacy/old_tpm/src_py/tpm/data/datahandler.py",
    "legacy/old_tpm/src_py/tpm/data/features/feature.py",
    "legacy/old_tpm/src_py/tpm/spn/main.py",
    "legacy/old_tpm/src_py/tpm/spn/encoding.py",
    "legacy/old_tpm/src_py/utils/densities.py",
)


def _training_rows() -> tuple[dict[str, object], ...]:
    """Return the deterministic source rows used by the production fixture."""

    rows: list[dict[str, object]] = []
    design_classes = ("compact", "balanced", "resilient")
    for index in range(36):
        battery_capacity_kwh = 2.0 + 2.0 * (index % 6)
        solar_enabled = index % 2
        design_class = design_classes[index % len(design_classes)]
        ambient_temperature_c = 20.0 + 2.0 * (index % 4)
        shortfall = max(
            0.0,
            0.18
            - 0.008 * battery_capacity_kwh
            - 0.04 * solar_enabled
            + (0.025 if design_class == "compact" else 0.0)
            + 0.002 * (ambient_temperature_c - 20.0),
        )
        rows.append(
            {
                "battery_capacity_kwh": battery_capacity_kwh,
                "solar_enabled": solar_enabled,
                "design_class": design_class,
                "ambient_temperature_c": ambient_temperature_c,
                "shortfall": shortfall,
            }
        )
    return tuple(rows)


def _build_request() -> TPMArtifactBuildRequest:
    return TPMArtifactBuildRequest(
        artifact_id="tpm-artifact:generic-rows-current-spflow-v1",
        dataset_reference="generic-rows-current-spflow-v1",
        decision_features=(
            "battery_capacity_kwh",
            "solar_enabled",
            "design_class",
        ),
        target_name="shortfall",
        event_target_name="shortfall_event",
        target_threshold=0.08,
        numeric_tolerance=REPEATABILITY_TOLERANCE,
        provenance={
            "author": "OpenAI Codex",
            "origin": (
                "Deterministic generic-row fixture fitted through the required "
                "current SPFlow 1.1 backend"
            ),
            "source_dataset": (
                "examples/tpm_planning/run_generic_rows_pipeline.py::_training_rows"
            ),
            "source_dataset_configuration": {
                "row_count": 36,
                "battery_cycle": [2.0, 4.0, 6.0, 8.0, 10.0, 12.0],
                "solar_cycle": [0, 1],
                "design_class_cycle": ["compact", "balanced", "resilient"],
                "ambient_temperature_cycle_c": [20.0, 22.0, 24.0, 26.0],
                "target_formula_version": "generic-shortfall-v1",
            },
            "generation_command": GENERATION_COMMAND,
            "verification_command": VERIFICATION_COMMAND,
            "random_seed": CANONICAL_SEED,
            "refresh_policy": (
                "Regenerate only when the source rows, fit configuration, SPFlow "
                "API, compiler contract, or schema-v2 artifact contract changes."
            ),
            "production_model": True,
            "legacy_evidence_paths": list(LEGACY_EVIDENCE_PATHS),
        },
    )


def _fit_config() -> TPMFitConfig:
    return TPMFitConfig(
        training_random_seed=CANONICAL_SEED,
        spn_payload_format="spflow-model-sidecar",
        learn_mspn_kwargs={
            "threshold": 0.3,
            "min_features_slice": 2,
            "min_instances_slice": 100,
            "n_clusters": 2,
        },
        notes=(
            "required-current-spflow-production-fixture",
            "canonical-seed-13",
            "deterministic-semantic-verification-not-pickle-byte-equality",
        ),
        execution_mode="production",
    )


def _query_request() -> TPMQueryRequest:
    return TPMQueryRequest(
        decision_assignments={
            "battery_capacity_kwh": 4.0,
            "solar_enabled": 1,
            "design_class": "balanced",
        },
        marginalized_features=("ambient_temperature_c",),
        target_name="shortfall",
        execution_mode="production",
    )


def _fit_to_path(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return fit_tpm_artifact_from_rows(
        _training_rows(),
        build_request=_build_request(),
        output_path=output_path,
        fit_config=_fit_config(),
    )


def _load_and_compile(artifact) -> tuple[dict[str, object], dict[str, object]]:
    runtime_payload = load_spflow_payload(artifact)
    if runtime_payload is None or runtime_payload.get("model") is None:
        raise RuntimeError("production fixture must contain a current-SPFlow model")
    compiled = compile_spflow_model_to_mio(
        runtime_payload["model"],
        feature_schema=artifact.feature_specs,
        breakpoint_count=CANONICAL_BREAKPOINT_COUNT,
        mio_epsilon=MIO_EPSILON,
    )
    return runtime_payload, compiled


def _compiler_parity(
    *,
    model: object,
    compiled: Mapping[str, object],
) -> dict[str, object]:
    import torch

    breakpoints = tuple(
        float(value)
        for value in compiled["breakpoint_policy"]["breakpoints"]  # type: ignore[index]
    )
    evidence_rows = tuple(
        (
            breakpoint,
            float(index % 2),
            float(index % 3),
            breakpoint,
            breakpoint,
            float(index % 2),
        )
        for index, breakpoint in enumerate(breakpoints)
    )
    evidence = torch.tensor(evidence_rows, dtype=torch.float64, device="cpu")
    with torch.no_grad():
        native = tuple(
            float(value)
            for value in torch.exp(model.log_likelihood(evidence)).reshape(-1).tolist()
        )
    approximate = tuple(
        evaluate_compiled_spflow_probability(
            compiled,
            normalized_evidence=row,
        )
        for row in evidence_rows
    )
    maximum_absolute_error = max(
        abs(native_value - compiled_value)
        for native_value, compiled_value in zip(native, approximate, strict=True)
    )
    if maximum_absolute_error > PARITY_TOLERANCE:
        raise RuntimeError(
            "current-SPFlow compiler parity exceeded tolerance: "
            f"{maximum_absolute_error} > {PARITY_TOLERANCE}"
        )
    return {
        "evidence_rows": [list(row) for row in evidence_rows],
        "native_probabilities": list(native),
        "compiled_probabilities": list(approximate),
        "maximum_absolute_error": maximum_absolute_error,
        "tolerance": PARITY_TOLERANCE,
    }


def _fixture_payload(
    *,
    artifact: object,
    compiled: Mapping[str, object],
    parity: Mapping[str, object],
) -> dict[str, object]:
    artifact_payload = artifact.to_dict()
    artifact_payload["created_at"] = FIXED_FIXTURE_TIMESTAMP
    artifact_payload["spn_payload"] = {
        **artifact_payload["spn_payload"],
        "locator": "sidecars/tpm_artifact_spflow_v1.spn_payload.pkl",
    }
    approximation_metadata = dict(artifact_payload["approximation_metadata"])
    compiler_policy = dict(compiled["breakpoint_policy"])
    approximation_metadata.update(
        {
            "compiler_version": compiled["compiler_version"],
            "backend_compiler_version": compiled["backend_compiler_version"],
            "compiler_schema_version": compiled["schema_version"],
            "compiler_status": "production-validated",
            "compiler_sum_encoding_mode": compiled["sum_encoding_mode"],
            "supported_spflow_module_types": list(
                compiled["supported_spflow_module_types"]
            ),
            "leaf_encoding_mode": compiled["leaf_encoding_mode"],
            "breakpoint_policy": {
                **dict(approximation_metadata["breakpoint_policy"]),
                **compiler_policy,
                "piecewise_breakpoint_count": compiler_policy["breakpoint_count"],
            },
            "mio_epsilon": compiled["mio_epsilon"],
            "native_probability_tolerance": PARITY_TOLERANCE,
            "repeatability_tolerance": REPEATABILITY_TOLERANCE,
            "compiled_graph_summary": {
                "root_id": compiled["root_id"],
                "node_count": len(compiled["nodes"]),
                "node_types": [node["type"] for node in compiled["nodes"]],
                "maximum_absolute_probability_error": parity[
                    "maximum_absolute_error"
                ],
            },
        }
    )
    artifact_payload["approximation_metadata"] = approximation_metadata
    provenance = dict(artifact_payload["provenance"])
    provenance.update(
        {
            "backend_generation": artifact_payload["backend_generation"],
            "backend_api_version": artifact_payload["backend_api_version"],
            "compiler_version": compiled["compiler_version"],
            "sidecar_sha256": artifact_payload["payload_hash"],
            "fixture_manifest_path": (
                "tests/fixtures/tpm/tpm_artifact_spflow_v1.json"
            ),
            "fixture_sidecar_path": (
                "tests/fixtures/tpm/sidecars/"
                "tpm_artifact_spflow_v1.spn_payload.pkl"
            ),
        }
    )
    artifact_payload["provenance"] = provenance
    return {
        "fixture_name": "tpm_artifact_spflow_v1",
        "fixture_status": "active",
        "purpose": (
            "Reproducibly fitted schema-v2 production artifact for required "
            "current-SPFlow fit, reload, query, compiler, and sidecar-integrity review."
        ),
        "spec_feature": "009-tpm-planning",
        "provenance": provenance,
        "planned_contracts": [
            "specs/009-tpm-planning/contracts/tpm-artifact-contract.md",
            "specs/009-tpm-planning/contracts/validation-contract.md",
        ],
        "notes": [
            "This fixture contains a real SPFlow 1.1 model and uses production mode.",
            (
                "Regeneration compares deterministic structure, parameters, "
                "likelihood, query, and compiler semantics rather than requiring "
                "pickle-byte equality."
            ),
            (
                "The separate tpm_artifact_v2.json fixture remains explicit "
                "empirical fixture_replay evidence."
            ),
        ],
        **artifact_payload,
    }


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


def regenerate_fixture() -> dict[str, object]:
    """Regenerate the committed production manifest and current-SPFlow sidecar."""

    started = perf_counter()
    artifact = _fit_to_path(PRODUCTION_SIDECAR_STAGE_PATH)
    runtime_payload, compiled = _load_and_compile(artifact)
    parity = _compiler_parity(model=runtime_payload["model"], compiled=compiled)
    payload = _fixture_payload(
        artifact=artifact,
        compiled=compiled,
        parity=parity,
    )
    _write_json_atomic(PRODUCTION_FIXTURE_PATH, payload)
    PRODUCTION_SIDECAR_STAGE_PATH.unlink(missing_ok=True)
    loaded = load_tpm_artifact(PRODUCTION_FIXTURE_PATH)
    elapsed = perf_counter() - started
    return {
        "mode": "regenerate_fixture",
        "manifest_path": str(PRODUCTION_FIXTURE_PATH.relative_to(REPO_ROOT)),
        "sidecar_path": str(PRODUCTION_SIDECAR_PATH.relative_to(REPO_ROOT)),
        "payload_hash": loaded.payload_hash,
        "compiler_version": compiled["compiler_version"],
        "breakpoint_policy": compiled["breakpoint_policy"],
        "mio_epsilon": compiled["mio_epsilon"],
        "maximum_absolute_probability_error": parity["maximum_absolute_error"],
        "elapsed_seconds": elapsed,
    }


def _assert_nested_close(
    actual: object,
    expected: object,
    *,
    path: str,
) -> None:
    if isinstance(actual, Mapping) and isinstance(expected, Mapping):
        if actual.keys() != expected.keys():
            raise AssertionError(f"{path} keys differ")
        for key in actual:
            _assert_nested_close(
                actual[key],
                expected[key],
                path=f"{path}.{key}",
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
            )
        return
    if isinstance(actual, Real) and isinstance(expected, Real):
        if not math.isclose(
            float(actual),
            float(expected),
            abs_tol=REPEATABILITY_TOLERANCE,
            rel_tol=0.0,
        ):
            raise AssertionError(f"{path} differs: {actual!r} != {expected!r}")
        return
    if actual != expected:
        raise AssertionError(f"{path} differs: {actual!r} != {expected!r}")


def verify_fixture() -> dict[str, object]:
    """Refit in a temporary directory and compare deterministic semantics."""

    started = perf_counter()
    committed = load_tpm_artifact(PRODUCTION_FIXTURE_PATH)
    committed_runtime, committed_compiled = _load_and_compile(committed)
    committed_query = query_tpm_artifact(committed, _query_request())
    committed_parity = _compiler_parity(
        model=committed_runtime["model"],
        compiled=committed_compiled,
    )

    with TemporaryDirectory(prefix="open-energy-lab-tpm-fixture-", dir="/tmp") as directory:
        fresh_path = Path(directory) / "tpm_artifact_spflow_v1.json"
        fresh = _fit_to_path(fresh_path)
        fresh_runtime, fresh_compiled = _load_and_compile(fresh)
        fresh_query = query_tpm_artifact(fresh, _query_request())
        fresh_parity = _compiler_parity(
            model=fresh_runtime["model"],
            compiled=fresh_compiled,
        )

    _assert_nested_close(
        committed.fit_configuration["fit_summary"],
        fresh.fit_configuration["fit_summary"],
        path="fit_summary",
    )
    _assert_nested_close(
        committed_compiled,
        fresh_compiled,
        path="compiled",
    )
    _assert_nested_close(
        committed_query,
        fresh_query,
        path="query",
    )
    _assert_nested_close(
        committed_parity,
        fresh_parity,
        path="parity",
    )

    metadata = committed.approximation_metadata
    if metadata.get("compiler_version") != committed_compiled["compiler_version"]:
        raise AssertionError("manifest compiler_version does not match compiled sidecar")
    if metadata.get("mio_epsilon") != MIO_EPSILON:
        raise AssertionError("manifest mio_epsilon is not canonical")
    if metadata.get("compiler_status") != "production-validated":
        raise AssertionError("manifest compiler status is not production-validated")

    elapsed = perf_counter() - started
    return {
        "mode": "verify_fixture",
        "manifest_path": str(PRODUCTION_FIXTURE_PATH.relative_to(REPO_ROOT)),
        "sidecar_path": str(PRODUCTION_SIDECAR_PATH.relative_to(REPO_ROOT)),
        "payload_hash": committed.payload_hash,
        "fit_summary_repeatable": True,
        "compiled_graph_repeatable": True,
        "query_repeatable": True,
        "maximum_absolute_probability_error": committed_parity[
            "maximum_absolute_error"
        ],
        "elapsed_seconds": elapsed,
    }


def run_example() -> dict[str, object]:
    """Fit, reload, query, and compile one generated production artifact."""

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    artifact_path = OUTPUT_ROOT / "generic_rows_tpm_artifact.json"
    summary_path = OUTPUT_ROOT / "generic_rows_pipeline_summary.json"
    artifact = _fit_to_path(artifact_path)
    reloaded = load_tpm_artifact(artifact_path)
    runtime_payload, compiled = _load_and_compile(reloaded)
    parity = _compiler_parity(model=runtime_payload["model"], compiled=compiled)
    query_result = query_tpm_artifact(reloaded, _query_request())
    summary = {
        "generated_by": str(Path(__file__).relative_to(REPO_ROOT)),
        "artifact_path": str(artifact_path.relative_to(REPO_ROOT)),
        "spflow_capabilities": detect_spflow_backend_capabilities(),
        "used_real_spflow_backend": True,
        "artifact_id": artifact.artifact_id,
        "schema_version": artifact.schema_version,
        "execution_mode": artifact.execution_mode,
        "backend_generation": artifact.backend_generation,
        "backend_api_version": artifact.backend_api_version,
        "payload_hash": artifact.payload_hash,
        "compiler_version": compiled["compiler_version"],
        "breakpoint_policy": compiled["breakpoint_policy"],
        "mio_epsilon": compiled["mio_epsilon"],
        "maximum_absolute_probability_error": parity[
            "maximum_absolute_error"
        ],
        "query_result": query_result,
    }
    _write_json_atomic(summary_path, summary)
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or regenerate the required current-SPFlow generic-row pipeline."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--regenerate-fixture",
        action="store_true",
        help="Replace the committed production manifest and sidecar.",
    )
    mode.add_argument(
        "--verify-fixture",
        action="store_true",
        help="Refit offline and compare deterministic semantic evidence.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.regenerate_fixture:
        result = regenerate_fixture()
    elif args.verify_fixture:
        result = verify_fixture()
    else:
        result = run_example()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
