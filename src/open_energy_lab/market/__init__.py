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
