# Composable Conditional MIO Embedding

Status: implemented by `016-conditional-mio-embedding`. This is an additive TPM compiler and
caller-model composition capability. It consumes declared-domain schema-v3 artifacts from Feature
014 and preserves the existing fitted-artifact, compiled-v1/v2, whole-model, and planning entry
points.

## Why a conditional pair is separate

A fitted TPM artifact describes one learned joint distribution. A conditional MIO pair is derived
compiler evidence with a different lifecycle: it fixes one binary event in a numerator, marginalizes
that event in a denominator, and applies one selected max or PWL approximation to both circuits.
OEL therefore persists it as a focused `conditional-pair-v1` record rather than strengthening the
source artifact, calling it an artifact v4, or treating it as a compiled-v3 whole model.

For retained decisions $X=x$ and declared event value $Y=1$, the roots mean

$$
z_{\mathrm{num}}(x) \approx \log p_{X,Y}(x,1)
$$

and

$$
z_{\mathrm{den}}(x) \approx \log p_X(x).
$$

For continuous decisions these are log densities, not point-probability logs. The optimization-facing
quantity is the raw difference

$$
z_{\mathrm{num}}(x)-z_{\mathrm{den}}(x) \approx \log P(Y=1\mid X=x).
$$

The denominator is always compiled from the same fitted SPN. Intended uniform decision sampling
does not permit replacing the learned marginal with a constant. Every nondecision, nonevent feature
is marginalized in both circuits; the event is fixed only in the numerator and marginalized in the
denominator.

## Source eligibility

Conditional compilation requires a persisted production schema-v3 artifact with:

- a verified current-SPFlow 1.1 model sidecar;
- explicit U-Bounds mathematical meaning rather than omitted or legacy-inferred meaning;
- one declared binary event target and one valid declared event value;
- complete ordered domains for retained binary and categorical decisions; and
- a finite declared decision domain plus an explicit finite approximation interval for every
  retained continuous decision.

Explicitly unknown or unbounded uncertainty may remain marginalized. A schema-v2 artifact remains
loadable through the established compatibility path but is ineligible here because observed extrema
cannot be promoted to mathematical or compiler validity. Compilation never refits, migrates,
rewrites, or repairs the source artifact.

## Pair lifecycle and public flow

The public TPM flow is deliberately staged:

1. Build a `TPMConditionalCompilationRequest` with the source path, event/value, ordered retained
   decisions, approximation domains, one explicit encoding, and purpose-labelled tolerances.
2. Call `compile_conditional_mio_pair` once. OEL verifies the source, structurally marginalizes
   unrelated features, compiles one retained graph, and derives both circuits from it.
3. Persist with `publish_conditional_pair`, or reload with `load_conditional_pair`. Publication is
   create-only or verify-identical; an existing conflict is never overwritten.
4. Call `evaluate_conditional_mio_pair` for solver-neutral execution of the exact persisted max or
   PWL semantics.
5. Call `attach_conditional_mio_pair` with an existing Pyomo model, complete typed mappings, and a
   unique namespace. Attachment reuses the pair without recompiling it.
6. After a caller-managed solve, call `inspect_conditional_mio_attachment` to read roots, raw risk,
   probability, solver metadata, and attachment-local residuals.
7. Build and publish embedding-parity and compiler-fidelity evidence separately.

Pair identity covers the source/model digests, event meaning, retained/marginalized features,
declared domains and normalization, approximation validity, encoding configuration, compiler/schema
versions, and numerical policy. Loading recomputes the identity and graph invariants. Changing any
defining input produces a distinguishable pair; evaluation and attachment do not mutate it.

## Direct evaluation

Direct evaluation is not a native-SPFlow query. It executes the selected compiled semantics exactly
as recorded: continuous/discrete leaves, Products, exact log-one marginalizations, and either max or
the persisted PWL weighted-log-sum-exp construction. This makes it the correct reference for Pyomo
embedding parity.

Assignments use exactly one complete mode:

- `declared-domain` accepts physical continuous values and declared binary/category labels; or
- `model-coordinate` accepts normalized continuous coordinates and declared discrete indices.

The evaluator enforces closed approximation validity and exact discrete domains. It does not clip,
extrapolate, fill missing assignments, clamp a probability, or fall back to empirical replay or
native evaluation.

## Caller-owned mappings

Attachment accepts one typed mapping for every retained decision and no unknown extras.

### Continuous

A continuous feature maps to a caller-owned scalar Pyomo variable or affine expression in physical
units. Fixed parameters, coefficients, constants, and fixed or unfixed continuous variables are
allowed. The expression must reference the target model and remain structurally affine; nonlinear
expressions, binaries, general integers, discrete domains, and foreign-model variables fail before
mutation. OEL creates the persisted U-Bounds physical-to-coordinate equality and closed
approximation-validity constraints without clamping the expression.

