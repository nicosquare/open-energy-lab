# Research: Declared TPM Feature Domains

## Decision 1: Represent four meanings explicitly

**Decision**: Model mathematical domain, observed training support, normalization meaning, and
compiler approximation validity as separate typed records. A feature's mathematical record has one
role-appropriate purpose—decision domain or distribution support—and one explicit shape/origin.

**Rationale**: The current bounds pair simultaneously controls normalization, native-query
admissibility, and physical decision decoding. A new field added beside that pair would not prevent
later code from making the same semantic mistake. Separate records make the legitimate input to each
operation reviewable and serializable.

**Alternatives considered**:

- Add a `theoretical_bounds` pair beside current bounds: rejected because pairs cannot distinguish
  unknown, one-sided, or explicitly unbounded domains and do not encode purpose or provenance.
- Use one generic metadata dictionary: rejected because invalid combinations would become runtime
  convention rather than validated state.
- Put compiler validity in the fitted feature schema: rejected because it belongs to a particular
  compilation request, not to the fitted SPN's intrinsic meaning.

## Decision 2: Resolve declarations before type inference and normalization

**Decision**: Prepare a fit in four explicit stages: canonicalize physical rows and derive training
support; overlay caller declarations and roles; validate the physical rows against resolved meaning;
then normalize and invoke SPFlow. Declared feature type and ordering take precedence over sample-only
inference.

**Rationale**: A declared binary with only one observed value is currently inferred as continuous.
Post-processing an already inferred and normalized schema cannot repair its type, its ordering, or
the original evidence faithfully. The staged pipeline also guarantees invalid observations fail
before the fitting backend or artifact publication.

**Alternatives considered**:

- Override inferred bounds after normalization: rejected because the training tensor would retain
  the wrong coordinates and unobserved discrete values could not be typed correctly.
- Require declarations for every feature: rejected because the spec preserves existing callers.
- Validate only after SPFlow fit: rejected because it wastes work and can publish or cache an
  invalid intermediate result.

## Decision 3: Distinguish omission, explicit unknown, and explicit unbounded

**Decision**: An omitted declaration preserves current sample-inferred transformation and validation
as `legacy-inferred`, while the mathematical domain remains unknown. An explicitly unknown
continuous declaration uses identity normalization and accepts every finite physical value. An
explicitly unbounded support is also identity-normalized but remains a positive claim about
distribution support rather than absence of knowledge.

**Rationale**: These states can produce the same numerical transform for some data yet support
different scientific claims and downstream operations. Preserving omission behavior avoids a
gratuitous caller break; recording its source prevents the compatibility path from masquerading as
theoretical truth.

**Alternatives considered**:

- Treat omission as explicit unknown: rejected because it changes normalization and query behavior
  for existing callers.
- Treat unknown as unbounded: rejected because lack of knowledge is not a support claim.
- Infer mathematical bounds from observations: rejected by the central feature requirement.

## Decision 4: Use declared min-max only for finite continuous mathematical domains

**Decision**: Finite decision domains and bounded distribution supports define affine min-max
normalization. Fixed domains map their one valid value to coordinate `0`. One-sided, unbounded, and
explicitly unknown continuous domains retain physical units under identity normalization. Declared
binary and categorical order defines discrete index coordinates.

**Rationale**: Only a finite mathematical interval supplies both endpoints for a stable affine
coordinate system. Identity preserves the meaning of features whose finite extent is absent or
unknown. Fixed handling avoids division by zero. Caller ordering makes a declared discrete domain
stable even when a category is unobserved.

**Alternatives considered**:

- Standardize unbounded values from sample mean and variance: rejected as a generalized transform
  framework outside this feature.
- Truncate unbounded distributions to sample extrema: rejected because it invents bounded support.
- Sort declared discrete labels: rejected because it discards caller-owned binary/category order.

## Decision 5: Write TPM artifact schema v3 and adapt v2 explicitly

**Decision**: New fits write schema v3 with the four semantic records and their provenance. The new
reader accepts v2 and v3. A v2 adapter classifies bare bounds/values as legacy-inferred training and
normalization information, leaves the mathematical domain unknown, and preserves existing query
restrictions. A loaded v2 artifact writes only its v2 representation and retains its v2 version;
obtaining v3 semantics requires refitting. V1 remains unsupported/refit-only.

**Rationale**: Existing v2 readers ignore unknown feature keys. Emitting new semantics under v2
would allow an older reader to load the artifact while silently discarding its scientific meaning.
A major artifact version makes the incompatibility visible and gives the new reader one explicit
place to preserve old behavior without strengthening old claims.

**Alternatives considered**:

- Extend v2 in place: rejected because old readers can silently lose the new semantics.
- Rewrite v2 files to v3 when loading: rejected because loading must not mutate evidence or invent
  declarations.
- Make writing a loaded v2 artifact fail: rejected because preserving its schema-aware v2 write path
  retains existing behavior without adding a new claim.
