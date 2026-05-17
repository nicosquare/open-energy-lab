# Contract: Minimal Weather-Driven PV Behavior

This contract defines the smallest weather and PV surface the simulator-core
may add in this feature.

## Purpose

The feature must migrate weather only to the extent needed to derive
deterministic PV output inside the new simulator scenario. It does not migrate
the broader weather subsystem. The model should use human-readable field names,
but each included field must retain an explicit mapping to its canonical TMY
source label.

## Required Weather Inputs

The MVP weather component must provide time-aligned inputs sufficient for the
chosen PV derivation. The minimal required set is:

- `timestamp_utc` mapped to `Date & time (UTC)`
- `dry_bulb_air_temperature_c` mapped to `T2m [°C]`
- at least one included irradiance field with a documented TMY mapping, such
  as `global_horizontal_irradiance_w_per_m2` -> `G(h) [W/m2]`,
  `direct_beam_irradiance_w_per_m2` -> `Gb(n) [W/m2]`, or
  `diffuse_horizontal_irradiance_w_per_m2` -> `Gd(h) [W/m2]`

Additional weather variables are out of scope unless a task shows they are
strictly required for the documented deterministic derivation. Standard TMY
fields that are not required now, such as relative humidity (`RH [%]`),
infrared radiation downwards (`IR(h) [W/m2]`), windspeed (`WS10m [m/s]`), wind
direction (`WD10m [°]`), or surface air pressure (`SP [Pa]`), should be
documented as deferred.

## Required PV Metadata

The MVP PV component must provide enough metadata to convert the weather inputs
into deterministic available generation. The minimal required set is:

- rated power in `kW`
- temperature coefficient in `%/C`
- reference irradiance in `W/m^2`
- reference temperature in `C`

Optional caps or derate factors are allowed only if they are documented and
covered by tests.

## Derivation Rules

The implementation must define a deterministic per-step PV derivation that:

1. scales PV output with one documented included TMY irradiance field or a
   documented combination of included TMY irradiance fields relative to a
   documented reference
2. adjusts output with the configured temperature coefficient relative to the
   documented reference temperature using `dry_bulb_air_temperature_c`
3. clamps the result to a non-negative value
4. keeps the output aligned to the time grid

The derivation should be described as an MVP approximation. It is not required
to be a full physical PV model.

## Preserved, Improved, and Rejected Semantics

**Preserved evidence direction**:

- `legacy/old_tpm/src_py/simulator/common/specs.py` provides real PV-oriented
  metadata such as rated power and temperature coefficient.
- `legacy/fed_trpo/src/custom/building.py` treats weather and solar generation
  as separate time-aligned concepts that participate in net electricity
  accounting.

**Improved semantics**:

- the new simulator defines an explicit small weather-to-PV derivation instead
  of hiding PV generation upstream in a broader environment
- the new simulator uses readable field names while preserving explicit TMY
  source-label mappings for the included subset
- the weather scope is documented and testable

**Rejected semantics**:

- migration of unrelated weather consumers
- stochastic weather generation
- real weather data ingestion
- broad CityLearn weather abstractions in simulator core

## Guarantees

The weather/PV contract must guarantee:

- deterministic repeated PV output from the same inputs
- non-negative PV generation
- no import of CityLearn, TorchRL, or other heavy stacks
- a clear path for future weather upgrades without requiring a redesign of the
  battery + load + PV scenario
