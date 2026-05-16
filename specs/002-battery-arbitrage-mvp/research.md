# Research: Battery Arbitrage Simulator MVP

## Decision: Keep the MVP as a Pure-Python Simulator Core

**Decision**: The first simulator migration should use a small typed Python
core in `src/open_energy_lab/simulator` and avoid new runtime dependencies
beyond the existing package scaffold.

**Rationale**: The feature needs reviewable simulator behavior, not numerical
throughput or training integration. A standard-library-first implementation is
enough for time steps, battery state transitions, price signals, and objective
settlement, and it keeps `import open_energy_lab.simulator` aligned with the
foundation dependency policy.

**Alternatives considered**: Pulling in `numpy` immediately would simplify some
array operations but is unnecessary for the first deterministic horizon.
Pulling in TorchRL, CityLearn, or solver libraries would violate the core
boundary without improving the MVP validation story.

## Decision: Preserve Battery Physics and Tolerance Semantics From the Legacy Battery Models

**Decision**: Preserve the battery invariants demonstrated in
`legacy/old_tpm/src_py/legacy/storage.py`,
`legacy/old_tpm/src_py/simulator/common/battery.py`, and
`legacy/old_tpm/scripts/test_battery_consistency.py`: bounded state of charge,
capacity limits, charge/discharge power limits, explicit efficiency losses, and
small floating-point tolerance near full and empty states.

**Rationale**: These are the strongest legacy behaviors with direct validation
evidence already present. They are also the minimum physics needed to trust a
battery arbitrage trace. The legacy consistency script already checks charging
efficiency, discharging efficiency, capacity bounds, power limits, and
full/empty behavior.

**Alternatives considered**: Copying the entire legacy `BatterySystem` surface
would drag in grid-import/export, PV, load, and policy methods that are broader
than the MVP. Using a simplified ideal battery with no efficiency or power
limits would be easier but would drop behavior the legacy references clearly
protect.

## Decision: Preserve Step-Start Tariff Semantics and Explicit Time-Step Hours

**Decision**: Preserve time-step semantics from
`legacy/old_tpm/src_py/simulator/common/time.py` and the default `"hold"`
pricing behavior from `legacy/old_tpm/src_py/simulator/common/pricing.py`:
time steps are expressed in hours, and a step-wise tariff uses the price of the
hour in which the step starts unless the scenario states otherwise.

**Rationale**: The legacy pricing helpers and time constants make timestep
handling explicit. Using step-start tariff semantics keeps the first MVP
deterministic and easy to audit, which matters more than offering multiple
interpolation modes at this stage.

**Alternatives considered**: Supporting nearest-hour and duration-weighted mean
pricing from day one would widen the API and test surface before the core case
is proven. Using implicit timestep assumptions would make energy accounting and
tolerances harder to review.

## Decision: Model Arbitrage as Feasible Dispatch Plus Settlement, Not Optimization

**Decision**: The MVP should evaluate a scenario from either explicit
dispatch requests or one built-in deterministic price-threshold policy and
compute arbitrage value as discounted-export settlement over the physically
feasible trace. It should not include a solver, planner, or learned
controller.

**Rationale**: The spec requires market-facing objective representation but
explicitly excludes planning/control implementations and solver-backed
optimization. A settlement model is enough to validate whether the simulator
correctly translates requested or rule-generated battery power into feasible
state transitions and price-linked economic outcomes, while a single
price-threshold rule gives the MVP one built-in behavior path without turning
the simulator into a control framework.

**Alternatives considered**: Only explicit dispatch requests would keep the
boundary even narrower but would leave the MVP without any self-contained
behavior path. Richer control heuristics or optimizers would violate the
dependency and scope rules.

## Decision: Use a Deterministic Synthetic Fixture as the Primary Validation Evidence

**Decision**: Define one small synthetic arbitrage case with fixed initial SOC,
fixed timestep hours, fixed price series, either fixed dispatch requests or the
built-in price-threshold policy, and explicit expected trajectory checks for
state of charge, stored energy, discounted export settlement terms, and total
objective value under absolute tolerance `1e-6`.

**Rationale**: The first simulator migration needs evidence that can run
locally and fail loudly when units, signs, or efficiency handling drift. A
small synthetic case is more reviewable than a large historical trace and does
not require external data ingestion.

**Alternatives considered**: Real tariff or demand data would complicate
provenance and reduce determinism. A parity-only strategy against broad legacy
simulation code would make the MVP dependent on code that includes unrelated
features.

## Decision: Treat `fed_trpo` Building and CityLearn References as Deferred Adapter Context

**Decision**: Use `legacy/fed_trpo/src/custom/building.py` only as evidence
that future adapters will need richer concepts such as buildings, observations,
and CityLearn-compatible storage interfaces. Do not migrate any of that surface
into this MVP.

**Rationale**: `building.py` imports `gymnasium`, `torch`, `citylearn`, and
other heavy dependencies, and its abstraction level is much broader than a
single battery arbitrage simulator case. It is useful as a boundary marker, not
as a source for the first core implementation.

**Alternatives considered**: Starting from the CityLearn-facing building layer
would force optional research dependencies into the first simulator migration.
Ignoring `fed_trpo` entirely would miss useful evidence about future adapter
needs.

## Decision: Keep the Initial Simulator Surface Narrow and Only Partly Public

**Decision**: The `open_energy_lab.simulator` package path is the stable module
location, but the first concrete arbitrage-specific types should be treated as
an experimental MVP until a later migration promotes them with broader
validation and additional use cases.

**Rationale**: The location of simulator code should stabilize early so later
migrations do not relocate the entire subsystem. The exact class and function
surface is still likely to evolve while more scenario types are migrated.

**Alternatives considered**: Promoting every first-pass class to stable public
API would make later simulator cleanup harder. Hiding everything as private
would make the MVP difficult to use and review.
