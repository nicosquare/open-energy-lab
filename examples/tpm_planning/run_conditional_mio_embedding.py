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
    TPMBinaryDecisionMapping,
    TPMCategoricalDecisionMapping,
    TPMContinuousDecisionMapping,
    TPMFeatureDomain,
    TPMFitConfig,
    TPMConditionalCompilationRequest,
    TPMConditionalEncodingPolicy,
    TPMConditionalNumericalPolicy,
    attach_conditional_mio_pair,
    build_compiler_fidelity_evidence,
    build_embedding_parity_evidence,
    canonical_conditional_json_bytes,
    compile_conditional_mio_pair,
    evaluate_conditional_mio_pair,
    evaluate_native_conditional_pair,
    detect_spflow_backend_capabilities,
    fit_tpm_artifact_from_rows,
    inspect_conditional_mio_attachment,
    load_tpm_artifact,
    load_conditional_pair,
    publish_conditional_pair,
)
from open_energy_lab.tpm.artifact import write_tpm_sidecar
from open_energy_lab.tpm.optional_spflow import load_spflow_payload
from open_energy_lab.tpm.query import reduce_spflow_log_likelihood
from open_energy_lab.tpm.piecewise import (
    PiecewiseBreakpointPolicy,
    build_logsumexp_piecewise_spec,
)


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
MAX_PAIR_PATH = FIXTURE_DIRECTORY / "conditional_pair_max_v1.json"
PWL_PAIR_PATH = FIXTURE_DIRECTORY / "conditional_pair_pwl_v1.json"
EVIDENCE_PATH = FIXTURE_DIRECTORY / "conditional_mio_evidence_v1.json"
FIXED_FIXTURE_TIMESTAMP = "2026-08-28T00:00:00Z"
STAGING_COMMAND = (
    "uv run --offline --locked --no-sync python "
    "examples/tpm_planning/run_conditional_mio_embedding.py "
    "--stage-fixtures <fresh-directory>"
)
PAIR_STAGING_COMMAND = (
    "uv run --offline --locked --no-sync python "
    "examples/tpm_planning/run_conditional_mio_embedding.py "
    "--stage-pairs <fresh-directory>"
)
EVIDENCE_STAGING_COMMAND = (
    "uv run --offline --locked --no-sync python "
    "examples/tpm_planning/run_conditional_mio_embedding.py "
    "--stage-evidence <fresh-directory>"
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
            "This artifact is fitted evidence for the committed max and PWL conditional pair fixtures.",
            "Verification refits and compares semantic values; it does not require pickle-byte identity.",
        ],
        **payload,
    }


def _conditional_encoding(
    source: Mapping[str, object],
    *,
    policy_name: str,
) -> TPMConditionalEncodingPolicy:
    compilation = _mapping(
        source.get("conditional_compilation"),
        field_name="conditional_compilation",
    )
    leaf = _mapping(compilation.get("leaf_policy"), field_name="leaf_policy")
    policies = _mapping(compilation.get("sum_policies"), field_name="sum_policies")
    selected = _mapping(
        policies.get(policy_name), field_name=f"sum_policies.{policy_name}"
    )
    sum_configuration = {
        key: value
        for key, value in selected.items()
        if key not in {"mode", "approximation_label", "certification_label"}
    }
    mode = str(selected["mode"])
    if mode == "piecewise":
        breakpoint_policy = PiecewiseBreakpointPolicy.from_dict(
            _mapping(
                selected.get("breakpoint_policy"),
                field_name="breakpoint_policy",
            )
        )
        curves = build_logsumexp_piecewise_spec(
            max_terms=len(_rows(source)),
            breakpoint_policy=breakpoint_policy,
        )
        exp_floor = float(selected["exp_domain_floor"])
        exp_x = tuple(float(value) for value in curves["exp_x_points"])
        exp_y = tuple(float(value) for value in curves["exp_y_points"])
        sum_configuration.update(curves)
        if exp_floor < exp_x[0]:
            sum_configuration["exp_x_points"] = (exp_floor, *exp_x)
            sum_configuration["exp_y_points"] = (0.0, *exp_y)
        sum_configuration.pop("breakpoint_policy", None)
    return TPMConditionalEncodingPolicy(
        mode=mode,
        approximation_label=str(selected["approximation_label"]),
        certification_label=str(selected["certification_label"]),
        leaf_configuration=leaf,
        sum_configuration=sum_configuration,
    )


