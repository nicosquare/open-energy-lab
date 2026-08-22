"""Offline end-to-end contracts for fixture-backed ENTSO-E acquisition."""

from __future__ import annotations

from collections.abc import Mapping
import io
import importlib
from pathlib import Path
import socket
from types import ModuleType
from typing import Any
import urllib.request
import zipfile

import pytest

from open_energy_lab.market.artifact import load_market_data_artifact
from tests.unit.market.test_entsoe_transport import (
    ENDPOINT,
    SENTINEL_TOKEN,
    ScriptedTransport,
    _request,
    _response,
)


FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "market" / "synthetic_entsoe"
SUCCESS_DOCUMENTS = {
    "A44": "a44_success.xml",
    "A81": "a81_success.xml",
}


def _entsoe_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.market.entsoe")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.market.entsoe is not implemented; T020/T021 must "
            "provide the explicit fixture workflow",
            pytrace=False,
        )
        raise AssertionError from exc


def _require(name: str) -> Any:
    module = _entsoe_module()
    try:
        return getattr(module, name)
    except AttributeError:
        pytest.fail(
            f"open_energy_lab.market.entsoe.{name} is not implemented",
            pytrace=False,
        )


def _fixture(name: str) -> bytes:
    return (FIXTURE_ROOT / name).read_bytes()


def _response_for(document_type: str, fixture_name: str):
    body = _fixture(fixture_name)
    if document_type == "A44":
        return _response(body=body)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"r3/{fixture_name}", body)
    return _response(
        body=buffer.getvalue(),
        headers={"Content-Type": "application/zip"},
    )


class FixtureTransport:
    """Route token-separated semantic requests to authored XML documents."""

    def __init__(self, documents: Mapping[str, str] | None = None) -> None:
        self.documents = dict(SUCCESS_DOCUMENTS if documents is None else documents)
        self.calls: list[dict[str, object]] = []

    def request(self, **kwargs: object):
        self.calls.append(kwargs)
        parameters = kwargs["parameters"]
        assert isinstance(parameters, Mapping)
        document_type = parameters["documentType"]
        assert isinstance(document_type, str)
        return _response_for(document_type, self.documents[document_type])


def _fetch(
    destination: Path,
    *,
    transport: object | None = None,
    raw_retention_policy: str = "digest_only",
):
    fetch = _require("fetch_entsoe_market_data")
    return fetch(
        _request(raw_retention_policy=raw_retention_policy),
        api_token=SENTINEL_TOKEN,
        destination_dir=destination,
        transport=FixtureTransport() if transport is None else transport,
    )


def _refresh(destination: Path, current: object, transport: object):
    refresh = _require("refresh_entsoe_market_data")
    return refresh(
        _request(),
        current_artifact=current,
        api_token=SENTINEL_TOKEN,
        destination_dir=destination,
        transport=transport,
    )


def _manifest_paths(destination: Path) -> list[Path]:
    return sorted(destination.glob("*.json"))


def _observable_text(value: object) -> str:
    diagnostic = getattr(value, "diagnostic", None)
    diagnostics = getattr(value, "diagnostics", None)
    return "\n".join((str(value), repr(value), repr(diagnostic), repr(diagnostics)))


def _assert_token_absent_from_tree(root: Path) -> None:
    for path in root.rglob("*"):
        assert SENTINEL_TOKEN not in str(path)
        if path.is_file():
            assert SENTINEL_TOKEN.encode() not in path.read_bytes()


def _assert_workflow_failure_diagnostic(
    error: BaseException,
    *,
    required_series: str,
    observed_resolution: str | None,
) -> None:
    diagnostic = error.diagnostic.to_dict()
    assert diagnostic["source"] == "ENTSO-E Transparency Platform"
    assert diagnostic["required_series"] == required_series
    assert diagnostic["requested_start_utc"] == "2022-08-18T22:00:00Z"
    assert diagnostic["requested_end_utc"] == "2022-08-19T02:00:00Z"
    assert diagnostic["expected_profile"] == "fr-day-ahead-symmetric-fcr-v1"
    assert diagnostic["expected_contract"]
    assert diagnostic["attempt_count"] == 1
    assert diagnostic["final_status"]
    if observed_resolution is not None:
        assert diagnostic["observed_resolution"] == observed_resolution
    text = _observable_text(error)
    assert SENTINEL_TOKEN not in text
    assert "securityToken" not in text
    assert ENDPOINT not in text


