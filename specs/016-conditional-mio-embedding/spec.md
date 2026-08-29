# Feature Specification: Composable Conditional MIO Embedding

**Feature Branch**: `016-conditional-mio-embedding`
**Created**: 2026-08-28
**Status**: Draft
**Input**: User description: "Expose reusable compiled conditional numerator and denominator circuits that attach to caller-owned decision models without taking ownership of their objectives, constraints, thresholds, or solver execution."

## Purpose *(mandatory)*

Give Open Energy Lab researchers a reusable way to place SPN-derived conditional risk inside a
model they own. A researcher must be able to compile one conditional numerator/denominator pair,
inspect and persist its meaning, attach that exact pair to an existing decision model, and use the
returned conditional log-risk in paper-specific constraints without copying OEL compiler logic.

The capability closes the gap between native conditional queries and optimization. Native querying
can evaluate a conditional probability at a supplied assignment, while later scalar, knapsack, and
newsvendor studies need the retained decisions to remain symbolic. OEL therefore owns the compiled
SPN circuits, their mathematical meaning, validity, provenance, and decision-coordinate links. The
caller continues to own primary decisions, objectives, deterministic constraints, chance thresholds,
chance constraints, and solver execution.

The feature extends the unified OEL TPM library. It does not create a benchmark workflow or a second
SPN implementation, and it does not enumerate candidate decisions or precompute conditional-risk
tables.

## Clarifications

### Session 2026-08-28

- Q: Which coordinate forms should the conditional pair's direct evaluator accept? → A: Accept
  either complete declared-domain assignments—physical units for continuous values and declared
  values for discrete features—or complete model-coordinate assignments, explicitly selected per
  evaluation. Declared-domain assignments are the normal researcher-facing path, and one evaluation
  cannot mix or supply both modes.
- Q: Must one conditional pair support continuous, binary, and categorical decisions together? →
  A: Yes. One pair may retain any supported mixture of continuous, binary, and categorical
  decisions; joint conditional risk must not be split into type-specific pairs.
- Q: After compilation, where should parity and compiler-fidelity results be stored? → A: Keep the
  published conditional pair immutable and store evaluation evidence in separate immutable records
  that reference the pair's identity.

## Scope Classification *(mandatory)*

- **Feature type**: New library capability with compiler, persistence, and parity validation
- **Target surface**: Public TPM compilation, direct-evaluation, persistence, and caller-owned
  Pyomo-model composition behavior; focused evidence records; offline demonstration notebook
- **Legacy reference paths**: None. Existing current OEL TPM fitting, native-query, compiler, and
  whole-model behavior are the compatibility baseline; `legacy/*` is not a runtime dependency or
  migration target.
- **New-code location**: The existing `src/open_energy_lab/tpm` library boundary and its public lazy
  dependency surface, with focused tests and one thin example notebook; exact modules, public names,
  record layouts, and file placement are planning decisions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compile a Reusable Conditional Pair (Priority: P1)

As a researcher with a current persisted SPN artifact, I need to compile an explicit binary event
into one reusable numerator/denominator pair so that the conditional probability retains its true
denominator and can later be evaluated or embedded without refitting.

**Why this priority**: The shared conditional pair is the scientific and architectural foundation
for every later attachment, parity check, and optimization use. Without an explicit denominator,
nonuniform decision evidence can produce the wrong conditional risk.

**Independent Test**: Compile one eligible current artifact for event value $Y=1$ while retaining a
decision feature. Reload the pair and directly evaluate its numerator, denominator, log-risk, and
derived probability at fixed assignments under each supported Sum encoding.

**Acceptance Scenarios**:

1. **Given** an eligible fitted artifact, one declared binary event target and value, retained
   decisions, required approximation domains, and a selected encoding, **When** compilation
   succeeds, **Then** one solver-neutral pair contains numerator and denominator circuits with a
   shared origin, event meaning, validity, encoding policy, and identity.
2. **Given** a decision assignment $x$, **When** the pair is directly evaluated, **Then** it exposes
   $z_{\mathrm{num}}(x)$, $z_{\mathrm{den}}(x)$,
   $z_{\mathrm{num}}(x)-z_{\mathrm{den}}(x)$, and its derived probability using the selected
   compiled semantics.