def _conditional_request(
    artifact_path: Path,
    source: Mapping[str, object],
    *,
    policy_name: str,
) -> TPMConditionalCompilationRequest:
    compilation = _mapping(
        source.get("conditional_compilation"),
        field_name="conditional_compilation",
    )
    return TPMConditionalCompilationRequest(
        source_artifact=str(artifact_path),
        event_target=str(compilation["event_target"]),
        event_value=compilation["event_value"],
        retained_decisions=tuple(
            str(name) for name in compilation["retained_decisions"]
        ),
        approximation_domains=tuple(
            _mapping(value, field_name="approximation_domain")
            for value in compilation["approximation_domains"]
        ),
        encoding=_conditional_encoding(source, policy_name=policy_name),
        numerical_policy=TPMConditionalNumericalPolicy(
            tolerances=_mapping(
                compilation.get("numerical_policy"),
                field_name="numerical_policy",
            )
        ),
    )


def _compile_pairs(
    artifact_path: Path,
    source: Mapping[str, object],
) -> dict[str, object]:
    return {
        policy_name: compile_conditional_mio_pair(
            _conditional_request(
                artifact_path,
                source,
                policy_name=policy_name,
            )
        )
        for policy_name in ("max", "pwl")
    }


def _write_json_new(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    with path.open("xb") as output:
        output.write(serialized)
        output.flush()


def stage_fixtures(staging_directory: Path) -> dict[str, object]:
    """Create reviewed source and final mixed pairs in one fresh directory."""

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
    source = _load_source()
    pairs = _compile_pairs(staged_manifest, source)
    pair_paths = {
        "max": destination / MAX_PAIR_PATH.name,
        "pwl": destination / PWL_PAIR_PATH.name,
    }
    pair_results = []
    for policy_name in ("max", "pwl"):
        publication = publish_conditional_pair(
            pairs[policy_name], pair_paths[policy_name]
        )
        if not publication.created or publication.reused:
            raise AssertionError("fresh staging must create each conditional pair")
        pair_paths[policy_name].chmod(0o644)
        pair_results.append(
            {
                "policy": policy_name,
                "path": str(pair_paths[policy_name]),
                "pair_id": pairs[policy_name].pair_id,
                "sha256": _sha256(pair_paths[policy_name]),
            }
        )
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
        "published_pairs": pair_results,
    }


def stage_pairs(staging_directory: Path) -> dict[str, object]:
    """Create final pairs from the already-reviewed committed source artifact."""

    destination = Path(staging_directory).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    artifact = load_tpm_artifact(ARTIFACT_PATH)
    source = _load_source()
    pairs = _compile_pairs(ARTIFACT_PATH, source)
    pair_paths = {
        "max": destination / MAX_PAIR_PATH.name,
        "pwl": destination / PWL_PAIR_PATH.name,
    }
    pair_results = []
    for policy_name in ("max", "pwl"):
        publication = publish_conditional_pair(
            pairs[policy_name], pair_paths[policy_name]
        )
        if not publication.created or publication.reused:
            raise AssertionError("fresh staging must create each conditional pair")
        pair_paths[policy_name].chmod(0o644)
        pair_results.append(
            {
                "policy": policy_name,
                "path": str(pair_paths[policy_name]),
                "pair_id": pairs[policy_name].pair_id,
                "sha256": _sha256(pair_paths[policy_name]),
            }
        )
    return {
        "mode": "stage_pairs",
        "staging_command": PAIR_STAGING_COMMAND,
        "staging_directory": str(destination),
        "source_artifact": str(ARTIFACT_PATH),
        "artifact_id": artifact.artifact_id,
        "manifest_sha256": _sha256(ARTIFACT_PATH),
        "sidecar_sha256": _sha256(SIDECAR_PATH),
        "published_pairs": pair_results,
    }


