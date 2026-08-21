"""Explicitly fetch or refresh a canonical French ENTSO-E market artifact."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import sys
from typing import Sequence

from open_energy_lab.market.artifact import (
    MarketArtifactValidationError,
    load_market_data_artifact,
)
from open_energy_lab.market.entsoe import (
    DEFAULT_ENTSOE_ENDPOINT,
    EntsoeAcquisitionError,
    EntsoeMarketDataRequest,
    MarketDataFetchResult,
    MarketDataRefreshResult,
    fetch_entsoe_market_data,
    refresh_entsoe_market_data,
)


def _utc_instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 aware UTC timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 aware UTC timestamp with Z or +00:00"
        )
    return parsed.astimezone(UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Explicitly acquire complete France A44/A81/A89 market data and "
            "publish a validated immutable artifact."
        )
    )
    parser.add_argument("--mode", choices=("fetch", "refresh"), required=True)
    parser.add_argument("--start", type=_utc_instant, required=True)
    parser.add_argument("--end", type=_utc_instant, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--current",
        type=Path,
        help="current immutable artifact path; required only for refresh",
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENTSOE_ENDPOINT,
        help="HTTPS ENTSO-E origin and path without query parameters",
    )
    parser.add_argument(
        "--raw-retention",
        choices=("digest_only", "permitted_sidecar"),
        default="digest_only",
        help="retain response digests only unless raw sidecar reuse is permitted",
    )
    parser.add_argument(
        "--normalization-version",
        default="entsoe-fr-v1",
        help="non-empty producer normalization version recorded in the artifact",
    )
    return parser


def _request_from_args(args: argparse.Namespace) -> EntsoeMarketDataRequest:
    return EntsoeMarketDataRequest(
        requested_start_utc=args.start,
        requested_end_utc=args.end,
        source_endpoint=args.endpoint,
        raw_retention_policy=args.raw_retention,
        normalization_version=args.normalization_version,
    )


def _print_fetch_result(result: MarketDataFetchResult) -> None:
    revisions = ",".join(
        f"{document.document_type}:r{document.revision_number}"
        for document in result.artifact.source_documents
        if document.status == "selected"
    )
    print(f"outcome={result.outcome}")
    print(f"artifact={result.artifact_path}")
    print(f"content_fingerprint={result.artifact.content_fingerprint}")
    print(f"source_documents={revisions}")


def _print_refresh_result(result: MarketDataRefreshResult) -> None:
    print(f"outcome={result.outcome}")
    print(f"current_artifact_fingerprint={result.current_artifact_fingerprint}")
    if result.returned_content_fingerprint is not None:
        print(f"returned_content_fingerprint={result.returned_content_fingerprint}")
    if result.new_artifact_path is not None:
        print(f"artifact={result.new_artifact_path}")
    if result.outcome == "revision_regression":
        for diagnostic in result.diagnostics:
            if not isinstance(diagnostic, dict) and not hasattr(diagnostic, "get"):
                continue
            if diagnostic.get("final_status") != "revision_regression":
                continue
            print(
                "revision_regression="
                f"{diagnostic.get('document_type')}:"
                f"{diagnostic.get('current_revision')}->"
                f"{diagnostic.get('returned_revision')}"
            )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.mode == "refresh" and args.current is None:
        parser.error("--current is required when --mode refresh is selected")
    if args.mode == "fetch" and args.current is not None:
        parser.error("--current is valid only when --mode refresh is selected")

    try:
        request = _request_from_args(args)
        current_artifact = (
            load_market_data_artifact(args.current)
            if args.mode == "refresh"
            else None
        )
    except (ValueError, OSError, MarketArtifactValidationError) as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2

    # This is the only credential read. It occurs immediately before the
    # explicitly selected source operation and never enters the request value.
    api_token = os.environ.get("ENTSOE_API_TOKEN", "").strip()
    if not api_token:
        print(
            "acquisition requires ENTSOE_API_TOKEN in the environment",
            file=sys.stderr,
        )
        return 2

    try:
        if args.mode == "fetch":
            result = fetch_entsoe_market_data(
                request,
                api_token=api_token,
                destination_dir=args.destination,
            )
            _print_fetch_result(result)
        else:
            assert current_artifact is not None
            refresh_result = refresh_entsoe_market_data(
                request,
                current_artifact=current_artifact,
                api_token=api_token,
                destination_dir=args.destination,
            )
            _print_refresh_result(refresh_result)
    except EntsoeAcquisitionError as exc:
        print(f"acquisition failed: {exc}", file=sys.stderr)
        return 1
    finally:
        api_token = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
