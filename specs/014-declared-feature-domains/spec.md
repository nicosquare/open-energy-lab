# Feature Specification: Declared TPM Feature Domains

**Feature Branch**: `014-declared-feature-domains`
**Created**: 2026-08-27
**Status**: Draft
**Input**: User description: "Add caller-declared mathematical feature domains to OEL TPM workflows while preserving training support, normalization meaning, approximation validity, and legacy compatibility as distinct concepts."

## Purpose *(mandatory)*

Give Open Energy Lab researchers a trustworthy way to declare the mathematical domains of TPM
features and carry those meanings through fitting, normalization, querying, persistence, and
compilation. A finite training sample must no longer silently define theoretical decision bounds,
distribution support, or the region over which a compiler approximation is valid.

The feature strengthens the existing TPM library rather than creating a paper-specific workflow.
It preserves existing artifacts and callers through visibly labelled compatibility behavior while
allowing new research to distinguish a mathematical decision domain, uncertainty support, observed
training support, and compiler approximation validity. This distinction is necessary for
reproducible models and for later optimization studies whose decisions may lie near mathematical
boundaries that training data cover sparsely.

## Clarifications

### Session 2026-08-27

- Q: When an existing caller fits a new artifact without declaring a continuous mathematical
  domain, how should that feature be normalized? → A: Use observed-extrema min-max normalization,
  label it legacy-inferred, and keep the mathematical domain unknown.
- Q: Which coordinate system should be authoritative when a caller declares a compiler
  approximation interval? → A: Declare it in physical units and persist both the authoritative
  physical interval and its derived normalized interval.
- Q: May one feature carry both a decision-domain declaration and a distribution-support
  declaration at the same time? → A: No. Each feature has one role-appropriate mathematical
  declaration; decision-sampling policy is not distribution support, and training support remains
  separate.
- Q: To which normalized coordinate should a fixed continuous domain $[l,l]$ map? → A: Map its
  sole valid physical value to the normalized coordinate $0$.
- Q: For an undeclared continuous feature using legacy-inferred min-max normalization, what should
  happen when a native query lies outside the observed extrema? → A: Reject it as a visibly
  labelled legacy-compatibility restriction, not as a mathematical-domain judgment.
- Q: If a caller explicitly declares a continuous mathematical domain as unknown, how should OEL
  normalize and query that feature? → A: Use identity normalization, accept finite fitting and
  native-query values, and fail only operations that require a mathematical domain.
- Q: When a declared binary or categorical value is absent from all training rows, what must a
  native query for that value do? → A: Accept it as domain-valid and leave its probability to the
  fitted model and backend; U-Bounds neither invents nor requires probability mass.
- Q: When a new fit omits a mathematical declaration for a discrete feature, which values should
  its compatibility path recognize? → A: Preserve the values, ordering, encoding, and validation
  inferred by existing behavior; label them legacy-inferred training information, keep the
  mathematical domain unknown, and do not fabricate unobserved values.
- Q: Must OEL versions from before U-Bounds be able to load new artifacts containing declared-domain
  semantics? → A: No. Compatibility is backward only: new OEL loads valid old artifacts, while old
  OEL need not load new artifacts and new artifacts must not discard semantics to mimic the old
  representation.
- Q: When a caller declares the two values of a binary feature, how should their normalized order be
  determined? → A: Preserve the caller-declared ordered pair; map its first value to $0$ and its
  second value to $1$ across normalization, persistence, querying, and binary decision linking.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability with compatibility validation
- **Target surface**: Public TPM feature declarations; fitting, normalization, native-query, and
  compiler behavior; persisted TPM and compiled-result metadata; focused validation fixtures
- **Legacy reference paths**: None. Existing OEL TPM artifacts and fixtures are the compatibility
  baseline; `legacy/*` is not a runtime dependency or migration target for this feature.
- **New-code location**: The existing `src/open_energy_lab/tpm` package and corresponding focused
  validation under `tests/unit/tpm` and `tests/integration/tpm`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declare and Audit Mathematical Domains (Priority: P1)

