# Contract: Validation And Review Boundary

## Default Review Path

- review remains offline and fixture-backed
- simulator export, dataset reload, TPM metadata validation, query fixtures,
  planning model assembly, real current-SPFlow fit/query, and real Pyomo/HiGHS
  solve checks run without notebooks, live services, GPUs, or commercial
  solver licenses
- one routine single-version job covers control, simulator, weather, demand,
  and repository import-boundary regressions; the required backend matrix
  separately covers Python 3.11 through 3.14
- package-root import checks verify required backend modules are not imported
  until their workflow boundaries are invoked

## Required Fixture Coverage

- committed planning-dataset export fixture
- committed TPM artifact or metadata fixture
- committed conditional-query fixture
- committed planning-problem assembly fixture
- real current-SPFlow fit, reload, marginalization/query, and payload evidence
- current-SPFlow-to-piecewise-MIO compilation parity against native likelihood
  results using the canonical five-breakpoint configuration
- exact categorical compiled-SPN risk parity and solver-strategy metadata for
  finite categorical battery/solar decisions
- real Pyomo/HiGHS optimal and infeasible solve cases
- non-optimal/time-limit handling that does not load an unproved solution
- cleared notebook execution counts and outputs in the committed walkthrough
- import-boundary and no-legacy-import checks
- canonical seed `13` across Python, NumPy, Torch, SPFlow, and solver settings,
  with robustness seeds `37` and `101`
- `1e-9` repeatability and `1e-6` native-versus-compiled maximum absolute
  probability error
- required Python 3.11, 3.12, 3.13, and 3.14 backend jobs; an unsupported
  interpreter must narrow project metadata with recorded evidence, not skip

## Optional Follow-Up Checks

- Gurobi-backed planning checks when its binary and license are available
- legacy tangent test comparisons when Pyomo and a supported solver are
  available

## Documentation Requirements

- skipped Gurobi or legacy-runtime checks must be documented in quickstart
  notes or final implementation review output; required SPFlow/HiGHS checks
  cannot be reported as successful skips
- validation commands must list only checks relevant to changed files
