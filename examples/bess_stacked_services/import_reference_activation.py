"""Explicitly import the pinned RTE frequency file into a canonical trace."""

from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from open_energy_lab.market import (
    ACTIVATION_SIGN_SEMANTICS,
    ActivationImportRequest,
    RegulationActivationTrace,
    import_regulation_activation_trace,
    write_regulation_activation_trace,
)


REFERENCE_COMMIT = "7e44738bb30e5c8204efe40103b9be4c2203685c"
REFERENCE_PATH = "data_processing/freq_data/RTE_Frequence_2022_08.txt"
REFERENCE_LOCATOR = f"lauinger/robust-storage-bidding@{REFERENCE_COMMIT}:{REFERENCE_PATH}"
SOURCE_TIMEZONE = "Europe/Paris"
EXPECTED_HEADER = ("DATE", "FREQUENCE_RETENUE(EN Hz)")


class ReferenceActivationImportError(ValueError):
    """Raised when the caller-supplied reference file fails provenance checks."""


def _utc_timestamp(value: str, *, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReferenceActivationImportError(
            f"{field_name} must be an ISO 8601 UTC timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReferenceActivationImportError(f"{field_name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _verify_digest(path: Path, expected_sha256: str) -> str:
    if len(expected_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha256
    ):
        raise ReferenceActivationImportError(
            "expected_sha256 must be a lowercase SHA-256 digest"
        )
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise ReferenceActivationImportError(
            f"raw RTE file SHA-256 mismatch: expected {expected_sha256}, got {actual}"
        )
    return actual


def _selected_samples(
    path: Path,
    *,
    start_utc: datetime,
    end_utc: datetime,
) -> list[dict[str, object]]:
    zone = ZoneInfo(SOURCE_TIMEZONE)
    selected: list[dict[str, object]] = []
    try:
        handle = path.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ReferenceActivationImportError(f"cannot open input file {path}") from exc
    with handle:
        reader = csv.reader(handle, delimiter=";")
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ReferenceActivationImportError("raw RTE file is empty") from exc
        normalized_header = tuple(item.strip() for item in header if item.strip())
        if normalized_header != EXPECTED_HEADER:
            raise ReferenceActivationImportError(
                f"unexpected raw RTE header {normalized_header!r}"
            )
        for line_number, row in enumerate(reader, start=2):
            values = [item.strip() for item in row if item.strip()]
            if not values:
                continue
            if len(values) != 2:
                raise ReferenceActivationImportError(
                    f"line {line_number} must contain one timestamp and frequency"
                )
            try:
                timestamp = datetime.strptime(values[0], "%d/%m/%Y %H:%M:%S")
                frequency_hz = float(values[1].replace(",", "."))
            except ValueError as exc:
                raise ReferenceActivationImportError(
                    f"line {line_number} contains an invalid timestamp or frequency"
                ) from exc
            instant_utc = timestamp.replace(tzinfo=zone).astimezone(UTC)
            if start_utc <= instant_utc < end_utc:
                selected.append(
                    {
                        "timestamp": timestamp,
                        "value": frequency_hz,
                        "source_unit": "Hz",
                    }
                )
    return selected


def import_reference_activation(
    input_path: str | Path,
    *,
    expected_sha256: str,
    source_revision: str,
    start_utc: datetime,
    end_utc: datetime,
    created_at_utc: datetime,
) -> RegulationActivationTrace:
    """Verify and normalize one caller-supplied pinned RTE frequency file."""

    path = Path(input_path)
    digest = _verify_digest(path, expected_sha256)
    if source_revision != REFERENCE_COMMIT:
        raise ReferenceActivationImportError(
            f"source_revision must identify pinned commit {REFERENCE_COMMIT}"
        )
    samples = _selected_samples(path, start_utc=start_utc, end_utc=end_utc)
    request = ActivationImportRequest(
        source_name="RTE France grid frequency via robust-storage-bidding",
        source_locator=REFERENCE_LOCATOR,
        source_revision=source_revision,
        source_sha256=digest,
        source_timezone=SOURCE_TIMEZONE,
        requested_start_utc=start_utc,
        requested_end_utc=end_utc,
        source_resolution="PT10S",
        source_value_kind="instantaneous_left_hold",
        source_sign_meaning=(
            "lower grid frequency requests upward/discharge response after droop normalization"
        ),
        normalization_rule={
            "conversion": "clip_linear_frequency_droop",
            "formula": "clip((50.0 - frequency_hz) / 0.2, -1, 1)",
            "point_to_interval": "instantaneous_left_hold",
            "nominal_frequency_hz": 50.0,
            "full_activation_deviation_hz": 0.2,
            "clip_min": -1.0,
            "clip_max": 1.0,
            "target_sign": ACTIVATION_SIGN_SEMANTICS,
        },
        redistribution_basis={
            "source": "RTE France public grid-frequency data",
            "source_terms": "RTE Services Portal General Terms of Service, Article 9",
            "source_terms_url": (
                "https://www.services-rte.com/en/general-terms-and-conditions-of-use.html"
            ),
            "attribution": "Source: RTE Réseau de Transport d'Électricité",
            "reference_repository_license": "MIT",
            "raw_file_retained": False,
            "transformation": (
                "selected timestamps only; no gap filling or duplicate removal; "
                "frequency droop normalization and explicit 10-second left hold"
            ),
        },
    )
    return import_regulation_activation_trace(
        request,
        samples,
        trace_id="france-2022-08-19-rte-activation-v1",
        created_at_utc=created_at_utc,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a caller-supplied pinned RTE frequency file"
    )
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument(
        "--created-at",
        default=None,
        help="optional deterministic UTC creation timestamp",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        start = _utc_timestamp(args.start, field_name="start")
        end = _utc_timestamp(args.end, field_name="end")
        created_at = (
            datetime.now(UTC)
            if args.created_at is None
            else _utc_timestamp(args.created_at, field_name="created_at")
        )
        trace = import_reference_activation(
            args.input,
            expected_sha256=args.expected_sha256,
            source_revision=args.source_revision,
            start_utc=start,
            end_utc=end,
            created_at_utc=created_at,
        )
        output = write_regulation_activation_trace(
            trace,
            destination_dir=args.destination,
        )
    except (OSError, ValueError) as exc:
        print(f"reference activation import failed: {exc}", file=sys.stderr)
        return 2
    print(output)
    print(f"samples={len(trace.samples)}")
    print(f"source_sha256={trace.source['sha256']}")
    print(f"content_fingerprint={trace.content_fingerprint}")
    print(f"artifact_fingerprint={trace.artifact_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