As a researcher fitting a TPM, I need to declare the mathematical domain appropriate to each
feature and inspect that declaration after persistence so that sampled extrema cannot be mistaken
for theoretical truth.

**Why this priority**: Every later normalization, query, and compilation decision depends on
knowing whether a range represents feasibility, uncertainty support, observed coverage, or
approximation validity.

**Independent Test**: A reviewer can build and reload feature descriptions for a finitely bounded
scalar decision, an explicitly unbounded normal uncertainty, one-sided continuous supports,
declared binary and categorical domains, and an unknown domain, then verify that each mathematical
meaning and its provenance remain distinct from observed training support.

**Acceptance Scenarios**:

1. **Given** scalar decision $x$ with declared domain $[40,160]$ and normal demand $D$ with fully
   unbounded support, **When** their feature descriptions are validated and persisted, **Then** the
   decision domain and distribution support retain their different purposes and demand has no
   fabricated finite endpoints.
2. **Given** finite, lower-bounded, upper-bounded, fully unbounded, and unknown continuous-domain
   declarations, **When** each is persisted and reloaded, **Then** its shape and meaning round trip
   without serializing numeric infinity and unknown never becomes explicitly unbounded.
3. **Given** a declared binary domain whose training rows contain only one of its values, **When**
   the feature description is produced, **Then** the complete two-value mathematical domain and the
   one-value observed training support are both preserved, and the declaration's first-to-$0$ and
   second-to-$1$ ordering remains unchanged.
4. **Given** a declared categorical value set and ordering whose training rows omit one declared
   category, **When** the feature description is produced, **Then** the complete declared set and
   ordering remain intact while the observed subset is recorded separately.
5. **Given** an existing caller that supplies no mathematical declaration, **When** fitting
   prepares feature metadata, **Then** the mathematical domain remains unknown and any observed
   extrema or values are identified only as training support or visibly legacy-inferred behavior.
6. **Given** a feature declaration that supplies both a decision domain and distribution support,
   **When** the declaration is validated, **Then** it is rejected as role-ambiguous before fitting
   or persistence begins.

---

### User Story 2 - Normalize and Query Against Declared Meaning (Priority: P1)

As a TPM consumer, I need normalization and assignment validation to follow declared mathematical
domains rather than a particular sample so that equivalent studies use stable coordinates and
valid decisions are not rejected merely because they were unobserved during training.

**Why this priority**: Sample-dependent normalization changes model inputs across seeds and can
exclude legitimate boundary decisions. Stable declared semantics are the principal user-visible
benefit of this feature.

**Independent Test**: Two training datasets with different observed extrema but the same declared
scalar domain normalize the same physical probe identically. A production fit and native query use
that finite decision normalization while an explicitly unbounded normal feature remains in
physical units.

**Acceptance Scenarios**:

1. **Given** two datasets with different observed extrema for $x$ but the same declared domain
   $[40,160]$, **When** $x=100$ is normalized in each workflow, **Then** both produce the same
   normalized coordinate and both persisted training-support summaries retain their actual,
   different extrema.
2. **Given** explicitly unbounded normal demand observations, **When** they are prepared for fitting
   and native querying, **Then** every finite value remains in physical units under identity
   normalization.
3. **Given** a decision assignment inside its declared domain but outside observed training
   extrema, **When** a native query validates the assignment, **Then** the assignment is accepted
   without widening or rewriting the training-support record.
4. **Given** a training observation outside a declared finite decision domain or bounded
   distribution support, **When** fitting validation begins, **Then** validation fails before a
   fitting backend runs and no complete artifact is published.
5. **Given** a value outside a declared binary or categorical domain, **When** training or query
   validation occurs, **Then** the value is rejected even if its type would otherwise be accepted.
6. **Given** a lower-bounded or upper-bounded feature, **When** finite values on and within its
   supported side are validated, **Then** they are accepted in physical units, while values beyond
   the finite endpoint are rejected.
