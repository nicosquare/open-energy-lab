"""Attach reviewed EPEX publication evidence to the validated reference market.

This operation performs no network access and never reads an ENTSO-E token. It
turns the technically validated, local-only market artifact into the fixed
repository fixture only when a caller supplies both a complete public
permission record and the private evidence bytes whose SHA-256 it records.

The checks establish structural completeness and exact scope matching. They do
not replace legal review or prove that a supplied document is authentic.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from types import MappingProxyType
import urllib.parse

from open_energy_lab.market import (
    FRANCE_AREA_EIC,
    FRANCE_PROFILE_ID,
    MarketArtifactValidationError,
    MarketDataArtifact,
    build_market_data_artifact,
    load_market_data_artifact,
)


PERMISSION_SCHEMA_VERSION = "oel.epex-publication-permission.v1"
REFERENCE_REPOSITORY_URL = "https://github.com/nicosquare/open-energy-lab"
REFERENCE_START_UTC = "2022-08-18T22:00:00Z"
REFERENCE_END_UTC = "2022-08-19T22:00:00Z"
REFERENCE_MARKET_FILENAME = "france_2022-08-19_market_v1.json"
MAX_PERMISSION_RECORD_BYTES = 64 * 1024
MAX_PERMISSION_EVIDENCE_BYTES = 32 * 1024 * 1024
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}\Z")
_GRANT_TYPES = {"written_permission", "market_data_agreement"}
_SCOPE_FIELDS = (
    "public_repository_distribution",
    "normalized_a44_value_distribution",
    "derived_replay_fixture_distribution",
    "adaptation_and_normalization",
    "public_forks_and_source_archives",
)
_TOP_LEVEL_FIELDS = (
    "schema_version",
    "rights_holder",
    "grant_type",
    "permission_reference",
    "permission_evidence_sha256",
    "effective_date",
    "reviewed_at_utc",
    "reviewed_by",
    "repository_url",
    "covered_data",
    "grant_scope",
    "attribution",
    "downstream_terms",
    "ai_ml_terms",
    "source_terms",
)
_COVERED_DATA_FIELDS = (
    "area_eic",
    "document_type",
    "delivery_start_utc",
    "delivery_end_utc",
    "description",
)
_SOURCE_TERMS_FIELDS = ("title", "version_date", "url")


class MarketPublicationPermissionError(ValueError):
    """Raised when publication evidence is absent, incomplete, or mismatched."""


def _mapping(value: object, *, field_name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise MarketPublicationPermissionError(f"{field_name} must be an object")
    return {str(key): inner for key, inner in value.items()}


def _require_exact_fields(
    value: Mapping[str, object],
    expected: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    missing = sorted(set(expected) - set(value))
    extra = sorted(set(value) - set(expected))
    if missing or extra:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise MarketPublicationPermissionError(
            f"{field_name} fields are invalid: {'; '.join(details)}"
        )


def _text(
    value: object,
    *,
    field_name: str,
    max_length: int = 4_096,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketPublicationPermissionError(f"{field_name} must be non-empty")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise MarketPublicationPermissionError(
            f"{field_name} exceeds {max_length} characters"
        )
    lowered = normalized.casefold()
    if (
        normalized.startswith("REPLACE_")
        or lowered in {"pending", "placeholder", "tbd", "to be determined"}
    ):
        raise MarketPublicationPermissionError(
            f"{field_name} contains an unresolved placeholder"
        )
    return normalized


def _utc_timestamp(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name, max_length=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketPublicationPermissionError(
            f"{field_name} must be an ISO 8601 UTC timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise MarketPublicationPermissionError(f"{field_name} must be UTC")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _date(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name, max_length=10)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise MarketPublicationPermissionError(
            f"{field_name} must be an ISO 8601 calendar date"
        ) from exc
    if parsed.isoformat() != text:
        raise MarketPublicationPermissionError(
            f"{field_name} must use canonical YYYY-MM-DD form"
        )
    return text


def _https_url(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name, max_length=2_048)
    parsed = urllib.parse.urlsplit(text)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise MarketPublicationPermissionError(
            f"{field_name} must be an absolute credential-free HTTPS URL"
        )
    return text


def _sha256(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name, max_length=64)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise MarketPublicationPermissionError(
            f"{field_name} must be a 64-character SHA-256 digest"
        )
    return text.casefold()


@dataclass(frozen=True, slots=True)
class MarketPublicationPermission:
    """Non-confidential summary of one reviewed rights-holder grant."""

    schema_version: str
    rights_holder: str
    grant_type: str
    permission_reference: str
    permission_evidence_sha256: str
    effective_date: str
    reviewed_at_utc: str
    reviewed_by: str
    repository_url: str
    covered_data: Mapping[str, str]
    grant_scope: Mapping[str, bool]
    attribution: str
    downstream_terms: str
    ai_ml_terms: str
    source_terms: Mapping[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "rights_holder": self.rights_holder,
            "grant_type": self.grant_type,
            "permission_reference": self.permission_reference,
            "permission_evidence_sha256": self.permission_evidence_sha256,
            "effective_date": self.effective_date,
            "reviewed_at_utc": self.reviewed_at_utc,
            "reviewed_by": self.reviewed_by,
            "repository_url": self.repository_url,
            "covered_data": dict(self.covered_data),
            "grant_scope": dict(self.grant_scope),
            "attribution": self.attribution,
            "downstream_terms": self.downstream_terms,
            "ai_ml_terms": self.ai_ml_terms,
            "source_terms": dict(self.source_terms),
        }


def _permission_from_mapping(
    payload: Mapping[str, object],
) -> MarketPublicationPermission:
    data = _mapping(payload, field_name="publication permission")
    _require_exact_fields(
        data,
        _TOP_LEVEL_FIELDS,
        field_name="publication permission",
    )
    schema_version = _text(
        data["schema_version"],
        field_name="schema_version",
        max_length=64,
    )
    if schema_version != PERMISSION_SCHEMA_VERSION:
        raise MarketPublicationPermissionError(
            f"schema_version must be {PERMISSION_SCHEMA_VERSION}"
        )
    rights_holder = _text(
        data["rights_holder"],
        field_name="rights_holder",
        max_length=128,
    )
    if rights_holder != "EPEX SPOT SE":
        raise MarketPublicationPermissionError(
            "rights_holder must be EPEX SPOT SE for the selected A44 values"
        )
    grant_type = _text(
        data["grant_type"],
        field_name="grant_type",
        max_length=64,
    )
    if grant_type not in _GRANT_TYPES:
        raise MarketPublicationPermissionError(
            "grant_type must be written_permission or market_data_agreement"
        )

    repository_url = _https_url(
        data["repository_url"],
        field_name="repository_url",
    ).rstrip("/")
    if repository_url != REFERENCE_REPOSITORY_URL:
        raise MarketPublicationPermissionError(
            f"repository_url must identify {REFERENCE_REPOSITORY_URL}"
        )

    covered = _mapping(data["covered_data"], field_name="covered_data")
    _require_exact_fields(
        covered,
        _COVERED_DATA_FIELDS,
        field_name="covered_data",
    )
    covered_data = {
        "area_eic": _text(
            covered["area_eic"], field_name="covered_data.area_eic", max_length=32
        ),
        "document_type": _text(
            covered["document_type"],
            field_name="covered_data.document_type",
            max_length=16,
        ),
        "delivery_start_utc": _utc_timestamp(
            covered["delivery_start_utc"],
            field_name="covered_data.delivery_start_utc",
        ),
        "delivery_end_utc": _utc_timestamp(
            covered["delivery_end_utc"],
            field_name="covered_data.delivery_end_utc",
        ),
        "description": _text(
            covered["description"],
            field_name="covered_data.description",
            max_length=512,
        ),
    }
    if covered_data["area_eic"] != FRANCE_AREA_EIC:
        raise MarketPublicationPermissionError(
            f"covered_data.area_eic must be {FRANCE_AREA_EIC}"
        )
    if covered_data["document_type"] != "A44":
        raise MarketPublicationPermissionError(
            "covered_data.document_type must be A44"
        )
    if covered_data["delivery_start_utc"] >= covered_data["delivery_end_utc"]:
        raise MarketPublicationPermissionError(
            "covered_data delivery period must have positive duration"
        )

    scope = _mapping(data["grant_scope"], field_name="grant_scope")
    _require_exact_fields(scope, _SCOPE_FIELDS, field_name="grant_scope")
    grant_scope: dict[str, bool] = {}
    for field_name in _SCOPE_FIELDS:
        value = scope[field_name]
        if value is not True:
            raise MarketPublicationPermissionError(
                f"grant_scope.{field_name} must be explicitly true"
            )
        grant_scope[field_name] = True

    source = _mapping(data["source_terms"], field_name="source_terms")
    _require_exact_fields(source, _SOURCE_TERMS_FIELDS, field_name="source_terms")
    source_terms = {
        "title": _text(
            source["title"], field_name="source_terms.title", max_length=512
        ),
        "version_date": _date(
            source["version_date"], field_name="source_terms.version_date"
        ),
        "url": _https_url(source["url"], field_name="source_terms.url"),
    }

    return MarketPublicationPermission(
        schema_version=schema_version,
        rights_holder=rights_holder,
        grant_type=grant_type,
        permission_reference=_text(
            data["permission_reference"],
            field_name="permission_reference",
            max_length=256,
        ),
        permission_evidence_sha256=_sha256(
            data["permission_evidence_sha256"],
            field_name="permission_evidence_sha256",
        ),
        effective_date=_date(data["effective_date"], field_name="effective_date"),
        reviewed_at_utc=_utc_timestamp(
            data["reviewed_at_utc"], field_name="reviewed_at_utc"
        ),
        reviewed_by=_text(
            data["reviewed_by"], field_name="reviewed_by", max_length=256
        ),
        repository_url=repository_url,
        covered_data=MappingProxyType(covered_data),
        grant_scope=MappingProxyType(grant_scope),
        attribution=_text(data["attribution"], field_name="attribution"),
        downstream_terms=_text(
            data["downstream_terms"], field_name="downstream_terms"
        ),
        ai_ml_terms=_text(data["ai_ml_terms"], field_name="ai_ml_terms"),
        source_terms=MappingProxyType(source_terms),
    )


def load_market_publication_permission(
    source: str | os.PathLike[str] | Mapping[str, object],
) -> MarketPublicationPermission:
    """Load a bounded non-confidential permission summary without its evidence."""

    if isinstance(source, Mapping):
        return _permission_from_mapping(source)
    path = Path(source)
    try:
        size = path.stat().st_size
        if size > MAX_PERMISSION_RECORD_BYTES:
            raise MarketPublicationPermissionError(
                "publication permission record exceeds 64 KiB"
            )
        text = path.read_text(encoding="utf-8")
    except MarketPublicationPermissionError:
        raise
    except (OSError, UnicodeError) as exc:
        raise MarketPublicationPermissionError(
            f"could not read publication permission record {path}"
        ) from exc
    try:
        payload = json.loads(
            text,
            parse_constant=lambda value: (_ for _ in ()).throw(
                MarketPublicationPermissionError(
                    f"publication permission contains non-finite value {value}"
                )
            ),
        )
    except MarketPublicationPermissionError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise MarketPublicationPermissionError(
            f"publication permission record is malformed JSON: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise MarketPublicationPermissionError(
            "publication permission record must contain a top-level object"
        )
    return _permission_from_mapping(payload)


def _permission_evidence_bytes(path: str | os.PathLike[str]) -> bytes:
    evidence_path = Path(path)
    try:
        size = evidence_path.stat().st_size
        if size <= 0:
            raise MarketPublicationPermissionError(
                "permission evidence file must be non-empty"
            )
        if size > MAX_PERMISSION_EVIDENCE_BYTES:
            raise MarketPublicationPermissionError(
                "permission evidence file exceeds 32 MiB"
            )
        return evidence_path.read_bytes()
    except MarketPublicationPermissionError:
        raise
    except OSError as exc:
        raise MarketPublicationPermissionError(
            f"could not read private permission evidence {evidence_path}"
        ) from exc


def _require_matching_evidence(
    permission: MarketPublicationPermission,
    evidence: bytes,
) -> None:
    if not isinstance(evidence, bytes) or not evidence:
        raise MarketPublicationPermissionError(
            "permission evidence must be non-empty bytes"
        )
    digest = hashlib.sha256(evidence).hexdigest()
    if digest != permission.permission_evidence_sha256:
        raise MarketPublicationPermissionError(
            "permission evidence SHA-256 does not match the permission record"
        )


def _require_reference_scope(
    market: MarketDataArtifact,
    permission: MarketPublicationPermission,
) -> None:
    if (
        market.profile_id != FRANCE_PROFILE_ID
        or market.area.get("eic") != FRANCE_AREA_EIC
    ):
        raise MarketPublicationPermissionError(
            "market artifact is not the closed Feature 010 France profile"
        )
    start = market.requested_period.start_utc.isoformat().replace("+00:00", "Z")
    end = market.requested_period.end_utc.isoformat().replace("+00:00", "Z")
    if start != REFERENCE_START_UTC or end != REFERENCE_END_UTC:
        raise MarketPublicationPermissionError(
            "market artifact is not the exact Feature 010 reference period"
        )
    if (
        permission.covered_data["delivery_start_utc"] != start
        or permission.covered_data["delivery_end_utc"] != end
    ):
        raise MarketPublicationPermissionError(
            "permission covered data period does not match the market artifact period"
        )
    if len(market.series["day_ahead_price"].observations) != 24:
        raise MarketPublicationPermissionError(
            "reference market artifact must contain 24 hourly A44 values"
        )
    if any(
        len(market.series[series_id].observations) != 6
        for series_id in ("fcr_contracted_volume", "fcr_capacity_price")
    ):
        raise MarketPublicationPermissionError(
            "reference market artifact must contain six aligned A81 blocks"
        )
    if any(item.retention_status != "digest_only" for item in market.raw_responses):
        raise MarketPublicationPermissionError(
            "publication permission covers normalized values, not raw-response sidecars"
        )


def authorize_reference_market_artifact(
    market: MarketDataArtifact,
    permission: MarketPublicationPermission,
    *,
    permission_evidence: bytes,
) -> MarketDataArtifact:
    """Return a re-fingerprinted artifact whose publication grant is explicit."""

    if not isinstance(market, MarketDataArtifact):
        raise TypeError("market must be a MarketDataArtifact")
    if not isinstance(permission, MarketPublicationPermission):
        raise TypeError("permission must be a MarketPublicationPermission")
    verified = MarketDataArtifact.from_dict(market.to_dict())
    verified_permission = _permission_from_mapping(permission.to_dict())
    _require_matching_evidence(verified_permission, permission_evidence)
    _require_reference_scope(verified, verified_permission)

    payload = verified.to_dict()
    payload["created_at_utc"] = verified_permission.reviewed_at_utc
    payload["predecessor_artifact_fingerprint"] = verified.artifact_fingerprint
    retention = dict(verified.retention_and_license)
    retention["series_redistribution"] = {
        "day_ahead_price": {
            "status": "rights_holder_permission",
            "source_document_type": "A44",
            "rights_holder": verified_permission.rights_holder,
            "permission_reference": verified_permission.permission_reference,
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
    retention["repository_publication"] = "permitted"
    retention["publication_permission"] = verified_permission.to_dict()
    retention["normalized_artifact_attribution"] = verified_permission.attribution
    payload["retention_and_license"] = retention
    authorized = build_market_data_artifact(payload)
    if authorized.content_fingerprint != verified.content_fingerprint:
        raise MarketPublicationPermissionError(
            "authorization unexpectedly changed normalized market content"
        )
    return authorized


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
        raise MarketPublicationPermissionError(
            "authorized market fixture could not be serialized"
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
                raise MarketPublicationPermissionError(
                    "existing fixed reference market fixture differs from "
                    "authorized bytes"
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
                raise MarketPublicationPermissionError(
                    "fixed reference market fixture appeared during publication"
                )
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    except MarketPublicationPermissionError:
        raise
    except (OSError, MarketArtifactValidationError) as exc:
        raise MarketPublicationPermissionError(
            "authorized reference market fixture could not be published atomically"
        ) from exc
    return output


def write_authorized_reference_market_fixture(
    market_path: str | os.PathLike[str],
    *,
    permission_path: str | os.PathLike[str],
    permission_evidence_path: str | os.PathLike[str],
    destination_dir: str | os.PathLike[str],
) -> Path:
    """Verify private grant evidence and publish the fixed repository fixture."""

    market = load_market_data_artifact(market_path)
    permission = load_market_publication_permission(permission_path)
    evidence = _permission_evidence_bytes(permission_evidence_path)
    authorized = authorize_reference_market_artifact(
        market,
        permission,
        permission_evidence=evidence,
    )
    return _write_fixed_manifest(authorized, destination_dir=destination_dir)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument("--permission", type=Path, required=True)
    parser.add_argument("--permission-evidence", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = write_authorized_reference_market_fixture(
            args.market,
            permission_path=args.permission,
            permission_evidence_path=args.permission_evidence,
            destination_dir=args.destination,
        )
        artifact = load_market_data_artifact(output)
    except (MarketPublicationPermissionError, MarketArtifactValidationError) as exc:
        print(f"publication authorization failed: {exc}", file=sys.stderr)
        return 2
    print(f"market_fixture={output}")
    print(f"content_fingerprint={artifact.content_fingerprint}")
    print(f"artifact_fingerprint={artifact.artifact_fingerprint}")
    print("repository_publication=permitted_by_reviewed_permission_record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