def test_fetch_validates_all_series_and_publishes_one_canonical_artifact(
    tmp_path: Path,
) -> None:
    transport = FixtureTransport()

    result = _fetch(tmp_path, transport=transport)

    assert result.outcome == "published"
    assert result.artifact_path.parent == tmp_path
    assert result.artifact_path in _manifest_paths(tmp_path)
    assert result.artifact.artifact_fingerprint in result.artifact_path.name
    assert result.artifact.content_fingerprint
    assert set(result.artifact.series) == {
        "day_ahead_price",
        "fcr_contracted_volume",
        "fcr_capacity_price",
    }
    assert [
        item.value for item in result.artifact.series["day_ahead_price"].observations
    ] == [475.0, -5.0, 540.0, 120.5]
    assert result.artifact.series["fcr_contracted_volume"].observations[0].value == 125.0
    assert result.artifact.series["fcr_capacity_price"].observations[0].value == 17.5
    assert len(result.artifact.query_windows) == 2
    assert all(
        window.start_utc == "2022-08-18T22:00:00Z"
        and window.end_utc == "2022-08-19T22:00:00Z"
        for window in result.artifact.query_windows
    )
    assert len(result.artifact.raw_responses) == 2
    assert len(result.artifact.source_documents) == 2
    assert len(transport.calls) == 2
    assert [call["parameters"]["documentType"] for call in transport.calls] == [
        "A44",
        "A81",
    ]
    assert result.artifact.series["fcr_contracted_volume"].source_document_type == "A81"
    assert result.artifact.series["fcr_capacity_price"].source_document_type == "A81"
    assert result.artifact.source_documents[1].archive_member == "r3/a81_success.xml"
    redistribution = result.artifact.retention_and_license["series_redistribution"]
    assert redistribution["day_ahead_price"]["status"].startswith("local_only")
    assert redistribution["fcr_contracted_volume"]["status"] == "cc-by-4.0"
    assert all(call["api_token"] == SENTINEL_TOKEN for call in transport.calls)
    assert all(
        SENTINEL_TOKEN not in repr(call["parameters"]) for call in transport.calls
    )
    assert all(item.final_outcome == "success" for item in result.attempt_diagnostics)


