# Contract: Aligned Historical Inputs To Fitted Demand Artifact Workflow

This contract defines the stable first-release workflow from aligned demand and
weather history to one persisted fitted demand artifact.

## Purpose

The workflow gives library users one owned path from explicit historical
non-thermal electric demand, explicit historical cooling demand in `RT`, and
canonical weather history to a reusable demand artifact. It is the stable
front door for producer-side demand fitting inside the unified library.

## Stable Inputs

The stable first-release workflow accepts:

- canonical weather history produced by the weather feature
- explicit historical non-thermal electric demand aligned to that weather
- explicit historical cooling demand in `RT` aligned to that weather
- one artifact timestep resolution
- optional fit configuration that does not widen the stable artifact schema

The workflow does not accept:

- total electric load as the only stable training input
- inferred or decomposed cooling demand in place of explicit cooling history
- direct CityLearn runtime coupling
- direct legacy runtime imports

## Alignment And Conditioning Rules

The workflow must:

1. validate that weather and both demand outputs align on one timestep and one
   time grid
2. preserve the canonical weather field references required by the demand
   model
3. fit separate non-thermal electric and cooling outputs while allowing
   shared residual variation
4. preserve local-civil-time semantics for feature extraction and sampling
5. record provenance for the aligned training dataset and the demand artifact

## Double-Counting Prevention

The first-release workflow must prevent electric and thermal double counting:

- sampled non-thermal electric demand must not hide the same cooling service
  represented by explicit cooling demand
- the artifact must record this policy explicitly
- the workflow must reject ambiguous training inputs that do not preserve the
  separation between non-thermal electric demand and cooling demand

## Fail-Fast Conditions

The workflow must fail fast when:

- aligned historical cooling demand in `RT` is missing
- aligned historical non-thermal electric demand is missing
- the weather inputs do not satisfy the documented canonical contract
- the three input histories do not share one common timestep and horizon
- the requested timestep cannot be supported by the aligned historical record
- the fit workflow cannot produce a supported artifact schema version

The workflow must not create a partial artifact in any of these cases.

## Dependency Boundary

The workflow may use lightweight data-processing helpers during fit, but those
dependencies must remain outside ordinary package imports and outside offline
artifact loading and sampling. Heavy building, RL, solver, notebook, or live
service stacks remain out of scope for the stable path.

## Guarantees

The stable workflow guarantees:

- explicit producer-side ownership of demand fitting
- required separation between non-thermal electric and cooling demand
- canonical weather-conditioned fitting semantics
- deterministic artifact creation from the same aligned record and fit
  configuration
- failures that are explicit rather than silently degraded
