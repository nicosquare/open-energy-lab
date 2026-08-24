"""Closed, credential-free RTE Balancing Energy request contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import inspect
import re

import pytest

from open_energy_lab.market.rte import (
    RTE_AFRR_PROFILE,
    RTE_MFRR_PROFILE,
    RTEAcquisitionDiagnostic,
    RTEAcquisitionMode,
    RTERequestValidationError,
    build_rte_query_windows,
    build_rte_restoration_request,
    execute_rte_request,
)


AFRR_START = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
AFRR_END = AFRR_START + timedelta(hours=1)


def _request(**overrides: object):
    values: dict[str, object] = {
        "resource": "standard_afrr_data",
        "requested_start_utc": AFRR_START,
        "requested_end_utc": AFRR_END,
        "requested_series_ids": RTE_AFRR_PROFILE.series_ids,
        "required_series_ids": RTE_AFRR_PROFILE.required_series_ids,
        "normalization_version": "rte-balancing-energy-v5.2-v1",
        "raw_retention_policy": "DIGEST_ONLY",
        "mode": "FETCH",
    }
    values.update(overrides)
    return build_rte_restoration_request(**values)


def test_closed_profiles_pin_catalog_path_root_resolution_and_series_contracts() -> None:
    assert RTE_AFRR_PROFILE.profile_id == "fr-rte-balancing-energy-v5.2-afrr-v1"
    assert RTE_AFRR_PROFILE.catalog_version == "5.2"
    assert RTE_AFRR_PROFILE.api_path_version == "v5"
    assert RTE_AFRR_PROFILE.source_name == "RTE Balancing Energy"
    assert RTE_AFRR_PROFILE.resource == "standard_afrr_data"
    assert RTE_AFRR_PROFILE.root_field == "picasso"
    assert RTE_AFRR_PROFILE.rows_field == "picasso_mesures"
    assert RTE_AFRR_PROFILE.expected_resolution == "PT15M"
    assert len(RTE_AFRR_PROFILE.series_ids) == 8

    assert RTE_MFRR_PROFILE.resource == "standard_mfrr_data"
    assert RTE_MFRR_PROFILE.root_field == "mari"
    assert RTE_MFRR_PROFILE.rows_field == "mari_mesures"
    assert "mfrr_sa_requested_volume_downward" in RTE_MFRR_PROFILE.series_ids
    assert "mfrr_da_requested_volume_downward" in RTE_MFRR_PROFILE.series_ids
    assert RTE_MFRR_PROFILE.required_series_ids == ()
    assert RTE_AFRR_PROFILE.series_ids != RTE_MFRR_PROFILE.series_ids

    with pytest.raises((FrozenInstanceError, AttributeError)):
        RTE_AFRR_PROFILE.resource = "standard_mfrr_data"  # type: ignore[misc]


def test_request_has_one_profile_https_origin_path_and_token_free_identity() -> None:
    request = _request()

    assert request.source == "RTE"
    assert request.profile is RTE_AFRR_PROFILE
    assert request.resource_identity == "standard_afrr_data"
    assert request.source_endpoint == (
        "https://digital.iservices.rte-france.com/"
        "open_api/balancing_energy/v5/standard_afrr_data"
    )
    assert request.requested_start_utc == AFRR_START
    assert request.requested_end_utc == AFRR_END
    assert request.mode is RTEAcquisitionMode.FETCH
    assert re.fullmatch(r"[0-9a-f]{64}", request.request_identity)
    rendered = repr(request)
    assert "client" not in rendered.casefold()
    assert "secret" not in rendered.casefold()
    assert "token" not in rendered.casefold()
    assert "?" not in request.source_endpoint


def test_request_identity_is_deterministic_and_covers_semantic_inputs() -> None:
    baseline = _request()
    assert _request().request_identity == baseline.request_identity

    changed = _request(mode="REFRESH")
    assert changed.mode is RTEAcquisitionMode.REFRESH
    assert changed.request_identity == baseline.request_identity

    changed = _request(requested_end_utc=AFRR_END + timedelta(minutes=15))
    assert changed.request_identity != baseline.request_identity


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (AFRR_START.replace(tzinfo=None), AFRR_END, "UTC|aware"),
        (AFRR_START, AFRR_START, "before|later|period"),
        (AFRR_START + timedelta(minutes=1), AFRR_END, "15-minute|aligned"),
        (AFRR_START, AFRR_START + timedelta(days=32), "window|bounded|maximum"),
    ],
)
def test_request_rejects_unbounded_or_misaligned_periods(start, end, message) -> None:
    with pytest.raises(RTERequestValidationError, match=message):
        _request(requested_start_utc=start, requested_end_utc=end)


def test_request_rejects_cross_resource_unknown_or_invalid_series_selection() -> None:
    with pytest.raises(RTERequestValidationError, match="resource|profile"):
        _request(resource="standard_mfrr_data")
    with pytest.raises(RTERequestValidationError, match="unknown|series"):
        _request(requested_series_ids=("not_a_real_series",))
    with pytest.raises(RTERequestValidationError, match="required|subset|requested"):
        _request(required_series_ids=("afrr_requested_need_upward", "not_requested"))


def test_source_endpoint_cannot_contain_query_fragment_userinfo_or_wrong_origin() -> None:
    for endpoint in (
        "https://user@example.test/open_api/balancing_energy/v5/standard_afrr_data",
        "https://digital.iservices.rte-france.com/open_api/balancing_energy/v5/standard_afrr_data?token=x",
        "https://digital.iservices.rte-france.com/open_api/balancing_energy/v5/standard_afrr_data#fragment",
        "http://digital.iservices.rte-france.com/open_api/balancing_energy/v5/standard_afrr_data",
        "https://example.test/open_api/balancing_energy/v5/standard_afrr_data",
    ):
        with pytest.raises(RTERequestValidationError, match="endpoint|HTTPS|origin|query|fragment"):
            _request(source_endpoint=endpoint)


def test_query_windows_are_deterministic_contiguous_and_sanitized() -> None:
    windows = build_rte_query_windows(_request())
    assert len(windows) == 1
    assert windows[0].resource == "standard_afrr_data"
    assert windows[0].start_utc == AFRR_START
    assert windows[0].end_utc == AFRR_END
    assert re.fullmatch(r"[0-9a-f]{64}", windows[0].request_id)
    assert "token" not in repr(windows[0]).casefold()


def test_diagnostic_has_only_sanitized_public_fields() -> None:
    diagnostic = RTEAcquisitionDiagnostic(
        code="rte_invalid_period",
        phase="request",
        resource="standard_afrr_data",
        field="requested_period",
        requested_period="[2026-08-20T00:00:00Z, 2026-08-20T01:00:00Z)",
        observed_condition="start was not quarter-hour aligned",
        expected_condition="aware UTC bounds aligned to PT15M",
        attempt_count=0,
        public_message="RTE request period is invalid",
    )
    payload = diagnostic.to_dict()
    assert set(payload) == {
        "code",
        "phase",
        "source",
        "resource",
        "field",
        "requested_period",
        "observed_condition",
        "expected_condition",
        "attempt_count",
        "public_message",
    }
    assert payload["source"] == "RTE"
    assert not any(
        fragment in repr(diagnostic).casefold()
        for fragment in ("authorization", "bearer", "basic", "client_secret")
    )


def test_credentials_are_keyword_only_at_explicit_transport_boundary() -> None:
    signature = inspect.signature(execute_rte_request)
    assert signature.parameters["client_id"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["client_secret"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "client_id" not in inspect.signature(build_rte_restoration_request).parameters
    assert "client_secret" not in inspect.signature(build_rte_restoration_request).parameters