def test_published_artifact_reloads_offline_with_zero_transport_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = FixtureTransport()
    published = _fetch(tmp_path, transport=transport)
    calls_after_fetch = len(transport.calls)

    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("offline artifact load attempted network access")

    monkeypatch.setattr(socket, "socket", _network_forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", _network_forbidden)

    loaded = load_market_data_artifact(published.artifact_path)

    assert loaded.artifact_fingerprint == published.artifact.artifact_fingerprint
    assert loaded.content_fingerprint == published.artifact.content_fingerprint
    assert len(transport.calls) == calls_after_fetch


@pytest.mark.parametrize(
    ("document_type", "fixture_name", "error_name", "series", "resolution"),
    [
        (
            "A44",
            "a44_gap.xml",
            "EntsoeCoverageError",
            "day_ahead_price",
            "PT1H",
        ),
        (
            "A81",
            "a81_wrong_product.xml",
            "EntsoeProductValidationError",
            "fcr_contracted_volume",
            "PT30M",
        ),
        (
            "A81",
            "a81_missing_price.xml",
            "EntsoeSemanticValidationError",
            "fcr_contracted_volume",
            None,
        ),
        (
            "A81",
            "a81_wrong_unit.xml",
            "EntsoeUnitValidationError",
            "fcr_contracted_volume",
            "PT30M",
        ),
    ],
)
def test_fetch_validates_every_series_in_memory_before_publication(
    tmp_path: Path,
    document_type: str,
    fixture_name: str,
    error_name: str,
    series: str,
    resolution: str | None,
) -> None:
    documents = dict(SUCCESS_DOCUMENTS)
    documents[document_type] = fixture_name
    error_type = _require(error_name)

    with pytest.raises(error_type) as caught:
        _fetch(tmp_path, transport=FixtureTransport(documents))

    assert list(tmp_path.iterdir()) == []
    _assert_workflow_failure_diagnostic(
        caught.value,
        required_series=series,
        observed_resolution=resolution,
    )


def test_permitted_raw_sidecars_are_written_before_and_verified_by_manifest(
    tmp_path: Path,
) -> None:
    result = _fetch(tmp_path, raw_retention_policy="permitted_sidecar")

    retained = result.artifact.raw_responses
    assert all(item.retention_status == "sidecar_retained" for item in retained)
    assert all(item.sidecar_locator and item.sidecar_sha256 for item in retained)
    for evidence in retained:
        assert evidence.sidecar_locator is not None
        sidecar = tmp_path / evidence.sidecar_locator
        assert sidecar.is_file()
        if evidence.media_type == "application/zip":
            with zipfile.ZipFile(sidecar) as archive:
                assert archive.read("r3/a81_success.xml") == _fixture("a81_success.xml")
        else:
            assert sidecar.read_bytes() == _fixture("a44_success.xml")

    loaded = load_market_data_artifact(result.artifact_path, artifact_root=tmp_path)
    assert loaded.artifact_fingerprint == result.artifact.artifact_fingerprint
    assert result.artifact_path.stat().st_mtime_ns >= max(
        (tmp_path / item.sidecar_locator).stat().st_mtime_ns
        for item in retained
        if item.sidecar_locator is not None
    )


def test_unchanged_refresh_writes_nothing_and_preserves_current_identity(
    tmp_path: Path,
) -> None:
    current = _fetch(tmp_path).artifact
    original_paths = _manifest_paths(tmp_path)

    result = _refresh(tmp_path, current, FixtureTransport())

    assert result.outcome == "unchanged"
    assert result.current_artifact_fingerprint == current.artifact_fingerprint
    assert result.returned_content_fingerprint == current.content_fingerprint
    assert result.new_artifact is None
    assert result.new_artifact_path is None
    assert _manifest_paths(tmp_path) == original_paths


def test_changed_refresh_publishes_linked_immutable_successor(tmp_path: Path) -> None:
    current_result = _fetch(tmp_path)
    current_bytes = current_result.artifact_path.read_bytes()
    changed_documents = dict(SUCCESS_DOCUMENTS)
    changed_documents["A44"] = "a44_revision_3.xml"

    result = _refresh(
        tmp_path,
        current_result.artifact,
        FixtureTransport(changed_documents),
    )

    assert result.outcome == "published"
    assert result.new_artifact is not None
    assert result.new_artifact_path is not None
    assert result.new_artifact.predecessor_artifact_fingerprint == (
        current_result.artifact.artifact_fingerprint
    )
    assert result.new_artifact.content_fingerprint != (
        current_result.artifact.content_fingerprint
    )
    assert result.new_artifact.series["day_ahead_price"].observations[0].value == 480.0
    assert len(_manifest_paths(tmp_path)) == 2
    assert current_result.artifact_path.read_bytes() == current_bytes


def test_revision_regression_rejects_candidate_and_preserves_current_artifact(
    tmp_path: Path,
) -> None:
    current_result = _fetch(tmp_path)
    current_bytes = current_result.artifact_path.read_bytes()
    regressed_documents = dict(SUCCESS_DOCUMENTS)
    regressed_documents["A44"] = "a44_revision_1.xml"

    result = _refresh(
        tmp_path,
        current_result.artifact,
        FixtureTransport(regressed_documents),
    )

    assert result.outcome == "revision_regression"
    assert result.current_artifact_fingerprint == current_result.artifact.artifact_fingerprint
    assert result.new_artifact is None
    assert result.new_artifact_path is None
    assert len(_manifest_paths(tmp_path)) == 1
    assert current_result.artifact_path.read_bytes() == current_bytes
    diagnostic_text = repr(result.diagnostics)
    assert "A44" in diagnostic_text
    assert "current_revision" in diagnostic_text
    assert "returned_revision" in diagnostic_text
    assert "2" in diagnostic_text and "1" in diagnostic_text
    assert SENTINEL_TOKEN not in diagnostic_text


def test_atomic_manifest_failure_leaves_no_candidate_or_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    publication_error = _require("EntsoePublicationError")
    artifact_module = importlib.import_module("open_energy_lab.market.artifact")

    def _fail_replace(source: object, destination: object) -> None:
        raise OSError("injected atomic publication failure")

    monkeypatch.setattr(artifact_module.os, "replace", _fail_replace)

    with pytest.raises(publication_error, match="publish|atomic|artifact") as caught:
        _fetch(tmp_path)

    assert list(tmp_path.iterdir()) == []
    assert SENTINEL_TOKEN not in _observable_text(caught.value)
    assert "securityToken" not in _observable_text(caught.value)


def test_transient_exhaustion_publishes_nothing_and_reports_attempts(
    tmp_path: Path,
) -> None:
    exhausted_error = _require("EntsoeTransientExhaustedError")
    transport = ScriptedTransport([_response(503), _response(503), _response(503)])

    with pytest.raises(exhausted_error) as caught:
        _fetch(tmp_path, transport=transport)

    assert list(tmp_path.iterdir()) == []
    assert len(caught.value.diagnostics) == 3
    assert [item.attempt for item in caught.value.diagnostics] == [1, 2, 3]
    assert caught.value.diagnostics[-1].final_outcome == "transient_exhausted"
    assert SENTINEL_TOKEN not in _observable_text(caught.value)
    assert ENDPOINT not in _observable_text(caught.value)


def test_sentinel_token_never_appears_in_outputs_files_logs_or_failures(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    result = _fetch(tmp_path / "success")
    bad_documents = dict(SUCCESS_DOCUMENTS)
    bad_documents["A81"] = "a81_wrong_product.xml"
    product_error = _require("EntsoeProductValidationError")

    with pytest.raises(product_error) as caught:
        _fetch(tmp_path / "failure", transport=FixtureTransport(bad_documents))

    captured = capsys.readouterr()
    assert SENTINEL_TOKEN not in repr(result)
    assert SENTINEL_TOKEN not in repr(result.artifact.to_dict())
    assert SENTINEL_TOKEN not in _observable_text(caught.value)
    assert SENTINEL_TOKEN not in captured.out
    assert SENTINEL_TOKEN not in captured.err
    assert SENTINEL_TOKEN not in caplog.text
    _assert_token_absent_from_tree(tmp_path)