def _fixed_assignment_diagnostics(
    pair,
    assignments: Mapping[str, object],
    *,
    namespace: str,
):
    import highspy
    import pyomo.environ as pyo

    model = pyo.ConcreteModel()
    model.x = pyo.Var(bounds=(40.0, 160.0))
    model.activation = pyo.Var(domain=pyo.Binary)
    model.category = pyo.Set(
        initialize=("economy", "standard", "priority"), ordered=True
    )
    model.service_tier = pyo.Var(model.category, domain=pyo.Binary)
    attachment = attach_conditional_mio_pair(
        pair,
        model,
        mappings=(
            TPMContinuousDecisionMapping("x", model.x),
            TPMBinaryDecisionMapping("activation", model.activation),
            TPMCategoricalDecisionMapping(
                "service_tier",
                tuple(
                    (label, model.service_tier[label]) for label in model.category
                ),
            ),
        ),
        namespace=namespace,
    )
    model.x.fix(float(assignments["x"]))
    model.activation.fix(1 if assignments["activation"] == "on" else 0)
    for label in model.category:
        model.service_tier[label].fix(
            int(label == assignments["service_tier"])
        )
    if tuple(model.component_objects(pyo.Objective, descend_into=True)):
        raise AssertionError("fixed-assignment evidence must remain objective-free")
    result = pyo.SolverFactory("highs").solve(model)
    return inspect_conditional_mio_attachment(
        attachment,
        solver_metadata={
            "solver_name": "highs",
            "solver_version": highspy.Highs().version(),
            "status": str(result.solver.status),
            "termination_condition": str(result.solver.termination_condition),
        },
    )


