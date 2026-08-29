# Research: Composable Conditional MIO Embedding

## Dedicated conditional-pair record

**Decision**: Introduce a separate `conditional-pair-v1` record kind and compiler version instead of
changing `TPMArtifact` schema v3 or the existing compiled-v1/v2 payload contracts. Keep import-light
records, canonical identity, loading, and create-only persistence in a focused TPM module.

**Rationale**: A fitted artifact, a one-graph compiler payload, and a reusable conditional pair have
different meanings and lifecycles. `TPMArtifact` owns fitted-model identity and its verified sidecar;
the pair is derived evidence containing two conditioned circuits and one selected encoding. A
separate schema prevents derived compiler claims from being written back into the source artifact
and avoids another ambiguous use of the labels v2/v3. Existing fitted-artifact and compiler loaders
can remain unchanged.

**Alternatives considered**:

- Add conditional fields to `TPMArtifact` v4: rejected because compilation must not mutate or
  strengthen a fitted model.
- Call the pair compiled-v3: rejected because it contains two circuits and a composition contract,
  not the next version of the existing single-graph payload.
- Store a loosely typed mapping only: rejected because strict round-trip validation, immutability,
  and identity verification are acceptance requirements.

## Eligible source artifact

**Decision**: The pair compiler accepts an artifact manifest path or a `TPMArtifact` previously
loaded from a path, requires `schema_version == "v3"`, production execution, current-SPFlow 1.1,
`spflow-model-sidecar`, a verified sidecar with a real model, and no feature whose mathematical
domain was omitted or whose normalization is legacy-inferred. Caller-declared unknown support is
still distinct from omitted legacy inference and may be marginalized; retained continuous
decisions must additionally have finite declared decision domains and explicit approximation
intervals.

**Rationale**: Feature 014 made schema v3 capable of recording declared, omitted, and legacy-inferred
meaning separately. This feature may consume explicit U-Bounds semantics but must not promote an
observed range. Requiring a persisted source path ensures the existing sidecar digest verification
actually runs. Retained discrete decisions need complete declared ordering, and the internally exact
binary event target remains eligible.

**Alternatives considered**:

- Accept an arbitrary in-memory artifact mapping: rejected because it cannot prove persisted
  current-SPFlow payload integrity.
- Accept schema v2 plus caller-supplied intervals: rejected because an approximation interval cannot
  create missing mathematical meaning.
- Reject caller-declared unknown marginalized support: rejected because explicit unknown is a valid
  U-Bounds state and the feature does not condition on that feature.

## One verified graph, then two circuits

**Decision**: Load the model from the verified source sidecar, retain the ordered decision features
and event target, structurally marginalize every other feature, compile the retained graph once,
then derive numerator and denominator circuits from that one compiled graph. The numerator fixes
the requested event value by its declared binary ordering index; the denominator marginalizes the
event. Both circuits share one base-graph digest, validity set, and encoding policy.

**Rationale**: The current production sidecar stores the fitted model but not reusable conditional
models. The existing planning path already demonstrates marginalize-before-compile followed by a
serialized conditioning transform. Generalizing that behavior inside TPM provides the required
common origin and avoids issuing native queries or compiling two independently configured graphs.
It also removes the current planning transform's hard-coded event state `1`.

**Alternatives considered**:

- Compile numerator and denominator independently: rejected because settings or graph traversal
  could drift and shared provenance would be weaker.
- Depend on `build_spn_mip_payload`: rejected because ordinary current-SPFlow production sidecars do
  not contain its expected pre-serialized `conditional_models`.
- Enumerate decision assignments and query the SPN: rejected by the feature purpose and scope.

## Exact marginalization before approximation

**Decision**: Add an explicit constant-log node representing log-one and simplify conditioned
subcircuits before max/PWL encoding. A fully marginalized leaf becomes constant zero in log space;
a Product drops zero constants and becomes zero if no children remain; a Sum whose children all
simplify to log-one becomes log-one exactly rather than passing through max or PWL.

