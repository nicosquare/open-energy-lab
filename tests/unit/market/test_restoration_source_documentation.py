"""Documentation completeness contract for every demonstrated source field."""

from __future__ import annotations

from pathlib import Path


RTE_DOC = Path("docs/architecture/rte-balancing-energy.md")
ENTSOE_DOC = Path("docs/architecture/entsoe-transparency-platform.md")
MIGRATION_DOC = Path("docs/migration/afrr-mfrr-services.md")
FIXTURE_DOC = Path("tests/fixtures/restoration/README.md")
NOTEBOOK = Path(
    "examples/restoration_services/restoration_services_walkthrough.ipynb"
)

AFRR_FIELDS = {
    "afrr_requested_need_upward": "upward_afrr_requested_need",
    "afrr_requested_need_downward": "downward_afrr_requested_need",
    "afrr_activated_for_fr_upward": "upward_afrr_activated_volume_for_fr",
    "afrr_activated_for_fr_downward": "downward_afrr_activated_volume_for_fr",
    "afrr_activated_in_fr_upward": "upward_afrr_activated_volume_in_fr",
    "afrr_activated_in_fr_downward": "downward_afrr_activated_volume_in_fr",
    "afrr_weighted_average_price_upward": (
        "upward_weighted_average_price_afrr_activated_for_fr"
    ),
    "afrr_weighted_average_price_downward": (
        "downward_weighted_average_price_afrr_activated_for_fr"
    ),
}

MFRR_FIELD_GROUPS = {
    "mfrr_sa_requested_volume_*": "total_requested_volume_sa",
    "mfrr_sa_satisfied_need_*": "total_satisfied_need_sa",
    "mfrr_sa_activated_volume_*": "total_activated_volume_sa",
    "mfrr_da_requested_volume_*": "total_requested_volume_da",
    "mfrr_da_satisfied_need_*": "total_satisfied_need_da",
    "mfrr_da_activated_volume_*": "total_activated_volume_da",
    "mfrr_clearing_price_*": "clearing_price",
    "mfrr_settlement_price_current_*": "settlement_price_current",
    "mfrr_settlement_price_previous_*": "settlement_price_previous",
    "mfrr_submitted_offer_volume_*": "total_volume_submitted_offers",
    "mfrr_filtered_offer_volume_*": "total_volume_filtered_offers",
}


def _read(path: Path) -> str:
    assert path.is_file(), f"missing documentation artifact: {path}"
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_rte_document_maps_every_closed_series_to_exact_source_meaning() -> None:
    content = _read(RTE_DOC)
    for canonical_id, source_field in AFRR_FIELDS.items():
        assert f"`{canonical_id}`" in content
        assert f"`{source_field.lower()}`" in content
    for canonical_group, source_field in MFRR_FIELD_GROUPS.items():
        assert f"`{canonical_group}`" in content
        assert f"`{source_field}`" in content

    for nested_field in (
        "requested_activated_volumes_by_prices",
        "activation_type",
        "requested_price",
        "requested_volume",
        "satisfied_need",
        "`atp`",
    ):
        assert nested_field in content


def test_source_document_covers_every_required_provenance_dimension() -> None:
    content = _read(RTE_DOC)
    required = (
        "rte réseau de transport d'électricité",
        "catalog version **5.2**",
        "path segment `v5`",
        "/open_api/balancing_energy/v5/standard_afrr_data",
        "/open_api/balancing_energy/v5/standard_mfrr_data",
        "`start_date` is inclusive and `end_date` is exclusive",
        "at most 31 days per caller request",
        "source calls of at most one day",
        "pt15m",
        "mw",
        "eur/mwh",
        "continuous, start-inclusive/end-exclusive utc",
        "`europe/paris` local start and end labels",
        "chronological row ordering while retaining `source_row`",
        "field absent, source json null, and numeric zero",
        "observed area aggregate",
        "derived_simulation",
        "scenario_proxy",
        "not commands addressed to the reference battery",
        "rte balancing energy api v5.2; normalized by open energy lab",
        "repository_publication",
        "packages, releases, public ci artifacts, public forks or mirrors",
        "digest-only",
        "at most three total attempts",
    )
    missing = [term for term in required if term not in content]
    assert missing == []


def test_derived_display_fields_have_owner_transformation_and_limits() -> None:
    migration = _read(MIGRATION_DOC)
    notebook = _read(NOTEBOOK)
    required_migration = (
        "single-owner boundaries",
        "requested_bess_kw = requested_area_mw * 1000 * 0.001",
        "fixed for the complete scenario",
        "no request is clipped",
        "interval-average requests",
        "rectangular-shape assumptions",
        "2,000 kwh",
        "500 / 500 kw",
        "0.95 / 0.95",
        "absolute numeric tolerance",
        "scenario_proxy",
        "not an electrochemical-aging model",
        "feature 011 is additive",
        "explicit exclusions",
    )
    assert [term for term in required_migration if term not in migration] == []

    required_notebook = (
        "provenance_table",
        "afrr_market_table",
        "mfrr_market_table",
        "commitment_table",
        "activation_table",
        "physical_table",
        "performance_table",
        "energy_table",
        "settlement_table",
        "reproducibility_table",
        "notebook_display_fingerprint",
        "result_set_fingerprint",
        "derived_simulation",
        "not observed battery dispatch",
    )
    assert [term for term in required_notebook if term not in notebook] == []


def test_entsoe_composition_and_fixture_evidence_remain_independent() -> None:
    entsoe = _read(ENTSOE_DOC)
    fixture = _read(FIXTURE_DOC)
    required_entsoe = (
        "feature 011 does not add an entso-e afrr or mfrr acquisition profile",
        "`fr-day-ahead-symmetric-fcr-v1`",
        "a44 `day_ahead_price`",
        "series fingerprint",
        "`restorationstudybundle`",
        "does not copy, merge, rename, resample, or reinterpret",
        "never an automatic fallback",
        "strictest policy",
    )
    assert [term for term in required_entsoe if term not in entsoe] == []

    required_fixture = (
        "origin and owner:",
        "source api/profile/version:",
        "requested and covered utc period:",
        "resolution, units, and directions:",
        "generation command:",
        "transformation history:",
        "raw-response digest/retention:",
        "refresh policy:",
        "83f0c88e5c8d9c0f781305a9552596c3a03956588a75871e9f78e97415811516",
        "d2d4007fafe5138f0bfdc8d91ba232c435f9b4f7097a0cc519064011c624ca10",
        "88ab88e3859e4fe81555651468bcc9e4c474db43feee11ecd1eef6b18568e976",
        "abe68d7130db368245ca41d972dd41ec5a544ba4ef25d208c93377b3e440586f",
    )
    assert [term for term in required_fixture if term not in fixture] == []
