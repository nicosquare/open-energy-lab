"""Behavior of the shared persisted-artifact helpers in core.artifact."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from open_energy_lab.core.artifact import (
    PLACEHOLDER_FINGERPRINT,
    decode_json_document,
    immutable_filename,
    payload_without,
    publish_write_once,
    read_artifact_source,
    recorded_fingerprints,
    resolve_sidecar,
    safe_sidecar_locator,
    seal_fingerprints,
    verify_fingerprints,
    verify_sidecar_bytes,
)
from open_energy_lab.core.errors import ValidationError
from open_energy_lab.core.serialization import fingerprint, sha256_hex


class Integrity(ValidationError):
    pass


class Publication(OSError):
    pass


@dataclass(frozen=True)
class Doc:
    name: str
    content_fingerprint: str = PLACEHOLDER_FINGERPRINT
    artifact_fingerprint: str = PLACEHOLDER_FINGERPRINT

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "content_fingerprint": self.content_fingerprint,
            "artifact_fingerprint": self.artifact_fingerprint,
        }


def _seal(name: str) -> Doc:
    return seal_fingerprints(
        Doc(name),
        (
            ("content_fingerprint", lambda d: {"name": d.name}),
            ("artifact_fingerprint", lambda d: payload_without(d, "artifact_fingerprint")),
        ),
    )


def test_seal_fills_stages_in_order_and_each_sees_the_previous() -> None:
    doc = _seal("a")
    assert doc.content_fingerprint == fingerprint({"name": "a"})
    assert doc.artifact_fingerprint == fingerprint(
        {"name": "a", "content_fingerprint": doc.content_fingerprint}
    )


def test_recorded_fingerprints_are_format_checked_and_verified() -> None:
    doc = _seal("a")
    recorded = recorded_fingerprints(doc.to_dict(), ("content_fingerprint", "artifact_fingerprint"))
    verify_fingerprints(doc, recorded, integrity_error=Integrity)
    with pytest.raises(Integrity, match="artifact_fingerprint mismatch"):
        verify_fingerprints(doc, {**recorded, "artifact_fingerprint": "f" * 64}, integrity_error=Integrity)
    with pytest.raises(ValidationError):
        recorded_fingerprints({"content_fingerprint": "nope"}, ("content_fingerprint",))


def test_decode_rejects_non_finite_malformed_and_non_object_documents() -> None:
    assert decode_json_document('{"a": 1}', source_name="x", label="doc") == {"a": 1}
    for text in ('{"a": NaN}', "{", "[1]"):
        with pytest.raises(ValidationError):
            decode_json_document(text, source_name="x", label="doc")


def test_read_artifact_source_accepts_paths_and_mappings(tmp_path: Path) -> None:
    path = tmp_path / "doc.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    assert read_artifact_source(path, label="doc") == ({"a": 1}, str(path), tmp_path)
    assert read_artifact_source({"b": 2}, label="doc") == ({"b": 2}, "in-memory manifest", None)
    with pytest.raises(ValidationError, match="cannot be read"):
        read_artifact_source(tmp_path / "missing.json", label="doc")


def test_immutable_filename_sanitizes_and_refuses_credential_labels() -> None:
    assert immutable_filename("fr day/1", "a" * 64) == f"fr-day-1-{'a' * 64}.json"
    for identity in ("api-token-1", "///"):
        with pytest.raises(ValidationError):
            immutable_filename(identity, "a" * 64)


def test_publish_write_once_reuses_identical_files_and_refuses_changes(tmp_path: Path) -> None:
    target = tmp_path / "doc.json"
    kwargs = dict(
        load_existing=lambda path: path.read_bytes(),
        same_identity=lambda existing: True,
        label="doc",
        validation_error=ValidationError,
        integrity_error=Integrity,
        publication_error=Publication,
    )
    assert publish_write_once(target, b"one", **kwargs) == target
    assert publish_write_once(target, b"one", **kwargs) == target
    with pytest.raises(Integrity, match="differs from requested bytes"):
        publish_write_once(target, b"two", **kwargs)
    assert target.read_bytes() == b"one"


def test_sidecar_locators_resolution_and_bytes(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    sidecar = tmp_path / "raw" / "a.bin"
    sidecar.write_bytes(b"xyz")
    for bad in ("../a", "/abs", "a\\b", "c:d", "a/../b"):
        with pytest.raises(ValidationError):
            safe_sidecar_locator(bad, field_name="loc")
    resolved = resolve_sidecar(tmp_path, "raw/a.bin", validation_error=ValidationError, integrity_error=Integrity)
    assert resolved == sidecar.resolve()
    with pytest.raises(Integrity, match="missing"):
        resolve_sidecar(tmp_path, "raw/b.bin", validation_error=ValidationError, integrity_error=Integrity)
    verify_sidecar_bytes(
        resolved, locator="raw/a.bin", expected_sha256=sha256_hex(b"xyz"), expected_byte_count=3,
        integrity_error=Integrity,
    )
    with pytest.raises(Integrity, match="byte count"):
        verify_sidecar_bytes(
            resolved, locator="raw/a.bin", expected_sha256=sha256_hex(b"xyz"), expected_byte_count=4,
            integrity_error=Integrity,
        )
