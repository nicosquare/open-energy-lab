"""Public package-surface contracts for canonical market consumers."""

from __future__ import annotations

import importlib
import sys

import pytest


EXPECTED_EXPORTS = [
    "FRANCE_AREA_EIC",
    "FRANCE_MARKET_TIMEZONE",
    "FRANCE_PROFILE_ID",
    "HALF_OPEN_INTERVAL_CONVENTION",
    "MARKET_DATA_SCHEMA_VERSION",
    "REQUIRED_SERIES_IDS",
    "SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS",
    "CanonicalInterval",
    "MarketArtifactIntegrityError",
    "MarketArtifactPublicationError",
    "MarketArtifactValidationError",
    "MarketDataArtifact",
    "MarketObservation",
    "MarketSeries",
    "MarketTimeValidationError",
    "MultiRateTimeIndex",
    "RawResponseEvidence",
    "SourceDocumentEvidence",
    "SourceQueryWindow",
    "UnsupportedMarketArtifactVersionError",
    "build_local_delivery_day",
    "build_market_data_artifact",
    "build_multi_rate_index",
    "canonical_interval",
    "canonical_json_bytes",
    "load_market_data_artifact",
    "market_data_artifact_filename",
    "parse_iso8601_duration",
    "require_complete_blocks",
    "write_market_data_artifact",
    "ACTIVATION_SCHEMA_VERSION",
    "ACTIVATION_SIGN_SEMANTICS",
    "ACTIVATION_VALUE_SEMANTICS",
    "SUPPORTED_ACTIVATION_SCHEMA_VERSIONS",
    "ActivationImportRequest",
    "ActivationIntegrityError",
    "ActivationPublicationError",
    "ActivationSample",
    "ActivationValidationError",
    "RegulationActivationTrace",
    "UnsupportedActivationSchemaError",
    "import_regulation_activation_trace",
    "load_regulation_activation_trace",
    "write_regulation_activation_trace",
    "RESTORATION_MARKET_SCHEMA_VERSION",
    "RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION",
    "SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS",
    "SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS",
    "ObservationValueState",
    "SeriesAvailability",
    "RestorationDataSource",
    "RawRetentionPolicy",
    "RestorationArtifactValidationError",
    "UnsupportedRestorationArtifactVersionError",
    "RestorationArtifactIntegrityError",
    "RestorationArtifactPublicationError",
    "RestorationMarketObservation",
    "RestorationMarketSeries",
    "SourceRequestEvidence",
    "RestorationMarketArtifact",
    "RestorationStudyBundleRef",
    "RestorationStudyBundle",
    "build_restoration_market_artifact",
    "canonical_restoration_json_bytes",
    "restoration_market_artifact_filename",
    "write_restoration_market_artifact",
    "load_restoration_market_artifact",
    "build_restoration_study_bundle",
    "load_restoration_study_bundle",
    "RestorationProduct",
    "RestorationDirection",
    "RestorationSourceKind",
    "RestorationActivationValidationError",
    "RestorationActivationIntegrityError",
    "DerivedSimulationMapping",
    "AFRRActivationSample",
    "AFRRActivationTrajectory",
    "MFRRActivationKind",
    "MFRRActivationEvent",
    "MFRRActivationSequence",
    "build_derived_simulation_mapping",
    "build_afrr_activation_trajectory",
    "build_afrr_trajectory_from_rte_requested_need",
    "build_mfrr_activation_sequence",
    "build_mfrr_sequence_from_rte_sa_requested_volume",
]
RELOADED_MARKET_MODULES = (
    "open_energy_lab.market.rte",
    "open_energy_lab.market.entsoe",
    "open_energy_lab.market.restoration_artifact",
    "open_energy_lab.market.restoration_activation",
    "open_energy_lab.market.activation",
    "open_energy_lab.market.artifact",
    "open_energy_lab.market.time",
    "open_energy_lab.market",
)


@pytest.fixture(autouse=True)
def _restore_market_module_identity_after_fresh_surface_check():
    """Fresh-root checks must not replace types held by collected test modules."""

    before = {
        name: sys.modules[name]
        for name in RELOADED_MARKET_MODULES
        if name in sys.modules
    }
    root = sys.modules.get("open_energy_lab")
    root_market = getattr(root, "market", None) if root is not None else None
    yield
    for name in RELOADED_MARKET_MODULES:
        sys.modules.pop(name, None)
    sys.modules.update(before)
    if root is not None:
        if root_market is None:
            root.__dict__.pop("market", None)
        else:
            root.market = root_market


def _fresh_market_root():
    for module_name in RELOADED_MARKET_MODULES:
        sys.modules.pop(module_name, None)
    return importlib.import_module("open_energy_lab.market")


def test_market_root_publishes_the_documented_canonical_surface():
    market = _fresh_market_root()

    assert market.__all__ == EXPECTED_EXPORTS
    assert set(EXPECTED_EXPORTS).issubset(dir(market))
    assert "fetch_entsoe_market_data" not in market.__all__
    assert "refresh_entsoe_market_data" not in market.__all__


