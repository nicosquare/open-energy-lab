"""TMY fetch helpers for the stochastic-weather feature."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._canonical import (
    CanonicalWeatherDataset,
    SOURCE_FIELD_LABELS,
    normalize_recorded_tmy_response,
)


class WeatherLocationUnavailableError(ValueError):
    """Raised when the upstream weather source cannot serve a location."""


class WeatherCacheUnavailableError(RuntimeError):
    """Raised when neither a compatible canonical cache nor a fetch is available."""


DEFAULT_PVGIS_TMY_ENDPOINT = "https://re.jrc.ec.europa.eu/api/v5_3/"
CANONICAL_TMY_CACHE_SCHEMA_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class PVGISTMYRequestConfig:
    """Explicit versioned PVGIS TMY request and provenance configuration."""

    endpoint_url: str = DEFAULT_PVGIS_TMY_ENDPOINT
    use_horizon: bool = True
    start_year: int | None = None
    end_year: int | None = None
    timeout_seconds: int = 30
    map_variables: bool = True

    def __post_init__(self) -> None:
        endpoint = str(self.endpoint_url)
        if not endpoint.startswith("https://"):
            raise ValueError("endpoint_url must use HTTPS")
        if not endpoint.endswith("/"):
            endpoint += "/"
        object.__setattr__(self, "endpoint_url", endpoint)
        if not isinstance(self.use_horizon, bool):
            raise TypeError("use_horizon must be boolean")
        if not isinstance(self.map_variables, bool):
            raise TypeError("map_variables must be boolean")
        if (self.start_year is None) != (self.end_year is None):
            raise ValueError("start_year and end_year must be supplied together")
        if self.start_year is not None:
            start = int(self.start_year)
            end = int(self.end_year)
            if start > end:
                raise ValueError("start_year must not exceed end_year")
            object.__setattr__(self, "start_year", start)
            object.__setattr__(self, "end_year", end)
        if isinstance(self.timeout_seconds, bool) or int(self.timeout_seconds) <= 0:
            raise ValueError("timeout_seconds must be a positive integer")
        object.__setattr__(self, "timeout_seconds", int(self.timeout_seconds))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def fetch_tmy_dataset(
    latitude: float,
    longitude: float,
    *,
    recorded_response: Mapping[str, object] | None = None,
    fetcher: Callable[[float, float], object] | None = None,
    timezone_name: str | None = None,
    source_name: str = "PVGIS TMY",
    timestep_hours: float | None = None,
    api_config: PVGISTMYRequestConfig | None = None,
) -> CanonicalWeatherDataset:
    """Fetch or accept a recorded TMY response and normalize it."""

    response = _resolve_tmy_response(
        latitude,
        longitude,
        recorded_response=recorded_response,
        fetcher=fetcher,
        timezone_name=timezone_name,
        source_name=source_name,
        api_config=api_config,
    )
    if _response_marks_location_unavailable(response):
        detail = response.get("error") or response.get("message") or "location unavailable"
        raise WeatherLocationUnavailableError(
            f"weather source is unable to serve location ({latitude}, {longitude}): {detail}"
        )

    effective_timezone = timezone_name or _string_value(response.get("timezone_name"))
    if not effective_timezone:
        raise ValueError("TMY response must provide timezone_name")

    effective_source_name = _string_value(response.get("source_name")) or source_name
    return normalize_recorded_tmy_response(
        response,
        latitude=latitude,
        longitude=longitude,
        timezone_name=effective_timezone,
        source_name=effective_source_name,
        timestep_hours=timestep_hours,
    )


def _resolve_tmy_response(
    latitude: float,
    longitude: float,
    *,
    recorded_response: Mapping[str, object] | None,
    fetcher: Callable[[float, float], object] | None,
    timezone_name: str | None = None,
    source_name: str = "PVGIS TMY",
    api_config: PVGISTMYRequestConfig | None = None,
) -> Mapping[str, object]:
    if recorded_response is not None:
        return recorded_response
    response = _fetch_with_default_or_override(
        latitude,
        longitude,
        fetcher=fetcher,
        timezone_name=timezone_name,
        source_name=source_name,
        api_config=api_config,
    )
    if not isinstance(response, Mapping):
        raise TypeError("weather fetch workflow must resolve to a mapping response")
    return response


def _fetch_with_default_or_override(
    latitude: float,
    longitude: float,
    *,
    fetcher: Callable[[float, float], object] | None,
    timezone_name: str | None,
    source_name: str,
    api_config: PVGISTMYRequestConfig | None,
) -> Mapping[str, object]:
    config = api_config or PVGISTMYRequestConfig()
    if fetcher is not None:
        raw_result = fetcher(latitude, longitude)
    else:
        raw_result = _fetch_live_pvgis_result(latitude, longitude, config=config)
    response = _coerce_fetch_result(
        raw_result,
        latitude=latitude,
        longitude=longitude,
        timezone_name=timezone_name,
        source_name=source_name,
    )
    source_metadata = response.get("source_metadata", {})
    if not isinstance(source_metadata, Mapping):
        raise TypeError("source_metadata must be a mapping")
    return dict(response) | {
        "source_metadata": dict(source_metadata)
        | {"pvgis_request": config.to_dict()}
    }


def _fetch_live_pvgis_result(
    latitude: float,
    longitude: float,
    *,
    config: PVGISTMYRequestConfig | None = None,
) -> object:
    request = config or PVGISTMYRequestConfig()
    try:
        pvlib = _import_pvlib()
        return pvlib.iotools.get_pvgis_tmy(
            latitude,
            longitude,
            outputformat="json",
            usehorizon=request.use_horizon,
            startyear=request.start_year,
            endyear=request.end_year,
            map_variables=request.map_variables,
            url=request.endpoint_url,
            timeout=request.timeout_seconds,
        )
    except Exception as exc:
        if _exception_marks_location_unavailable(exc):
            raise WeatherLocationUnavailableError(
                f"weather source is unable to serve location ({latitude}, {longitude}): {exc}"
            ) from exc
        raise


def load_or_fetch_tmy_dataset(
    latitude: float,
    longitude: float,
    *,
    timezone_name: str,
    cache_path: str | Path,
    api_config: PVGISTMYRequestConfig | None = None,
    allow_network: bool = True,
    refresh_cache: bool = False,
    fetcher: Callable[[float, float], object] | None = None,
    source_name: str = "PVGIS TMY",
) -> CanonicalWeatherDataset:
    """Load a compatible canonical TMY cache or fetch and atomically create it."""

    path = Path(cache_path)
    config = api_config or PVGISTMYRequestConfig()
    request_payload = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "timezone_name": str(timezone_name),
        "source_name": str(source_name),
        "api_config": config.to_dict(),
    }
    if path.exists() and not refresh_cache:
        dataset, payload_sha = _load_canonical_cache(
            path,
            expected_request=request_payload,
        )
        return _with_cache_provenance(
            dataset,
            path=path,
            status="hit",
            payload_sha256=payload_sha,
        )
    if not allow_network:
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} is unavailable and network access is disabled"
        )

    try:
        dataset = fetch_tmy_dataset(
            latitude,
            longitude,
            fetcher=fetcher,
            timezone_name=timezone_name,
            source_name=source_name,
            timestep_hours=1.0,
            api_config=config,
        )
    except Exception as exc:
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} is unavailable and the configured PVGIS fetch failed: {exc}"
        ) from exc

    cache_payload = {
        "schema_version": CANONICAL_TMY_CACHE_SCHEMA_VERSION,
        "request": request_payload,
        "dataset": _canonical_dataset_to_dict(dataset),
    }
    canonical_bytes = (
        json.dumps(cache_payload, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    payload_sha = hashlib.sha256(canonical_bytes).hexdigest()
    _atomic_write(path, canonical_bytes)
    return _with_cache_provenance(
        dataset,
        path=path,
        status="refreshed" if refresh_cache else "miss_fetched",
        payload_sha256=payload_sha,
    )


def _load_canonical_cache(
    path: Path,
    *,
    expected_request: Mapping[str, object],
) -> tuple[CanonicalWeatherDataset, str]:
    payload_bytes = path.read_bytes()
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} is not valid JSON"
        ) from exc
    if not isinstance(payload, Mapping):
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} must contain a JSON object"
        )
    if payload.get("schema_version") != CANONICAL_TMY_CACHE_SCHEMA_VERSION:
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} has unsupported schema_version "
            f"{payload.get('schema_version')!r}"
        )
    if payload.get("request") != expected_request:
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} does not match the configured location or PVGIS request"
        )
    dataset_payload = payload.get("dataset")
    if not isinstance(dataset_payload, Mapping):
        raise WeatherCacheUnavailableError(
            f"canonical TMY cache {path} is missing its dataset payload"
        )
    return (
        _canonical_dataset_from_dict(dataset_payload),
        hashlib.sha256(payload_bytes).hexdigest(),
    )


def _canonical_dataset_to_dict(dataset: CanonicalWeatherDataset) -> dict[str, object]:
    return {
        "dataset_id": dataset.dataset_id,
        "latitude": dataset.latitude,
        "longitude": dataset.longitude,
        "source_name": dataset.source_name,
        "source_metadata": dataset.source_metadata,
        "timezone_name": dataset.timezone_name,
        "time_basis": dataset.time_basis,
        "timestep_hours": dataset.timestep_hours,
        "timestamp_utc": list(dataset.timestamp_utc),
        "local_civil_step_labels": list(dataset.local_civil_step_labels),
        "canonical_field_order": list(dataset.canonical_field_order),
        "field_series": {
            name: list(values) for name, values in dataset.field_series.items()
        },
        "source_field_labels": dataset.source_field_labels,
    }


def _canonical_dataset_from_dict(payload: Mapping[str, object]) -> CanonicalWeatherDataset:
    field_series = payload.get("field_series")
    if not isinstance(field_series, Mapping):
        raise WeatherCacheUnavailableError("canonical TMY cache field_series must be a mapping")
    return CanonicalWeatherDataset(
        dataset_id=str(payload["dataset_id"]),
        latitude=float(payload["latitude"]),
        longitude=float(payload["longitude"]),
        source_name=str(payload["source_name"]),
        source_metadata=dict(payload["source_metadata"]),
        timezone_name=str(payload["timezone_name"]),
        time_basis=str(payload["time_basis"]),
        timestep_hours=float(payload["timestep_hours"]),
        timestamp_utc=tuple(str(value) for value in payload["timestamp_utc"]),
        local_civil_step_labels=tuple(
            str(value) for value in payload["local_civil_step_labels"]
        ),
        canonical_field_order=tuple(
            str(value) for value in payload["canonical_field_order"]
        ),
        field_series={
            str(name): tuple(values) for name, values in field_series.items()
        },
        source_field_labels={
            str(name): str(value)
            for name, value in dict(payload["source_field_labels"]).items()
        },
    )


def _with_cache_provenance(
    dataset: CanonicalWeatherDataset,
    *,
    path: Path,
    status: str,
    payload_sha256: str,
) -> CanonicalWeatherDataset:
    return replace(
        dataset,
        source_metadata=dict(dataset.source_metadata)
        | {
            "cache_provenance": {
                "status": status,
                "path": path.as_posix(),
                "payload_sha256": payload_sha256,
                "schema_version": CANONICAL_TMY_CACHE_SCHEMA_VERSION,
            }
        },
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        staging_path = Path(handle.name)
        handle.write(payload)
        handle.flush()
    staging_path.replace(path)


def _coerce_fetch_result(
    raw_result: object,
    *,
    latitude: float,
    longitude: float,
    timezone_name: str | None,
    source_name: str,
) -> Mapping[str, object]:
    if isinstance(raw_result, Mapping):
        return raw_result
    if isinstance(raw_result, Sequence) and not isinstance(raw_result, (str, bytes, bytearray)):
        if len(raw_result) < 2:
            raise TypeError("PVGIS fetch results must include data and metadata")
        data_frame = raw_result[0]
        metadata: dict[str, object] = {}
        for index, item in enumerate(raw_result[1:], start=1):
            if isinstance(item, Mapping):
                metadata.update({str(key): value for key, value in item.items()})
            elif index == 1 and isinstance(item, Sequence) and not isinstance(
                item, (str, bytes, bytearray)
            ):
                metadata["months_selected"] = list(item)
        if not metadata:
            raise TypeError("PVGIS fetch results must include mapping metadata")
        return _build_recorded_response_from_pvgis_result(
            data_frame,
            metadata,
            latitude=latitude,
            longitude=longitude,
            timezone_name=timezone_name,
            source_name=source_name,
        )
    raise TypeError("fetcher must return either a mapping response or a PVGIS-style result tuple")


def _build_recorded_response_from_pvgis_result(
    data_frame: object,
    metadata: Mapping[str, object],
    *,
    latitude: float,
    longitude: float,
    timezone_name: str | None,
    source_name: str,
) -> Mapping[str, object]:
    index = getattr(data_frame, "index", None)
    columns = getattr(data_frame, "columns", None)
    if index is None or columns is None:
        raise TypeError("PVGIS fetch data must expose dataframe-like index and columns")

    records: list[dict[str, object]] = []
    column_mapping = {
        SOURCE_FIELD_LABELS["dry_bulb_air_temperature_c"]: ("temp_air",),
        SOURCE_FIELD_LABELS["global_horizontal_irradiance_w_per_m2"]: ("ghi",),
        SOURCE_FIELD_LABELS["direct_beam_irradiance_w_per_m2"]: ("dni",),
        SOURCE_FIELD_LABELS["diffuse_horizontal_irradiance_w_per_m2"]: ("dhi",),
        SOURCE_FIELD_LABELS["relative_humidity_pct"]: ("relative_humidity",),
        SOURCE_FIELD_LABELS["infrared_radiation_downwards_w_per_m2"]: ("ghi_infrared", "IR(h)"),
        SOURCE_FIELD_LABELS["windspeed_10m_m_per_s"]: ("wind_speed",),
        SOURCE_FIELD_LABELS["wind_direction_10m_deg"]: ("wind_direction",),
        SOURCE_FIELD_LABELS["surface_air_pressure_pa"]: ("pressure",),
    }
    resolved_columns: dict[str, str] = {}
    for target_label, candidate_columns in column_mapping.items():
        for candidate_column in candidate_columns:
            if candidate_column in columns:
                resolved_columns[target_label] = candidate_column
                break
        else:
            formatted_candidates = ", ".join(repr(name) for name in candidate_columns)
            raise ValueError(
                "PVGIS dataframe is missing required mapped column for "
                f"{target_label!r}; expected one of {formatted_candidates}"
            )

    for row_index, timestamp in enumerate(index):
        record = {
            SOURCE_FIELD_LABELS["timestamp_utc"]: _format_utc_timestamp(timestamp),
        }
        for target_label, column_name in resolved_columns.items():
            record[target_label] = float(data_frame.iloc[row_index][column_name])
        records.append(record)

    resolved_timezone_name = (
        timezone_name
        or _string_value(metadata.get("timezone"))
        or _string_value(metadata.get("timezone_name"))
        or _infer_timezone_name(latitude, longitude)
    )
    if not resolved_timezone_name:
        raise ValueError("unable to determine timezone_name for PVGIS TMY response")

    return {
        "source_name": source_name,
        "timezone_name": resolved_timezone_name,
        "source_metadata": dict(metadata) | {"latitude": latitude, "longitude": longitude},
        "records": records,
    }


def _response_marks_location_unavailable(response: Mapping[str, object]) -> bool:
    status = _string_value(response.get("status"))
    available = response.get("available")
    return status in {"location-unavailable", "unavailable", "error"} or available is False


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _format_utc_timestamp(timestamp: object) -> str:
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)
        return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(timestamp)


def _infer_timezone_name(latitude: float, longitude: float) -> str | None:
    try:
        timezonefinder = _import_timezonefinder()
    except ImportError:
        return None
    return timezonefinder.TimezoneFinder().timezone_at(lat=latitude, lng=longitude)


def _import_pvlib() -> Any:
    try:
        import pvlib
    except ImportError as exc:  # pragma: no cover - exercised only when optional deps are absent
        raise ImportError(
            "pvlib must be installed to fetch live PVGIS TMY data; recorded_response remains fully supported."
        ) from exc
    return pvlib


def _import_timezonefinder() -> Any:
    try:
        import timezonefinder
    except ImportError as exc:  # pragma: no cover - exercised only when optional deps are absent
        raise ImportError(
            "timezonefinder must be installed to infer timezone_name for live PVGIS TMY fetches."
        ) from exc
    return timezonefinder


def _exception_marks_location_unavailable(error: Exception) -> bool:
    message = str(error).lower()
    return any(
        token in message
        for token in ("outside", "location", "coverage", "not available", "no data")
    )


__all__ = [
    "CANONICAL_TMY_CACHE_SCHEMA_VERSION",
    "DEFAULT_PVGIS_TMY_ENDPOINT",
    "PVGISTMYRequestConfig",
    "WeatherCacheUnavailableError",
    "WeatherLocationUnavailableError",
    "fetch_tmy_dataset",
    "load_or_fetch_tmy_dataset",
]