7. **Given** a fixed continuous domain $[l,l]$, **When** its sole valid value is normalized, queried,
   persisted, and reloaded, **Then** it maps to $0$ without division by zero or coordinate drift.
8. **Given** an explicitly unknown continuous domain, **When** finite training or native-query
   values are processed, **Then** they remain in physical units under identity normalization, while
   a later operation requiring a mathematical domain fails without reclassifying the feature as
   unbounded or legacy-inferred.
9. **Given** a declared binary or categorical value absent from all training rows, **When** a native
   query assigns that value, **Then** domain validation accepts it and the fitted model and backend
   determine the returned probability without U-Bounds adding or requiring probability mass.

---

### User Story 3 - Qualify Compiler Approximation Regions (Priority: P2)

As a researcher compiling an SPN expression, I need every approximation to state the finite region
over which it is constructed and valid so that the compiled result cannot silently claim validity
from training extrema or distribution support.

**Why this priority**: Compiler evidence is meaningful only when its validity region is explicit.
An optimizer can otherwise exploit extrapolation beyond the interval that was actually encoded and
assessed.

**Independent Test**: A small continuous-decision compilation records a caller-selected finite
approximation interval, maps physical and normalized decision values consistently, and rejects
evaluation outside that interval. A missing interval fails only when the selected approximation
requires one.

**Acceptance Scenarios**:

1. **Given** a continuous decision domain $[40,160]$ and an explicitly selected approximation
   interval $[60,140]$, **When** an approximation is compiled, **Then** the result records the
   authoritative physical interval, its derived normalized interval, its declared source, and the
   encoding it qualifies without changing the fitted feature's decision domain or normalization.
2. **Given** an approximation that requires a finite validity interval but none is declared,
   **When** compilation is requested, **Then** compilation fails rather than substituting training
   extrema, distribution support, or a default normalized interval.
3. **Given** an approximation interval extending outside a decision feature's mathematical domain,
   **When** compilation validates it, **Then** the incompatible declaration is rejected.
4. **Given** a compiled result with a recorded approximation interval, **When** evaluation is
   requested outside that interval, **Then** evaluation fails without clipping or extrapolation.
5. **Given** a marginalized feature or a feature treatment that is exact and needs no finite
   approximation region, **When** compilation occurs, **Then** no artificial approximation domain
   is required or recorded for that feature.

---

### User Story 4 - Preserve Existing Artifacts Without Strengthening Their Claims (Priority: P2)

As an OEL maintainer, I need existing TPM artifacts and callers to remain usable while their
sample-derived ranges are labelled honestly so that this feature improves semantics without
silently rewriting prior evidence or causing an avoidable compatibility break.

**Why this priority**: OEL already persists feature bounds and uses them in fitting, querying, and
planning. Compatibility is required, but reproducing old behavior must not turn observed ranges
into new theoretical claims.

**Independent Test**: Representative pre-feature artifacts load without mutation, retain their
existing normalization results, and expose their finite ranges as legacy-inferred rather than as
declared decision domains, bounded distribution support, or compiler approximation domains.

**Acceptance Scenarios**:

1. **Given** a valid pre-feature artifact containing a bare continuous bounds pair, **When** it is
   loaded, **Then** it remains usable through its existing compatibility path and its range is
   identified as legacy-inferred training information.
2. **Given** a pre-feature artifact, **When** it is loaded or queried, **Then** its persisted source
   bytes are not rewritten and no new mathematical-domain claim is added to it implicitly.
3. **Given** an artifact with only an unknown domain or legacy-inferred range, **When** an operation
   requires a finite mathematical decision domain or approximation interval, **Then** that
   operation fails with the missing semantic requirement identified.
4. **Given** an existing caller that omits declarations, **When** it fits and reloads an artifact,
   **Then** observed-extrema min-max normalization remains available, the mathematical domain stays
   unknown, and the transform is visibly labelled legacy-inferred rather than caller-declared.