3. **Given** deliberately nonuniform decision evidence, **When** a pair is compiled, **Then** its
   denominator is derived from the same fitted SPN and is neither discarded nor replaced by a
   uniform-density assumption or caller constant.
4. **Given** the same artifact but a different event value, retained decision set, approximation
   domain, encoding configuration, or semantic tolerance, **When** compilation is requested,
   **Then** the resulting pair has a distinguishable identity and does not overwrite the earlier
   pair.

---

### User Story 2 - Attach Continuous Risk to a Caller Model (Priority: P1)

As a model author, I need to attach a compiled pair to an existing Pyomo model using my own
continuous decision variable or affine expression so that I can combine conditional risk with my
own objective and deterministic constraints.

**Why this priority**: Composability is the capability's central gap. Existing whole-model behavior
cannot cleanly express caller-owned benchmark formulations, and recreating primary decisions would
make ownership and coupling ambiguous.

**Independent Test**: Create a small caller-owned Pyomo model with a continuous decision expression
in physical units, attach an already-compiled pair under a unique namespace, and verify that the
caller can add an unrelated constraint and objective around the returned log-risk while OEL adds
only its own namespaced circuits, auxiliaries, validity constraints, and coordinate links.

**Acceptance Scenarios**:

1. **Given** a scalar affine expression containing only caller-owned continuous variables and fixed
   parameters, **When** it is mapped to a retained continuous decision, **Then** OEL links the
   expression from physical units to the artifact's declared model coordinates without recreating
   the caller's primary variables.
2. **Given** a finite closed approximation domain, **When** the pair is attached, **Then** the
   attachment enforces its inclusive validity boundaries without clamping the caller expression.
3. **Given** an attached pair, **When** the caller adds its own objective, deterministic constraint,
   threshold $\alpha$, and constraint
   $z_{\mathrm{num}}-z_{\mathrm{den}}\leq\log\alpha$, **Then** no OEL-owned objective, threshold,
   chance constraint, or solver invocation conflicts with those choices.
4. **Given** a nonlinear expression or an expression containing a general integer variable,
   **When** attachment validation runs, **Then** the request fails before the caller model is
   modified.

---

### User Story 3 - Compose Binary and Categorical Decisions (Priority: P1)

As a model author with discrete design choices, I need to map caller-owned binary decisions and
ordered categorical one-hot indicators to compiled SPN decisions so that battery, panel, and similar
choices can participate without enumerating their Cartesian product.

**Why this priority**: Binary and categorical decisions already occur in OEL planning examples. A
new composable path that supported only continuous decisions would regress an important existing
capability and would not support the intended diagnostic models.

**Independent Test**: Attach a real compiled discrete case to a caller model containing one binary
variable and an ordered categorical one-hot vector. Evaluate both binary states and representative
categories while verifying declared ordering, exactly-one enforcement, and absence of Cartesian
lookup data.

**Acceptance Scenarios**:

1. **Given** a retained binary feature and a caller-owned binary variable, **When** attachment
   succeeds, **Then** the two variable states are interpreted using the artifact's declared
   two-value ordering.
2. **Given** a retained categorical feature and one caller-owned binary indicator per declared
   category in persisted order, **When** attachment succeeds, **Then** the OEL-owned attachment adds
   the required exactly-one relationship and maps each indicator to the corresponding category.
3. **Given** missing, duplicate, reordered, nonbinary, foreign-model, or extra categorical
   indicators, **When** validation runs, **Then** the attachment is rejected without partial model
   mutation.
4. **Given** several discrete decisions, **When** they are attached, **Then** the circuit remains
   symbolic and no table over the Cartesian decision space is generated.
5. **Given** retained decisions of more than one supported type, **When** the pair is compiled and
   attached, **Then** all decisions participate jointly in the same numerator, denominator, and
   conditional log-risk rather than being divided into type-specific pairs.

---

### User Story 4 - Distinguish Solver Parity from Compiler Fidelity (Priority: P1)

As a compiler reviewer, I need fixed-assignment evidence that separates symbolic embedding errors
from max or PWL approximation error so that a solver mismatch cannot be confused with a scientific
compiler discrepancy.