**Rationale**: Marginalizing a normalized subtree must return probability one, hence log value zero.
If a fully marginalized Sum is left in the graph, max would produce `max(log(weight_i))` rather than
zero and PWL could add approximation error to a quantity known exactly. That would corrupt the
denominator solely because of the selected encoding. Simplification keeps marginalization exact
while applying approximation only to subcircuits that still depend on retained evidence.

**Alternatives considered**:

- Preserve every Sum after replacing leaves with neutral leaves: rejected because it is wrong under
  max and needlessly approximate under PWL.
- Marginalize only at native-SPFlow level and compile numerator/denominator separately: rejected
  because SPFlow exposes structural marginalization but no general persistent conditioning API for
  an arbitrary event value.

## Resolved leaf and Sum encoding policy

**Decision**: Require one explicit compilation request that contains leaf-curve options,
approximation domains, a complete max or PWL Sum policy, and tolerances. Persist the compiler's
resolved leaf breakpoints and validity, the selected Sum mode, maximum Sum arity, PWL exp/log curves
when used, MIO epsilon, max big-M, exp-domain floor, compiler/schema/backend versions, and the
approximation/certification labels. Apply the same resolved policy to both circuits with no fallback.

**Rationale**: Existing compilation has two layers: piecewise Normal log-density curves are produced
by `compile_spflow_model_to_mio`, while max/PWL weighted-log-sum-exp is selected later by the Pyomo
encoder. Hidden constants such as `_SUM_BIG_M` and the exponential floor affect feasibility and
parity and therefore belong in the pair's resolved semantic record. The pair must be sufficient to
reproduce direct and attached execution without reading mutable defaults.

**Alternatives considered**:

- Silently inherit the fitted artifact's approximation metadata: rejected because compilation is a
  separate request and the caller must select max or PWL explicitly.
- Store only `mode = "max"` or `"piecewise"`: rejected because two PWL configurations could then
  share an identity despite different semantics.
- Add breakpoint tuning or certification: rejected as later scientific qualification work.

## Pair and source-model identity

**Decision**: Compute a source-model digest from the canonical compiled base graph and its resolved
feature/compiler context, retain the fitted artifact ID and sidecar SHA-256 separately, and compute
`pair_id` as SHA-256 over canonical finite JSON of every semantic pair field except `pair_id`,
creation time, and output location. Nested stored values are recursively immutable; `to_dict()`
returns detached copies. Loading recomputes both graph and pair identities.

**Rationale**: The sidecar hash proves exact persisted bytes but is broader than the model snapshot
consumed by the compiler. A base-graph digest identifies the exact graph/parameters from which both
circuits came, while pair identity distinguishes event value, decision order, validity, encodings,
and tolerances. Excluding wall-clock and path metadata makes identity reproducible.

**Alternatives considered**:

- Use only `artifact_id`: rejected because identifiers need not prove model bytes or compiler input.
- Use only sidecar SHA-256: rejected because it does not identify the resolved compilation semantics.
- Trust `frozen=True` with nested dictionaries: rejected because dataclass freezing alone is shallow.

## Immutable publication

**Decision**: Serialize pair and evidence records as canonical JSON with sorted keys, compact
separators, UTF-8, one terminal newline, and `allow_nan=False`. Publish through a flushed and
fsynced same-directory temporary file plus an atomic no-replace operation such as a hard link; do
not use `os.replace` for the final create-only step. An absent target is created; an existing
byte- and identity-identical record is verified and reused; any incomplete or conflicting target
fails and is never overwritten. A target that appears concurrently is validated under the same
rule.

**Rationale**: Existing TPM artifact writing is atomic but overwrites its target, which is suitable
for fitted artifacts but not for immutable pair/evidence publication. The focused create-or-verify
rule supplies auditable reuse without introducing registries, aliases, databases, or generalized
artifact infrastructure.

**Alternatives considered**:

- Always overwrite an existing path: rejected because changed scientific inputs must preserve prior
  evidence.
