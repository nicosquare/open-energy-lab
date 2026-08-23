# Restoration-Service Fixtures

This directory is the offline evidence boundary for Feature 011, French BESS
aFRR and mFRR services. Reusable acquisition, validation, mapping, replay, and
settlement behavior belongs under `src/open_energy_lab`; tests and examples
consume only explicit, versioned artifacts from this directory.

## Layout

```text
restoration/
├── README.md
├── RESTRICTED_DATA.md
├── synthetic_rte/                         # authored RTE JSON parser inputs
├── manual_afrr_v1.json                    # authored arithmetic oracle
├── manual_mfrr_v1.json                    # authored arithmetic oracle
├── france_2026-08-20_afrr_market_v1.json  # restricted normalized source data
├── france_2026-08-20_afrr_scenario_v1.json
├── france_2026-08-15_mfrr_market_v1.json  # restricted normalized source data
├── france_2026-08-15_mfrr_scenario_v1.json
└── france_restoration_expected_results_v1.json
```

Files are added by their owning implementation tasks. A missing restricted
artifact is never downloaded or synthesized on cache miss.

## Authored Fixtures

`synthetic_rte/` and the two `manual_*` files are project-authored test inputs.
They contain no production response body or caller data and may be distributed
with the repository under its normal license. Each authored fixture must state:

- the parser, equation, or failure path it validates;
- its generation method or that it was written by hand;
- exact input periods, units, directions, and expected invariants;
- the default absolute tolerance when numeric results are involved; and
- that it is synthetic and is not evidence of an operational BESS command.

Synthetic cases preserve source-null, field-absent, and numeric-zero states as
different values. They may imitate the documented RTE JSON shape but must never
be described as a captured production response.

The authored `synthetic_rte/` matrix contains successful aFRR and mFRR shapes
plus malformed-root, empty, null/missing/zero, gap, overlap, conflicting
duplicate, wrong-resolution, wrong-direction, wrong-unit, oversized,
authentication, rate-limit, transient, and permanent response cases. The four
aFRR requested-need values and one mFRR SA requested-volume value reproduce the
documented hand-checkable scenario inputs; all response bytes remain authored
and are not production captures.

`manual_afrr_v1.json` is a project-authored arithmetic oracle for Feature 011
User Story 2. Its six deterministic cases separately publish nominal upward,
downward, and zero tracking; ramp saturation; charge-power saturation;
maximum-SOC/energy saturation; reserved downward-headroom saturation; and
zero-activation baseline preservation. Every input is synthetic, every power
value is an interval average under the charge-positive convention, and every
expected terminal or activation energy is direct `kW * interval-hours`
integration with absolute tolerance `1e-6`. The fixture is maintained by hand
and changes only with a versioned activation, battery, or replay equation.

`manual_mfrr_v1.json` is the corresponding project-authored event oracle for
User Story 3. It publishes a rectangular upward scheduled activation, a
downward direct activation with explicit delay and linear ramps, an empty
zero-activation horizon, and one invalid scheduled/direct overlap. Requested
event energy follows `power * (hold + 0.5*ramp_up + 0.5*ramp_down) / 3600`;
native-grid interval averages conserve that analytic result within `1e-6`.
The values are synthetic and are not evidence of an RTE-to-asset activation
order. The fixture changes only with a versioned event-shape, overlap, battery,
or replay equation.

## Restricted Fixtures

Every `france_*` file listed in `RESTRICTED_DATA.md` is derived from real market
observations and is restricted to authorized collaborators in the confirmed
private repository. That policy covers normalized source artifacts, derived
scenarios, and expected results because downstream values can reproduce the
restricted observations.

Restricted fixtures must be excluded from wheels, source distributions,
releases, public CI artifacts, public forks or mirrors, and external artifact
stores. They must be removed or reassessed before any repository visibility
change. Private repository access is not permission to redistribute them.

## Credentials and Raw Responses

No client ID, client secret, access token, Basic/Bearer header, credential-
bearing URL, OAuth response, or local `.env` value may appear in a fixture,
filename, digest input, log, exception, notebook output, or documentation
example. Routine tests use conspicuous sentinels and require zero occurrences.

Production market-response bodies are digest-only by default. A raw response
may be retained only as a separately verified restricted sidecar when source
terms and project policy explicitly allow it. OAuth responses are never raw
market evidence and are never retained or fingerprinted.

## Provenance Template

Each fixture record must provide:

```text
Fixture path:
Purpose:
Origin and owner:
Source API/profile/version or authored contract:
Requested and covered UTC period:
Resolution, units, and directions:
Generation command:
Input artifacts and fingerprints:
Expected invariant and tolerance:
Transformation history:
Raw-response digest/retention status:
License, access, and redistribution policy:
Refresh policy:
```

Real artifacts are refreshed only through an explicit credentialed acquisition
followed by the fixed private-staging workflow. An upstream response-digest
change is reported for semantic review and is not, by itself, permission to
overwrite an existing immutable fixture.