**Why this priority**: Comparing an approximate embedded circuit to an exact native evaluator and
calling the difference solver parity would attribute error to the wrong layer. Later research must
know whether a discrepancy came from compilation or model attachment and evaluation.

**Independent Test**: For boundary and interior continuous assignments, both binary states, and
representative categorical values, compare an objective-free fixed-assignment Pyomo/HiGHS solve
with direct evaluation of the identical compiled pair, then record native-current-SPFlow
comparisons separately.

**Acceptance Scenarios**:

1. **Given** a compiled pair and fixed caller decisions, **When** its attached roots are evaluated,
   **Then** the numerator root, denominator root, conditional log-risk, solver status, and relevant
   residuals are retained.
2. **Given** the same fixed assignment, **When** direct compiled and attached-model values are
   compared, **Then** each root and their difference agree within an absolute tolerance of
   $10^{-6}$, every applicable constraint residual has absolute value no greater than $10^{-6}$,
   or the parity check fails operationally.
3. **Given** native numerator and denominator log values from the source SPN, **When** compiler
   fidelity is reported, **Then** numerator error, denominator error, conditional-log-risk error,
   and probability difference are retained without an adequacy gate.
4. **Given** a max or PWL pair, **When** direct evaluation supplies the parity reference, **Then** it
   executes that exact selected approximation rather than an exact log-sum-exp substitute.
5. **Given** a compiled conditional log-risk above $10^{-6}$, **When** validity is assessed,
   **Then** it is rejected; a smaller positive value remains visible as numerical noise rather than
   being clamped.

---

### User Story 5 - Attach Safely and Reuse Auditable Evidence (Priority: P2)

As an OEL maintainer, I need conditional pairs and attachments to preserve identity, isolate their
namespaces, and fail atomically so that multiple risks can coexist and rejected requests cannot
corrupt caller models or prior evidence.

**Why this priority**: Reuse is safe only when the pair used for direct evaluation is exactly the
pair later attached, and when model mutation does not occur until every semantic input is valid.

**Independent Test**: Persist and reload a pair, attach it twice under distinct names, reject a
duplicate namespace and several invalid mappings, and verify that failed requests leave component
names and model structure unchanged.

**Acceptance Scenarios**:

1. **Given** a persisted pair, **When** it is reloaded, **Then** its identity, circuits, event
   meaning, retained and marginalized features, domains, encoding, tolerances, and provenance are
   unchanged.
2. **Given** a published pair that has been directly evaluated or checked through a fixed-assignment
   solve, **When** its evidence is retained, **Then** the pair remains byte-for-byte and semantically
   unchanged while separate immutable evidence records reference its identity.
3. **Given** two distinct attachment names, **When** the same or different pairs are attached to one
   caller model, **Then** their blocks and diagnostics remain isolated.
4. **Given** a duplicate or conflicting namespace, incomplete mapping, unknown extra mapping,
   foreign-model variable, incompatible domain, or ineligible artifact, **When** attachment is
   attempted, **Then** it fails before leaving any partial component on the model.
5. **Given** an existing OEL whole-model caller, **When** the composable capability is added,
   **Then** the existing entry point retains its compatibility behavior and is not silently routed
   through a different public contract.

---

### User Story 6 - Review the Composition Boundary Offline (Priority: P3)

As a researcher reviewing OEL, I need a small self-contained notebook demonstrating how conditional
risk moves from a fitted artifact into a caller-owned model so that I can understand the contract
without reading compiler internals.

**Why this priority**: The notebook is explanatory evidence for a boundary that is otherwise hard to
inspect. Automated tests and persisted parity evidence remain authoritative.

**Independent Test**: Execute the output-free notebook from top to bottom in the locked offline CPU
environment and verify that it calls only reviewed public behavior while presenting continuous,
binary, and categorical mappings under max and PWL.

**Acceptance Scenarios**:

1. **Given** installed dependencies and reviewed local fixtures, **When** the notebook executes
   without network access, **Then** it explains and demonstrates numerator, denominator,
   conditional log-risk, caller-owned attachment, and fixed-assignment evaluation.
2. **Given** max and PWL examples, **When** their results are presented, **Then** embedding/solver
   parity and native/compiler fidelity are labelled as different comparisons.
