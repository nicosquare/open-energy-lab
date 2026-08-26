from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
from pathlib import Path

import pytest

from open_energy_lab.market.reference_fcr import (
    ExternalReferenceDataError,
    load_golden_reference_fixture,
    load_reference_activation_trace,
)


FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)
HEADER = "DateTime,Frequency (Hz),xi,xi_EU"


@lru_cache(maxsize=4)
def _csv_bytes(day: str = "2023-06-18", header: str = HEADER) -> bytes:
    start = datetime.fromisoformat(f"{day}T00:00:00")
    rows = [header]
    for index in range(8640):
        timestamp = start + timedelta(seconds=10 * index)
        rows.append(f"{timestamp:%Y-%m-%d %H:%M:%S},50.0,0.1,0.1")
    return ("\n".join(rows) + "\n").encode("utf-8")


def _descriptor(data: bytes):
    fixture = load_golden_reference_fixture(FIXTURE_PATH)
    return replace(
        fixture.external_activation,
        byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def test_explicit_loader_constructs_exact_pt10s_trace(tmp_path: Path) -> None:
    data = _csv_bytes()
    path = _write(tmp_path / "regulation_signal.csv", data)
    descriptor = _descriptor(data)

    first = load_reference_activation_trace(path, descriptor=descriptor)
    repeated = load_reference_activation_trace(path, descriptor=descriptor)

    assert len(first.samples) == 8640
    assert first.resolution == "PT10S"
    assert first.samples[0].interval.local_start.isoformat() == (
        "2023-06-18T00:00:00+02:00"
    )
    assert first.samples[-1].interval.local_start.isoformat() == (
        "2023-06-18T23:59:50+02:00"
    )
    assert first.samples[0].activation == 0.1
    assert first.artifact_fingerprint == repeated.artifact_fingerprint


def test_loader_missing_path_is_actionable_and_does_not_search_or_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = _csv_bytes()
    descriptor = _descriptor(data)
    monkeypatch.setenv(
        "OPEN_ENERGY_LAB_REFERENCE_ACTIVATION",
        "baselines/robust_storage_bidding/data/regulation_signal.csv",
    )

    with pytest.raises(ExternalReferenceDataError) as exc_info:
        load_reference_activation_trace(
            tmp_path / "caller-selected-missing.csv",
            descriptor=descriptor,
        )

    message = str(exc_info.value)
    assert descriptor.download_url in message
    assert descriptor.local_relative_path in message
    assert "caller-selected-missing.csv" in message
    assert "download" in message.casefold()
    assert "explicit" in message.casefold()


def test_loader_does_not_treat_a_same_named_misplaced_file_as_installed(
    tmp_path: Path,
) -> None:
    data = _csv_bytes()
    descriptor = _descriptor(data)
    misplaced = tmp_path / "elsewhere" / "regulation_signal.csv"
    misplaced.parent.mkdir(parents=True, exist_ok=True)
    _write(misplaced, data)

    requested = tmp_path / descriptor.local_relative_path
    with pytest.raises(ExternalReferenceDataError) as exc_info:
        load_reference_activation_trace(requested, descriptor=descriptor)

    message = str(exc_info.value)
    assert requested.as_posix() in message
    assert descriptor.local_relative_path in message


def test_loader_rejects_wrong_byte_count_before_parsing(tmp_path: Path) -> None:
    data = _csv_bytes()
    path = _write(tmp_path / "wrong-size.csv", data)
    descriptor = replace(_descriptor(data), byte_count=len(data) + 1)

    with pytest.raises(ExternalReferenceDataError, match="byte count"):
        load_reference_activation_trace(path, descriptor=descriptor)


def test_loader_rejects_wrong_digest_before_parsing(tmp_path: Path) -> None:
    data = _csv_bytes()
    path = _write(tmp_path / "wrong-digest.csv", data)
    descriptor = replace(_descriptor(data), sha256="0" * 64)

    with pytest.raises(ExternalReferenceDataError, match="SHA-256"):
        load_reference_activation_trace(path, descriptor=descriptor)


def test_loader_rejects_wrong_header(tmp_path: Path) -> None:
    data = _csv_bytes(header="DateTime,Frequency (Hz),xi,wrong")
    path = _write(tmp_path / "wrong-header.csv", data)

    with pytest.raises(ExternalReferenceDataError, match="header"):
        load_reference_activation_trace(path, descriptor=_descriptor(data))


def test_loader_rejects_wrong_selected_column(tmp_path: Path) -> None:
    data = _csv_bytes()
    path = _write(tmp_path / "wrong-column.csv", data)
    descriptor = replace(_descriptor(data), selected_column="not_present")

    with pytest.raises(ExternalReferenceDataError, match="selected column"):
        load_reference_activation_trace(path, descriptor=descriptor)


@pytest.mark.parametrize("kind", ("duplicate", "gap", "overlap"))
def test_loader_rejects_duplicate_gap_and_overlap_timestamps(
    tmp_path: Path,
    kind: str,
) -> None:
    rows = _csv_bytes().decode("utf-8").splitlines()
    row_index = 101
    columns = rows[row_index].split(",")
    timestamp = datetime.strptime(columns[0], "%Y-%m-%d %H:%M:%S")
    if kind == "duplicate":
        replacement = datetime.strptime(
            rows[row_index - 1].split(",")[0], "%Y-%m-%d %H:%M:%S"
        )
    elif kind == "gap":
        replacement = timestamp + timedelta(seconds=10)
    else:
        replacement = timestamp - timedelta(seconds=5)
    columns[0] = replacement.strftime("%Y-%m-%d %H:%M:%S")
    rows[row_index] = ",".join(columns)
    data = ("\n".join(rows) + "\n").encode("utf-8")
    path = _write(tmp_path / f"{kind}.csv", data)

    with pytest.raises(
        ExternalReferenceDataError,
        match="duplicate, gap, overlap, or out-of-order",
    ):
        load_reference_activation_trace(path, descriptor=_descriptor(data))


def test_loader_rejects_nonfinite_selected_values(tmp_path: Path) -> None:
    rows = _csv_bytes().decode("utf-8").splitlines()
    columns = rows[100].split(",")
    columns[-1] = "NaN"
    rows[100] = ",".join(columns)
    data = ("\n".join(rows) + "\n").encode("utf-8")
    path = _write(tmp_path / "nonfinite.csv", data)

    with pytest.raises(ExternalReferenceDataError, match="nonfinite"):
        load_reference_activation_trace(path, descriptor=_descriptor(data))


def test_loader_rejects_a_file_without_the_declared_date(tmp_path: Path) -> None:
    data = _csv_bytes(day="2023-06-17")
    path = _write(tmp_path / "wrong-date.csv", data)

    with pytest.raises(ExternalReferenceDataError, match="selected row count 0"):
        load_reference_activation_trace(path, descriptor=_descriptor(data))
