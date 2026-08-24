"""Stage the two verified RTE references into fixed restricted fixture paths.

This command performs no acquisition, imports no live adapter, and reads no
credential or dotenv value.  It consumes two already acquired, fully validated
restoration artifacts and publishes normalized manifests only.  The fixed
outputs remain restricted to authorized collaborators in the private
repository and are never suitable for packages, releases, public CI artifacts,
mirrors, or external artifact stores.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from open_energy_lab.market.restoration_artifact import (
    ObservationValueState,
    RestorationArtifactValidationError,
    RestorationDataSource,
    RestorationMarketArtifact,
    SeriesAvailability,
    load_restoration_market_artifact,
)
from open_energy_lab.market.rte import (
    RTE_AFRR_PROFILE,
    RTE_CATALOG_VERSION,
    RTE_EXPECTED_RESOLUTION,
    RTE_MFRR_PROFILE,
)


AFRR_REFERENCE_FILENAME = "france_2026-08-20_afrr_market_v1.json"
MFRR_REFERENCE_FILENAME = "france_2026-08-15_mfrr_market_v1.json"
AFRR_PLANNING_RAW_SHA256 = (
    "d2496d713c7f217ff76487db2aba0b7a49479861118bea61ca3c001fbbfe2eb3"
)
MFRR_PLANNING_RAW_SHA256 = (
    "ce9d3c3d694a78776e5bdb188239f9b2ed4b711e3c389d0e89c8a47e5391d1a1"
)
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_RELATIVE_DIRECTORY = Path("tests/fixtures/restoration")
_AFRR_START = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
_AFRR_END = datetime(2026, 8, 20, 1, 0, tzinfo=UTC)
_MFRR_START = datetime(2026, 8, 15, 10, 15, tzinfo=UTC)
_MFRR_END = datetime(2026, 8, 15, 10, 30, tzinfo=UTC)
_EXPECTED_TRANSFORMATIONS = ("rte-v5.2-chronological-row-order",)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_TARGET_PARTS = frozenset(
    {
        "artifacts",
        "ci-artifacts",
        "dist",
        "distribution",
        "external-store",
        "mirror",
        "mirrors",
        "public",
        "release",
        "releases",
    }
)
_FORBIDDEN_PERSISTED_MARKERS = (
    b'"access_token"',
    b'"authorization"',
    b'"body"',
    b'"client_secret"',
    b'"mari"',
    b'"mari_mesures"',
    b'"oauth_response"',
    b'"picasso"',
    b'"picasso_mesures"',
    b"basic ",
    b"bearer ",
)
_REQUIRED_POLICY = {
    "repository_storage": "permitted_private_restricted",
    "repository_publication": "prohibited",
    "package_distribution": "prohibited",
    "release_distribution": "prohibited",
    "public_ci_artifact": "prohibited",
    "public_mirror_or_fork": "prohibited",
    "external_artifact_store": "prohibited",
    "visibility_change_action": "remove_or_reassess_before_change",
}


class ReferenceDataStagingError(ValueError):
    """Raised when an acquired artifact is unsafe or outside the fixed scope."""


@dataclass(frozen=True, slots=True)
class StagedReferenceData:
    """Fixed outputs and non-gating planning-digest comparisons."""

    afrr_path: Path
    mfrr_path: Path
    digest_comparisons: tuple[tuple[str, str, str, str], ...]


def _manifest_bytes(artifact: RestorationMarketArtifact) -> bytes:
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
        raise ReferenceDataStagingError(
            "normalized restoration artifact cannot be serialized"
        ) from exc


def _read_and_scan(
    path: Path, *, secret_sentinels: Sequence[str]
) -> tuple[bytes, RestorationMarketArtifact]:
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise ReferenceDataStagingError(
            f"acquired artifact cannot be read: {path}"
        ) from exc
    lowered = source_bytes.lower()
    for marker in _FORBIDDEN_PERSISTED_MARKERS:
        if marker in lowered:
            raise ReferenceDataStagingError(
                "acquired artifact contains raw market, OAuth, or secret material"
            )
    rendered_path = str(path)
    for sentinel in secret_sentinels:
        if not isinstance(sentinel, str) or not sentinel:
            raise ReferenceDataStagingError(
                "secret sentinels must be non-empty strings"
            )
        encoded = sentinel.encode("utf-8")
        if encoded in source_bytes or sentinel in rendered_path:
            raise ReferenceDataStagingError(
                "acquired artifact path or bytes contain a secret sentinel"
            )
    try:
        artifact = load_restoration_market_artifact(path)
    except RestorationArtifactValidationError as exc:
        raise ReferenceDataStagingError(
            f"acquired artifact failed integrity validation: {path}"
        ) from exc
    return source_bytes, artifact


def _require_period(
    artifact: RestorationMarketArtifact,
    *,
    start: datetime,
    end: datetime,
    label: str,
) -> None:
    if (
        artifact.requested_period.start_utc != start
        or artifact.requested_period.end_utc != end
        or artifact.covered_period.start_utc != start
        or artifact.covered_period.end_utc != end
    ):
        raise ReferenceDataStagingError(
            f"{label} artifact must match the exact verified requested and covered period"
        )


def _series_by_id(
    artifact: RestorationMarketArtifact,
) -> dict[str, object]:
    return {item.series_id: item for item in artifact.series}


def _require_common_scope(
    artifact: RestorationMarketArtifact,
    *,
    profile,
    start: datetime,
    end: datetime,
    label: str,
) -> dict[str, object]:
    if (
        artifact.source is not RestorationDataSource.RTE
        or artifact.source_version != RTE_CATALOG_VERSION
        or artifact.profile_id != profile.profile_id
        or artifact.resource != profile.resource
    ):
        raise ReferenceDataStagingError(
            f"{label} artifact is not the exact RTE v5.2 {label} profile/resource"
        )
    _require_period(artifact, start=start, end=end, label=label)
    expected_ids = set(profile.series_ids)
    if set(artifact.series_manifest) != expected_ids:
        raise ReferenceDataStagingError(
            f"{label} artifact must contain the exact selected profile series fields"
        )
    by_id = _series_by_id(artifact)
    if set(by_id) != expected_ids:
        raise ReferenceDataStagingError(
            f"{label} artifact series must exactly match its profile fields"
        )
    for series_id, series in by_id.items():
        if (
            series.source is not RestorationDataSource.RTE
            or series.source_version != RTE_CATALOG_VERSION
            or series.resource != profile.resource
            or series.product != label.upper()
            or series.source_resolution != RTE_EXPECTED_RESOLUTION
            or series.canonical_resolution != RTE_EXPECTED_RESOLUTION
            or series.requested_period != artifact.requested_period
            or series.covered_period != artifact.covered_period
            or series.transformations != _EXPECTED_TRANSFORMATIONS
        ):
            raise ReferenceDataStagingError(
                f"{label} series {series_id} has incompatible semantic or transformation metadata"
            )
        manifest = artifact.series_manifest[series_id]
        if not isinstance(manifest, Mapping) or manifest.get("requested") is not True:
            raise ReferenceDataStagingError(
                f"{label} series {series_id} is not explicitly requested"
            )
        if manifest.get("availability") != series.availability.value:
            raise ReferenceDataStagingError(
                f"{label} series {series_id} availability metadata disagrees"
            )

    if len(artifact.request_evidence) != 1:
        raise ReferenceDataStagingError(
            f"{label} reference requires one bounded market-response digest"
        )
    evidence = artifact.request_evidence[0]
    if (
        evidence.resource != profile.resource
        or evidence.start_utc != start.isoformat().replace("+00:00", "Z")
        or evidence.end_utc != end.isoformat().replace("+00:00", "Z")
        or evidence.attempt_count < 1
        or evidence.http_status_class != "2xx"
        or evidence.response_media_type != "application/json"
        or evidence.response_bytes < 1
        or _SHA256.fullmatch(evidence.raw_sha256) is None
    ):
        raise ReferenceDataStagingError(
            f"{label} artifact lacks fresh valid SHA-256 market-response evidence"
        )
    try:
        retrieved_at = datetime.fromisoformat(
            artifact.retrieved_at_utc.replace("Z", "+00:00")
        ).astimezone(UTC)
    except ValueError as exc:
        raise ReferenceDataStagingError(
            f"{label} retrieval timestamp is invalid"
        ) from exc
    if retrieved_at < end:
        raise ReferenceDataStagingError(
            f"{label} retrieval timestamp predates its source period"
        )
    if artifact.raw_retention.get("policy") != "DIGEST_ONLY":
        raise ReferenceDataStagingError(
            f"{label} reference raw evidence must be digest-only"
        )
    responses = artifact.raw_retention.get("responses")
    if not isinstance(responses, Mapping) or set(responses) != {evidence.request_id}:
        raise ReferenceDataStagingError(
            f"{label} raw-retention evidence does not match its request"
        )
    retention = responses[evidence.request_id]
    if not isinstance(retention, Mapping) or retention != {
        "status": "digest_only",
        "sidecar_locator": None,
        "sidecar_sha256": None,
    }:
        raise ReferenceDataStagingError(
            f"{label} reference cannot retain a raw response sidecar"
        )
    for field_name, expected in _REQUIRED_POLICY.items():
        if artifact.redistribution_policy.get(field_name) != expected:
            raise ReferenceDataStagingError(
                f"{label} restricted policy field {field_name} must be {expected}"
            )
    return by_id


def _require_afrr_scope(artifact: RestorationMarketArtifact) -> None:
    by_id = _require_common_scope(
        artifact,
        profile=RTE_AFRR_PROFILE,
        start=_AFRR_START,
        end=_AFRR_END,
        label="aFRR",
    )
    if any(
        series.availability is not SeriesAvailability.PRESENT
        or len(series.observations) != 4
        for series in by_id.values()
    ):
        raise ReferenceDataStagingError(
            "aFRR reference requires four PRESENT PT15M records for every field"
        )
    upward = by_id["afrr_requested_need_upward"]
    downward = by_id["afrr_requested_need_downward"]
    if [item.value for item in upward.observations] != [425.0, 315.0, 290.0, 345.0]:
        raise ReferenceDataStagingError(
            "aFRR requested-need values differ from verified semantic planning evidence"
        )
    if [item.value for item in downward.observations] != [0.0, 0.0, 0.0, 0.0]:
        raise ReferenceDataStagingError(
            "aFRR downward requested need differs from verified zero-valued evidence"
        )


def _require_mfrr_scope(artifact: RestorationMarketArtifact) -> None:
    by_id = _require_common_scope(
        artifact,
        profile=RTE_MFRR_PROFILE,
        start=_MFRR_START,
        end=_MFRR_END,
        label="mFRR",
    )
    if any(len(series.observations) != 1 for series in by_id.values()):
        raise ReferenceDataStagingError(
            "mFRR reference requires one PT15M observation per directional field"
        )
    requested = by_id["mfrr_sa_requested_volume_downward"].observations[0]
    satisfied = by_id["mfrr_sa_satisfied_need_downward"].observations[0]
    if (
        requested.value_state is not ObservationValueState.VALUE
        or requested.value != 357.0
    ):
        raise ReferenceDataStagingError(
            "mFRR downward SA requested semantic evidence must equal 357 MW"
        )
    if (
        satisfied.value_state is not ObservationValueState.VALUE
        or satisfied.value != 300.0
    ):
        raise ReferenceDataStagingError(
            "mFRR downward SA satisfied semantic evidence must equal 300 MW"
        )
    clearing = by_id["mfrr_clearing_price_downward"].observations[0]
    if clearing.value_state is not ObservationValueState.VALUE or clearing.value != 64.83:
        raise ReferenceDataStagingError(
            "mFRR downward clearing-price evidence must equal 64.83 EUR/MWh"
        )


def _require_safe_fixed_destination(repository_root: Path) -> Path:
    resolved_root = repository_root.resolve()
    if any(part.casefold() in _FORBIDDEN_TARGET_PARTS for part in resolved_root.parts):
        raise ReferenceDataStagingError(
            "restricted fixture target cannot be a public, distribution, release, mirror, CI-artifact, or external-store path"
        )
    destination = resolved_root / _FIXTURE_RELATIVE_DIRECTORY
    expected = resolved_root / "tests" / "fixtures" / "restoration"
    if destination != expected:
        raise ReferenceDataStagingError(
            "restricted references may use only the fixed repository fixture target"
        )
    return destination


def _write_fixed_manifests(
    manifests: Sequence[tuple[Path, bytes]],
) -> None:
    if not manifests:
        raise ReferenceDataStagingError("no fixed manifests were selected")
    destination = manifests[0][0].parent
    if any(path.parent != destination for path, _content in manifests):
        raise ReferenceDataStagingError("fixed manifests must share one destination")
    try:
        destination.mkdir(parents=True, exist_ok=True)
        for path, desired in manifests:
            if path.exists() and path.read_bytes() != desired:
                raise ReferenceDataStagingError(
                    f"existing immutable restricted fixture differs: {path.name}"
                )
        for path, desired in manifests:
            if path.exists():
                continue
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=destination
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(desired)
                    handle.flush()
                    os.fsync(handle.fileno())
                if path.exists():
                    raise ReferenceDataStagingError(
                        f"fixed restricted fixture appeared during staging: {path.name}"
                    )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    except ReferenceDataStagingError:
        raise
    except OSError as exc:
        raise ReferenceDataStagingError(
            "fixed restricted fixtures could not be published atomically"
        ) from exc


def _digest_comparison(
    artifact: RestorationMarketArtifact, *, planning_digest: str
) -> tuple[str, str, str, str]:
    observed = artifact.request_evidence[0].raw_sha256
    status = "MATCH" if observed == planning_digest else "DRIFT_REVIEW_REQUIRED"
    return artifact.resource, planning_digest, observed, status


def stage_private_reference_data(
    afrr_artifact_path: str | os.PathLike[str],
    mfrr_artifact_path: str | os.PathLike[str],
    *,
    repository_root: str | os.PathLike[str] = _REPOSITORY_ROOT,
    private_repository_acknowledged: bool,
    secret_sentinels: Sequence[str] = (),
) -> StagedReferenceData:
    """Validate then publish the two fixed normalized restricted manifests."""

    if private_repository_acknowledged is not True:
        raise ReferenceDataStagingError(
            "private restricted repository storage must be explicitly acknowledged"
        )
    sentinels = tuple(secret_sentinels)
    destination = _require_safe_fixed_destination(Path(repository_root))
    _afrr_bytes, afrr = _read_and_scan(
        Path(afrr_artifact_path), secret_sentinels=sentinels
    )
    _mfrr_bytes, mfrr = _read_and_scan(
        Path(mfrr_artifact_path), secret_sentinels=sentinels
    )
    _require_afrr_scope(afrr)
    _require_mfrr_scope(mfrr)

    afrr_output = destination / AFRR_REFERENCE_FILENAME
    mfrr_output = destination / MFRR_REFERENCE_FILENAME
    afrr_manifest = _manifest_bytes(afrr)
    mfrr_manifest = _manifest_bytes(mfrr)
    for persisted in (afrr_manifest, mfrr_manifest):
        lowered = persisted.lower()
        if any(marker in lowered for marker in _FORBIDDEN_PERSISTED_MARKERS):
            raise ReferenceDataStagingError(
                "normalized fixed manifest contains raw market, OAuth, or secret material"
            )
        if any(sentinel.encode("utf-8") in persisted for sentinel in sentinels):
            raise ReferenceDataStagingError(
                "normalized fixed manifest contains a secret sentinel"
            )
    _write_fixed_manifests(
        ((afrr_output, afrr_manifest), (mfrr_output, mfrr_manifest))
    )
    return StagedReferenceData(
        afrr_path=afrr_output,
        mfrr_path=mfrr_output,
        digest_comparisons=(
            _digest_comparison(afrr, planning_digest=AFRR_PLANNING_RAW_SHA256),
            _digest_comparison(mfrr, planning_digest=MFRR_PLANNING_RAW_SHA256),
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--afrr-artifact", type=Path, required=True)
    parser.add_argument("--mfrr-artifact", type=Path, required=True)
    parser.add_argument(
        "--acknowledge-private-restricted-repository",
        action="store_true",
        help=(
            "confirm private authorized-collaborator storage and prohibition "
            "of package, release, public-CI, mirror, and external publication"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = stage_private_reference_data(
            args.afrr_artifact,
            args.mfrr_artifact,
            private_repository_acknowledged=(
                args.acknowledge_private_restricted_repository
            ),
        )
        afrr = load_restoration_market_artifact(result.afrr_path)
        mfrr = load_restoration_market_artifact(result.mfrr_path)
    except (OSError, ReferenceDataStagingError, RestorationArtifactValidationError) as exc:
        print(f"restricted reference staging failed: {exc}", file=sys.stderr)
        return 2
    print(f"afrr_fixture={result.afrr_path}")
    print(f"afrr_artifact_fingerprint={afrr.artifact_fingerprint}")
    print(f"mfrr_fixture={result.mfrr_path}")
    print(f"mfrr_artifact_fingerprint={mfrr.artifact_fingerprint}")
    for resource, expected, observed, status in result.digest_comparisons:
        print(f"{resource}_planning_raw_sha256={expected}")
        print(f"{resource}_observed_raw_sha256={observed}")
        print(f"{resource}_planning_digest_status={status}")
    print("repository_storage=permitted_private_restricted")
    print("repository_publication=prohibited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