3. **Given** the notebook source, **When** it is reviewed, **Then** it contains no compiler
   implementation, adaptive fitting, benchmark optimization, Cartesian enumeration, hand-edited
   quantitative results, or stored cell outputs.

### Edge Cases

- The event target is absent, not binary, mapped to an undeclared value, retained as a decision, or
  accompanied by a second event target.
- A feature is omitted from both the retained-decision set and the fixed marginalization contract,
  or a context-like feature is supplied as extra fixed evidence.
- The numerator and denominator refer to different fitted artifacts, model digests, event meanings,
  decision orderings, approximation domains, or Sum-encoding configurations.
- A current artifact is incomplete, corrupt, missing its current-SPFlow payload, or lacks declared
  U-Bounds semantics; a legacy-inferred artifact must not be promoted to eligibility.
- A continuous approximation domain is missing when required, empty, reversed, nonfinite, or
  outside its declared decision domain.
- A caller expression lies exactly on an inclusive approximation boundary or one representable
  step outside it.
- A continuous mapping is constant, affine over several continuous variables, nonlinear, or
  contains an unfixed parameter or a general integer decision variable.
- A mapping omits a retained decision, includes an unknown feature, maps one feature twice, or uses
  a variable belonging to another model.
- A binary variable uses the expected solver domain but its declared feature values are not numeric
  zero and one; persisted declared ordering remains authoritative.
- A categorical mapping omits a category, duplicates an indicator, changes category order, uses a
  nonbinary indicator, or contains indicators that already participate in caller constraints.
- An attachment name is invalid, already occupied by an OEL attachment, or conflicts with an
  unrelated caller-owned component.
- Validation succeeds but component creation encounters an unexpected failure; no partial
  attachment may remain.
- Direct evaluation or attached evaluation produces a nonfinite root, difference, residual, or
  derived probability.
- The conditional log-risk is slightly positive but no greater than $10^{-6}$, materially positive,
  or sufficiently negative that exponentiation underflows for a diagnostic probability.
- The selected max encoding has no existing query-specific selectivity certificate and therefore
  must remain labelled approximate and uncertified.
- The selected PWL configuration is incomplete or cannot reproduce the compiled node semantics
  during direct evaluation.
- The required open solver, current-SPFlow backend, or notebook dependency is unavailable in the
  validation environment.

## Requirements *(mandatory)*

### Functional Requirements

#### Conditional meaning

- **FR-001**: The feature MUST compile exactly one explicitly declared binary event target and one
  explicitly declared event value per conditional pair. The event target MUST be distinct from the
  retained decision set.
- **FR-002**: For retained decisions $X=x$, the numerator MUST represent the selected compiled
  semantics for $\log p_{X,Y}(x,y)$, where $y$ is the declared event value.
- **FR-003**: For the same retained decisions, the denominator MUST represent the selected compiled
  semantics for $\log p_X(x)$ from the same fitted artifact.
- **FR-004**: The numerator MUST fix the event target to the declared value and marginalize every
  other nondecision feature. The denominator MUST additionally marginalize the event target.
- **FR-005**: Every nonevent feature not retained as a decision, including context-like features,
  MUST be marginalized in both circuits. The feature MUST reject extra fixed contextual evidence.
- **FR-006**: Continuous-decision joint and marginal quantities MUST be documented and reported as
  densities rather than point probabilities.
- **FR-007**: The pair MUST expose the raw conditional log-risk
  $z_{\mathrm{num}}-z_{\mathrm{den}}$ and MAY derive its conditional probability by exponentiation.
  Neither value may be clamped to conceal invalid compiled behavior.
- **FR-008**: The denominator MUST always be compiled and retained. The feature MUST NOT assume
  uniform decision density, accept a caller-supplied denominator constant, or infer constancy from
  the intended sampling design.
- **FR-009**: The capability MUST NOT enumerate decision assignments, issue native queries as a
  substitute for symbolic composition, or create a Cartesian risk table.

#### Compilation, identity, and compatibility

- **FR-010**: Compilation MUST consume one persisted fitted artifact, the declared event target and
  value, retained decision features, fixed marginalization semantics, selected max or PWL
  configuration, and every required approximation domain.