- Timestamped append-only directories and a registry: rejected as unnecessary generalized
  infrastructure.

## Exact selected-semantics direct evaluation

**Decision**: Add a raw log evaluator for the conditioned circuit format. Continuous and discrete
leaves use the persisted compiled values, Products sum child logs, constant nodes return their exact
log value, max Sums return the maximum weighted child log, and PWL Sums reproduce the attached
max-shift, exp interpolation, total, log interpolation, and final addition using the persisted
curves. Interpolation checks its domain and fails rather than using the existing clamping helper
outside endpoints.

**Rationale**: `evaluate_compiled_spflow_probability` and the categorical evaluator currently use
exact weighted log-sum-exp. Those are useful compiler-fidelity references but are not valid
embedding-parity references for approximate max/PWL circuits. Direct evaluation must execute the
same approximation as Pyomo or a solver mismatch could be misclassified.

**Alternatives considered**:

- Reuse exact log-sum-exp and compare it with Pyomo: rejected because the difference would include
  compiler approximation error.
- Clamp PWL arguments to table endpoints: rejected because the attached model enforces explicit
  domains and does not silently reinterpret out-of-domain evaluations.

## Direct assignment modes

**Decision**: Public direct evaluation accepts a complete mapping of retained decision names and one
explicit mode: `declared-domain` or `model-coordinate`. Declared-domain mode uses physical units for
continuous values and persisted declared labels for binary/categorical values. Model-coordinate
mode uses finite continuous coordinates and exact ordered integer indices for discrete features.
Missing, extra, mixed, or simultaneous modes fail. Declared-domain mode is the documented normal
path.

**Rationale**: Named complete mappings keep feature identity visible and avoid the existing
full-schema positional sequence convention. The two modes satisfy both researcher use and internal
parity without allowing ambiguous mixed coordinates.

**Alternatives considered**:

- Accept partial assignments and marginalize at evaluation time: rejected because the published
  pair already fixes its retained symbolic scope.
- Accept one-hot arrays in direct evaluation: rejected because one-hot is a Pyomo composition form,
  not the declared value of a categorical feature.

## Raw numerical policy

**Decision**: Return numerator log, denominator log, raw difference, un-clamped exponential, and a
classification. A finite difference in `(0, 1e-6]` is visible as `numerical-noise`; a difference
greater than `1e-6` raises an operational numerical error carrying the raw evaluation; nonfinite
roots, difference, probability, or residuals also fail. Domain membership remains exact and does
not reuse the parity tolerance.

**Rationale**: The user needs the raw value for diagnosis, while a materially positive conditional
log-risk implies a conditional probability above one. Carrying the evaluation in the error preserves
evidence without clamping the result into apparent validity.

**Alternatives considered**:

- Apply `min(0, difference)` and clamp probability into `[0,1]`: rejected because current query and
  solution helpers do this and the feature explicitly forbids it.
- Treat every positive bit as failure: rejected because the agreed policy distinguishes bounded
  numerical noise at `1e-6`.

## Native raw-log evaluation

**Decision**: Add a public explicit-event native evaluator that consumes the pair, its matching
persisted source artifact, and complete declared-domain decision assignments. It verifies source
identity, builds one NaN evidence row, assigns decisions, evaluates the denominator, then assigns
the pair's declared event value and evaluates the numerator. It returns raw roots, difference, and
un-clamped probability without applying a compiler adequacy gate.

**Rationale**: The existing native query internally computes both roots but exposes a clamped
conditional probability and always selects the final binary ordering value. A focused raw helper is
needed for event value zero as well as one and for separate numerator/denominator fidelity evidence.

**Alternatives considered**:

- Call a private query helper from tests: rejected because the notebook and downstream research need
  reviewed public behavior.
- Reconstruct native values from compiled circuits: rejected because that would no longer be an
  independent compiler-fidelity reference.

## Typed caller-owned mappings

**Decision**: Accept an ordered sequence of typed mapping records so duplicate feature mappings are
detectable:

- continuous: feature name plus a caller-owned scalar Var or structurally affine expression;
- binary: feature name plus one caller-owned binary Var;
- categorical: feature name plus ordered `(declared category, caller-owned binary indicator)`
  entries.

The sequence must cover every retained feature once and no others. Continuous expressions must
reference at least one caller-owned continuous variable; fixed continuous variables are allowed,
but constant/fixed-parameter-only expressions, nonlinear structure, and any binary/general-integer
variable are rejected. Categorical labels and order must exactly match persisted ordering, and
indicators must be distinct.

**Rationale**: A dictionary cannot represent duplicate entries, and an unlabeled categorical vector
cannot reliably diagnose a reordered mapping. Requiring at least one variable keeps a retained
decision symbolic while fixed caller variables still support parity. The existing encoder can
consume these mappings through its scalar/indexed model-coordinate convention without recreating
primary decisions.

**Alternatives considered**:

- Accept a plain mapping keyed by feature name: rejected because duplicate mapping behavior would be
  untestable.
- Create OEL copies of binary/categorical variables: rejected because ownership and coupling would
  be ambiguous.
- Accept constant expressions as decisions: rejected because a retained decision mapping must refer
  to a caller-owned decision variable; fixed Vars already cover fixed-assignment use.

## Structural affine validation

**Decision**: Lazily inspect every Pyomo expression with fixed variables included, verify that all
variables belong to the caller model and are continuous, and determine polynomial structure without
temporarily unfixing or mutating caller variables. Replace referenced variables only in an internal
expression clone or use an equivalent structural visitor so fixed nonlinear products remain degree
two and are rejected. Validate finite coefficients and constants.

**Rationale**: Pyomo's ordinary polynomial-degree and standard-representation utilities fold fixed
variables into constants. A fixed `x*x` can therefore appear degree zero, and `fixed_x*y` can appear
degree one, even though their structure is nonlinear when used as a decision mapping. Validation
must not trust that simplified degree and must never unfix caller variables.

**Alternatives considered**:

- Use `expr.polynomial_degree()` directly: rejected because it misses fixed nonlinear structure.
- Temporarily unfix caller variables: rejected because preflight must not mutate the caller model.

## Atomic namespaced attachment

**Decision**: Complete pair, namespace, mapping, domain, expression, category, and ownership
validation first. Build one detached concrete Pyomo `Block` containing shared coordinate links,
physical/model validity constraints, categorical exactly-one constraints, numerator and denominator
subblocks, and a named conditional-log-risk `Expression`. After successful construction, call
`model.add_component(namespace, block)` once. If that final operation reports an exception after
attaching this exact block, remove only that block. Return a frozen attachment result; add no
probability expression, objective, alpha, chance constraint, or solver call.

**Rationale**: Existing whole-model assembly attaches components incrementally and creates caller
policy. A detached block makes all compiler/encoding failures non-mutating and one final add makes
namespace ownership auditable. Diagnostic probability is safely computed in Python after fixed
evaluation rather than adding a nonlinear exponential to the MIO.

**Alternatives considered**:

- Attach components as they are built and clean up on error: rejected because proving complete
  rollback across Pyomo internals is harder.
- Clone the caller model and return the clone: rejected because the feature must compose with the
  caller's actual decisions and constraints.
- Reuse the categorical Cartesian lookup: rejected because categorical composition must remain
  symbolic.

## Attachment-local diagnostics

**Decision**: Provide a post-solve inspection function that does not invoke a solver. It evaluates
the two roots and raw difference and walks active constraints only inside the attachment block.
Equality residual is absolute body-minus-bound; inequality residual is the nonnegative violation of
applicable lower/upper bounds, not slack. Return named residuals and their maximum. The caller or
test harness owns any zero objective, variable fixing, HiGHS invocation, and solver-status capture.

**Rationale**: Scanning only the attachment avoids attributing unrelated caller constraint problems
to OEL. Violation magnitude makes a satisfied inactive inequality report zero, which matches the
`1e-6` residual acceptance policy. Keeping solve invocation outside the attachment preserves caller
ownership.

