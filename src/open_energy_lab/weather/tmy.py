"""TMY fetch helpers for the stochastic-weather feature."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ._canonical import (
    CanonicalWeatherDataset,
    SOURCE_FIELD_LABELS,
    normalize_recorded_tmy_response,
)


class WeatherLocationUnavailableError(ValueError):
    """Raised when the upstream weather source cannot serve a location."""


def fetch_tmy_dataset(
    latitude: float,
    longitude: float,
    *,
    recorded_response: Mapping[str, object] | None = None,
    fetcher: Callable[[float, float], object] | None = None,
    timezone_name: str | None = None,
    source_name: str = "PVGIS TMY",
    timestep_hours: float | None = None,
) -> CanonicalWeatherDataset:
    """Fetch or accept a recorded TMY response and normalize it."""

    response = _resolve_tmy_response(
        latitude,
        longitude,
        recorded_response=recorded_response,
        fetcher=fetcher,
        timezone_name=timezone_name,
        source_name=source_name,
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
) -> Mapping[str, object]:
    if recorded_response is not None:
        return recorded_response
    response = _fetch_with_default_or_override(
        latitude,
        longitude,
        fetcher=fetcher,
        timezone_name=timezone_name,
        source_name=source_name,
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
) -> Mapping[str, object]:
    if fetcher is not None:
        raw_result = fetcher(latitude, longitude)
    else:
        raw_result = _fetch_live_pvgis_result(latitude, longitude)
    return _coerce_fetch_result(
        raw_result,
        latitude=latitude,
        longitude=longitude,
        timezone_name=timezone_name,
        source_name=source_name,
    )


def _fetch_live_pvgis_result(latitude: float, longitude: float) -> object:
    try:
        pvlib = _import_pvlib()
        return pvlib.iotools.get_pvgis_tmy(
            latitude,
            longitude,
            outputformat="json",
            usehorizon=True,
            map_variables=True,
            timeout=30,
        )
    except Exception as exc:
        if _exception_marks_location_unavailable(exc):
            raise WeatherLocationUnavailableError(
                f"weather source is unable to serve location ({latitude}, {longitude}): {exc}"
            ) from exc
        raise


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
        metadata = raw_result[1]
        if not isinstance(metadata, Mapping):
            raise TypeError("PVGIS fetch metadata must be a mapping")
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


__all__ = ["WeatherLocationUnavailableError", "fetch_tmy_dataset"]