- **FR-011**: Compilation MUST produce one solver-neutral, serializable pair that contains both
  circuits and enough information for direct evaluation, later attachment, validation, and audit.
- **FR-012**: Compilation MUST NOT fit, refit, or alter the source SPN.
- **FR-013**: The composable path MUST accept only a current fitted artifact with declared U-Bounds
  semantics and a valid current-SPFlow payload.
- **FR-014**: Legacy-inferred artifacts MUST remain available only through their existing
  compatibility paths and MUST NOT be silently promoted, migrated, rewritten, or assigned new
  conditional-pair claims.
- **FR-015**: The pair MUST retain the fitted-artifact identity and model digest; event target and
  value; retained and marginalized feature identities; approximation domains; resolved encoding
  configuration; compiler and record versions; numerical tolerances; and all other inputs that
  change its mathematical meaning. Retained decision identity and ordering, each approximation
  domain's declared source, and the encoding it qualifies MUST remain explicit.
- **FR-016**: Persisting and reloading a pair MUST preserve its identity and all evidence-defining
  semantics. Changing any defining input MUST create a distinguishable identity and MUST NOT
  overwrite an existing pair. Once published, the pair MUST remain immutable; direct evaluation,
  attachment, parity, and fidelity checks MUST NOT append results to or otherwise revise it.
- **FR-017**: Existing OEL whole-model entry points MUST retain their compatibility behavior and MUST
  NOT be silently redefined as the new composable path.
- **FR-018**: Conditional-pair persistence MUST remain focused on this compiler capability rather
  than becoming a generalized artifact framework.

#### Attachment and decision ownership

- **FR-019**: Attachment MUST consume an already-compiled pair, one existing caller-owned Pyomo
  model, a complete decision mapping, and a caller-selected unique namespace.
- **FR-020**: Attachment MUST use the supplied pair unchanged and MUST NOT refit, recompile, mutate,
  strengthen, or silently resolve a different encoding configuration.
- **FR-021**: The same compiled pair MUST be usable by direct evaluation, fixed-assignment parity,
  and later unfixed caller optimization.
- **FR-022**: One attachment namespace MUST be represented by one Pyomo Block containing the
  numerator circuit, denominator circuit, compiler auxiliaries, physical-to-model-coordinate links,
  and required categorical exactly-one relationships.
- **FR-023**: The attachment result MUST expose the created namespace, numerator root, denominator
  root, conditional log-risk difference, decision links, pair metadata, and relevant diagnostics.
- **FR-024**: OEL MUST reference rather than recreate caller-owned primary decision variables.
- **FR-025**: OEL MUST NOT add a substantive objective, chance threshold, chance constraint, or
  solver invocation. The caller owns each of those choices.
- **FR-026**: Distinct namespaces MUST permit multiple conditional attachments in one caller model.
  A duplicate or conflicting namespace MUST fail without leaving partial components.
- **FR-027**: All pair, namespace, mapping, expression, variable-domain, category-coverage,
  approximation-domain, and model-ownership checks MUST complete before attachment mutates the
  caller model.
- **FR-028**: The decision mapping MUST cover every retained decision feature exactly once and MUST
  reject missing, duplicate, or unknown extra entries. One pair and mapping MUST support any mixture
  of the continuous, binary, and categorical decision forms defined below.
- **FR-029**: Every mapped variable MUST belong to the caller's model. Fixed caller variables MUST
  remain acceptable for diagnostic parity.

#### Supported mappings

- **FR-030**: A retained continuous decision MUST accept one scalar caller-owned Pyomo variable or
  affine expression in physical units containing only continuous variables and fixed parameters.
- **FR-031**: Continuous mapping MUST reject nonlinear expressions and general integer variables,
  including integer variables hidden in an otherwise affine expression.
- **FR-032**: Continuous mapping MUST use persisted U-Bounds normalization meaning to create the
  physical-to-model-coordinate relationship.
- **FR-033**: When the selected compiler treatment requires a finite approximation domain, its
  authoritative interval MUST be declared in physical units, its derived model-coordinate interval
  and declared source MUST remain traceable, and the attachment MUST enforce its exact closed
  inclusive boundaries without clamping, widening, or extrapolating the caller expression.
