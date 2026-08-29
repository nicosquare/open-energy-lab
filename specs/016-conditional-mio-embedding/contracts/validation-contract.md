# Contract: Validation, Fixtures, Notebook, and CI

## Acceptance layers

Validation is intentionally layered:

1. import-light record, identity, persistence, circuit, mapping, and numerical unit tests;
2. one deterministic real current-SPFlow fit/persist/reload/native/compile path;
3. direct-versus-Pyomo/HiGHS fixed-assignment parity for max and PWL;
4. separate native-versus-compiled fidelity evidence;
5. current TPM/planning compatibility and lazy-import regressions; and
6. one output-free public-API notebook executed headlessly and offline.

Fake graphs may isolate failure paths in unit tests but cannot replace the real production path.
Production evidence shall not fall back to empirical replay or metadata-only behavior.

## Reviewed mixed source case

The feature adds one small, human-reviewable JSON input table and one versioned fit configuration.
The table contains:

- a continuous decision with finite declared domain $[40,160]$;
- deliberately nonuniform observed values over that domain, so a constant learned denominator is
  not a valid assumption;
- one exact declared binary decision with both states observed;
- one declared ordered categorical decision with every category observed;
- at least one marginalized continuous uncertainty with explicit support semantics; and
- one exact declared binary event with both values observed.

The row table itself is committed and authoritative; it is not regenerated randomly during tests.
Its exact row count is not elevated into a public capability contract. The versioned fit uses one
fixed seed and one bounded configuration chosen to produce genuine current-SPFlow structure on this
small fixture. Fixture generation fails rather than retrying or adapting if the resulting retained
base graph and conditioned circuits do not contain real Sum structure.

The source artifact is persisted as schema v3 with a verified current-SPFlow sidecar. The validation
script records source-row digest, declarations, fit seed/options, artifact/model digests, SPFlow
version, and all compiler inputs. It proves that loading uses the current backend payload.

Existing fixtures are not repurposed because they do not jointly establish nonuniform evidence and
genuine learned Sum nodes.

## Published pair cases

The same source artifact produces two separate immutable pairs:

- one with explicit max Sum encoding;
- one with explicit configured PWL Sum encoding.

Both use identical source model, event/value, retained decision ordering, marginalization,
continuous approximation interval, leaf policy, and numerical tolerances. Only the declared Sum
policy and its required resolved inputs differ. The pair fixtures must reload with matching IDs and
must retain their complete semantics through a canonical JSON round trip.

The feature does not tune or select between these encodings. It only proves that each chosen pair is
reused consistently by its direct and Pyomo paths.

## Representative fixed assignments

Each pair is evaluated at three declared-domain assignments selected before inspecting parity or
fidelity results:

1. continuous lower approximation boundary, binary state zero, first declared category;
2. continuous interior point, binary state one, a different declared category; and
3. continuous upper approximation boundary, a representative remaining category.

Together these cases cover both binary states, all categories in the reviewed fixture, and
continuous lower/interior/upper behavior without a Cartesian grid. The exact values and declared
category labels live in the versioned validation fixture.

For every assignment and encoding, validation retains:

- direct selected-semantics roots, risk, probability, and classification;
- objective-free caller-owned Pyomo/HiGHS roots, risk, probability, solver status, and residuals;
- parity deltas and the absolute $10^{-6}$ verdict;
- native current-SPFlow roots and risk; and
- separate compiler-fidelity differences without an adequacy verdict.

The same published pair object/file is used in direct evaluation, attachment, and evidence. Tests
verify its bytes and ID remain unchanged.

## Caller composition case

One small consumer-owned Pyomo model demonstrates, without solving a benchmark optimization, that a
caller can:

- define and retain its own continuous, binary, and categorical primary decisions;
- attach a pair through public OEL behavior;
- add one unrelated deterministic constraint;
- add its own objective;
- choose an $\alpha$ and add
  `attachment.conditional_log_risk <= log(alpha)`; and
- attach another pair under a different namespace.

Tests assert that OEL did not add these policy components itself. Separate negative cases prove
duplicate namespaces and invalid mappings leave the caller model structurally unchanged.

## Focused automated coverage

### Import-light and record tests

- request/pair/evidence construction, recursive immutability, finite JSON, canonical identity;
- create-only publication, verified reuse, conflict, corruption, incomplete content, and changed
  input identity;
- loading records without importing SPFlow, Torch, Pyomo, or HiGHS;
- source eligibility and explicit rejection of schema-v2/legacy-inferred artifacts.

### Circuit and direct-evaluation tests

