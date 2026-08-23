"""Explicitly fetch or refresh one canonical French RTE restoration artifact."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import sys

from open_energy_lab.market.restoration_artifact import (
    RestorationArtifactPublicationError,
    RestorationArtifactValidationError,
    load_restoration_market_artifact,
)
from open_energy_lab.market.rte import (
    RTE_PROFILES,
    RTEAuthenticationError,
    RTEParseError,
    RTERequestValidationError,
    RTETransportError,
    RestorationFetchResult,
    RestorationRefreshResult,
    build_rte_restoration_request,
    fetch_rte_restoration_data,
    refresh_rte_restoration_data,
)


_DOTENV_ALLOWLIST = frozenset(
    {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}
)
_RTE_CREDENTIAL_KEYS = ("RTE_CLIENT_ID", "RTE_CLIENT_SECRET")


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
            "Explicitly acquire one bounded RTE Balancing Energy v5.2 aFRR or "
            "mFRR period and publish a validated immutable artifact."
        )
    )
    parser.add_argument(
        "--resource",
        choices=tuple(RTE_PROFILES),
        required=True,
        help="closed RTE v5.2 restoration resource",
    )
    parser.add_argument("--start-utc", type=_utc_instant, required=True)
    parser.add_argument("--end-utc", type=_utc_instant, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--refresh-from",
        type=Path,
        help=(
            "existing immutable artifact to refresh; omission selects a new fetch"
        ),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help=(
            "strict local dotenv source used only for missing exported RTE "
            "credentials (default: .env)"
        ),
    )
    parser.add_argument(
        "--raw-retention",
        choices=("digest_only", "permitted_sidecar"),
        default="digest_only",
        help="record response digests only unless restricted sidecars are permitted",
    )
    parser.add_argument(
        "--normalization-version",
        default="rte-balancing-energy-v5.2-v1",
        help="non-empty normalization version recorded in the artifact",
    )
    return parser


def _read_dotenv_values(
    path: Path, *, requested_keys: Sequence[str]
) -> dict[str, str]:
    """Read a strict, non-interpolating dotenv subset without mutating env."""

    requested = tuple(requested_keys)
    if not requested or any(key not in _DOTENV_ALLOWLIST for key in requested):
        raise ValueError("dotenv requested keys must be non-empty and allowlisted")
    if len(set(requested)) != len(requested):
        raise ValueError("dotenv requested keys must be unique")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"could not read dotenv file {path}") from exc

    values: dict[str, str] = {}
    seen: set[str] = set()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").lstrip()
        key, separator, raw_value = line.partition("=")
        if not separator:
            raise ValueError(
                f"dotenv declaration on line {line_number} must use KEY=VALUE"
            )
        key = key.strip()
        if key not in _DOTENV_ALLOWLIST:
            raise ValueError(
                f"dotenv declaration on line {line_number} is not allowlisted"
            )
        if key in seen:
            raise ValueError(f"dotenv file contains duplicate {key} declarations")
        seen.add(key)

        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        elif value.startswith(("'", '"')) or value.endswith(("'", '"')):
            raise ValueError(
                f"dotenv declaration for {key} on line {line_number} has "
                "unmatched quotes"
            )
        value = value.strip()
        if not value:
            raise ValueError(
                f"dotenv declaration for {key} must be non-empty"
            )
        if key in requested:
            values[key] = value
    return values


def _rte_credentials(env_file: Path) -> tuple[str, str]:
    """Resolve RTE credentials with exported values taking per-key precedence."""

    exported = {
        key: os.environ.get(key, "").strip() for key in _RTE_CREDENTIAL_KEYS
    }
    if all(exported.values()):
        return exported["RTE_CLIENT_ID"], exported["RTE_CLIENT_SECRET"]

    from_file = _read_dotenv_values(env_file, requested_keys=_RTE_CREDENTIAL_KEYS)
    resolved = {
        key: exported[key] or from_file.get(key, "") for key in _RTE_CREDENTIAL_KEYS
    }
    missing = [key for key in _RTE_CREDENTIAL_KEYS if not resolved[key]]
    if missing:
        raise ValueError(
            "explicit RTE acquisition requires both RTE_CLIENT_ID and "
            "RTE_CLIENT_SECRET in exported environment values or the selected "
            "dotenv file"
        )
    return resolved["RTE_CLIENT_ID"], resolved["RTE_CLIENT_SECRET"]


def _request_from_args(args: argparse.Namespace):
    profile = RTE_PROFILES[args.resource]
    mode = "REFRESH" if args.refresh_from is not None else "FETCH"
    return build_rte_restoration_request(
        resource=profile.resource,
        requested_start_utc=args.start_utc,
        requested_end_utc=args.end_utc,
        requested_series_ids=profile.series_ids,
        required_series_ids=profile.required_series_ids,
        normalization_version=args.normalization_version,
        raw_retention_policy=args.raw_retention.upper(),
        mode=mode,
    )


def _print_fetch_result(result: RestorationFetchResult) -> None:
    print("outcome=created")
    print(f"artifact={result.path}")
    print(f"content_fingerprint={result.artifact.content_fingerprint}")
    print(f"artifact_fingerprint={result.artifact.artifact_fingerprint}")


def _print_refresh_result(result: RestorationRefreshResult) -> None:
    print(f"outcome={result.status.value.lower()}")
    print(f"artifact_fingerprint={result.artifact.artifact_fingerprint}")
    if result.path is not None:
        print(f"artifact={result.path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)

    try:
        request = _request_from_args(args)
        current_artifact = (
            load_restoration_market_artifact(args.refresh_from)
            if args.refresh_from is not None
            else None
        )
    except (OSError, RTERequestValidationError, RestorationArtifactValidationError) as exc:
        print(f"input validation failed: {exc}", file=sys.stderr)
        return 2

    # The script import and all offline library paths remain credential-free.
    # This explicit operation boundary is the only environment/dotenv read.
    try:
        client_id, client_secret = _rte_credentials(args.env_file)
    except ValueError as exc:
        print(f"credential loading failed: {exc}", file=sys.stderr)
        return 2

    try:
        if current_artifact is None:
            result = fetch_rte_restoration_data(
                request,
                client_id=client_id,
                client_secret=client_secret,
                output_directory=args.output_dir,
            )
            _print_fetch_result(result)
        else:
            refresh_result = refresh_rte_restoration_data(
                current_artifact,
                request,
                client_id=client_id,
                client_secret=client_secret,
                output_directory=args.output_dir,
            )
            _print_refresh_result(refresh_result)
    except (
        RTEAuthenticationError,
        RTETransportError,
        RTEParseError,
        RTERequestValidationError,
        RestorationArtifactValidationError,
        RestorationArtifactPublicationError,
    ) as exc:
        print(f"acquisition failed: {exc}", file=sys.stderr)
        return 1
    finally:
        client_id = ""
        client_secret = ""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
