"""Import-light public boundary for canonical market-data workflows.

The package root exposes source-independent time and artifact contracts lazily.
Source adapters, transports, credentials, notebooks, solvers, and legacy
modules remain outside this import boundary.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .activation import (
        ACTIVATION_SCHEMA_VERSION,
        ACTIVATION_SIGN_SEMANTICS,
        ACTIVATION_VALUE_SEMANTICS,
        SUPPORTED_ACTIVATION_SCHEMA_VERSIONS,
        ActivationImportRequest,
        ActivationIntegrityError,
        ActivationPublicationError,
        ActivationSample,
        ActivationValidationError,
        RegulationActivationTrace,
        UnsupportedActivationSchemaError,
        import_regulation_activation_trace,
        load_regulation_activation_trace,
        write_regulation_activation_trace,
    )
    from .artifact import (
        FRANCE_AREA_EIC,
        FRANCE_PROFILE_ID,
        MARKET_DATA_SCHEMA_VERSION,
        REQUIRED_SERIES_IDS,
        SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS,
        MarketArtifactIntegrityError,
        MarketArtifactPublicationError,
        MarketArtifactValidationError,
        MarketDataArtifact,
        MarketObservation,
        MarketSeries,
        RawResponseEvidence,
        SourceDocumentEvidence,
        SourceQueryWindow,
        UnsupportedMarketArtifactVersionError,
        build_market_data_artifact,
        canonical_json_bytes,
        load_market_data_artifact,
        market_data_artifact_filename,
        write_market_data_artifact,
    )
    from .restoration_artifact import (
        RESTORATION_MARKET_SCHEMA_VERSION,
        RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION,
        SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS,
        SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS,
        ObservationValueState,
        RawRetentionPolicy,
        RestorationArtifactIntegrityError,
        RestorationArtifactPublicationError,
        RestorationArtifactValidationError,
        RestorationDataSource,
        RestorationMarketArtifact,
        RestorationMarketObservation,
        RestorationMarketSeries,
        RestorationStudyBundle,
        RestorationStudyBundleRef,
        SeriesAvailability,
        SourceRequestEvidence,
        UnsupportedRestorationArtifactVersionError,
        build_restoration_market_artifact,
        build_restoration_study_bundle,
        canonical_restoration_json_bytes,
        load_restoration_market_artifact,
        load_restoration_study_bundle,
        restoration_market_artifact_filename,
        write_restoration_market_artifact,
    )
    from .restoration_activation import (
        AFRRActivationSample,
        AFRRActivationTrajectory,
        DerivedSimulationMapping,
        MFRRActivationEvent,
        MFRRActivationKind,
        MFRRActivationSequence,
        RestorationActivationIntegrityError,
        RestorationActivationValidationError,
        RestorationDirection,
        RestorationProduct,
        RestorationSourceKind,
        build_afrr_activation_trajectory,
        build_afrr_trajectory_from_rte_requested_need,
        build_derived_simulation_mapping,
        build_mfrr_activation_sequence,
        build_mfrr_sequence_from_rte_sa_requested_volume,
    )
    from .time import (
        FRANCE_MARKET_TIMEZONE,
        HALF_OPEN_INTERVAL_CONVENTION,
        CanonicalInterval,
        MarketTimeValidationError,
        MultiRateTimeIndex,
        build_local_delivery_day,
        build_multi_rate_index,
        canonical_interval,
        parse_iso8601_duration,
        require_complete_blocks,
    )

_EXPORT_MAP = {
    "FRANCE_AREA_EIC": ("artifact", "FRANCE_AREA_EIC"),
    "FRANCE_MARKET_TIMEZONE": ("time", "FRANCE_MARKET_TIMEZONE"),
    "FRANCE_PROFILE_ID": ("artifact", "FRANCE_PROFILE_ID"),
    "HALF_OPEN_INTERVAL_CONVENTION": ("time", "HALF_OPEN_INTERVAL_CONVENTION"),
    "MARKET_DATA_SCHEMA_VERSION": ("artifact", "MARKET_DATA_SCHEMA_VERSION"),
    "REQUIRED_SERIES_IDS": ("artifact", "REQUIRED_SERIES_IDS"),
    "SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS": (
        "artifact",
        "SUPPORTED_MARKET_DATA_SCHEMA_VERSIONS",
    ),
    "CanonicalInterval": ("time", "CanonicalInterval"),
    "MarketArtifactIntegrityError": ("artifact", "MarketArtifactIntegrityError"),
    "MarketArtifactPublicationError": (
        "artifact",
        "MarketArtifactPublicationError",
    ),
    "MarketArtifactValidationError": ("artifact", "MarketArtifactValidationError"),
    "MarketDataArtifact": ("artifact", "MarketDataArtifact"),
    "MarketObservation": ("artifact", "MarketObservation"),
    "MarketSeries": ("artifact", "MarketSeries"),
    "MarketTimeValidationError": ("time", "MarketTimeValidationError"),
    "MultiRateTimeIndex": ("time", "MultiRateTimeIndex"),
    "RawResponseEvidence": ("artifact", "RawResponseEvidence"),
    "SourceDocumentEvidence": ("artifact", "SourceDocumentEvidence"),
    "SourceQueryWindow": ("artifact", "SourceQueryWindow"),
    "UnsupportedMarketArtifactVersionError": (
        "artifact",
        "UnsupportedMarketArtifactVersionError",
    ),
    "build_local_delivery_day": ("time", "build_local_delivery_day"),
    "build_market_data_artifact": ("artifact", "build_market_data_artifact"),
    "build_multi_rate_index": ("time", "build_multi_rate_index"),
    "canonical_interval": ("time", "canonical_interval"),
    "canonical_json_bytes": ("artifact", "canonical_json_bytes"),
    "load_market_data_artifact": ("artifact", "load_market_data_artifact"),
    "market_data_artifact_filename": (
        "artifact",
        "market_data_artifact_filename",
    ),
    "parse_iso8601_duration": ("time", "parse_iso8601_duration"),
    "require_complete_blocks": ("time", "require_complete_blocks"),
    "write_market_data_artifact": ("artifact", "write_market_data_artifact"),
    "ACTIVATION_SCHEMA_VERSION": ("activation", "ACTIVATION_SCHEMA_VERSION"),
    "ACTIVATION_SIGN_SEMANTICS": ("activation", "ACTIVATION_SIGN_SEMANTICS"),
    "ACTIVATION_VALUE_SEMANTICS": ("activation", "ACTIVATION_VALUE_SEMANTICS"),
    "SUPPORTED_ACTIVATION_SCHEMA_VERSIONS": (
        "activation",
        "SUPPORTED_ACTIVATION_SCHEMA_VERSIONS",
    ),
    "ActivationImportRequest": ("activation", "ActivationImportRequest"),
    "ActivationIntegrityError": ("activation", "ActivationIntegrityError"),
    "ActivationPublicationError": ("activation", "ActivationPublicationError"),
    "ActivationSample": ("activation", "ActivationSample"),
    "ActivationValidationError": ("activation", "ActivationValidationError"),
    "RegulationActivationTrace": ("activation", "RegulationActivationTrace"),
    "UnsupportedActivationSchemaError": (
        "activation",
        "UnsupportedActivationSchemaError",
    ),
    "import_regulation_activation_trace": (
        "activation",
        "import_regulation_activation_trace",
    ),
    "load_regulation_activation_trace": (
        "activation",
        "load_regulation_activation_trace",
    ),
    "write_regulation_activation_trace": (
        "activation",
        "write_regulation_activation_trace",
    ),
    "RESTORATION_MARKET_SCHEMA_VERSION": (
        "restoration_artifact",
        "RESTORATION_MARKET_SCHEMA_VERSION",
    ),
    "RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION": (
        "restoration_artifact",
        "RESTORATION_STUDY_BUNDLE_SCHEMA_VERSION",
    ),
    "SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS": (
        "restoration_artifact",
        "SUPPORTED_RESTORATION_MARKET_SCHEMA_VERSIONS",
    ),
    "SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS": (
        "restoration_artifact",
        "SUPPORTED_RESTORATION_STUDY_BUNDLE_SCHEMA_VERSIONS",
    ),
    "ObservationValueState": ("restoration_artifact", "ObservationValueState"),
    "SeriesAvailability": ("restoration_artifact", "SeriesAvailability"),
    "RestorationDataSource": ("restoration_artifact", "RestorationDataSource"),
    "RawRetentionPolicy": ("restoration_artifact", "RawRetentionPolicy"),
    "RestorationArtifactValidationError": (
        "restoration_artifact",
        "RestorationArtifactValidationError",
    ),
    "UnsupportedRestorationArtifactVersionError": (
        "restoration_artifact",
        "UnsupportedRestorationArtifactVersionError",
    ),
    "RestorationArtifactIntegrityError": (
        "restoration_artifact",
        "RestorationArtifactIntegrityError",
    ),
    "RestorationArtifactPublicationError": (
        "restoration_artifact",
        "RestorationArtifactPublicationError",
    ),
    "RestorationMarketObservation": (
        "restoration_artifact",
        "RestorationMarketObservation",
    ),
    "RestorationMarketSeries": (
        "restoration_artifact",
        "RestorationMarketSeries",
    ),
    "SourceRequestEvidence": ("restoration_artifact", "SourceRequestEvidence"),
    "RestorationMarketArtifact": (
        "restoration_artifact",
        "RestorationMarketArtifact",
    ),
    "RestorationStudyBundleRef": (
        "restoration_artifact",
        "RestorationStudyBundleRef",
    ),
    "RestorationStudyBundle": (
        "restoration_artifact",
        "RestorationStudyBundle",
    ),
    "build_restoration_market_artifact": (
        "restoration_artifact",
        "build_restoration_market_artifact",
    ),
    "canonical_restoration_json_bytes": (
        "restoration_artifact",
        "canonical_restoration_json_bytes",
    ),
    "restoration_market_artifact_filename": (
        "restoration_artifact",
        "restoration_market_artifact_filename",
    ),
    "write_restoration_market_artifact": (
        "restoration_artifact",
        "write_restoration_market_artifact",
    ),
    "load_restoration_market_artifact": (
        "restoration_artifact",
        "load_restoration_market_artifact",
    ),
    "build_restoration_study_bundle": (
        "restoration_artifact",
        "build_restoration_study_bundle",
    ),
    "load_restoration_study_bundle": (
        "restoration_artifact",
        "load_restoration_study_bundle",
    ),
    "RestorationProduct": ("restoration_activation", "RestorationProduct"),
    "RestorationDirection": (
        "restoration_activation",
        "RestorationDirection",
    ),
    "RestorationSourceKind": (
        "restoration_activation",
        "RestorationSourceKind",
    ),
    "RestorationActivationValidationError": (
        "restoration_activation",
        "RestorationActivationValidationError",
    ),
    "RestorationActivationIntegrityError": (
        "restoration_activation",
        "RestorationActivationIntegrityError",
    ),
    "DerivedSimulationMapping": (
        "restoration_activation",
        "DerivedSimulationMapping",
    ),
    "AFRRActivationSample": (
        "restoration_activation",
        "AFRRActivationSample",
    ),
    "AFRRActivationTrajectory": (
        "restoration_activation",
        "AFRRActivationTrajectory",
    ),
    "MFRRActivationKind": (
        "restoration_activation",
        "MFRRActivationKind",
    ),
    "MFRRActivationEvent": (
        "restoration_activation",
        "MFRRActivationEvent",
    ),
    "MFRRActivationSequence": (
        "restoration_activation",
        "MFRRActivationSequence",
    ),
    "build_derived_simulation_mapping": (
        "restoration_activation",
        "build_derived_simulation_mapping",
    ),
    "build_afrr_activation_trajectory": (
        "restoration_activation",
        "build_afrr_activation_trajectory",
    ),
    "build_afrr_trajectory_from_rte_requested_need": (
        "restoration_activation",
        "build_afrr_trajectory_from_rte_requested_need",
    ),
    "build_mfrr_activation_sequence": (
        "restoration_activation",
        "build_mfrr_activation_sequence",
    ),
    "build_mfrr_sequence_from_rte_sa_requested_volume": (
        "restoration_activation",
        "build_mfrr_sequence_from_rte_sa_requested_volume",
    ),
}

__all__ = list(_EXPORT_MAP)


def __getattr__(name: str) -> Any:
    """Resolve documented exports without eagerly loading feature modules."""

    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include lazy exports in interactive and introspection results."""

    return sorted(set(globals()) | set(__all__))
