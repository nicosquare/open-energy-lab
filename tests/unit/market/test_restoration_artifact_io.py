"""Persistence, integrity, sidecar, and offline contracts for restoration data."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import urllib.request

import pytest

from open_energy_lab.market.restoration_artifact import (
    RestorationArtifactIntegrityError,
    RestorationArtifactPublicationError,
    RestorationArtifactValidationError,
    build_restoration_market_artifact,
    canonical_restoration_json_bytes,
    load_restoration_market_artifact,
    restoration_market_artifact_filename,
    write_restoration_market_artifact,
)
from tests.unit.market.test_restoration_artifact import (
    _build_restoration_artifact,
    _valid_restoration_artifact_input,
)


def test_canonical_json_is_deterministic_and_rejects_non_finite_values() -> None:
    assert canonical_restoration_json_bytes({"b": 1, "a": [0, None]}) == (
        b'{"a":[0,null],"b":1}'
    )
    with pytest.raises(RestorationArtifactValidationError, match="finite|NaN"):
        canonical_restoration_json_bytes({"value": float("nan")})


def test_atomic_publication_reuses_identical_bytes_and_uses_fingerprint_filename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _build_restoration_artifact()
    replace_calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def _record_replace(source: os.PathLike[str], destination: os.PathLike[str]) -> None:
        replace_calls.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", _record_replace)

    path = write_restoration_market_artifact(artifact, destination_dir=tmp_path)
    original = path.read_bytes()
    reused = write_restoration_market_artifact(artifact, destination_dir=tmp_path)

    assert path == reused
    assert path.name == restoration_market_artifact_filename(artifact)
    assert artifact.artifact_fingerprint in path.name
    assert path.read_bytes() == original
    assert original.endswith(b"\n")
    assert replace_calls[0][0].parent == path.parent
    assert not replace_calls[0][0].exists()
    assert load_restoration_market_artifact(path) == artifact


def test_corrupt_immutable_destination_is_never_replaced(tmp_path: Path) -> None:
    artifact = _build_restoration_artifact()
    path = write_restoration_market_artifact(artifact, destination_dir=tmp_path)
    corrupt = b'{"corrupt":true}\n'
    path.write_bytes(corrupt)

    with pytest.raises(RestorationArtifactIntegrityError, match="immutable|existing"):
        write_restoration_market_artifact(artifact, destination_dir=tmp_path)

    assert path.read_bytes() == corrupt


def test_failed_atomic_replace_leaves_no_partial_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _build_restoration_artifact()

    def _fail_replace(*args: object, **kwargs: object) -> None:
        raise OSError("injected publication failure")

    monkeypatch.setattr(os, "replace", _fail_replace)
    with pytest.raises(RestorationArtifactPublicationError, match="atomic|publish"):
        write_restoration_market_artifact(artifact, destination_dir=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_raw_digest_and_safe_relative_sidecar_are_verified(tmp_path: Path) -> None:
    sidecar = b'{"synthetic":"retained-response"}'
    sidecar_path = tmp_path / "sidecars" / "rte-afrr-hour.json"
    sidecar_path.parent.mkdir()
    sidecar_path.write_bytes(sidecar)
    payload = _valid_restoration_artifact_input()
    evidence = payload["request_evidence"][0]
    evidence["response_bytes"] = len(sidecar)
    evidence["raw_sha256"] = hashlib.sha256(sidecar).hexdigest()
    payload["raw_retention"] = {
        "policy": "PERMITTED_SIDECAR",
        "responses": {
            "rte-afrr-hour-1": {
                "status": "sidecar_retained",
                "sidecar_locator": "sidecars/rte-afrr-hour.json",
                "sidecar_sha256": hashlib.sha256(sidecar).hexdigest(),
            }
        },
    }
    artifact = build_restoration_market_artifact(payload)
    manifest = write_restoration_market_artifact(artifact, destination_dir=tmp_path)

    assert load_restoration_market_artifact(manifest, artifact_root=tmp_path) == artifact
    sidecar_path.write_bytes(b"tampered")
    with pytest.raises(RestorationArtifactIntegrityError, match="sidecar|digest"):
        load_restoration_market_artifact(manifest, artifact_root=tmp_path)


def test_sidecar_traversal_is_rejected_before_file_access() -> None:
    payload = _valid_restoration_artifact_input()
    raw = payload["raw_retention"]
    raw["policy"] = "PERMITTED_SIDECAR"
    raw["responses"]["rte-afrr-hour-1"] = {
        "status": "sidecar_retained",
        "sidecar_locator": "../outside.json",
        "sidecar_sha256": payload["request_evidence"][0]["raw_sha256"],
    }

    with pytest.raises(RestorationArtifactValidationError, match="sidecar|relative|traversal"):
        build_restoration_market_artifact(payload)


def test_loader_rejects_non_finite_and_tampered_manifests(tmp_path: Path) -> None:
    artifact = _build_restoration_artifact()
    payload = artifact.to_dict()
    payload["series"][0]["observations"][0]["value"] = float("inf")
    path = tmp_path / "non-finite.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RestorationArtifactValidationError, match="finite|Infinity"):
        load_restoration_market_artifact(path)

    tampered = deepcopy(artifact.to_dict())
    tampered["series"][0]["observations"][0]["value"] = 123.0
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(RestorationArtifactIntegrityError, match="fingerprint"):
        load_restoration_market_artifact(path)


def test_offline_loading_reads_no_credentials_and_opens_no_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = _build_restoration_artifact()
    path = write_restoration_market_artifact(artifact, destination_dir=tmp_path)

    def _forbid_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("offline restoration load attempted network access")

    real_getenv = os.getenv

    def _guard_getenv(key: str, default: str | None = None) -> str | None:
        if key in {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}:
            raise AssertionError(f"offline restoration load read {key}")
        return real_getenv(key, default)

    monkeypatch.setattr(socket, "create_connection", _forbid_network)
    monkeypatch.setattr(urllib.request, "urlopen", _forbid_network)
    monkeypatch.setattr(os, "getenv", _guard_getenv)

    assert load_restoration_market_artifact(path) == artifact
