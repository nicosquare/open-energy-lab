# Parity Tests

Parity tests compare migrated library behavior with legacy references,
documented equations, fixtures, snapshots, or deterministic smoke checks.

## Future Parity Strategy

Future migration specs should add parity cases here only after naming the
target module path, validation path, legacy reference paths, fixtures, and the
relevant parity evidence for the migrated behavior.

Acceptable parity evidence includes fixture-based checks, deterministic seeds
or configs, documented equations or invariants, legacy command output,
snapshots, focused smoke runs, or an explicit note explaining why full parity
cannot run locally.

## Legacy Reference Policy

Parity cases must cite exact files, directories, configs, notebooks, or scripts
under `legacy/*`. Legacy code remains reference material and must not become
the target architecture for new reusable library code.

When a migration spec uses legacy behavior as evidence, it should record what
is being preserved, improved, or rejected and keep any environment assumptions,
tolerances, and provenance visible to reviewers.

## Current State

No migrated parity cases exist in this foundation feature. This directory is a
placeholder for future migration specs rather than a home for algorithm
migration in the current scope.

## Battery Arbitrage MVP Stance

For `specs/002-battery-arbitrage-mvp`, parity is intentionally narrow rather
than broad end-to-end replay against the legacy simulator.

The exact legacy evidence used for this MVP is:

- `legacy/old_tpm/scripts/test_battery_consistency.py`
- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`

This feature relies on targeted deterministic invariants instead of a full
legacy parity suite because:

- the migrated scope is one synthetic battery-arbitrage case, not the broader
  simulator stack
- the validated behavior is battery physics, timestep alignment, discounted
  export settlement, and deterministic policy execution
- the legacy script environment is not self-contained from the repository root
  and currently fails with `ModuleNotFoundError: storage`

The current battery-arbitrage parity evidence is therefore:

- unit tests for battery transition, pricing, scenario assembly, and
  settlement contracts
- one deterministic integration fixture covering explicit dispatch and
  `price_threshold` execution
- documented `1e-6` tolerance-backed invariants rather than a broad snapshot or
  whole-simulator replay

## Battery Load PV MVP Stance

For `specs/003-battery-load-pv`, parity is also intentionally narrow rather
than broad end-to-end replay against the legacy simulator.

The exact legacy weather/PV/grid evidence used for this MVP is:

- `legacy/old_tpm/src_py/legacy/storage.py`
- `legacy/old_tpm/scripts/test_battery_consistency.py`
- `legacy/old_tpm/src_py/simulator/common/battery.py`
- `legacy/old_tpm/src_py/simulator/common/pricing.py`
- `legacy/old_tpm/src_py/simulator/common/time.py`
- `legacy/old_tpm/src_py/simulator/common/specs.py`
- `legacy/fed_trpo/src/custom/building.py`

This feature relies on targeted deterministic invariants instead of a broad
legacy parity suite because:

- the migrated scope is one synthetic battery + load + weather + PV case, not
  the broader legacy simulator or building stack
- the validated behavior is battery physics, weather-driven PV derivation,
  one-net grid accounting, discounted export settlement, and deterministic
  policy execution
- the cited legacy battery script is reference-only evidence here and does not
  provide additional value for the new library validation in the current
  repository environment

The current battery-load-PV parity evidence is therefore:

- unit tests for load, weather, PV, multi-component scenario assembly,
  settlement, and import-boundary contracts
- one deterministic integration fixture covering explicit dispatch and
  `price_threshold` execution against the same energy-balance rules
- documented `1e-6` tolerance-backed invariants rather than a broad snapshot or
  whole-simulator replay