- Require old OEL to read v3: rejected by the clarified backward-only compatibility policy.

## Decision 6: Keep compatibility fields as projections, not sources of truth

**Decision**: Keep existing per-feature conveniences such as bounds, discrete values, ordering, and
normalization labels where compatibility requires them, but derive their v3 meaning from resolved
semantic records. New fit, query, and compiler code reads the resolved records directly.

**Rationale**: Removing every old attribute at once would broaden the migration and break callers.
Continuing to treat them as authoritative would preserve the very ambiguity U-Bounds removes.

**Alternatives considered**:

- Remove the fields immediately: rejected as an unnecessary public break.
- Maintain two independently writable representations: rejected because they can contradict each
  other.

## Decision 7: Do not synthesize training evidence for declared domains

**Decision**: Training support is derived only from caller-supplied physical rows. A declared but
unobserved binary/category remains query-valid without inserting an alternate training row or
claiming probability mass. Backend stabilization, if necessary, must remain explicitly backend-only
and cannot modify persisted training support; a backend that cannot fit valid degenerate data fails
with a focused diagnostic.

**Rationale**: Current SPFlow tensor preparation can replace a row to create a second discrete value
and slightly perturb a constant continuous column. Those mechanics cannot be allowed to redefine
what was observed or imply that the model learned an unobserved category. U-Bounds owns domain
validity, not smoothing policy.

**Alternatives considered**:

- Add one row for every declared value: rejected because it fabricates evidence and probability
  mass.
- Reject every unobserved declared value at declaration time: rejected by the clarified query
  contract.
- Specify a new smoothing probability: rejected because backend modeling policy is out of scope.

## Decision 8: Declare compiler intervals in physical units

**Decision**: Every retained continuous leaf treatment that uses a finite approximation must receive
an explicit, positive-width physical interval. Breakpoint layout is expressed relative to that
interval, transformed through the feature's persisted normalization, and recorded as both physical
and model-coordinate points and validity intervals. No fallback comes from training support,
distribution support, legacy bounds, `[0,1]`, or the whole decision domain. New compiled-v2 output
requires a v3 fitted artifact and a finite declared mathematical domain for every retained
continuous decision approximation. Loaded v2 fitted artifacts must be refit with declarations;
supplying an interval cannot strengthen their legacy-inferred range into a mathematical domain.

**Rationale**: Researchers reason about decision and support values in physical units. The fitted
normalization is still the authoritative map into the SPN. Treating a selected subset such as
`[60,140]` as a fresh `[0,1]` interval would silently change a feature normalized by its mathematical
domain `[40,160]`.

**Alternatives considered**:

- Accept normalized intervals only: rejected because they hide the physical validity claim.
- Default to the whole declared decision domain: rejected because selecting that region must remain
  an explicit approximation decision.
- Use training extrema: rejected because coverage evidence is not compiler validity.
- Accept a caller interval against a loaded v2 artifact: rejected because interval containment
  cannot be established without a declared mathematical decision domain.
- Require arbitrary physical breakpoint lists: rejected for this feature because interval plus
  relative layout is smaller and avoids inconsistent endpoint declarations; existing layout policy
  can remain configurable without fixing a new count here.

## Decision 9: Version compiled payloads and preserve legacy evaluation separately

**Decision**: New compiler output uses a v2 representation with per-feature physical and derived
model-coordinate validity, declaration source, encoding identity, normalization meaning, and actual
breakpoints, and is produced only from qualifying v3 fitted artifacts. Existing compiled v1
payloads remain evaluable through their normalized-only legacy path and are never reinterpreted as
physical-domain evidence. The fitted-artifact version and compiled-payload version remain separate
version axes.

**Rationale**: The current compiler hard-codes normalized `[0,1]` curves and accepts normalized
evidence only. Adding physical metadata without a version boundary would make it unclear whether a
payload actually enforces the new contract.

**Alternatives considered**:

- Mutate compiled v1 in place: rejected because existing payload semantics would become ambiguous.
- Drop compiled v1 evaluation: rejected because compatibility can be preserved cheaply at the read
  boundary.
- Reinterpret normalized v1 limits as physical: rejected because there is no evidence supporting
  that claim.

## Decision 10: Marginalize before compiling and request intervals only for retained approximations

**Decision**: Planning consumers use the existing structural marginalization primitive before
compilation. The compiler requires intervals only for retained continuous features that receive an
approximate treatment. Exact binary/categorical treatments, absent features, fixed/conditioned
features, and structurally marginalized features do not invent intervals.

**Rationale**: The current planning path compiles the full graph and discards marginalized features
afterward, forcing meaningless curves for uncertainty that should not remain in the MIO. Reordering
existing operations solves that problem without introducing conditional numerator/denominator MIO
embedding, which belongs to a later feature.

**Alternatives considered**:

- Supply broad intervals for every continuous feature: rejected because it fabricates validity.
- Teach this feature a new conditional MIO formulation: rejected as U-Conditional scope.
- Keep post-compile marginalization: rejected because the unwanted approximation has already been
  constructed and recorded.

