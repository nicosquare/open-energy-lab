"""Persistence, integrity, sidecar, and offline-load contracts for market data."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
from typing import Any
import urllib.request

import pytest

from tests.unit.market.test_artifact import (
    _artifact_module,
    _build_artifact,
    _require,
    _valid_artifact_input,
)


def _field(value: object, name: str) -> Any:
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def _write_manifest(path: Path, payload: Mapping[str, object]) -> None:
    path.write_text(
        json.dumps(payload, allow_nan=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _raw_response(payload: dict[str, object], response_id: str) -> dict[str, object]:
    responses = payload["raw_responses"]
    assert isinstance(responses, list)
    return next(
        response
        for response in responses
        if isinstance(response, dict) and response["response_id"] == response_id
    )


def _sidecar_artifact_input(
    sidecar_bytes: bytes,
    *,
    locator: str = "sidecars/response-a44.xml",
) -> dict[str, object]:
    payload = _valid_artifact_input()
    evidence = _raw_response(payload, "response-a44")
    digest = hashlib.sha256(sidecar_bytes).hexdigest()
    evidence.update(
        {
            "byte_count": len(sidecar_bytes),
            "sha256": digest,
            "retention_status": "sidecar_retained",
            "sidecar_locator": locator,
            "sidecar_sha256": digest,
        }
    )
    return payload


def _manifest_with_recomputed_artifact_fingerprint(
    payload: dict[str, object],
) -> dict[str, object]:
    canonical_json_bytes = _require("canonical_json_bytes")
    payload = deepcopy(payload)
    payload.pop("artifact_fingerprint", None)
    payload["artifact_fingerprint"] = hashlib.sha256(
        canonical_json_bytes(payload)
    ).hexdigest()
    return payload


def test_loader_rejects_unknown_schema_before_exposing_values(tmp_path: Path) -> None:
    load_market_data_artifact = _require("load_market_data_artifact")
    error_type = _require("UnsupportedMarketArtifactVersionError")
    payload = _build_artifact().to_dict()
    payload["schema_version"] = "oel.market-data.v999"
    path = tmp_path / "unknown-schema.json"
    _write_manifest(path, payload)

    with pytest.raises(error_type, match="schema|version|v999"):
        load_market_data_artifact(path)


def test_loader_rejects_malformed_json_with_a_typed_diagnostic(tmp_path: Path) -> None:
    load_market_data_artifact = _require("load_market_data_artifact")
    error_type = _require("MarketArtifactValidationError")
    path = tmp_path / "malformed.json"
    path.write_text('{"schema_version": ', encoding="utf-8")

    with pytest.raises(error_type, match="JSON|malformed|decode"):
        load_market_data_artifact(path)


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_loader_rejects_non_finite_json_numbers(
    tmp_path: Path,
    non_finite: float,
) -> None:
    load_market_data_artifact = _require("load_market_data_artifact")
    error_type = _require("MarketArtifactValidationError")
    payload = _build_artifact().to_dict()
    observations = payload["series"]["day_ahead_price"]["observations"]
    observations[0]["value"] = non_finite
    path = tmp_path / "non-finite.json"
    _write_manifest(path, payload)

    with pytest.raises(error_type, match="finite|NaN|Infinity"):
        load_market_data_artifact(path)


def test_digest_only_evidence_loads_without_a_sidecar_root(tmp_path: Path) -> None:
    write_market_data_artifact = _require("write_market_data_artifact")
    load_market_data_artifact = _require("load_market_data_artifact")
    artifact = _build_artifact()

    path = write_market_data_artifact(artifact, destination_dir=tmp_path)
    loaded = load_market_data_artifact(path)

    assert loaded.artifact_fingerprint == artifact.artifact_fingerprint
    assert all(
        _field(evidence, "retention_status") == "digest_only"
        for evidence in loaded.raw_responses
    )
    assert all(
        _field(evidence, "sidecar_locator") is None
        and _field(evidence, "sidecar_sha256") is None
        for evidence in loaded.raw_responses
    )


def test_digest_only_evidence_rejects_sidecar_claims() -> None:
    payload = _valid_artifact_input()
    evidence = _raw_response(payload, "response-a44")
    evidence["sidecar_locator"] = "sidecars/unclaimed.xml"
    evidence["sidecar_sha256"] = evidence["sha256"]
    error_type = _require("MarketArtifactValidationError")

    with pytest.raises(error_type, match="digest_only|sidecar"):
        _build_artifact(payload)


def test_atomic_write_uses_a_sibling_temporary_file_and_reuses_verified_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_market_data_artifact = _require("write_market_data_artifact")
    load_market_data_artifact = _require("load_market_data_artifact")
    artifact = _build_artifact()
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def _record_replace(
        source: str | bytes | os.PathLike[str],
        destination: str | bytes | os.PathLike[str],
    ) -> None:
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", _record_replace)

    path = write_market_data_artifact(artifact, destination_dir=tmp_path)
    original_bytes = path.read_bytes()
    reused_path = write_market_data_artifact(artifact, destination_dir=tmp_path)

    assert path == reused_path
    assert path.read_bytes() == original_bytes
    assert artifact.artifact_fingerprint in path.name
    assert replace_calls
    temporary_path, destination_path = replace_calls[0]
    assert destination_path == path
    assert temporary_path != path
    assert temporary_path.parent == path.parent
    assert not temporary_path.exists()
    assert load_market_data_artifact(path).artifact_fingerprint == (
        artifact.artifact_fingerprint
    )


def test_immutable_write_refuses_to_replace_a_corrupt_existing_manifest(
    tmp_path: Path,
) -> None:
    write_market_data_artifact = _require("write_market_data_artifact")
    error_type = _require("MarketArtifactIntegrityError")
    artifact = _build_artifact()
    path = write_market_data_artifact(artifact, destination_dir=tmp_path)
    corrupt_bytes = b'{"corrupt":true}\n'
    path.write_bytes(corrupt_bytes)

    with pytest.raises(error_type, match="existing|integrity|immutable"):
        write_market_data_artifact(artifact, destination_dir=tmp_path)

    assert path.read_bytes() == corrupt_bytes


def test_failed_atomic_publication_leaves_no_manifest_or_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_market_data_artifact = _require("write_market_data_artifact")
    error_type = _require("MarketArtifactPublicationError")
    artifact = _build_artifact()

    def _fail_replace(
        source: str | bytes | os.PathLike[str],
        destination: str | bytes | os.PathLike[str],
    ) -> None:
        raise OSError("injected replace failure")

    monkeypatch.setattr(os, "replace", _fail_replace)

    with pytest.raises(error_type, match="publish|atomic|replace"):
        write_market_data_artifact(artifact, destination_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_safe_relative_sidecar_is_contained_and_digest_verified(
    tmp_path: Path,
) -> None:
    write_market_data_artifact = _require("write_market_data_artifact")
    load_market_data_artifact = _require("load_market_data_artifact")
    integrity_error = _require("MarketArtifactIntegrityError")
    sidecar_bytes = b"<Publication_MarketDocument>safe</Publication_MarketDocument>\n"
    sidecar_path = tmp_path / "sidecars" / "response-a44.xml"
    sidecar_path.parent.mkdir()
    sidecar_path.write_bytes(sidecar_bytes)
    artifact = _build_artifact(_sidecar_artifact_input(sidecar_bytes))

    manifest_path = write_market_data_artifact(artifact, destination_dir=tmp_path)
    loaded = load_market_data_artifact(manifest_path, artifact_root=tmp_path)

    retained = next(
        evidence
        for evidence in loaded.raw_responses
        if _field(evidence, "response_id") == "response-a44"
    )
    assert _field(retained, "retention_status") == "sidecar_retained"
    assert _field(retained, "sidecar_locator") == "sidecars/response-a44.xml"
    assert _field(retained, "sidecar_sha256") == hashlib.sha256(
        sidecar_bytes
    ).hexdigest()

    sidecar_path.write_bytes(b"tampered")
    with pytest.raises(integrity_error, match="sidecar|digest|sha256"):
        load_market_data_artifact(manifest_path, artifact_root=tmp_path)


def test_loader_rejects_sidecar_traversal_even_when_outside_file_matches(
    tmp_path: Path,
) -> None:
    load_market_data_artifact = _require("load_market_data_artifact")
    validation_error = _require("MarketArtifactValidationError")
    integrity_error = _require("MarketArtifactIntegrityError")
    sidecar_bytes = b"outside-artifact-root"
    outside_path = tmp_path / "outside.xml"
    outside_path.write_bytes(sidecar_bytes)
    root = tmp_path / "artifact-root"
    root.mkdir()

    safe_artifact = _build_artifact(
        _sidecar_artifact_input(sidecar_bytes, locator="sidecars/response-a44.xml")
    )
    manifest = safe_artifact.to_dict()
    evidence = _raw_response(manifest, "response-a44")
    evidence["sidecar_locator"] = "../outside.xml"
    manifest = _manifest_with_recomputed_artifact_fingerprint(manifest)
    manifest_path = root / "unsafe.json"
    _write_manifest(manifest_path, manifest)

    with pytest.raises(
        (validation_error, integrity_error),
        match="sidecar|relative|traversal|artifact root",
    ):
        load_market_data_artifact(manifest_path, artifact_root=root)


def test_offline_loading_never_uses_network_or_reads_the_entsoe_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_market_data_artifact = _require("write_market_data_artifact")
    load_market_data_artifact = _require("load_market_data_artifact")
    artifact = _build_artifact()
    path = write_market_data_artifact(artifact, destination_dir=tmp_path)

    def _forbid_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("offline artifact loading attempted network access")

    real_getenv = os.getenv

    def _guard_getenv(key: str, default: str | None = None) -> str | None:
        if key == "ENTSOE_API_TOKEN":
            raise AssertionError("offline artifact loading read ENTSOE_API_TOKEN")
        return real_getenv(key, default)

    monkeypatch.setattr(socket, "create_connection", _forbid_network)
    monkeypatch.setattr(urllib.request, "urlopen", _forbid_network)
    monkeypatch.setattr(os, "getenv", _guard_getenv)

    loaded = load_market_data_artifact(path)

    assert loaded.artifact_fingerprint == artifact.artifact_fingerprint
    assert _artifact_module().__name__ == "open_energy_lab.market.artifact"