**Alternatives considered**:

- Reuse existing `solve_spn_chance_model`: rejected because it expects an OEL-owned objective and
  chance constraint.
- Scan every caller-model constraint: rejected because parity evidence concerns the embedded pair,
  not the caller's independent formulation.

## Separate immutable parity and fidelity evidence

**Decision**: Publish two record kinds that reference an unchanged pair ID. Embedding-parity
evidence contains assignment, direct results, attached results, deltas, solver status/termination,
named attachment residuals, tolerance, and pass/fail. Compiler-fidelity evidence contains the same
assignment, direct compiled values, native values, the four required discrepancies, and no adequacy
status. Record identities are canonical SHA-256 values; pair files are byte-snapshotted before and
after evidence generation.

**Rationale**: The two comparisons answer different questions and use different acceptance rules.
Storing them outside the pair enforces the clarification that published compiler semantics are
immutable.

**Alternatives considered**:

- Append evaluation arrays to the pair: rejected because repeated use would mutate the published
  compiler object.
- One combined `parity_error` metric: rejected because it would conflate solver/embedding defects
  with expected compiler approximation error.

## Fixture and representative cases

**Decision**: Add one dedicated, reviewable mixed-type source fixture with a finite continuous
decision, binary decision, ordered categorical decision, unbounded continuous uncertainty, and
binary event. Deliberately skew the continuous decision evidence, observe every discrete value, use
one fixed fit seed and explicit small fit controls that produce genuine learned Sum nodes, and fail
fixture generation if both conditioned circuits do not retain a Sum. Compile max and PWL pairs from
that same artifact. For each encoding use exactly three non-Cartesian fixed assignments: lower
continuous boundary with binary state zero and the first category, one interior point with binary
state one and a second category, and the upper boundary with a representative third category.

**Rationale**: Existing committed current-SPFlow fixtures contain no learned Sum modules, so merely
changing an encoding label would not exercise max/PWL behavior. A trial using the current reviewed
mixed rows with explicit small-slice fitting produced several Sum modules in seconds, making a
small deterministic fixture feasible. Three cases per encoding cover both boundaries, an interior
point, both binary states, representative categories, mixed composition, and six bounded HiGHS
solves without a Cartesian grid.

**Alternatives considered**:

- Reuse `tpm_artifact_domains_v3.json` alone: rejected because its continuous evidence is evenly
  distributed and its fitted graph contains no Sum nodes.
- Hand-construct a Sum graph only: rejected as the sole evidence because at least one full real fit
  path is required.
- Evaluate all discrete combinations: rejected as prohibited enumeration.

## Notebook and CI

**Decision**: Add `examples/tpm_planning/conditional_mio_embedding_walkthrough.ipynb`. It loads the
reviewed fitted artifact, max/PWL pairs, and separate evidence through public TPM exports; attaches
the pairs to caller-owned continuous, binary, and categorical decisions; performs representative
fixed-assignment HiGHS solves; distinguishes parity from fidelity; and constructs but does not solve
an unfixed caller policy example. The source remains output-free and contains no fit, regeneration,
compiler math, grid, or hand-edited results. Add a required Python-3.11 notebook CI job using the
existing notebook group; keep library and solver tests in the current Python 3.11-3.14 backend job.

**Rationale**: The notebook is a required explanation of the composition boundary, but notebook
packages need not be installed four times across the backend matrix. Existing source and headless
execution tests already provide a proven pattern for output-free notebooks, blocked network calls,
and byte preservation.

**Alternatives considered**:

- Let the notebook refit the SPN: rejected because the notebook must be thin and fast and committed
  fixtures already own authoritative evidence.
- Make `pytest.importorskip` the only notebook evidence: rejected because the specification requires
  a headless execution test, not a perpetual optional skip.
- Run the notebook on all four Python versions: rejected as redundant cost; the library behavior
  remains covered by the full matrix.
