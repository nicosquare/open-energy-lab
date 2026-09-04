# Composable Conditional MIO Embedding

Status: implemented by `016-conditional-mio-embedding`. This is an additive TPM compiler and
caller-model composition capability. It consumes declared-domain schema-v3 artifacts from Feature
014 and preserves the existing fitted-artifact, compiled-v1/v2, whole-model, and planning entry
points.

## Why a conditional pair is separate

A fitted TPM artifact describes one learned joint distribution. A conditional MIO pair is derived
compiler evidence with a different lifecycle: it fixes one binary event in a numerator, marginalizes
that event in a denominator, and applies one selected max or PWL approximation to both circuits.
OEL therefore persists it as a focused `conditional-pair-v2` record rather than strengthening the
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
6. For a fixed-assignment parity solve, optionally call
   `initialize_conditional_mio_attachment` after assigning the caller-owned decisions. It fills
   only attachment-owned auxiliaries so a supporting solver can validate the complete graph as a
   MIP start.
7. After a caller-managed solve, call `inspect_conditional_mio_attachment` to read roots, raw risk,
   probability, solver metadata, and attachment-local residuals.
8. Build and publish embedding-parity and compiler-fidelity evidence separately.

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

## Conditional-pair-v2 guarded exponential correction

`conditional-pair-v1` placed a zero-valued guard point at `-500` before the first positive
exponential point at $c=\log(10^{-3})$. Linear interpolation therefore created a small positive
ramp throughout `(-500, c)`, even though the intended guarded function was zero below the cutoff.
The older reference representation used a duplicated cutoff input to express a vertical jump;
that duplicate input is not a single-valued continuous PWL function and cannot be passed unchanged
to Pyomo's continuous `Piecewise` component.

Pair v2 replaces both ambiguous forms with one deterministic continuous policy:

- $B$ is the unchanged resolution-specific base PWL exponential curve;
- the output is exactly zero for $r\leq c$;
- the fixed transition width is $\delta=10^{-3}$ log-units;
- the segment from $(c,0)$ to $(c+\delta,B(c+\delta))$ is linear; and
- $B(r)$ is reproduced unchanged for every $r\geq c+\delta$.

The guard policy name, probability floor, $c$, boundary convention, $\delta$, transition end,
base points/values, and resolved strictly increasing, monotone table are persisted in pair identity.
Compilation, direct evaluation, and Pyomo attachment validate and consume that same resolved table.
The transition width is a versioned conformance constant; it is not fitted or tuned against native
SPFlow or downstream accuracy evidence.

The corrected runtime intentionally rejects every `conditional-pair-v1` record with guidance to
recompile its fitted artifact. It does not maintain dual evaluation semantics or reinterpret old
bytes. Existing production schema-v3 fitted SPNs remain valid inputs and can be recompiled into
distinguishable v2 max and PWL pairs. Historical v1 files remain useful as immutable rejection and
diagnostic evidence only.

## Objective-free attachment formulation in pair v2

Pair v2 also persists an immutable attachment-formulation record. OEL derives finite reachable
intervals bottom-up from persisted circuit values: leaves use their recorded log values, Products
sum child intervals, weighted Sum terms add $\log w_i$, maxima combine term intervals, and PWL Sum
records continue through relative inputs, guarded exponentials, totals, logarithms, and final node
outputs. Every floating-point arithmetic bound is rounded outward. The record contains each node's
output interval plus per-Sum term, maximum, relative, exponential, total, logarithm, output, and
branch-specific big-$M$ data.

The configured `sum_big_m=100` is a cap, not the coefficient placed on every branch. For branch
$i$, OEL persists and uses the outward-rounded value $M_i=U_m-L_{t_i}$. Compilation fails before
Pyomo mutation if a required value exceeds the cap. Attachment revalidates the pair identity and
derived formulation before constructing its detached block, then applies the finite bounds to node
outputs, maxima, relative inputs, exponential/logarithm auxiliaries, totals, and representation-owned
convex weights.

Five-point continuous leaf tables have four segments and use the persisted `DLOG` policy. Other
continuous leaf tables and all Sum exponential/logarithm tables use `DCC`. These representation
choices are identity-bearing and are never changed opportunistically during attachment.

The guarded exponential Piecewise input uses the versioned solver coordinate
$q=(r+500)/500$. The direct evaluator and persisted guarded curve remain in native log units; only
the solver-facing breakpoints are transformed to the unit interval, with identical output values.
This fallback was activated after the frozen scalar PWL cases were infeasible in native coordinates
even though a direct-derived assignment satisfied every unscaled equation within $10^{-6}$ (the
largest audited residual was $8.33\times10^{-16}$).

## Exact logarithm-table arity endpoint

The inherited logarithmic breakpoint calculation ended with
`exp(log(maximum_sum_arity))`. For exactly representable integer arities this round trip can land
one or more binary64 steps below or above the integer. In particular, arities 64, 96, and 128
previously resolved to `63.99999999999998`, `95.99999999999999`, and
`127.99999999999997`. The first and third values made the otherwise correct pre-mutation coverage
check reject a table whose intended closed domain reached the Sum arity.

The versioned `arity-log-table-endpoint-exactification-v1` policy preserves every legacy interior
breakpoint and replaces only the final logarithm input with the exact declared integer arity. The
corresponding logarithm output remains binary64-identical: applying `log` to either the legacy
round-trip endpoint or the exact integer produces the same stored value for the affected arities.
New conditional PWL pairs persist both the policy label and resolved arity in their identity-bearing
Sum configuration. Direct evaluation, formulation bounds, MIP initialization, and Pyomo attachment
therefore consume the same closed table; no adapter-side monkey patch is needed.

The correction changes no guarded-exponential point or value, no interior logarithm point, and no
logarithm value. Existing pair bytes remain immutable and load under their recorded v2 semantics;
newly compiled affected-arity pairs receive a distinguishable identity. Unit coverage exercises
resolutions 5, 9, and 17 over small and large arities, including 64, 96, and 128, and a real
conditional-pair construction test proves that a 64-child Sum persists and directly evaluates the
exact endpoint policy.

## Fixed-assignment MIP-start validation

Large objective-free attachments can make a MIP solver search blindly for thousands of deterministic
PWL branch choices. In the frozen scalar case, Gurobi 13.0.2 solved the numerator and denominator
circuits independently to machine precision, yet its default cut path declared their combined DCC
model infeasible. Disabling cuts eventually found the unchanged feasible solution, and supplying the
direct-derived values as a MIP start made Gurobi accept the full model without branch-and-bound.
This isolates a solver search/cut failure; it does not make the denominator circuit optional.

`initialize_conditional_mio_attachment` implements the deterministic fixed-assignment protocol. It
validates the complete assignment through the same direct evaluator, initializes the normalized
coordinate, node outputs, exact maximum choices, guarded-exponential/logarithm values, and persisted
DLOG/DCC representation auxiliaries, and returns the direct evaluation. It does not fix or alter any
caller-owned decision, change a bound, add an objective, remove either circuit, or deactivate a
constraint. A supporting solver must still be invoked with warm-start handling enabled and remains
responsible for accepting or rejecting every original equation.

This initializer is a parity and feasibility aid for known fixed assignments, not a replacement for
the caller's optimization objective or a proof that the unrestricted chance-constrained MIP will be
easy to solve. Variable-decision optimization still requires an independently suitable formulation,
solver configuration, and termination assessment.

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