- **FR-034**: A retained binary decision MUST accept a caller-owned Pyomo binary variable and MUST
  interpret its states through the artifact's declared two-value ordering.
- **FR-035**: A retained categorical decision MUST accept one caller-owned Pyomo binary indicator
  for every declared category in persisted order and MUST add the exactly-one relationship inside
  the attachment namespace.
- **FR-036**: Categorical composition MUST remain symbolic and MUST NOT enumerate the Cartesian
  product of decision values. Mixed-type composition MUST preserve one joint numerator,
  denominator, and conditional log-risk rather than creating type-specific pairs.
- **FR-037**: General integer features and integer-specific decision composition MUST be rejected
  with a clear diagnostic.

#### Encoding and numerical evaluation

- **FR-038**: The conditional pair MUST support both existing max and configurable PWL Sum
  encodings, selected explicitly by the caller without silent fallback.
- **FR-039**: One resolved encoding policy MUST apply consistently to both numerator and
  denominator, and the pair MUST retain its complete resolved configuration and derived node data.
- **FR-040**: The feature MUST reuse existing max and PWL compiler mathematics and MUST NOT add
  adaptive breakpoint selection, configuration sweeps, or unrecorded defaults.
- **FR-041**: Max MUST remain labelled approximate and uncertified unless the consumed compiler
  already provides valid query-specific selectivity certification. This feature MUST NOT create a
  new certification method.
- **FR-042**: PWL MUST remain labelled as an approximation of weighted log-sum-exp.
- **FR-043**: Direct numerical evaluation MUST execute the selected compiled max or PWL semantics
  exactly and MUST NOT substitute native or exact log-sum-exp evaluation. It MUST accept exactly one
  explicit, complete assignment mode per evaluation: declared-domain values transformed through
  the pair's persisted feature semantics, or already-derived model-coordinate values. In the
  declared-domain mode, continuous values use physical units and binary or categorical values use
  their declared values. Declared-domain assignments are the normal researcher-facing mode;
  missing, extra, mixed, or simultaneously supplied modes MUST be rejected.
- **FR-044**: Domain-membership checks MUST preserve U-Bounds' exact closed-bound behavior and MUST
  NOT reuse the solver-parity tolerance as a domain tolerance.
- **FR-045**: Fixed-assignment roots and their conditional log-risk difference MUST agree with
  direct compiled evaluation within an absolute tolerance of $10^{-6}$. Every reported constraint
  residual MUST have absolute value no greater than $10^{-6}$.
- **FR-046**: A compiled conditional log-risk greater than $10^{-6}$ MUST be rejected as invalid. A
  smaller positive value MUST remain visible and be classified as numerical noise rather than
  clamped.
- **FR-047**: A nonfinite root, log-risk difference, residual, or derived probability MUST be an
  operational failure.
- **FR-048**: Every numerical tolerance MUST be persisted with the pair or parity evidence according
  to its declared purpose.

#### Parity, evidence, and demonstration

- **FR-049**: Fixed-assignment embedding/solver parity MUST compare attached-model numerator,
  denominator, difference, and residuals with direct evaluation of the identical compiled pair.
  A mismatch beyond tolerance MUST be an operational failure. Results MUST be retained in one or
  more separate immutable evidence records that reference the unchanged pair identity.
- **FR-050**: Compiler fidelity MUST separately compare direct compiled numerator, denominator,
  conditional log-risk, and probability with native current-SPFlow results from the source artifact.
  Its results MUST remain outside the conditional pair in immutable evidence that references the
  pair identity.
- **FR-051**: Compiler-fidelity evidence MUST retain numerator log error, denominator log error,
  conditional-log-risk error, and probability difference without imposing an accuracy or adequacy
  gate.
- **FR-052**: Required integration evidence MUST include one real current-SPFlow continuous case
  with deliberately nonuniform decision evidence under both max and PWL, covering boundary and
  interior assignments.
- **FR-053**: Required integration evidence MUST include one real current-SPFlow discrete case
  covering both binary states and representative categorical values without a full Cartesian grid.
  At least one required integration case MUST retain decisions from more than one supported type in
  the same conditional pair.