- declared event direction for both binary values;
- numerator event fixing and denominator event marginalization;
- common marginalization of every other nondecision feature;
- exact log-one simplification of fully marginalized normalized Product/Sum subtrees;
- max and PWL node evaluation using selected, persisted semantics;
- strict interval/category validation and inclusive boundaries without clipping;
- complete declared-domain versus model-coordinate assignment modes;
- nonfinite failure, positive numerical-noise classification, and materially positive risk failure.

### Mapping and attachment tests

- continuous variable and affine-expression normalization/linking;
- structural rejection of nonlinear expressions even when variables are fixed;
- rejection of constant-only, binary-containing, integer-containing, and foreign-model continuous
  expressions;
- binary ordering and ordered categorical one-hot coverage/exactly-one behavior;
- missing, duplicate, extra, mis-typed, and foreign-model mappings;
- detached construction, namespace isolation, distinct repeated attachments, collision rollback,
  and absence of partial mutation;
- absence of OEL-owned objective, threshold, chance constraint, and solve call;
- attachment-local residual definition and raw output policy.

### Real integration and compatibility tests

- current-SPFlow fit, schema-v3 persist/reload, explicit-event native numerator/denominator query,
  compile, pair persist/reload, and direct evaluation;
- max and PWL objective-free Pyomo/HiGHS parity at representative assignments;
- separate immutable fidelity evidence;
- consumer-owned policy composition;
- existing whole-model TPM/planning behavior and planning conditioner compatibility;
- package surface, no-legacy, lazy-dependency, lock, and offline CPU behavior.

Required backend tests fail rather than skip when current SPFlow, Pyomo, or HiGHS is unavailable in
the locked test environment.

## Fixture verification workflow

`examples/tpm_planning/run_conditional_mio_embedding.py` is the reviewed fixture command. Its normal
verification mode:

1. validates the committed source rows and configuration;
2. verifies source artifact and sidecar integrity/current-backend identity;
3. reloads both pair fixtures and validates their IDs and circuit invariants;
4. recomputes direct, native, and fixed-assignment HiGHS evidence;
5. compares recomputed semantic evidence with the committed evidence record; and
6. fails on a mismatch without rewriting any committed fixture.

An explicit maintainer-only regeneration mode may write to a fresh staging directory. It uses the
same predeclared rows, seed, and settings, performs no retries, and never overwrites committed
evidence in place. Reviewers compare staged semantic records before replacing fixtures through an
ordinary source-control change.

## Demonstration notebook

`examples/tpm_planning/conditional_mio_embedding_walkthrough.ipynb` is output-free and uses only
public OEL APIs and committed reviewed fixtures. Its markdown explains:

- numerator, explicit learned denominator, log-density meaning, and conditional log-risk;
- why uniform intended sampling does not replace the learned denominator;
- caller/OEL ownership boundaries;
- continuous affine, binary, and ordered one-hot categorical mappings;
- fixed-assignment max and PWL evaluation;
- embedding/solver parity versus native/compiler fidelity; and
- how a caller adds its own deterministic constraints, objective, $\alpha$, and log-risk constraint.

Its code loads and verifies fixtures, attaches to caller models, solves only the representative
objective-free diagnostic cases, displays persisted/recomputed evidence, and constructs but does
not solve the small consumer policy example. It does not fit, regenerate fixtures, implement
compiler math, tune encodings, enumerate a grid, or contain hand-edited outputs.

Notebook source tests assert no outputs/execution counts, public imports, prohibited implementation
or regeneration calls, required explanatory sections, and compact cell structure. The headless test
copies the notebook, blocks network access, executes it through the locked local kernel, verifies
semantic markers, and confirms the committed notebook bytes are unchanged.

## CI contract

- The existing required backend Python 3.11-3.14 matrix continues to run library, current-SPFlow,
  and Pyomo/HiGHS tests. It explicitly excludes the headless notebook execution file so lack of the
  notebook group cannot become a skip-based false pass.
- A separate required Python 3.11 notebook job installs the locked `dev` and `notebook` groups and
  runs both notebook source and headless execution tests offline after installation.
- Neither job uses Gurobi, GPU, network services, adaptive retries, or unpinned dependency updates.
- No dependency or lockfile change is expected; `uv lock --check` remains required.

## Acceptance

The feature is accepted when all focused tests and real validation paths pass, both immutable pair
fixtures verify, direct/Pyomo values and residuals meet the declared parity tolerance, native
differences remain separately auditable, the notebook executes headlessly, compatibility suites
remain green, and the repository/lock integrity checks pass. Unfavorable native/compiler fidelity
does not by itself fail acceptance.
