"""Fixture-backed contracts for defensive ENTSO-E XML normalization."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import io
import importlib
from pathlib import Path
from types import ModuleType
from typing import Any
import zipfile

import pytest

from tests.unit.market.test_entsoe_transport import (
    ENDPOINT,
    SENTINEL_TOKEN,
    _request,
    _window,
)


FIXTURE_ROOT = Path(__file__).parents[2] / "fixtures" / "market" / "synthetic_entsoe"
PERIOD_START = datetime(2022, 8, 18, 22, tzinfo=UTC)
PERIOD_END = datetime(2022, 8, 19, 2, tzinfo=UTC)
SERIES_BY_DOCUMENT = {
    "A44": "day_ahead_price",
    "A81": "fcr_contracted_volume",
}


def _entsoe_module() -> ModuleType:
    try:
        return importlib.import_module("open_energy_lab.market.entsoe")
    except ModuleNotFoundError as exc:
        pytest.fail(
            "open_energy_lab.market.entsoe is not implemented; T019 must "
            "provide defensive XML parsing and normalization",
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


def _request_for(start: datetime, end: datetime):
    return _request(requested_start_utc=start, requested_end_utc=end)


def _window_for(document_type: str, start: datetime, end: datetime):
    return _window(
        window_id=f"fr-{document_type.lower()}-{start.date().isoformat()}",
        document_type=document_type,
        process_type="A01" if document_type == "A44" else "A52",
        business_type=None if document_type == "A44" else "B95",
        start_utc=start,
        end_utc=end,
        market_agreement_type=None if document_type == "A44" else "A01",
    )


def _parse_bytes(
    body: bytes,
    *,
    document_type: str,
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
    response_id: str = "response-synthetic",
):
    parse_entsoe_document = _require("parse_entsoe_document")
    return parse_entsoe_document(
        body,
        request=_request_for(start, end),
        window=_window_for(document_type, start, end),
        response_id=response_id,
    )


def _parse(
    fixture_name: str,
    *,
    document_type: str,
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
):
    return _parse_bytes(
        _fixture(fixture_name),
        document_type=document_type,
        start=start,
        end=end,
        response_id=f"response-{Path(fixture_name).stem}",
    )


def _error_text(error: BaseException) -> str:
    diagnostic = getattr(error, "diagnostic", None)
    if diagnostic is not None and hasattr(diagnostic, "to_dict"):
        diagnostic = diagnostic.to_dict()
    return "\n".join((str(error), repr(error), repr(diagnostic)))


def _assert_failure_diagnostic(
    error: BaseException,
    *,
    required_series: str,
    observed_resolution: str | None = None,
    observed_unit: str | None = None,
    observed_coverage: bool = False,
) -> None:
    diagnostic = getattr(error, "diagnostic", None)
    assert diagnostic is not None
    payload = diagnostic.to_dict()
    assert payload["source"] == "ENTSO-E Transparency Platform"
    assert payload["required_series"] == required_series
    assert payload["requested_start_utc"] == "2022-08-18T22:00:00Z"
    assert payload["requested_end_utc"] == "2022-08-19T02:00:00Z"
    assert payload["expected_profile"] == "fr-day-ahead-symmetric-fcr-v1"
    assert payload["expected_contract"]
    assert payload["final_status"]
    if observed_resolution is not None:
        assert payload["observed_resolution"] == observed_resolution
    if observed_unit is not None:
        assert payload["observed_unit"] == observed_unit
    if observed_coverage:
        assert payload["observed_start_utc"] == "2022-08-18T22:00:00Z"
        assert payload["observed_end_utc"] == "2022-08-19T02:00:00Z"
    text = _error_text(error)
    assert SENTINEL_TOKEN not in text
    assert "securityToken" not in text
    assert ENDPOINT not in text


@pytest.mark.parametrize(
    ("fixture_name", "document_type", "series_id", "root_name", "resolution"),
    [
        (
            "a44_success.xml",
            "A44",
            "day_ahead_price",
            "Publication_MarketDocument",
            "PT1H",
        ),
        (
            "a81_success.xml",
            "A81",
            "fcr_contracted_volume",
            "Balancing_MarketDocument",
            "PT30M",
        ),
    ],
)
def test_success_documents_preserve_validated_source_semantics(
    fixture_name: str,
    document_type: str,
    series_id: str,
    root_name: str,
    resolution: str,
) -> None:
    parsed = _parse(fixture_name, document_type=document_type)

    assert parsed.series.series_id == series_id
    assert parsed.series.source_document_type == document_type
    assert parsed.series.source_resolution == resolution
    assert parsed.source_document.root_document_type == root_name
    assert parsed.source_document.namespace_uri.startswith("urn:iec62325.351:")
    assert parsed.source_document.document_type == document_type
    assert parsed.source_document.area_eic == "10YFR-RTE------C"
    assert parsed.source_document.document_period.start_utc == PERIOD_START
    assert parsed.source_document.document_period.end_utc == PERIOD_END
    assert parsed.source_document.status == "selected"


def test_a44_preserves_negative_day_ahead_prices_and_hourly_positions() -> None:
    parsed = _parse("a44_success.xml", document_type="A44")

    assert parsed.series.source_unit == "EUR/MWh"
    assert parsed.series.canonical_unit == "EUR/MWh"
    assert parsed.series.currency == "EUR"
    assert [item.value for item in parsed.series.observations] == [
        475.0,
        -5.0,
        540.0,
        120.5,
    ]
    assert [item.source_position for item in parsed.series.observations] == [1, 2, 3, 4]


def test_a44_preserves_absent_source_process_while_query_remains_day_ahead() -> None:
    body = _fixture("a44_success.xml").replace(
        b"  <process.processType>A01</process.processType>\n",
        b"",
    )

    parsed = _parse_bytes(body, document_type="A44")

    assert parsed.source_document.process_type is None


def test_a44_accepts_and_preserves_source_pt60m_as_canonical_pt1h() -> None:
    body = _fixture("a44_success.xml").replace(
        b"<resolution>PT1H</resolution>",
        b"<resolution>PT60M</resolution>",
    )

    parsed = _parse_bytes(body, document_type="A44")

    assert parsed.series.source_resolution == "PT60M"
    assert parsed.series.canonical_resolution == "PT1H"


def test_combined_a81_produces_aligned_volume_and_capacity_price_series() -> None:
    parsed = _parse("a81_success.xml", document_type="A81")
    volume = parsed.series
    price = parsed.additional_series[0]

    assert parsed.source_document.business_type == "B95"
    assert parsed.source_document.process_type == "A52"
    assert parsed.source_document.flow_direction == "A03"
    assert parsed.source_document.market_agreement_type == "A01"
    assert parsed.source_document.root_document_type == "Balancing_MarketDocument"
    assert volume.source_document_type == price.source_document_type == "A81"
    assert volume.source_value_field == "quantity"
    assert price.source_value_field == "procurement_Price.amount"
    assert volume.source_unit == "MW"
    assert volume.canonical_resolution == "PT4H"
    assert volume.observations[0].value == 125.0
    assert price.source_unit == "EUR/MW/ISP"
    assert price.canonical_unit == "EUR/MW/h"
    assert price.canonical_resolution == "PT4H"
    assert price.observations[0].value == 17.5
    assert price.conversion is not None
    assert price.conversion["factor"] == 2.0
    assert price.conversion["formula"] == "source_value / ISP_duration_hours"
    assert price.observations[0].conversion_ref
    assert volume.observations[0].document_ref == price.observations[0].document_ref


def test_combined_a81_allows_absent_standard_market_product_and_preserves_null() -> None:
    body = _fixture("a81_success.xml").replace(
        b"    <standard_MarketProduct.marketProductType>A01</standard_MarketProduct.marketProductType>\n",
        b"",
    )

    parsed = _parse_bytes(body, document_type="A81")

    assert parsed.source_document.product_identity["market_product_type"] is None


def test_variable_sized_blocks_expand_until_the_next_position_or_period_end() -> None:
    parsed = _parse("a44_variable_blocks.xml", document_type="A44")

    assert [item.value for item in parsed.series.observations] == [10.0, 10.0, 20.0, 20.0]
    assert parsed.series.diagnostics["curve_type"] == "A03"
    assert parsed.series.diagnostics["expanded_variable_blocks"] == 2


def test_highest_comparable_revision_is_selected_and_older_evidence_retained() -> None:
    select_current = _require("select_current_entsoe_documents")
    parsed = [
        _parse("a44_revision_1.xml", document_type="A44"),
        _parse("a44_success.xml", document_type="A44"),
        _parse("a44_revision_3.xml", document_type="A44"),
    ]

    selection = select_current(parsed)

    assert len(selection.selected) == 1
    assert selection.selected[0].source_document.revision_number == 3
    assert selection.selected[0].series.observations[0].value == 480.0
    assert [
        item.source_document.revision_number for item in selection.superseded
    ] == [1, 2]
    assert all(
        item.source_document.status == "superseded" for item in selection.superseded
    )


@pytest.mark.parametrize(
    ("fixture_name", "error_name", "final_status"),
    [
        ("acknowledgement.xml", "EntsoeAcknowledgementError", "acknowledgement"),
        ("empty_publication.xml", "EntsoeEmptyResponseError", "empty_response"),
    ],
)
def test_acknowledgement_and_empty_documents_are_classified_explicitly(
    fixture_name: str,
    error_name: str,
    final_status: str,
) -> None:
    error_type = _require(error_name)

    with pytest.raises(error_type) as caught:
        _parse(fixture_name, document_type="A44")

    assert caught.value.diagnostic.final_status == final_status
    _assert_failure_diagnostic(caught.value, required_series="day_ahead_price")


@pytest.mark.parametrize("fixture_name", ["unsafe_doctype.xml", "unsafe_entity.xml"])
def test_dtd_and_entity_declarations_are_rejected_before_xml_parse(
    fixture_name: str,
) -> None:
    unsafe_error = _require("EntsoeUnsafeXmlError")
    body = _fixture(fixture_name) + f"<!-- {SENTINEL_TOKEN} -->".encode()

    with pytest.raises(unsafe_error, match="DTD|entity|unsafe") as caught:
        _parse_bytes(body, document_type="A44")

    _assert_failure_diagnostic(caught.value, required_series="day_ahead_price")


def test_untrusted_namespace_is_not_accepted_as_market_data() -> None:
    classification_error = _require("EntsoeXmlClassificationError")

    with pytest.raises(classification_error, match="namespace|root") as caught:
        _parse("wrong_namespace.xml", document_type="A44")

    _assert_failure_diagnostic(caught.value, required_series="day_ahead_price")


def test_malformed_xml_has_a_typed_sanitized_failure() -> None:
    parse_error = _require("EntsoeXmlParseError")
    body = _fixture("a44_success.xml")[:200] + SENTINEL_TOKEN.encode()

    with pytest.raises(parse_error, match="malformed|XML|parse") as caught:
        _parse_bytes(body, document_type="A44")

    _assert_failure_diagnostic(caught.value, required_series="day_ahead_price")


@pytest.mark.parametrize(
    ("fixture_name", "document_type", "missing_fragment", "required_series"),
    [
        (
            "a44_success.xml",
            "A44",
            b"<currency_Unit.name>EUR</currency_Unit.name>",
            "day_ahead_price",
        ),
        (
            "a81_success.xml",
            "A81",
            b"<flowDirection.direction>A03</flowDirection.direction>",
            "fcr_contracted_volume",
        ),
    ],
)
def test_required_semantic_fields_cannot_be_inferred_from_the_request(
    fixture_name: str,
    document_type: str,
    missing_fragment: bytes,
    required_series: str,
) -> None:
    semantic_error = _require("EntsoeSemanticValidationError")
    body = _fixture(fixture_name)
    assert missing_fragment in body

    with pytest.raises(semantic_error, match="missing|required|field") as caught:
        _parse_bytes(
            body.replace(missing_fragment, b""),
            document_type=document_type,
        )

    _assert_failure_diagnostic(caught.value, required_series=required_series)


def test_combined_a81_requires_both_quantity_and_price_at_every_change() -> None:
    semantic_error = _require("EntsoeSemanticValidationError")

    with pytest.raises(semantic_error, match="price|procurement|required|field") as caught:
        _parse("a81_missing_price.xml", document_type="A81")

    _assert_failure_diagnostic(
        caught.value,
        required_series="fcr_contracted_volume",
    )


def test_exact_duplicate_collapses_only_with_an_explicit_diagnostic() -> None:
    parsed = _parse("a44_exact_duplicate.xml", document_type="A44")

    assert len(parsed.series.observations) == 4
    assert parsed.series.diagnostics["exact_duplicates_collapsed"] == 1
    assert parsed.series.observations[1].value == -5.0


def test_conflicting_duplicate_is_rejected_with_observed_contract() -> None:
    duplicate_error = _require("EntsoeDuplicateObservationError")

    with pytest.raises(duplicate_error, match="duplicate|conflict|position") as caught:
        _parse("a44_conflicting_duplicate.xml", document_type="A44")

    _assert_failure_diagnostic(
        caught.value,
        required_series="day_ahead_price",
        observed_resolution="PT1H",
        observed_unit="EUR/MWh",
        observed_coverage=True,
    )


def test_gap_is_rejected_with_observed_coverage_and_resolution() -> None:
    coverage_error = _require("EntsoeCoverageError")

    with pytest.raises(coverage_error, match="gap|coverage|position") as caught:
        _parse("a44_gap.xml", document_type="A44")

    _assert_failure_diagnostic(
        caught.value,
        required_series="day_ahead_price",
        observed_resolution="PT1H",
        observed_unit="EUR/MWh",
        observed_coverage=True,
    )


def test_wrong_fcr_product_is_rejected_without_query_assumption() -> None:
    product_error = _require("EntsoeProductValidationError")

    with pytest.raises(product_error, match="product|direction|A03") as caught:
        _parse("a81_wrong_product.xml", document_type="A81")

    _assert_failure_diagnostic(
        caught.value,
        required_series="fcr_contracted_volume",
        observed_resolution="PT30M",
        observed_unit="MW",
        observed_coverage=True,
    )


def test_wrong_unit_is_rejected_with_observed_unit() -> None:
    unit_error = _require("EntsoeUnitValidationError")

    with pytest.raises(unit_error, match="unit|MWH|MAW") as caught:
        _parse("a81_wrong_unit.xml", document_type="A81")

    _assert_failure_diagnostic(
        caught.value,
        required_series="fcr_contracted_volume",
        observed_resolution="PT30M",
        observed_unit="EUR/MWh",
        observed_coverage=True,
    )


def test_pt4h_reconciliation_rejects_nonconstant_isps_without_inference() -> None:
    resolution_error = _require("EntsoeResolutionValidationError")
    body = _fixture("a81_success.xml").replace(
        b"</Point>",
        b"</Point><Point><position>2</position><quantity>126.0</quantity>"
        b"<procurement_Price.amount>8.75</procurement_Price.amount></Point>",
        1,
    )

    with pytest.raises(resolution_error, match="PT4H|constant|reconcil") as caught:
        _parse_bytes(body, document_type="A81")

    _assert_failure_diagnostic(
        caught.value,
        required_series="fcr_contracted_volume",
        observed_resolution="PT30M",
        observed_unit="MW",
        observed_coverage=True,
    )


def test_zip_response_members_are_bounded_and_preserve_member_provenance() -> None:
    extract_members = _require("extract_entsoe_xml_members")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("r3/a81.xml", _fixture("a81_success.xml"))

    members = extract_members(
        buffer.getvalue(),
        media_type="application/zip",
        max_uncompressed_bytes=1024 * 1024,
    )
    assert members == (("r3/a81.xml", _fixture("a81_success.xml")),)

    parse_entsoe_document = _require("parse_entsoe_document")
    parsed = parse_entsoe_document(
        members[0][1],
        request=_request_for(PERIOD_START, PERIOD_END),
        window=_window_for("A81", PERIOD_START, PERIOD_END),
        response_id="response-archive",
        archive_member=members[0][0],
    )
    assert parsed.source_document.archive_member == "r3/a81.xml"


@pytest.mark.parametrize(
    ("member_name", "body"),
    [
        ("../escape.xml", b"<x/>") ,
        ("nested.zip", b"PK\x03\x04"),
        ("not-xml.txt", b"<x/>") ,
    ],
)
def test_zip_response_rejects_traversal_nested_and_non_xml_members(
    member_name: str,
    body: bytes,
) -> None:
    extract_members = _require("extract_entsoe_xml_members")
    archive_error = _require("EntsoeArchiveValidationError")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        archive.writestr(member_name, body)

    with pytest.raises(archive_error, match="archive|ZIP|member|XML|path"):
        extract_members(
            buffer.getvalue(),
            media_type="application/zip",
            max_uncompressed_bytes=1024,
        )


def test_legacy_a89_query_is_rejected_by_the_revised_v1_profile() -> None:
    validation_error = _require("EntsoeRequestValidationError")

    with pytest.raises(validation_error, match="A44|A81|document_type"):
        _window(
            document_type="A89",
            process_type="A34",
            business_type="A95",
            market_agreement_type="A01",
        )


def test_wrong_resolution_is_rejected_with_observed_resolution() -> None:
    resolution_error = _require("EntsoeResolutionValidationError")

    with pytest.raises(resolution_error, match="resolution|PT30M|PT1H") as caught:
        _parse("a44_wrong_resolution.xml", document_type="A44")

    _assert_failure_diagnostic(
        caught.value,
        required_series="day_ahead_price",
        observed_resolution="PT30M",
        observed_unit="EUR/MWh",
        observed_coverage=True,
    )


@pytest.mark.parametrize(
    ("replacement", "error_name", "message"),
    [
        (b"<curveType>A99</curveType>", "EntsoeCurveValidationError", "curve"),
        (b"<position>0</position>", "EntsoeCurveValidationError", "position"),
        (b"<price.amount>NaN</price.amount>", "EntsoeValueValidationError", "finite"),
    ],
)
def test_unknown_curve_invalid_position_and_nonfinite_value_are_rejected(
    replacement: bytes,
    error_name: str,
    message: str,
) -> None:
    body = _fixture("a44_success.xml")
    if b"curveType" in replacement:
        body = body.replace(b"<curveType>A01</curveType>", replacement)
    elif b"position" in replacement:
        body = body.replace(b"<position>1</position>", replacement, 1)
    else:
        body = body.replace(b"<price.amount>475.0</price.amount>", replacement)
    error_type = _require(error_name)

    with pytest.raises(error_type, match=message) as caught:
        _parse_bytes(body, document_type="A44")

    _assert_failure_diagnostic(
        caught.value,
        required_series="day_ahead_price",
        observed_resolution="PT1H",
        observed_unit="EUR/MWh",
        observed_coverage=True,
    )


def test_spring_delivery_day_expands_to_23_unambiguous_utc_intervals() -> None:
    start = datetime(2022, 3, 26, 23, tzinfo=UTC)
    end = datetime(2022, 3, 27, 22, tzinfo=UTC)
    parsed = _parse(
        "a44_dst_spring_23h.xml",
        document_type="A44",
        start=start,
        end=end,
    )

    assert len(parsed.series.observations) == 23
    second = parsed.series.observations[1].interval
    assert second.local_start.hour == 1
    assert second.local_end.hour == 3
    assert second.start_utc_offset_seconds == 3600
    assert second.end_utc_offset_seconds == 7200


def test_fall_delivery_day_preserves_both_local_02_hours_and_folds() -> None:
    start = datetime(2022, 10, 29, 22, tzinfo=UTC)
    end = datetime(2022, 10, 30, 23, tzinfo=UTC)
    parsed = _parse(
        "a44_dst_fall_25h.xml",
        document_type="A44",
        start=start,
        end=end,
    )

    assert len(parsed.series.observations) == 25
    repeated = [
        item.interval
        for item in parsed.series.observations
        if item.interval.local_start.hour == 2
    ]
    assert len(repeated) == 2
    assert [item.start_fold for item in repeated] == [0, 1]
    assert [item.start_utc_offset_seconds for item in repeated] == [7200, 3600]
