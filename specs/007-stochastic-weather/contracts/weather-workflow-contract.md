# Contract: Geolocation To Fitted Weather Artifact Workflow

This contract defines the stable first-release workflow from geolocation input
to one persisted fitted weather artifact.

## Purpose

The workflow must give library users one owned path from geolocation to
fetching TMY data, canonical normalization, local-civil-time alignment, and
artifact creation. It is the stable front door for fitting stochastic weather
models inside the unified library.

## Stable Inputs

The stable first-release workflow accepts:

- latitude
- longitude
- artifact timestep resolution
- optional fit configuration that does not widen the stable artifact schema

The workflow does not accept:

- city-code-only shortcuts as the only stable location surface
- partial canonical weather field requests
- direct legacy runtime imports

## Fetch And Normalization Rules

The workflow must:

1. fetch TMY weather data for the provided geolocation through a library-owned
   workflow
2. map the fetched data into the canonical ten-field weather schema
3. normalize the annual weather record into location-local civil time for model
   fitting and sampling semantics
4. preserve canonical `timestamp_utc` values in the public normalized output
5. record source and normalization provenance in the artifact

## Fail-Fast Conditions

The workflow must fail fast when:

- the TMY source cannot serve the requested location
- any required canonical weather field is missing or unmappable
- the requested timestep cannot be produced from the fetched record using the
  documented workflow
- the fit workflow cannot produce a supported artifact schema version

The workflow must not create a partial artifact in any of these cases.

## Canonical Weather Fields

The first-release canonical workflow must fit all of these fields:

- `timestamp_utc`
- `dry_bulb_air_temperature_c`
- `global_horizontal_irradiance_w_per_m2`
- `direct_beam_irradiance_w_per_m2`
- `diffuse_horizontal_irradiance_w_per_m2`
- `relative_humidity_pct`
- `infrared_radiation_downwards_w_per_m2`
- `windspeed_10m_m_per_s`
- `wind_direction_10m_deg`
- `surface_air_pressure_pa`

Every field must retain explicit source-label provenance.

## Dependency Boundary

The workflow may use network-backed and heavier normalization dependencies
during fetch and fit, but those dependencies must remain outside ordinary base
library imports and outside offline artifact sampling.

## Guarantees

The stable workflow guarantees:

- geolocation is the primary stable user input
- the canonical variable set is uniform across fitted artifacts
- fitting semantics are based on local civil time
- artifact creation is deterministic from the same normalized record and fit
  configuration
- failures are explicit and do not silently degrade into partial artifacts