## Decision 11: Expose physical and model-coordinate decisions in Pyomo

**Decision**: Continuous MIO decisions use a physical variable, a TPM model-coordinate variable,
and the linear equality implied by persisted normalization. The approximation interval bounds the
valid physical/model coordinates. Identity normalization links equal values; a fixed feature is
fixed or removed rather than assigned repeated piecewise points. Declared binary labels map by
caller order to the solver's `0/1` coordinate and decode back to the original labels.

**Rationale**: The current model owns only a `[0,1]` variable and reconstructs a so-called physical
expression from overloaded bounds. Explicit variables and a linking equality make the units and the
validity restriction auditable in a HiGHS model.

**Alternatives considered**:

- Keep only the model-coordinate variable and a physical expression: rejected because the required
  physical-to-model-coordinate link would remain implicit in solver evidence.
- Bound every identity-normalized variable to `[0,1]`: rejected because identity coordinates retain
  physical units.
- Restrict binary declarations to numeric zero/one: rejected because the clarification makes
  caller-declared pair ordering authoritative.

## Decision 12: Use focused offline fixtures and current required backends

**Decision**: Keep the current v2 fixtures byte-stable, add one reviewable scalar-domain input and
one production v3 SPFlow artifact, and validate with current SPFlow plus a TPM-local Pyomo/HiGHS
feasibility smoke test. A focused offline example command regenerates or verifies only that v3
fixture. Tests record seeds, backend versions, digests, physical probes, expected coordinates, and
assertion tolerances. No dependency or lockfile change is planned.

**Rationale**: Deterministic unit cases prove semantic rules; a real sidecar and fit/query cycle prove
the lazy production backend; HiGHS proves the physical/model linking without introducing a
benchmark objective or commercial solver. Existing dependencies already support all of it.

**Alternatives considered**:

- Fake backends only: rejected because they do not exercise current SPFlow serialization or Pyomo
  linking.
- Gurobi as required evidence: rejected because routine validation must remain open and offline.
- Notebook evidence: rejected because the feature is a reusable upstream library capability.
- A large parity grid or performance campaign: rejected as premature and explicitly out of scope.

## Decision 13: Use one declaration mapping across every fit path

**Decision**: The public concept is an optional `feature_domains` mapping keyed by fitted feature
name. Generic-row fitting stores it on `TPMArtifactBuildRequest`; planning-dataset and study-manifest
fitting accept it as an optional keyword argument. All three paths call one internal resolver,
reject unknown or unselected keys, and treat missing keys as omission. Existing planning metadata is
never upgraded into a mathematical declaration.

**Rationale**: Only generic-row fitting currently owns a build request. Naming that request alone
does not define how the other public entry points receive declarations, and silently interpreting
their existing option metadata would strengthen old claims without caller intent.

**Alternatives considered**:

- Require a new common request object for every fit path: rejected because it would unnecessarily
  replace stable planning and study call signatures.
- Infer domains from planning feature bounds: rejected because those bounds do not carry the new
  purpose and provenance contract.
- Add both a build-request field and a duplicate keyword to generic-row fitting: rejected because
  two independently writable inputs could conflict.

## Decision 14: Use exact mathematical-domain membership

**Decision**: Finite and one-sided endpoints use exact closed comparisons. U-Bounds neither defines
nor consumes a domain-boundary tolerance. Existing fit, query, approximation, and assertion
tolerances keep their current purpose and provenance and do not widen, clamp, or reinterpret a
mathematical declaration.

**Rationale**: The repository has numerical tolerances for other operations, but none has an
established domain-membership meaning. Reusing one would invent a global policy and make it unclear
whether a slightly out-of-domain physical value was accepted, clamped, or extrapolated.

**Alternatives considered**:

- Reuse `TPMArtifactBuildRequest.numeric_tolerance`: rejected because it already qualifies other
  numeric behavior and has a default that was not selected as domain policy.
- Add a new default boundary tolerance: rejected by the feature requirement.
- Accept a slightly outside value and clamp it: rejected because declarations must never be silently
  widened or clamped.

## Decision 15: Make declarations structurally single-feature

**Decision**: Each declaration mapping entry describes one named feature only. Domain value objects
accept coordinate-domain data, not expressions or references to other features. Multi-feature
references, budget/capacity expressions, and other coupled feasibility payloads fail declaration
validation.

**Rationale**: Coupled feasibility belongs to the caller's optimization model. Rejecting it at the
typed declaration boundary keeps mathematical coordinate domains auditable and prevents a capacity
constraint from being flattened into misleading per-coordinate support.

**Alternatives considered**:

- Store coupled constraints as opaque domain metadata: rejected because downstream fit and compiler
  code could not validate or apply their meaning consistently.
- Derive coordinate bounds from a coupled constraint: rejected because the projection requires
  benchmark/model semantics outside U-Bounds.