5. **Given** an undeclared continuous feature using legacy-inferred min-max normalization, **When**
   a native query falls outside its observed extrema, **Then** the query is rejected and the
   diagnostic identifies an operational legacy-compatibility limit rather than claiming a
   mathematical-domain violation.
6. **Given** a new fit with an undeclared discrete feature, **When** OEL derives and reloads its
   feature metadata, **Then** existing observed-value encoding, ordering, and validation remain
   available as visibly legacy-inferred behavior, the mathematical domain remains unknown, and no
   unobserved binary value or category is synthesized.
7. **Given** a new artifact containing declared-domain semantics, **When** compatibility is
   assessed, **Then** it round trips through the new reader without semantic loss and is not
   required to load in a pre-feature reader or emitted as a legacy representation that would omit
   those meanings.

### Edge Cases

- A continuous declaration contains a non-numeric endpoint, a non-finite stored endpoint, or a
  lower endpoint greater than its upper endpoint.
- A finite declaration has equal endpoints and therefore represents one fixed physical value.
- A declaration attempts to combine unknown with an explicit bounded or unbounded meaning.
- An explicit unknown declaration must remain distinct from omission-based legacy inference even
  when their training rows have the same observed extrema.
- A binary declaration has other than two distinct values, or a categorical declaration contains
  duplicates or an ordering that does not cover the declared value set exactly.
- A declared binary pair uses non-numeric labels or training observes only its second value; neither
  condition may reorder the first-to-$0$, second-to-$1$ mapping.
- Training rows contain `NaN`, positive or negative infinity, or values outside a declared domain.
- A query is inside the mathematical domain but outside training support, or inside training
  support but outside the mathematical domain.
- An undeclared feature receives a native query outside the observed extrema that supply its
  legacy-inferred normalization range.
- An undeclared discrete feature has observations that are insufficient to establish a complete
  binary or categorical mathematical domain.
- A one-sided support receives a value on its finite endpoint or beyond it.
- A caller supplies coupled feasibility logic, such as a budget or capacity constraint, as though
  it were an independent feature bound.
- An approximation interval is absent, empty, reversed, non-finite, wider than the decision domain,
  or confused with an uncertainty feature's distribution support.
- A compiler request mixes exact, marginalized, and approximated features, only some of which need
  explicit finite approximation intervals.
- A pre-feature artifact lacks enough metadata to infer whether its bare range originally described
  a decision, uncertainty, or context feature.
- An explicitly declared but unobserved binary or categorical value remains valid for native
  queries; its fitted probability may be weak, absent, smoothed, or otherwise backend-dependent.
- An existing workflow has a documented numerical tolerance at a finite boundary, while another
  workflow has no such tolerance.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The feature MUST represent mathematical decision domains, distribution support,
  observed training support, and compiler approximation domains as distinct meanings. A feature
  MUST NOT simultaneously declare both a decision domain and distribution support; its one
  mathematical declaration MUST match its role.
- **FR-002**: Callers MUST have a documented public way to provide mathematical feature-domain
  declarations during TPM artifact construction without depending on inferred training extrema.
- **FR-003**: A continuous mathematical domain MUST distinguish finite, lower-bounded,
  upper-bounded, fully unbounded, and unknown states.
- **FR-004**: Unknown MUST remain distinct from explicit unboundedness in memory, persisted
  artifacts, validation, and user-visible diagnostics.
- **FR-005**: Unbounded endpoints MUST be represented through domain meaning rather than persisted
  non-finite numeric values.
- **FR-006**: Finite endpoints MUST be ordered, closed, and inclusive. Equal endpoints MUST denote
  a fixed-value domain whose sole valid physical value maps to normalized coordinate $0$ without
  division by zero.
- **FR-007**: A feature declaration MUST retain its purpose and origin so that consumers can
  distinguish caller-declared mathematical information from observed or legacy-inferred data.
- **FR-008**: OEL MUST derive continuous training extrema and observed discrete values from physical
  training rows and persist them separately from mathematical domains.