- **FR-054**: A fixed-assignment harness MUST use Pyomo with the open CPU HiGHS path, expose solver
  status and residuals, and contain no substantive optimization objective. A constant zero
  objective MAY be supplied only when required for solver evaluation.
- **FR-055**: A small consumer-owned model MUST demonstrate that unrelated caller objectives and
  deterministic constraints can use the returned conditional log-risk without copying OEL
  internals.
- **FR-056**: Deterministic tests MUST cover pair identity and serialization; invalid and mismatched
  artifacts; incomplete, duplicate, and extra mappings; variable ownership; nonlinear and integer
  expressions; invalid domains; namespace collisions; atomic failure; and numerical failures.
- **FR-057**: At least one required validation path MUST fit, persist, reload, natively query,
  compile, directly evaluate, attach, and fixed-assignment evaluate a real current-SPFlow artifact.
  Production evidence MUST NOT silently fall back to empirical replay or metadata-only behavior.
- **FR-058**: One thin, output-free notebook MUST use reviewed fixtures and public OEL behavior to
  explain the numerator, denominator, and log-risk; demonstrate caller-owned attachment; exercise
  max and PWL fixed assignments; and show continuous, binary, and categorical mappings.
- **FR-059**: The notebook MUST distinguish embedding/solver parity from native/compiler fidelity,
  MUST contain no compiler implementation or hand-edited result, and MUST NOT perform adaptive
  fitting, benchmark optimization, or Cartesian decision enumeration.
- **FR-060**: The notebook and required validation workflow MUST run offline after dependency
  installation on CPU with HiGHS and MUST be executable headlessly through the locked project
  `uv` environment.
- **FR-061**: Current-SPFlow, model-composition, solver, and notebook dependencies MUST remain lazy
  or optional at the core import boundary. Their absence in a required validation environment MUST
  produce a clear failure rather than silent fallback.

### Key Entities

- **Conditional pair**: A versioned, solver-neutral record containing one compiled event numerator
  and its matching marginal denominator, their shared identity and provenance, retained and
  marginalized feature meanings, validity domains, selected Sum-encoding semantics, and numerical
  policies. It is immutable once published.
- **Conditional event declaration**: The one binary target feature and one declared target value
  fixed in the numerator and marginalized in the denominator.
- **Retained decision set**: The complete ordered set of artifact features that remain symbolic in
  both circuits and therefore require caller-owned mappings; it may contain any supported mixture of
  continuous, binary, and categorical features.
- **Decision mapping**: The exact association between every retained feature and a caller-owned
  continuous affine expression, binary variable, or ordered categorical one-hot vector.
- **Conditional attachment**: One namespaced model component that references caller decisions and
  owns only compiled circuits, auxiliaries, validity relationships, coordinate links, and returned
  diagnostics.
- **Direct compiled evaluation**: Numerical execution of the exact selected max or PWL circuit
  semantics without constructing or solving an attached decision model, using one explicitly
  selected complete assignment in declared-domain values or model coordinates.
- **Evaluation evidence record**: An immutable result that references one published conditional-pair
  identity and retains the evaluation-defining assignments, comparison kind, diagnostics, and
  results without modifying the pair.
- **Embedding/solver parity evidence**: Fixed-assignment comparison of attached roots and residuals
  against direct evaluation of the identical compiled pair.
- **Compiler-fidelity evidence**: Separate comparison of direct compiled outputs with native
  current-SPFlow numerator, denominator, conditional log-risk, and probability values.

### Dependency and Environment Requirements

- **Core dependencies**: No new unconditional heavyweight dependency. Existing lightweight OEL
  artifact, domain, compiler-record, and serialization behavior remains available at the core
  boundary.
- **Optional dependencies**: Current SPFlow for real fitting and native queries; Pyomo and HiGHS for
  attachment parity; notebook tooling for the demonstration. These dependencies remain behind lazy
  research and validation boundaries.
- **External services**: None. Required tests and notebook execution use reviewed local fixtures and
  require no network access after dependencies are installed.