def _build_evidence_bundle() -> dict[str, object]:
    artifact = load_tpm_artifact(ARTIFACT_PATH)
    source = _load_source()
    pairs = {
        "max": load_conditional_pair(MAX_PAIR_PATH),
        "pwl": load_conditional_pair(PWL_PAIR_PATH),
    }
    pair_before = {
        "max": MAX_PAIR_PATH.read_bytes(),
        "pwl": PWL_PAIR_PATH.read_bytes(),
    }
    parity_records = []
    fidelity_records = []
    for policy_name, pair in pairs.items():
        parity_cases = {}
        fidelity_cases = {}
        for raw_case in source["representative_assignments"]:
            case = _mapping(raw_case, field_name="representative_assignment")
            case_name = str(case["case_name"])
            assignments = _mapping(case["values"], field_name="values")
            direct = evaluate_conditional_mio_pair(
                pair,
                declared_domain_assignments=assignments,
            )
            native = evaluate_native_conditional_pair(
                artifact,
                pair,
                declared_domain_assignments=assignments,
            )
            diagnostics = _fixed_assignment_diagnostics(
                pair,
                assignments,
                namespace=f"{policy_name}_{case_name.replace('-', '_')}",
            )
            parity_cases[case_name] = (direct, diagnostics)
            fidelity_cases[case_name] = (direct, native)
        provenance = {
            "spec_feature": "016-conditional-mio-embedding",
            "source_fixture_sha256": _sha256(SOURCE_PATH),
            "artifact_manifest_sha256": _sha256(ARTIFACT_PATH),
            "pair_sha256": _sha256(
                MAX_PAIR_PATH if policy_name == "max" else PWL_PAIR_PATH
            ),
            "network_required": False,
            "commercial_solver_required": False,
        }
        parity = build_embedding_parity_evidence(
            pair,
            case_results=parity_cases,
            provenance={**provenance, "comparison": "embedding-solver-parity"},
        )
        if not parity.accepted:
            raise AssertionError(
                f"{policy_name} embedding parity did not meet the acceptance contract"
            )
        fidelity = build_compiler_fidelity_evidence(
            pair,
            case_results=fidelity_cases,
            provenance={**provenance, "comparison": "native-compiler-fidelity"},
        )
        parity_records.append(parity.to_dict())
        fidelity_records.append(fidelity.to_dict())
    if MAX_PAIR_PATH.read_bytes() != pair_before["max"]:
        raise AssertionError("max pair changed while building evidence")
    if PWL_PAIR_PATH.read_bytes() != pair_before["pwl"]:
        raise AssertionError("PWL pair changed while building evidence")
    return {
        "fixture_name": "conditional_mio_evidence_v1",
        "fixture_status": "active-generated-evidence",
        "record_kind": "conditional-mio-evidence-fixture-v1",
        "schema_version": "v1",
        "spec_feature": "016-conditional-mio-embedding",
        "purpose": (
            "Separate immutable embedding/solver parity and native/compiler "
            "fidelity records for the reviewed mixed conditional pairs."
        ),
        "source": {
            "artifact_id": artifact.artifact_id,
            "source_fixture_sha256": _sha256(SOURCE_PATH),
            "artifact_manifest_sha256": _sha256(ARTIFACT_PATH),
            "artifact_sidecar_sha256": _sha256(SIDECAR_PATH),
        },
        "pairs": [
            {
                "policy": policy_name,
                "pair_id": pairs[policy_name].pair_id,
                "sha256": _sha256(
                    MAX_PAIR_PATH if policy_name == "max" else PWL_PAIR_PATH
                ),
            }
            for policy_name in ("max", "pwl")
        ],
        "representative_assignments": source["representative_assignments"],
        "embedding_parity_records": parity_records,
        "compiler_fidelity_records": fidelity_records,
        "provenance": {
            "author": "OpenAI Codex",
            "origin": (
                "Generated deterministically from the reviewed feature-016 source "
                "artifact and immutable max/PWL pairs."
            ),
            "legacy_evidence_paths": [],
            "generation_command": EVIDENCE_STAGING_COMMAND,
            "random_seed": 16028,
            "refresh_policy": (
                "Stage once in a fresh directory after an intentional semantic "
                "change; never retry, adapt, repair, or overwrite during verification."
            ),
            "staging_command": EVIDENCE_STAGING_COMMAND,
            "verification_command": VERIFICATION_COMMAND,
            "cpu_only": True,
            "network_required": False,
            "commercial_solver_required": False,
            "retry_policy": "none",
        },
        "notes": [
            "Parity compares attached Pyomo roots with direct execution of the identical selected max or PWL semantics and is gated at 1e-6.",
            "Fidelity compares direct compiled values with current-SPFlow and intentionally has no numerical adequacy gate.",
            "The published pair files remain byte-identical before and after all evidence cases.",
        ],
    }


