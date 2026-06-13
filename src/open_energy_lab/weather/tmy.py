"""TMY fetch helpers for the stochastic-weather feature."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ._canonical import CanonicalWeatherDataset, normalize_recorded_tmy_response


class WeatherLocationUnavailableError(ValueError):
    """Raised when the upstream weather source cannot serve a location."""


def fetch_tmy_dataset(
    latitude: float,
    longitude: float,
    *,
    recorded_response: Mapping[str, object] | None = None,
    fetcher: Callable[[float, float], Mapping[str, object]] | None = None,
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
    fetcher: Callable[[float, float], Mapping[str, object]] | None,
) -> Mapping[str, object]:
    if recorded_response is not None:
        return recorded_response
    if fetcher is None:
        raise NotImplementedError(
            "Live PVGIS-backed fetch is planned for a later task; supply recorded_response or fetcher for now."
        )
    response = fetcher(latitude, longitude)
    if not isinstance(response, Mapping):
        raise TypeError("fetcher must return a mapping response")
    return response


def _response_marks_location_unavailable(response: Mapping[str, object]) -> bool:
    status = _string_value(response.get("status"))
    available = response.get("available")
    return status in {"location-unavailable", "unavailable", "error"} or available is False


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


__all__ = ["WeatherLocationUnavailableError", "fetch_tmy_dataset"]