def test_market_root_defers_canonical_modules_until_symbol_access():
    market = _fresh_market_root()

    assert "open_energy_lab.market.time" not in sys.modules
    assert "open_energy_lab.market.artifact" not in sys.modules
    assert "open_energy_lab.market.activation" not in sys.modules
    assert "open_energy_lab.market.entsoe" not in sys.modules
    assert "open_energy_lab.market.restoration_artifact" not in sys.modules
    assert "open_energy_lab.market.restoration_activation" not in sys.modules
    assert "open_energy_lab.market.rte" not in sys.modules

    assert (
        market.AFRRActivationTrajectory.__module__
        == "open_energy_lab.market.restoration_activation"
    )
    assert "open_energy_lab.market.restoration_activation" in sys.modules
    assert "open_energy_lab.market.rte" not in sys.modules

    assert market.CanonicalInterval.__module__ == "open_energy_lab.market.time"
    assert "open_energy_lab.market.time" in sys.modules
    assert "open_energy_lab.market.artifact" not in sys.modules

    assert market.MarketDataArtifact.__module__ == "open_energy_lab.market.artifact"
    assert "open_energy_lab.market.artifact" in sys.modules
    assert "open_energy_lab.market.activation" not in sys.modules
    assert "open_energy_lab.market.entsoe" not in sys.modules

    assert (
        market.RegulationActivationTrace.__module__
        == "open_energy_lab.market.activation"
    )
    assert "open_energy_lab.market.activation" in sys.modules

    assert (
        market.RestorationMarketArtifact.__module__
        == "open_energy_lab.market.restoration_artifact"
    )
    assert "open_energy_lab.market.restoration_artifact" in sys.modules
    assert "open_energy_lab.market.rte" not in sys.modules


def test_every_documented_export_resolves_from_its_owned_module():
    market = _fresh_market_root()
    time_exports = {
        "FRANCE_MARKET_TIMEZONE",
        "HALF_OPEN_INTERVAL_CONVENTION",
        "CanonicalInterval",
        "MarketTimeValidationError",
        "MultiRateTimeIndex",
        "build_local_delivery_day",
        "build_multi_rate_index",
        "canonical_interval",
        "parse_iso8601_duration",
        "require_complete_blocks",
    }
    activation_exports = {
        "ACTIVATION_SCHEMA_VERSION",
        "ACTIVATION_SIGN_SEMANTICS",
        "ACTIVATION_VALUE_SEMANTICS",
        "SUPPORTED_ACTIVATION_SCHEMA_VERSIONS",
        "ActivationImportRequest",
        "ActivationIntegrityError",
        "ActivationPublicationError",
        "ActivationSample",
        "ActivationValidationError",
        "RegulationActivationTrace",
        "UnsupportedActivationSchemaError",
        "import_regulation_activation_trace",
        "load_regulation_activation_trace",
        "write_regulation_activation_trace",
    }
    restoration_exports = {
        "RESTORATION_MARKET_SCHEMA_VERSION",
        "RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION",
        "SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS",
        "SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS",
        "ObservationValueState",
        "SeriesAvailability",
        "RestorationDataSource",
        "RawRetentionPolicy",
        "RestorationArtifactValidationError",
        "UnsupportedRestorationArtifactVersionError",
        "RestorationArtifactIntegrityError",
        "RestorationArtifactPublicationError",
        "RestorationMarketObservation",
        "RestorationMarketSeries",
        "SourceRequestEvidence",
        "RestorationMarketArtifact",
        "RestorationStudyBundleRef",
        "RestorationStudyBundle",
        "build_restoration_market_artifact",
        "canonical_restoration_json_bytes",
        "restoration_market_artifact_filename",
        "write_restoration_market_artifact",
        "load_restoration_market_artifact",
        "build_restoration_study_bundle",
        "load_restoration_study_bundle",
    }
    restoration_activation_exports = {
        "RestorationProduct",
        "RestorationDirection",
        "RestorationSourceKind",
        "RestorationActivationValidationError",
        "RestorationActivationIntegrityError",
        "DerivedSimulationMapping",
        "AFRRActivationSample",
        "AFRRActivationTrajectory",
        "MFRRActivationKind",
        "MFRRActivationEvent",
        "MFRRActivationSequence",
        "build_derived_simulation_mapping",
        "build_afrr_activation_trajectory",
        "build_afrr_trajectory_from_rte_requested_need",
        "build_mfrr_activation_sequence",
        "build_mfrr_sequence_from_rte_sa_requested_volume",
    }

    for name in EXPECTED_EXPORTS:
        value = getattr(market, name)
        if hasattr(value, "__module__"):
            owner = (
                "time"
                if name in time_exports
                else "activation"
                if name in activation_exports
                else "restoration_artifact"
                if name in restoration_exports
                else "restoration_activation"
                if name in restoration_activation_exports
                else "artifact"
            )
            assert value.__module__ == f"open_energy_lab.market.{owner}"

    assert "open_energy_lab.market.entsoe" not in sys.modules
    assert "open_energy_lab.market.rte" not in sys.modules


def test_unknown_market_root_attribute_fails_without_adapter_import():
    market = _fresh_market_root()

    with pytest.raises(AttributeError, match="no attribute 'unknown_contract'"):
        getattr(market, "unknown_contract")
    assert "open_energy_lab.market.entsoe" not in sys.modules
    assert "open_energy_lab.market.rte" not in sys.modules