### Binary

A binary feature maps to one caller-owned Pyomo binary variable. Solver states zero and one are
interpreted through the pair's declared two-value ordering. A bounded integer or continuous
surrogate is not accepted.

### Categorical

A categorical feature maps to one caller-owned binary indicator per declared category, supplied in
the persisted category order. OEL validates labels, ordering, uniqueness, ownership, and binary
domains, then adds one exactly-one constraint inside its attachment block. It does not enumerate the
Cartesian product or precompute a risk table.

## Ownership and atomic attachment

The caller owns:

- every primary decision variable;
- deterministic constraints and operational coupling;
- the objective;
- $\alpha$ and the chance constraint;
- solver choice, options, invocation, and interpretation.

OEL owns one caller-named Pyomo Block containing numerator and denominator circuit blocks,
auxiliaries, coordinate links, validity constraints, and categorical exactly-one constraints. The
returned attachment exposes both roots and their symbolic difference, so a caller may add

$$
z_{\mathrm{num}}-z_{\mathrm{den}} \leq \log \alpha
$$

without accessing compiler internals.

Preflight validates the pair, namespace, complete mappings, expression structure, variable domains,
model ownership, category coverage, normalization, and approximation intervals before model
mutation. OEL builds a detached block and performs one final component addition. A failed final add
rolls back only that exact OEL component; caller-owned or concurrently added components are not
deleted. Distinct namespaces permit multiple attachments in one model.

## Max and PWL meaning

Both circuits use one fully resolved policy:

- `max` remains a visible, generally uncertified approximation of weighted log-sum-exp; and
- `piecewise` reproduces the persisted shift, exponential interpolation, sum, logarithm
  interpolation, and final addition.

There is no silent fallback between policies and no adaptive tuning in this feature. Leaf
breakpoints, Sum constants, big-M values, PWL curves, validity intervals, labels, and versions needed
to reproduce the selected semantics are part of the pair. Scientific qualification of settings
belongs to downstream compiler experiments.

## Numerical policy

Declared-domain membership retains Feature 014's closed, inclusive semantics. The persisted
acceptance tolerance is $10^{-6}$ for direct-versus-Pyomo numerator/denominator roots, conditional
log-risk, and attachment-local residuals. A conditional log-risk greater than $10^{-6}$ is invalid;
a smaller positive value remains visible as `positive-numerical-noise`. Roots, differences,
probabilities, and residuals must be finite. Raw values are not clamped.

## Parity and fidelity are different evidence

Embedding/solver parity compares an objective-free fixed Pyomo/HiGHS solve with direct execution of
the identical persisted pair. It is an operational acceptance gate: roots, log-risk, status, and
attachment-local residuals must pass the recorded tolerance.

Native/compiler fidelity compares direct compiled roots with independent current-SPFlow numerator
and denominator queries from the exact source artifact. It retains signed numerator, denominator,
conditional-log-risk, and probability differences with no adequacy verdict. A max or PWL
approximation may disagree with native SPFlow while embedding parity still passes; labeling that
difference a solver error would conflate two layers.

Both evidence record types have canonical identities and create-only publication. They reference
the immutable pair but do not alter it.

## Compatibility and limitations

Existing whole-model compilation, compiled-v1/v2 payloads, categorical lookup behavior, and
planning assembly remain independent compatibility paths. Feature 016 adds no second conditioner
and does not route those APIs through the conditional-pair record.

This capability intentionally does not provide:

- SPN fitting or artifact migration;
- multiple targets, arbitrary event conjunctions/ranges, or fixed contextual evidence;
- general integer feature linking;
- a caller model builder, objective, deterministic benchmark constraints, risk threshold, chance
  constraint, or solver call;
- Cartesian risk enumeration;
- max/PWL tuning, selectivity certification, or a compiled/native accuracy gate;
- a generalized artifact registry; or
- GPU/device selection, scheduler, retry, or commercial-solver policy.

The demonstration notebook is fixture-backed and explanatory. It solves only representative fixed
assignments for parity and leaves its caller-policy composition unsolved. Tests and persisted
evidence remain authoritative.

## Dependencies and validation

Pair records, identity, loading, direct evaluation, and package-root imports remain usable without
eagerly importing SPFlow, Torch, Pyomo, HiGHS, or notebook packages. Compilation and native queries
load current SPFlow lazily; attachment loads Pyomo lazily; required solver validation loads HiGHS;
the notebook execution test requires the locked notebook group. Missing boundary dependencies fail
clearly without fallback.

Run the full offline acceptance workflow from
`specs/016-conditional-mio-embedding/quickstart.md`. The core review commands include fixture
verification, focused and full TPM/planning tests, the Python 3.11 headless notebook contract,
package/import/no-legacy checks, `uv lock --check`, and repository/provenance inspection.