- **Hardware assumptions**: Routine evidence runs on CPU. No accelerator, distributed execution,
  commercial solver, or license service is required.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every eligible source artifact and valid request, researchers receive exactly one
  reusable pair containing one event numerator and its matching explicit denominator, and a
  persist/reload round trip preserves every evidence-defining field and identity. Subsequent
  evaluations leave the pair unchanged and publish their results separately by pair identity.
- **SC-002**: At every declared fixed-assignment parity case, both attached roots, their conditional
  log-risk difference agree with direct evaluation of the identical compiled pair within absolute
  tolerance $10^{-6}$, and every applicable constraint residual has absolute value no greater than
  $10^{-6}$.
- **SC-003**: Required evidence successfully exercises both supported Sum encodings, continuous
  boundary and interior assignments, both binary states, and representative categorical values
  without constructing a Cartesian decision table, and at least one case composes more than one
  supported decision type in a single pair.
- **SC-004**: Every compiler-fidelity case reports all four required discrepancies—numerator log,
  denominator log, conditional log-risk, and conditional probability—and no case is rejected solely
  for failing an unestablished native-versus-compiled adequacy threshold.
- **SC-005**: Every tested invalid artifact, mapping, expression, domain, or namespace request leaves
  the caller model with exactly the component structure it had before the rejected attachment.
- **SC-006**: A caller can add and evaluate at least one unrelated deterministic constraint and one
  caller-owned objective around the returned conditional log-risk without OEL creating or replacing
  either one.
- **SC-007**: The demonstration notebook executes headlessly from first cell to last in the locked,
  offline CPU environment, contains no stored outputs or duplicate compiler implementation, and
  presents all three supported decision-mapping forms.
- **SC-008**: Existing whole-model callers and artifacts continue through their established
  compatibility paths, and the core library remains importable when optional fitting, composition,
  solver, and notebook dependencies are absent.

## Assumptions

- U-Bounds is complete and provides authoritative decision domains, discrete value ordering,
  normalization meaning, training-support provenance, and approximation-domain semantics.
- The current fitted-artifact format can distinguish declared-domain artifacts with valid
  current-SPFlow payloads from legacy-inferred artifacts.
- Existing max and PWL compiler mathematics and supported SPN node treatments are the behavior to
  compose and validate; their scientific redesign or tuning is not part of this feature.
- One binary event target and value is sufficient for the scalar and planned first optimization
  uses. Arbitrary conjunctions, ranges, multiple targets, and additional fixed context will be
  specified only when a concrete benchmark establishes their need.
- Caller-owned categorical choices are represented by complete ordered one-hot binary vectors.
  General integer feature composition is deferred to a separate benchmark-driven capability.
- The caller supplies unique attachment names and retains ownership of all primary decisions,
  objectives, deterministic constraints, thresholds, chance constraints, and solver calls.
- Required fixtures remain intentionally small and deterministic. Exact sample counts and parity
  grid sizes are planning choices and are not scientific requirements.
- Max and PWL approximation quality is retained as compiler-fidelity evidence; selection and
  scientific qualification of their configurations belongs to the later scalar compiler feature.
- Required evidence can be produced with current SPFlow and an open CPU solver without network
  access, commercial licenses, or accelerator hardware after dependencies are installed.
- All reusable implementation and validation work remains in OEL. Recording the completed OEL
  revision in the parent paper repository is a separate later gitlink change.

## Out of Scope

- Benchmark objectives, capacity or budget constraints, operational risk thresholds, and selection
  of optimized decisions
- Figure 1 reproduction or scientific qualification of scalar max and PWL configurations
- Cartesian decision enumeration, risk-table precomputation, or one native query per candidate
- Arbitrary event conjunctions, event ranges, multiple event targets, or a general conditional-
  evidence language
- Fixed weather, time, scenario, or other contextual evidence
- General integer feature composition or integer-specific decision linking
- An all-purpose caller-model builder or replacement of existing whole-model entry points
- New SPN modeling experiments, adaptive fitting, or model selection
- New approximation mathematics, breakpoint search, configuration sweeps, or selectivity
  certification
- Large parity grids, prescribed fixture sample counts, reusable solver-option bundles, retry or
  scheduling machinery, and generalized artifact infrastructure
- Commercial solvers, GPU execution, distributed execution, or device-selection behavior
- Changes to the parent paper repository or its OEL gitlink