- **FR-009**: Binary declarations MUST preserve exactly two distinct domain values as a
  caller-declared ordered pair independently of which values appear in training. The first value
  MUST map to normalized coordinate $0$ and the second to $1$, and that mapping MUST remain stable
  through persistence, querying, and binary decision linking.
- **FR-010**: Categorical declarations MUST preserve a complete distinct value set and an ordering
  covering that set independently of which categories appear in training.
- **FR-011**: Training observations outside a declared binary or categorical domain MUST fail
  validation rather than extending the declaration.
- **FR-012**: New artifacts with a finite declared continuous decision domain or bounded
  distribution support MUST use its endpoints for affine min-max normalization.
- **FR-013**: New artifacts with lower-bounded, upper-bounded, fully unbounded, or explicitly
  unknown continuous domains or support MUST use identity normalization and retain physical units.
- **FR-014**: Observed training extrema MUST NOT automatically determine normalization for a newly
  declared artifact.
- **FR-015**: Approximation-domain declarations MUST NOT change fitting or native-query
  normalization.
- **FR-016**: Training observations outside a declared continuous decision domain or bounded
  distribution support MUST fail before a fitting backend is invoked and before a complete artifact
  is published.
- **FR-017**: Every finite observation for an explicitly fully unbounded feature MUST be valid with
  respect to support, subject to the feature's other type requirements.
- **FR-018**: Lower-bounded and upper-bounded continuous domains or support MUST validate the finite
  endpoint in the declared direction while accepting any finite value on the unbounded side.
- **FR-019**: Native queries MUST accept assignments inside the declared mathematical domain even
  when those assignments fall outside observed training support. For an explicitly unknown
  continuous domain, every finite native-query assignment MUST be accepted without implying a
  bounded or unbounded mathematical-domain claim. A declared binary or categorical value MUST
  likewise remain queryable when unobserved in training, while its probability remains fitted-model
  and backend behavior outside the responsibility of this feature.
- **FR-020**: Validation failures MUST identify the feature, supplied value or declaration, violated
  domain meaning, and expected condition without clamping, truncating, widening, or rewriting the
  declaration.
- **FR-021**: This feature MUST NOT introduce a new fixed global boundary tolerance. A workflow
  that already declares a numerical tolerance MAY apply it consistently to floating-point boundary
  noise and MUST retain enough context to reproduce that interpretation.
- **FR-022**: Any approximation that requires a finite validity region MUST require an explicit
  finite approximation-domain declaration.
- **FR-023**: A decision feature's approximation domain MUST lie within its declared mathematical
  decision domain and MAY equal the entire domain or a deliberate subset.
- **FR-024**: Selecting the entire decision domain as an approximation domain MUST be an explicit
  caller choice rather than a silent default.
- **FR-025**: Training support and distribution support MUST NOT be substituted for a missing
  approximation domain.
- **FR-026**: Approximation domains MUST be declared in physical feature units. A compiled result
  MUST retain the authoritative physical interval, its derived normalized interval, the declared
  source, and the encoding whose validity it qualifies.
- **FR-027**: Compiled evaluation outside a recorded approximation domain MUST fail rather than
  extrapolate or clip.
- **FR-028**: Marginalized features and exact feature treatments MUST NOT be required to invent an
  approximation domain solely for schema completeness.
- **FR-029**: Existing callers MAY omit new declarations. For a newly fitted undeclared continuous
  feature, OEL MUST preserve observed-extrema min-max normalization, MUST label that transform
  legacy-inferred, and MUST keep the mathematical domain unknown. Native queries outside that
  legacy-inferred range MUST retain the existing rejection behavior, and the failure MUST identify
  the limit as operational compatibility behavior rather than mathematical invalidity. This
  omission-based compatibility path MUST NOT apply to an explicit unknown declaration. For a newly
  fitted undeclared discrete feature, OEL MUST preserve the observed-value inference, ordering,
  encoding, and validation supplied by existing behavior as legacy-inferred training information,
  MUST keep the mathematical domain unknown, and MUST NOT synthesize an unobserved binary value or
  category.
