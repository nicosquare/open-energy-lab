"""Stage the validated French market fixture in a restricted private repository.

This operation performs no network access and never reads an ENTSO-E token. It
does not claim or grant public redistribution rights. The caller must explicitly
confirm that the repository is private and that access is restricted to
authorized collaborators; the resulting metadata prohibits public publication,
forks, mirrors, packages, releases, and other external distribution.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile

from open_energy_lab.market import (
    FRANCE_AREA_EIC,
    FRANCE_PROFILE_ID,
    MarketArtifactValidationError,
    MarketDataArtifact,
    build_market_data_artifact,
    load_market_data_artifact,
)


REFERENCE_START_UTC = "2022-08-18T22:00:00Z"
REFERENCE_END_UTC = "2022-08-19T22:00:00Z"
REFERENCE_MARKET_FILENAME = "france_2022-08-19_market_v1.json"
PRIVATE_STORAGE_STATUS = "permitted_private_restricted"
PRIVATE_POLICY_VERSION = "oel.restricted-private-fixture.v1"


class PrivateFixtureStagingError(ValueError):
    """Raised when the restricted private-repository boundary is not proven."""


def _z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _restricted_policy() -> dict[str, object]:
    return {
        "policy_version": PRIVATE_POLICY_VERSION,
        "repository_visibility": "private",
        "authorized_audience": "repository collaborators",
        "repository_storage": "permitted",
        "public_distribution": "prohibited",
        "public_forks_and_mirrors": "prohibited",
        "package_distribution": "prohibited",
        "release_attachment": "prohibited",
        "external_artifact_upload": "prohibited",
        "visibility_change_action": (
            "remove restricted fixtures before making the repository public"
        ),
        "basis": "repository owner confirmed private restricted use on 2026-08-22",
    }


def _require_reference_scope(market: MarketDataArtifact) -> None:
    if (
        market.profile_id != FRANCE_PROFILE_ID
        or market.area.get("eic") != FRANCE_AREA_EIC
    ):
        raise PrivateFixtureStagingError(
            "market artifact is not the closed Feature 010 France profile"
        )
    start = _z(market.requested_period.start_utc)
    end = _z(market.requested_period.end_utc)
    if start != REFERENCE_START_UTC or end != REFERENCE_END_UTC:
        raise PrivateFixtureStagingError(
            "market artifact is not the exact Feature 010 reference period"
        )
    if (
        _z(market.actual_covered_period.start_utc) != REFERENCE_START_UTC
        or _z(market.actual_covered_period.end_utc) != REFERENCE_END_UTC
    ):
        raise PrivateFixtureStagingError(
            "market artifact actual coverage must equal the reference period"
        )
    if len(market.series["day_ahead_price"].observations) != 24:
        raise PrivateFixtureStagingError(
            "reference market artifact must contain 24 hourly A44 values"
        )
    if any(
        len(market.series[series_id].observations) != 6
        for series_id in ("fcr_contracted_volume", "fcr_capacity_price")
    ):
        raise PrivateFixtureStagingError(
            "reference market artifact must contain six aligned A81 blocks"
        )
    if any(item.retention_status != "digest_only" for item in market.raw_responses):
        raise PrivateFixtureStagingError(
            "restricted repository staging permits digest-only raw evidence"
        )


def stage_private_reference_market_artifact(
    market: MarketDataArtifact,
    *,
    private_repository_acknowledged: bool,
) -> MarketDataArtifact:
    """Record restricted private storage without changing normalized content."""

    if not isinstance(market, MarketDataArtifact):
        raise TypeError("market must be a MarketDataArtifact")
    if private_repository_acknowledged is not True:
        raise PrivateFixtureStagingError(
            "private restricted repository storage must be explicitly acknowledged"
        )
    verified = MarketDataArtifact.from_dict(market.to_dict())
    _require_reference_scope(verified)

    existing_policy = verified.retention_and_license.get(
        "restricted_repository_policy"
    )
    if (
        verified.retention_and_license.get("repository_storage")
        == PRIVATE_STORAGE_STATUS
        and existing_policy == _restricted_policy()
        and verified.retention_and_license.get("repository_publication")
        == "prohibited"
    ):
        return verified

    payload = verified.to_dict()
    payload["predecessor_artifact_fingerprint"] = verified.artifact_fingerprint
    retention = dict(verified.retention_and_license)
    retention["series_redistribution"] = {
        "day_ahead_price": {
            "status": "restricted_private_repository_only",
            "source_document_type": "A44",
        },
        "fcr_contracted_volume": {
            "status": "cc-by-4.0",
            "source_document_type": "A81",
        },
        "fcr_capacity_price": {
            "status": "cc-by-4.0",
            "source_document_type": "A81",
        },
    }
    retention["repository_storage"] = PRIVATE_STORAGE_STATUS
    retention["repository_publication"] = "prohibited"
    retention["restricted_repository_policy"] = _restricted_policy()
    payload["retention_and_license"] = retention
    staged = build_market_data_artifact(payload)
    if staged.content_fingerprint != verified.content_fingerprint:
        raise PrivateFixtureStagingError(
            "private staging unexpectedly changed normalized market content"
        )
    return staged


def _manifest_bytes(artifact: MarketDataArtifact) -> bytes:
    try:
        return (
            json.dumps(
                artifact.to_dict(),
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PrivateFixtureStagingError(
            "restricted market fixture could not be serialized"
        ) from exc


def _write_fixed_manifest(
    artifact: MarketDataArtifact,
    *,
    destination_dir: str | os.PathLike[str],
) -> Path:
    destination = Path(destination_dir)
    output = destination / REFERENCE_MARKET_FILENAME
    desired = _manifest_bytes(artifact)
    try:
        destination.mkdir(parents=True, exist_ok=True)
        if output.exists():
            existing = load_market_data_artifact(output)
            if (
                existing.artifact_fingerprint != artifact.artifact_fingerprint
                or output.read_bytes() != desired
            ):
                raise PrivateFixtureStagingError(
                    "existing fixed private market fixture differs from staged bytes"
                )
            return output
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{REFERENCE_MARKET_FILENAME}.",
            suffix=".tmp",
            dir=destination,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(desired)
                handle.flush()
                os.fsync(handle.fileno())
            if output.exists():
                raise PrivateFixtureStagingError(
                    "fixed private market fixture appeared during staging"
                )
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    except PrivateFixtureStagingError:
        raise
    except (OSError, MarketArtifactValidationError) as exc:
        raise PrivateFixtureStagingError(
            "restricted reference market fixture could not be staged atomically"
        ) from exc
    return output


def write_private_reference_market_fixture(
    market_path: str | os.PathLike[str],
    *,
    private_repository_acknowledged: bool,
    destination_dir: str | os.PathLike[str],
) -> Path:
    """Stage the fixed fixture after an explicit private-repository assertion."""

    market = load_market_data_artifact(market_path)
    staged = stage_private_reference_market_artifact(
        market,
        private_repository_acknowledged=private_repository_acknowledged,
    )
    return _write_fixed_manifest(staged, destination_dir=destination_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--acknowledge-private-restricted-repository",
        action="store_true",
        help=(
            "confirm that repository access is private/restricted and the "
            "fixture will not be packaged, released, mirrored, or made public"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = write_private_reference_market_fixture(
            args.market,
            private_repository_acknowledged=(
                args.acknowledge_private_restricted_repository
            ),
            destination_dir=args.destination,
        )
        artifact = load_market_data_artifact(output)
    except (
        OSError,
        PrivateFixtureStagingError,
        MarketArtifactValidationError,
    ) as exc:
        print(f"private fixture staging failed: {exc}", file=sys.stderr)
        return 2
    print(f"market_fixture={output}")
    print(f"content_fingerprint={artifact.content_fingerprint}")
    print(f"artifact_fingerprint={artifact.artifact_fingerprint}")
    print(f"repository_storage={PRIVATE_STORAGE_STATUS}")
    print("repository_publication=prohibited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
