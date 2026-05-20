# Research: Deterministic Battery Load PV Scenario MVP

## Decision: Extend the Existing Pure-Python Simulator Core Instead of Reframing It

**Decision**: Build the feature as a small extension of the existing
`open_energy_lab.simulator` modules and keep simulator-core runtime dependencies
limited to the Python standard library plus the already migrated simulator
code.

**Rationale**: The completed battery-arbitrage MVP already established the
package boundary, tolerance rules, dispatch conventions, and import-light
guarantees. This feature should exercise richer energy balance, not reopen the
dependency policy. Focused Python dataclasses and helper functions are enough
for deterministic load, weather, PV, and net-grid accounting.

**Alternatives considered**: Introducing `numpy` as a core requirement would
be convenient for vectorized traces but is not necessary for short deterministic
fixtures. Pulling in CityLearn or broader research stacks would widen the core
boundary before the simulator semantics are proven.

## Decision: Preserve the Existing Battery, Time-Step, and Export-Discount Semantics

**Decision**: Keep the battery transition rules, sign conventions, step-hours
semantics, default numeric tolerance, and discounted export settlement from the
completed battery-arbitrage MVP unchanged. Continue to ground them in
`legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/scripts/test_battery_consistency.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`,
`legacy/old_tpm/src_py/simulator/common/pricing.py`, and
`legacy/old_tpm/src_py/simulator/common/time.py`.

**Rationale**: The new feature should isolate the new semantics to load, PV,
weather, and net-grid balance. Re-opening the battery or tariff interpretation
at the same time would make failures harder to attribute and weaken the value
of the prior validation work.

**Alternatives considered**: Replacing the battery contract with a different
multi-component storage model would couple two migrations together. Loosening
the `1e-6` tolerance would make the new tests harder to compare with the
existing battery evidence.

## Decision: Represent Load as a Deterministic Exogenous Profile

**Decision**: Model load as an explicit time-aligned deterministic component
that contributes directly to per-step net-grid balance.

**Rationale**: The spec requires battery + load + PV behavior without migrating
the broader building or demand-control abstractions. A small exogenous load
profile matches the fixture-first validation strategy and aligns with how the
legacy battery helpers reason over `load_profile` inputs in
`legacy/old_tpm/src_py/simulator/common/battery.py`.

**Alternatives considered**: Reusing the `Building` abstraction from
`legacy/fed_trpo/src/custom/building.py` would import CityLearn-facing
concepts, many unrelated loads, and heavy dependencies. Folding load into an
undifferentiated scenario fixture would hide an important component the spec
explicitly asks to surface.

## Decision: Migrate Only Minimal Weather Inputs Needed to Derive Deterministic PV Output

**Decision**: Introduce a minimal weather component with explicit time-aligned
inputs needed for PV derivation, and keep the broader weather subsystem out of
scope for this feature, while preserving the exact TMY-style names of the
weather fields that are included.

**Rationale**: The spec explicitly brought weather into scope, but only for the
PV path. `legacy/old_tpm/src_py/simulator/common/specs.py` provides solar-panel
properties such as rated power and temperature coefficient, while
`legacy/fed_trpo/src/custom/building.py` shows the broader architecture pattern
of weather and solar generation as separate inputs to net electricity
consumption. Together they justify a small explicit weather-to-PV bridge
without migrating the full building or forecasting stack.

**Alternatives considered**: Treating PV as a fixed exogenous series would
conflict with the clarification that this feature should migrate weather.
Renaming the weather fields into a new internal vocabulary would add needless
schema churn versus the reference TMY source. Migrating the broader weather
subsystem would expand scope well beyond the MVP.

## Decision: Preserve Exact TMY Field Names for the Included Weather Subset

**Decision**: The MVP weather component should preserve exact TMY-style field
names for whichever weather variables it includes, and it should document the
remaining standard TMY fields as deferred rather than aliasing them into a new
core schema.

**Rationale**: The user wants continuity with the reference TMY-backed weather
source. Preserving names such as `Date & time (UTC)`, `T2m [°C]`, and the
chosen irradiance field names reduces adapter ambiguity and lets later weather
expansions stay additive instead of requiring a rename migration.

**Alternatives considered**: A descriptive internal schema with a mapping layer
would be easier to type but would break direct continuity with the reference
weather source. Requiring the entire TMY field set immediately would add fields
the MVP does not use.

## Decision: Define an Explicit MVP Weather-to-PV Derivation

**Decision**: Use a simple deterministic PV derivation driven by weather inputs
and PV component metadata, documented as an MVP approximation rather than a
full physical PV model.

**Rationale**: The legacy references do not provide one small standalone PV
derivation suitable for this new core. `legacy/old_tpm/src_py/simulator/common/specs.py`
provides enough PV metadata to justify a deterministic conversion rule, and the
spec allows improved semantics where behavior is made more explicit. A small
formula tied to irradiance and temperature gives the feature a reproducible,
reviewable path from weather to PV output.

**Alternatives considered**: Copying a broader PV or weather implementation
from CityLearn-facing code would bring in unrelated concerns. Leaving the
weather-to-PV mapping undocumented would make fixtures impossible to trust.

## Decision: Settle the Grid on One Signed Net-Grid Value Per Step

**Decision**: Compute one signed net-grid power value per step and settle it
directly: positive values mean import, negative values mean export, and both
cannot occur simultaneously within a timestep.

**Rationale**: This was clarified explicitly in the spec and is the cleanest
extension of the prior settlement model. The broader building reference in
`legacy/fed_trpo/src/custom/building.py` also computes a single net electricity
consumption value and applies import versus selling prices according to the
sign, which supports the same accounting direction at a simpler scale.

**Alternatives considered**: Separate import and export channels would widen
the fixture and invariant surface without adding value for this MVP. Allowing
simultaneous import and export would complicate reasoning before there is a need
for it.

## Decision: Keep the Built-In Deterministic Battery Rule Price-Only

**Decision**: Continue to support both explicit dispatch requests and the
existing built-in `price_threshold` rule, and keep that built-in rule driven by
price only even though load and PV are now present.

**Rationale**: This preserves continuity with the completed battery-arbitrage
MVP and keeps future controller integration clean. External controllers such as
MPC or RL can later target the explicit-dispatch boundary without changing the
simulator semantics, while the built-in rule remains a self-contained
deterministic regression path.

**Alternatives considered**: Load-aware or forecast-aware built-in policies
would turn this feature into a control-policy redesign. Supporting only one of
dispatch or rule-policy modes would make the migration less useful than the
already completed MVP.

## Decision: Validate With Small Deterministic Multi-Component Fixtures and Invariants

**Decision**: Use one or two small synthetic fixtures that document weather,
derived PV, load, battery, net-grid, and settlement expectations with absolute
tolerance `1e-6`.

**Rationale**: The feature needs evidence that the component traces agree with
the energy-balance equation, not a broad replay of the legacy simulator. Small
fixtures keep review manageable and fit the existing committed-fixture policy.
They also let tests verify both execution modes: explicit dispatch and the
price-threshold baseline.

**Alternatives considered**: Real weather or tariff datasets would reduce
determinism and add provenance burden. Broad legacy parity would drag in code
that includes many unrelated building and research concerns.