- **FR-030**: Valid pre-feature artifacts MUST remain loadable by the new implementation without
  byte mutation or silent migration, and their existing inferred ranges MUST be visibly classified
  as legacy-inferred. Pre-feature readers are not required to load new artifacts containing
  declared-domain semantics.
- **FR-031**: Existing artifacts MAY retain their inferred min-max transformation for compatibility,
  but that range MUST NOT be presented as a declared decision domain, bounded distribution support,
  or approximation-validity claim.
- **FR-032**: An operation requiring a finite mathematical domain or approximation domain MUST fail
  clearly when an artifact supplies only unknown or legacy-inferred range information.
- **FR-033**: The feature MUST preserve existing mixed-feature artifact loading and compatibility
  behavior without adding new mixed-domain semantics.
- **FR-034**: The feature MUST NOT introduce integer feature semantics; finite numeric intervals may
  describe quantity bounds without implying integrality.
- **FR-035**: Persisted domain, support, normalization, and approximation information MUST round trip
  through the new reader without loss of meaning or provenance. A new artifact MUST NOT discard or
  disguise these meanings merely to resemble a pre-feature representation.
- **FR-036**: Required fitting, native-query, and physical-to-normalized compiler validation MUST be
  reproducible offline on CPU using the project's existing production dependency boundaries.
- **FR-037**: Heavy or environment-sensitive dependencies MUST remain isolated at their existing
  workflow boundaries; importing the base library MUST NOT initiate those dependencies.
- **FR-038**: This feature MUST NOT modify the parent research repository. The parent gitlink update
  occurs only after the OEL feature is implemented, tested, and committed.
- **FR-039**: Required evidence MUST retain the exact domain declarations, physical fixture rows,
  fitting configuration and seeds where fitting occurs, normalization meaning, approximation
  request and encoding identity where compilation occurs, dependency context, and open-solver
  assumptions needed to reproduce each result.

### Out of Scope

- Conditional numerator/denominator MIO embedding and objective-free conditional-risk parity
- Caller-owned benchmark objectives, capacity constraints, budget constraints, and decision
  optimization
- Choosing benchmark bounds, truncating distributions, or measuring training coverage
- Declaring or interpreting decision-sampling distributions as uncertainty-feature support
- Integer feature semantics, integer MIO linking, and new mixed-feature behavior
- Device selection, GPU execution, distributed execution, or campaign resource management
- Configurable standardization or a generalized feature-transformation framework
- Notebooks, benchmark experiments, large parity grids, and paper-scale campaigns
- A reusable solver-option bundle or a commercial solver requirement
- Any parent-repository source, specification, roadmap, or gitlink change

### Compatibility Baseline

- Current OEL TPM feature metadata, normalized training behavior, persisted artifact loading,
  native assignment validation, and continuous decision compilation form the behavior baseline.
- Compatibility covers loading and reproducing valid pre-feature artifacts; it does not endorse the
  old interpretation of observed extrema as theoretical truth.
- The feature may evolve persisted representations as needed, provided old artifacts remain
  loadable without in-place rewriting and new artifacts preserve the meanings required above.
- Compatibility is backward only: the new implementation reads valid pre-feature artifacts, while
  no forward-compatibility guarantee is made for loading new artifacts with pre-feature readers.
- No behavior from `legacy/*` is migrated or used as a required parity oracle.

### Key Entities

- **Mathematical Feature Domain**: The caller's statement of feasible decision values or uncertainty
  support, including its purpose, shape, finite endpoints when present, and declaration provenance.
- **Training Support**: The extrema or discrete values observed in the physical training rows,
  retained as coverage evidence rather than mathematical feasibility or distribution truth.
- **Normalization Meaning**: The reproducible relationship between physical feature values and
  model coordinates, including whether declared min-max, physical-unit identity, or labelled
  legacy-inferred normalization applies.