def stage_evidence(staging_directory: Path) -> dict[str, object]:
    """Build reviewed evidence once in a fresh directory without rewriting fixtures."""

    destination = Path(staging_directory).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    output = destination / EVIDENCE_PATH.name
    bundle = _build_evidence_bundle()
    _write_json_new(output, bundle)
    output.chmod(0o644)
    return {
        "mode": "stage_evidence",
        "staging_directory": str(destination),
        "evidence": str(output),
        "evidence_sha256": _sha256(output),
        "parity_evidence_ids": [
            record["evidence_id"]
            for record in bundle["embedding_parity_records"]
        ],
        "fidelity_evidence_ids": [
            record["evidence_id"]
            for record in bundle["compiler_fidelity_records"]
        ],
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
    pair_before = {
        "max": MAX_PAIR_PATH.read_bytes(),
        "pwl": PWL_PAIR_PATH.read_bytes(),
    }
    evidence_before = EVIDENCE_PATH.read_bytes()
    committed = load_tpm_artifact(ARTIFACT_PATH)
    if committed.provenance.get("source_fixture_sha256") != _sha256(SOURCE_PATH):
        raise AssertionError("committed artifact source digest is stale")
    committed_semantics = _semantic_projection(committed)
    committed_pairs = {
        "max": load_conditional_pair(MAX_PAIR_PATH),
        "pwl": load_conditional_pair(PWL_PAIR_PATH),
    }
    recomputed_pairs = _compile_pairs(ARTIFACT_PATH, _load_source())
    for policy_name, expected_mode in (("max", "max"), ("pwl", "piecewise")):
        pair = committed_pairs[policy_name]
        if pair.encoding.mode != expected_mode:
            raise AssertionError(f"{policy_name} pair has the wrong selected encoding")
        if pair.retained_decisions != ("x", "activation", "service_tier"):
            raise AssertionError(f"{policy_name} pair lost mixed retained decisions")
        if canonical_conditional_json_bytes(pair) != canonical_conditional_json_bytes(
            recomputed_pairs[policy_name]
        ):
            raise AssertionError(f"{policy_name} pair differs from deterministic compilation")
        serialized = canonical_conditional_json_bytes(pair).lower()
        if any(term in serialized for term in (b"cartesian", b"combination", b"lookup")):
            raise AssertionError(f"{policy_name} pair contains an enumerated decision table")
        for raw_case in _load_source()["representative_assignments"]:
            case = _mapping(raw_case, field_name="representative_assignment")
            evaluation = evaluate_conditional_mio_pair(
                pair,
                declared_domain_assignments=_mapping(
                    case["values"], field_name="values"
                ),
            )
            if not math.isfinite(evaluation.conditional_log_risk):
                raise AssertionError(f"{policy_name} pair evaluation is nonfinite")
    committed_evidence = _mapping(
        json.loads(EVIDENCE_PATH.read_text(encoding="utf-8")),
        field_name="conditional_mio_evidence_v1",
    )
    recomputed_evidence = _build_evidence_bundle()
    _assert_nested_close(
        committed_evidence,
        recomputed_evidence,
        path="conditional_mio_evidence",
        tolerance=1e-9,
    )
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
    if MAX_PAIR_PATH.read_bytes() != pair_before["max"]:
        raise AssertionError("max pair changed during verification")
    if PWL_PAIR_PATH.read_bytes() != pair_before["pwl"]:
        raise AssertionError("PWL pair changed during verification")
    if EVIDENCE_PATH.read_bytes() != evidence_before:
        raise AssertionError("conditional evidence changed during verification")
    capabilities = detect_spflow_backend_capabilities()
    return {
        "mode": "verify_fixtures",
        "artifact_id": committed.artifact_id,
        "manifest_sha256": _sha256(ARTIFACT_PATH),
        "sidecar_sha256": _sha256(SIDECAR_PATH),
        "source_sha256": _sha256(SOURCE_PATH),
        "max_pair_sha256": _sha256(MAX_PAIR_PATH),
        "max_pair_id": committed_pairs["max"].pair_id,
        "pwl_pair_sha256": _sha256(PWL_PAIR_PATH),
        "pwl_pair_id": committed_pairs["pwl"].pair_id,
        "evidence_sha256": _sha256(EVIDENCE_PATH),
        "parity_evidence_ids": [
            record["evidence_id"]
            for record in committed_evidence["embedding_parity_records"]
        ],
        "fidelity_evidence_ids": [
            record["evidence_id"]
            for record in committed_evidence["compiler_fidelity_records"]
        ],
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
        help="create the source artifact, sidecar, and final max/PWL pairs in a new directory",
    )
    mode.add_argument(
        "--stage-pairs",
        type=Path,
        metavar="FRESH_DIRECTORY",
        help="create final max/PWL pairs from the committed source artifact",
    )
    mode.add_argument(
        "--stage-evidence",
        type=Path,
        metavar="FRESH_DIRECTORY",
        help="create separate parity/fidelity evidence from committed pairs",
    )
    mode.add_argument(
        "--verify-fixtures",
        action="store_true",
        help="read and refit committed source evidence without rewriting it",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.stage_fixtures is not None:
        result = stage_fixtures(args.stage_fixtures)
    elif args.stage_pairs is not None:
        result = stage_pairs(args.stage_pairs)
    elif args.stage_evidence is not None:
        result = stage_evidence(args.stage_evidence)
    else:
        result = verify_fixtures()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
