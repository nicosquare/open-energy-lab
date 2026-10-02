"""Contracts for import-light conditional pair records and persistence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
import json
import math
from threading import Barrier

import pytest

import tpm.conditional as conditional_module
from tpm.conditional import (
    CONDITIONAL_PAIR_COMPILER_VERSION,
    CONDITIONAL_PAIR_RECORD_KIND,
    CONDITIONAL_PAIR_SCHEMA_VERSION,
    TPMConditionalCircuit,
    TPMConditionalCircuitNode,
    TPMConditionalCompilationRequest,
    TPMConditionalEncodingPolicy,
    TPMConditionalEvent,
    TPMConditionalFeatureValidity,
    TPMConditionalNumericalPolicy,
    TPMConditionalPair,
    TPMConditionalSourceReference,
    canonical_conditional_json_bytes,
    load_conditional_pair,
    publish_conditional_pair,
)
from tpm.conditional_mio import evaluate_conditional_mio_pair
from tpm.piecewise import resolve_guarded_exponential_spec


def _source_reference() -> TPMConditionalSourceReference:
    return TPMConditionalSourceReference(
        artifact_id="tpm-artifact:conditional-unit",
        artifact_schema_version="v3",
        manifest_reference="tests/fixtures/tpm/source.json",
        sidecar_sha256="a" * 64,
        backend_generation="current-spflow",
        backend_api_version="1.1.0",
        model_digest="b" * 64,
    )


def _event(*, value: object = 1.0, index: int = 1) -> TPMConditionalEvent:
    return TPMConditionalEvent(
        feature_name="violation",
        declared_value=value,
        model_index=index,
    )


def _validity() -> tuple[TPMConditionalFeatureValidity, ...]:
    return (
        TPMConditionalFeatureValidity(
            feature_name="x",
            feature_index=0,
            feature_type="continuous",
            declared_domain={
                "feature_name": "x",
                "feature_kind": "continuous",
                "purpose": "decision-domain",
                "shape": "finite",
                "lower": 40.0,
                "upper": 160.0,
                "origin": "caller-declared",
            },
            normalization={
                "feature_name": "x",
                "feature_kind": "continuous",
                "kind": "min-max",
                "origin": "caller-declared",
                "lower": 40.0,
                "upper": 160.0,
            },
            approximation_domain={
                "feature_name": "x",
                "physical_interval": [40.0, 160.0],
                "model_interval": [0.0, 1.0],
                "source": "conditional-unit",
                "encoding": "piecewise-log-density",
            },
        ),
    )


def _encoding(mode: str = "max") -> TPMConditionalEncodingPolicy:
    if mode == "max":
        return TPMConditionalEncodingPolicy(
            mode="max",
            approximation_label="weighted-log-sum-exp-max-approximation",
            certification_label="uncertified",
            leaf_configuration={
                "policy_name": "physical-interval-relative-v2",
                "relative_breakpoints": [0.0, 0.5, 1.0],
                "mio_epsilon": 1e-6,
                "discrete_probability_floor": 1e-12,
            },
            sum_configuration={"sum_big_m": 100.0},
        )
    guarded = resolve_guarded_exponential_spec(
        base_x_points=[math.log(1e-3), -2.0, -1.0, -0.3, 0.0],
        base_y_points=[0.001, 0.14, 0.37, 0.74, 1.0],
        domain_floor=-500.0,
    )
    return TPMConditionalEncodingPolicy(
        mode="piecewise",
        approximation_label=(
            "weighted-log-sum-exp-piecewise-linear-approximation"
        ),
        certification_label="not-applicable",
        leaf_configuration={
            "policy_name": "physical-interval-relative-v2",
            "relative_breakpoints": [0.0, 0.5, 1.0],
            "mio_epsilon": 1e-6,
            "discrete_probability_floor": 1e-12,
        },
        sum_configuration={
            "sum_big_m": 100.0,
            **guarded,
            "log_x_points": [1.0, 1.19, 1.41, 1.68, 2.0],
            "log_y_points": [0.0, 0.17, 0.35, 0.52, 0.69],
        },
    )


def _numerical_policy() -> TPMConditionalNumericalPolicy:
    return TPMConditionalNumericalPolicy(
        tolerances={
            "embedding_parity_absolute_tolerance": 1e-6,
            "constraint_residual_absolute_tolerance": 1e-6,
            "positive_log_risk_limit": 1e-6,
            "domain_membership_tolerance": 0.0,
        }
    )


def _numerator() -> TPMConditionalCircuit:
    return TPMConditionalCircuit(
        root_id=2,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 0.5, 1.0],
                    "log_values": [-2.0, -1.0, -2.0],
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 1,
                    "type": "leaf_binary",
                    "feature_name": "violation",
                    "densities": [0.7, 0.3],
                    "fixed_value": 1,
                }
            ),
            TPMConditionalCircuitNode.from_dict(
                {"id": 2, "type": "product", "children": [0, 1]}
            ),
        ),
        metadata={"event_treatment": "fixed", "event_model_index": 1},
    )


def _denominator() -> TPMConditionalCircuit:
    return TPMConditionalCircuit(
        root_id=0,
        nodes=(
            TPMConditionalCircuitNode.from_dict(
                {
                    "id": 0,
                    "type": "leaf_piecewise",
                    "feature_name": "x",
                    "breakpoints": [0.0, 0.5, 1.0],
                    "log_values": [-1.5, -0.8, -1.5],
                }
            ),
        ),
        metadata={"event_treatment": "marginalized"},
    )


def _pair(*, encoding: TPMConditionalEncodingPolicy | None = None) -> TPMConditionalPair:
    return TPMConditionalPair(
        source=_source_reference(),
        event=_event(),
        feature_schema=(
            {
                "feature_name": "x",
                "feature_role": "decision",
                "feature_type": "continuous",
            },
            {
                "feature_name": "demand",
                "feature_role": "target",
                "feature_type": "continuous",
            },
            {
                "feature_name": "violation",
                "feature_role": "target",
                "feature_type": "binary",
                "ordering": [0.0, 1.0],
            },
        ),
        retained_decisions=("x",),
        marginalized_features=("demand",),
        validity=_validity(),
        encoding=encoding or _encoding(),
        numerical_policy=_numerical_policy(),
        numerator=_numerator(),
        denominator=_denominator(),
        provenance={"source_rows_sha256": "c" * 64},
    )


def test_compilation_request_preserves_ordered_explicit_inputs() -> None:
    request = TPMConditionalCompilationRequest(
        source_artifact="tests/fixtures/tpm/source.json",
        event_target="violation",
        event_value=0.0,
        retained_decisions=("x", "activation"),
        approximation_domains=(
            {
                "feature_name": "x",
                "lower": 40.0,
                "upper": 160.0,
                "source": "unit",
                "encoding": "piecewise-log-density",
            },
        ),
        encoding=_encoding(),
        numerical_policy=_numerical_policy(),
    )

    assert request.event_value == 0.0
    assert request.retained_decisions == ("x", "activation")
    assert request.approximation_domains[0]["feature_name"] == "x"
    with pytest.raises(TypeError):
        request.approximation_domains[0]["lower"] = 0.0


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("retained_decisions", (), "nonempty"),
        ("retained_decisions", ("x", "x"), "unique"),
        ("retained_decisions", ("violation",), "event target"),
        ("source_artifact", "", "source_artifact"),
    ],
)
def test_compilation_request_rejects_invalid_semantics(
    field: str,
    value: object,
    match: str,
) -> None:
    arguments = {
        "source_artifact": "tests/fixtures/tpm/source.json",
        "event_target": "violation",
        "event_value": 1.0,
        "retained_decisions": ("x",),
        "approximation_domains": (),
        "encoding": _encoding(),
        "numerical_policy": _numerical_policy(),
    }
    arguments[field] = value
    with pytest.raises((TypeError, ValueError), match=match):
        TPMConditionalCompilationRequest(**arguments)


def test_source_event_validity_encoding_and_tolerances_are_strict() -> None:
    assert _source_reference().model_digest == "b" * 64
    assert _event(value="safe", index=0).model_index == 0
    assert _validity()[0].approximation_domain["source"] == "conditional-unit"
    assert _encoding("piecewise").mode == "piecewise"

    with pytest.raises(ValueError, match="64-character"):
        TPMConditionalSourceReference(
            artifact_id="bad",
            artifact_schema_version="v3",
            manifest_reference="source.json",
            sidecar_sha256="short",
            backend_generation="current-spflow",
            backend_api_version="1.1.0",
            model_digest="b" * 64,
        )
    with pytest.raises(ValueError, match="model_index"):
        _event(index=2)
    with pytest.raises(ValueError, match="approximation_label"):
        TPMConditionalEncodingPolicy(
            mode="max",
            approximation_label="exact",
            certification_label="uncertified",
            leaf_configuration={},
            sum_configuration={"sum_big_m": 100.0},
        )
    with pytest.raises(ValueError, match="finite"):
        TPMConditionalNumericalPolicy(tolerances={"bad": math.inf})


def test_circuit_rejects_missing_roots_cycles_and_nonfinite_parameters() -> None:
    with pytest.raises(ValueError, match="root_id"):
        TPMConditionalCircuit(
            root_id=9,
            nodes=(TPMConditionalCircuitNode.from_dict({"id": 0, "type": "log_one"}),),
        )
    with pytest.raises(ValueError, match="acyclic"):
        TPMConditionalCircuit(
            root_id=0,
            nodes=(
                TPMConditionalCircuitNode.from_dict(
                    {"id": 0, "type": "product", "children": [1]}
                ),
                TPMConditionalCircuitNode.from_dict(
                    {"id": 1, "type": "product", "children": [0]}
                ),
            ),
        )
    with pytest.raises(ValueError, match="finite"):
        TPMConditionalCircuitNode.from_dict(
            {
                "id": 0,
                "type": "leaf_piecewise",
                "feature_name": "x",
                "breakpoints": [0.0, 1.0],
                "log_values": [0.0, math.nan],
            }
        )


def test_pair_is_recursively_immutable_and_returns_detached_serialization() -> None:
    pair = _pair()

    with pytest.raises(FrozenInstanceError):
        pair.pair_id = "changed"
    with pytest.raises(TypeError):
        pair.feature_schema[0]["feature_name"] = "changed"
    with pytest.raises(TypeError):
        pair.provenance["source_rows_sha256"] = "changed"
    with pytest.raises(TypeError):
        pair.validity[0].approximation_domain["source"] = "changed"
    with pytest.raises(TypeError):
        pair.encoding.leaf_configuration["relative_breakpoints"][0] = 0.25
    with pytest.raises(TypeError):
        pair.numerator.nodes[0].parameters["breakpoints"][0] = 0.25
    with pytest.raises(TypeError):
        pair.numerical_policy.tolerances["positive_log_risk_limit"] = 1.0

    detached = pair.to_dict()
    detached["retained_decisions"].append("changed")
    detached["feature_schema"][0]["feature_name"] = "changed"
    assert pair.retained_decisions == ("x",)
    assert pair.feature_schema[0]["feature_name"] == "x"


def test_pair_identity_is_canonical_and_changes_with_semantics() -> None:
    first = _pair()
    same = TPMConditionalPair.from_dict(first.to_dict())
    changed = _pair(encoding=_encoding("piecewise"))

    assert first.pair_id == same.pair_id
    assert first.pair_id != changed.pair_id
    assert len(first.pair_id) == 64
    assert (
        first.identity_payload()["compiler_version"]
        == CONDITIONAL_PAIR_COMPILER_VERSION
    )
    assert canonical_conditional_json_bytes(first) == canonical_conditional_json_bytes(
        same
    )


def test_pair_round_trip_preserves_complete_meaning() -> None:
    pair = _pair()
    payload = pair.to_dict()
    loaded = TPMConditionalPair.from_dict(json.loads(json.dumps(payload)))

    assert loaded == pair
    assert loaded.record_kind == CONDITIONAL_PAIR_RECORD_KIND
    assert loaded.schema_version == CONDITIONAL_PAIR_SCHEMA_VERSION
    assert loaded.compiler_version == CONDITIONAL_PAIR_COMPILER_VERSION


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("record_kind", "wrong", "record_kind"),
        ("schema_version", "v999", "schema_version"),
        ("compiler_version", "compiler-v999", "compiler_version"),
        ("pair_id", "0" * 64, "pair_id"),
    ],
)
def test_pair_loading_rejects_schema_or_identity_mismatch(
    field: str,
    value: object,
    match: str,
) -> None:
    payload = _pair().to_dict()
    payload[field] = value
    with pytest.raises(ValueError, match=match):
        TPMConditionalPair.from_dict(payload)


def test_pair_publication_creates_then_verifies_identical_bytes(tmp_path) -> None:
    pair = _pair()
    output = tmp_path / "pair.json"

    first = publish_conditional_pair(pair, output)
    original = output.read_bytes()
    second = publish_conditional_pair(pair, output)

    assert first.created is True and first.reused is False
    assert second.created is False and second.reused is True
    assert output.read_bytes() == original
    assert load_conditional_pair(output) == pair


def test_pair_publication_rejects_conflicts_and_cleans_temporary_files(tmp_path) -> None:
    output = tmp_path / "pair.json"
    publish_conditional_pair(_pair(), output)

    with pytest.raises(FileExistsError, match="conflicts"):
        publish_conditional_pair(_pair(encoding=_encoding("piecewise")), output)

    assert not tuple(tmp_path.glob(".pair.json.*.tmp"))


def test_pair_publication_concurrent_identical_publishers_create_once(tmp_path) -> None:
    pair = _pair()
    output = tmp_path / "pair.json"
    barrier = Barrier(4)

    def publish_once():
        barrier.wait()
        return publish_conditional_pair(pair, output)

    with ThreadPoolExecutor(max_workers=4) as executor:
        publications = tuple(executor.map(lambda _index: publish_once(), range(4)))

    assert sum(result.created for result in publications) == 1
    assert sum(result.reused for result in publications) == 3
    assert load_conditional_pair(output) == pair
    assert not tuple(tmp_path.glob(".pair.json.*.tmp"))


def test_pair_publication_concurrent_conflict_keeps_exactly_one_record(tmp_path) -> None:
    candidates = (_pair(), _pair(encoding=_encoding("piecewise")))
    output = tmp_path / "pair.json"
    barrier = Barrier(2)

    def publish(candidate):
        barrier.wait()
        try:
            return publish_conditional_pair(candidate, output)
        except FileExistsError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(publish, candidates))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, FileExistsError) for result in results) == 1
    assert load_conditional_pair(output).pair_id in {
        candidate.pair_id for candidate in candidates
    }
    assert not tuple(tmp_path.glob(".pair.json.*.tmp"))


@pytest.mark.parametrize("appearing_record", ["identical", "conflicting"])
def test_pair_publication_validates_a_final_name_that_appears_after_preflight(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    appearing_record: str,
) -> None:
    pair = _pair()
    output = tmp_path / "pair.json"
    competing = pair if appearing_record == "identical" else _pair(
        encoding=_encoding("piecewise")
    )
    real_link = conditional_module.os.link

    def racing_link(source, destination):
        destination = type(output)(destination)
        destination.write_bytes(canonical_conditional_json_bytes(competing))
        return real_link(source, destination)

    monkeypatch.setattr(conditional_module.os, "link", racing_link)

    if appearing_record == "identical":
        publication = publish_conditional_pair(pair, output)
        assert publication.reused is True
        assert load_conditional_pair(output) == pair
    else:
        before = canonical_conditional_json_bytes(competing)
        with pytest.raises(FileExistsError, match="conflicts"):
            publish_conditional_pair(pair, output)
        assert output.read_bytes() == before
    assert not tuple(tmp_path.glob(".pair.json.*.tmp"))


def test_pair_publication_rejects_incomplete_and_unwritable_targets_without_repair(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = tmp_path / "incomplete.json"
    incomplete.write_bytes(b'{"record_kind":"conditional-pair-v1"')
    before = incomplete.read_bytes()

    with pytest.raises(FileExistsError, match="conflicts"):
        publish_conditional_pair(_pair(), incomplete)
    assert incomplete.read_bytes() == before

    denied = tmp_path / "denied.json"

    def deny_temporary_file(*_args, **_kwargs):
        raise PermissionError("injected unwritable destination")

    monkeypatch.setattr(conditional_module.tempfile, "mkstemp", deny_temporary_file)
    with pytest.raises(PermissionError, match="unwritable"):
        publish_conditional_pair(_pair(), denied)
    assert not denied.exists()
    assert not tuple(tmp_path.glob(".denied.json.*.tmp"))


@pytest.mark.parametrize("failure_stage", ["write", "file-fsync", "link"])
def test_pair_publication_cleans_its_temporary_file_after_injected_io_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    output = tmp_path / "pair.json"
    if failure_stage == "write":
        real_fdopen = conditional_module.os.fdopen

        class FailingWriteStream:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.stream.close()

            def write(self, _payload):
                raise OSError("injected write")

            def flush(self):  # pragma: no cover - write fails first
                self.stream.flush()

            def fileno(self):  # pragma: no cover - write fails first
                return self.stream.fileno()

        monkeypatch.setattr(
            conditional_module.os,
            "fdopen",
            lambda descriptor, *args, **kwargs: FailingWriteStream(
                real_fdopen(descriptor, *args, **kwargs)
            ),
        )
    elif failure_stage == "file-fsync":
        monkeypatch.setattr(
            conditional_module.os,
            "fsync",
            lambda _descriptor: (_ for _ in ()).throw(OSError("injected fsync")),
        )
    else:
        monkeypatch.setattr(
            conditional_module.os,
            "link",
            lambda _source, _destination: (_ for _ in ()).throw(
                OSError("injected link")
            ),
        )

    with pytest.raises(OSError, match=failure_stage.split("-")[-1]):
        publish_conditional_pair(_pair(), output)

    assert not output.exists()
    assert not tuple(tmp_path.glob(".pair.json.*.tmp"))


def test_pair_publication_fsyncs_the_directory_after_link_and_recovers_by_reuse(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pair = _pair()
    output = tmp_path / "pair.json"
    calls = []
    real_fsync_directory = conditional_module._fsync_directory

    def observe_directory_fsync(directory):
        assert output.exists()
        assert load_conditional_pair(output) == pair
        calls.append(directory)
        real_fsync_directory(directory)

    monkeypatch.setattr(
        conditional_module, "_fsync_directory", observe_directory_fsync
    )
    first = publish_conditional_pair(pair, output)
    second = publish_conditional_pair(pair, output)

    assert first.created is True
    assert second.reused is True
    assert calls == [tmp_path]


def test_pair_publication_directory_fsync_failure_leaves_complete_reusable_record(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pair = _pair()
    output = tmp_path / "pair.json"

    monkeypatch.setattr(
        conditional_module,
        "_fsync_directory",
        lambda _directory: (_ for _ in ()).throw(OSError("directory fsync failed")),
    )
    with pytest.raises(OSError, match="directory fsync"):
        publish_conditional_pair(pair, output)

    assert load_conditional_pair(output) == pair
    assert not tuple(tmp_path.glob(".pair.json.*.tmp"))
    monkeypatch.undo()
    assert publish_conditional_pair(pair, output).reused is True


def test_pair_evaluation_and_changed_input_conflict_are_byte_stable(tmp_path) -> None:
    pair = _pair()
    output = tmp_path / "pair.json"
    publish_conditional_pair(pair, output)
    before = output.read_bytes()

    first = evaluate_conditional_mio_pair(
        load_conditional_pair(output), declared_domain_assignments={"x": 100.0}
    )
    second = evaluate_conditional_mio_pair(
        load_conditional_pair(output), declared_domain_assignments={"x": 100.0}
    )
    with pytest.raises(FileExistsError, match="conflicts"):
        publish_conditional_pair(_pair(encoding=_encoding("piecewise")), output)

    assert first == second
    assert output.read_bytes() == before


def test_pair_loading_rejects_corruption_without_repairing_source_bytes(tmp_path) -> None:
    output = tmp_path / "pair.json"
    output.write_bytes(b'{"record_kind":"conditional-pair-v1"')
    before = output.read_bytes()

    with pytest.raises(ValueError, match="corrupt"):
        load_conditional_pair(output)

    assert output.read_bytes() == before


def test_pair_identity_changes_for_validity_encoding_and_tolerance_inputs() -> None:
    baseline = _pair()

    validity_payload = baseline.to_dict()
    validity_payload["pair_id"] = ""
    validity_payload["validity"][0]["approximation_domain"]["source"] = "changed"
    changed_validity = TPMConditionalPair.from_dict(validity_payload)

    tolerance_payload = baseline.to_dict()
    tolerance_payload["pair_id"] = ""
    tolerance_payload["numerical_policy"]["tolerances"][
        "embedding_parity_absolute_tolerance"
    ] = 5e-7
    changed_tolerance = TPMConditionalPair.from_dict(tolerance_payload)

    assert baseline.pair_id != changed_validity.pair_id
    assert baseline.pair_id != changed_tolerance.pair_id
    assert baseline.pair_id != _pair(encoding=_encoding("piecewise")).pair_id


def test_pair_round_trip_preserves_explicit_approximation_labels() -> None:
    for mode in ("max", "piecewise"):
        pair = _pair(encoding=_encoding(mode))
        loaded = TPMConditionalPair.from_dict(pair.to_dict())

        assert loaded.encoding.mode == mode
        assert loaded.encoding.approximation_label == pair.encoding.approximation_label
        assert loaded.encoding.certification_label == pair.encoding.certification_label