- **Approximation Domain Declaration**: A caller-selected finite interval associated with one
  compiler request for a feature treatment that needs bounded validity.
- **Compiled Validity Record**: The authoritative physical interval, its derived normalized
  interval, source, encoding identity, and feature association that delimit where a compiled
  approximation may be evaluated.
- **Legacy-Inferred Range**: A pre-feature or compatibility range derived from observed data whose
  operational role is preserved without granting it mathematical-domain meaning.

### Dependency and Environment Requirements

- **Core dependencies**: No new unconditional dependency is required for domain declaration,
  validation, normalization, or artifact round trips.
- **Workflow dependencies**: Existing SPFlow fitting and native querying plus the existing Pyomo and
  HiGHS optimization/compiler path remain required only at their established lazy workflow
  boundaries. HiGHS is the routine compiler smoke solver.
- **External services**: None. All required evidence is offline and fixture-backed.
- **Hardware assumptions**: CPU only. No GPU, distributed environment, or commercial solver license
  is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All five continuous mathematical-domain states—finite, lower-bounded,
  upper-bounded, fully unbounded, and unknown—round trip with their meaning unchanged in focused
  acceptance fixtures.
- **SC-002**: Across two datasets with different observed extrema and one shared declared finite
  domain, every shared physical probe has the same normalized coordinate in both workflows.
- **SC-003**: Finite-domain endpoints map deterministically to their two endpoint coordinates,
  every fixed-value domain maps its sole valid value to $0$, and every accepted one-sided or fully
  unbounded value, as well as every finite explicitly unknown value, remains unchanged under
  identity normalization.
- **SC-004**: Every acceptance fixture containing an observation outside a declared continuous,
  binary, or categorical domain is rejected before fitting and produces no complete artifact.
- **SC-005**: Declared binary and categorical domains retain 100% of their declared values and
  ordering when training observes only a strict subset, and native domain validation accepts every
  retained value without U-Bounds manufacturing a probability result; every declared binary pair
  retains its first-to-$0$ and second-to-$1$ mapping.
- **SC-006**: A production scalar fit/query validation uses $x\in[40,160]$ independently of sampled
  extrema while fully unbounded normal demand retains physical-unit normalization.
- **SC-007**: Every representative pre-feature artifact fixture loads without source mutation,
  reproduces its continuous or discrete compatibility encoding, and identifies bare ranges or
  observed-value sets as legacy-inferred rather than mathematical or approximation truth; its
  unsupported native-query fixture is rejected with the same distinction and no missing discrete
  value is fabricated.
- **SC-008**: Every compiler acceptance fixture that needs approximation bounds records matching
  physical and derived normalized intervals, rejects a missing or incompatible interval, and
  rejects every tested evaluation outside the authoritative physical interval.
- **SC-009**: One small physical-to-normalized decision-linking workflow completes offline on CPU
  through the open solver path without network access or a commercial license.
- **SC-010**: Importing the base library continues to complete without activating fitting,
  compiler, or solver dependencies.
- **SC-011**: No acceptance artifact conflates a mathematical domain, distribution support,
  training support, normalization range, or compiler approximation domain when audited after
  persistence and reload.

## Assumptions

- Researchers provide domain declarations appropriate to feature roles; this capability validates
  and preserves declarations but does not choose benchmark bounds or probability distributions.
- Finite and one-sided endpoints are closed. A finite declaration with equal endpoints represents
  a fixed physical feature value.
- Training support is derived from raw physical values before normalization.
- A declared but unobserved category remains a valid mathematical value even when fitted evidence
  for that category is weak or absent.
- Existing artifacts may require compatibility interpretation because their bare bounds do not
  contain enough information to recover original mathematical intent.
- Exact public names, object layouts, and persisted schema mechanics are planning decisions; the
  specification fixes observable behavior and preserved meaning rather than those designs.
- Objective-free conditional-risk parity, caller-owned conditional MIO blocks, integer linking,
  mixed-feature redesign, generalized transformation policies, device selection, and benchmark
  experiments remain separate features.
