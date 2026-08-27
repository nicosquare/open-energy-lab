# Contract: Compiler Approximation Validity

“Model coordinate” means the output of the fitted feature's persisted normalization transform. It
is the compiler-facing name for the derived normalized coordinate in the feature specification;
under identity normalization it remains numerically in physical units.

## Request contract

A new compiled-v2 request consumes a v3 fitted artifact and supplies one explicit physical-unit
interval for every retained continuous feature treatment that requires finite approximation. Each
request identifies the feature, closed finite interval, caller source, and encoding it qualifies.
The interval must have positive width.

No interval is inferred from:

- observed training extrema;
- mathematical decision domain or distribution support;
- legacy bounds;
- a default model-coordinate `[0,1]`; or
- a global compiler range.

Selecting the entire decision domain is valid only when the caller explicitly supplies it.

## Applicability and validation

- Every retained continuous decision approximation has a finite declared mathematical domain in the
  v3 fitted artifact, and its requested interval lies within that domain.
- A loaded v2 fitted artifact, or unknown/legacy-only fitted meaning, fails new compiled-v2
  compilation. Supplying an interval does not promote a legacy operational range into a declared
  domain; refitting with declarations is required.
- A fixed decision is fixed/conditioned or handled exactly rather than given repeated PWL points.
- A structurally marginalized or absent feature requires and records no interval.
- An exact binary/categorical treatment requires and records no interval.
- Missing intervals for retained approximate continuous treatments fail compilation.
- Requests for unknown feature names, discrete features, unused features, or non-approximate
  treatments fail rather than being ignored.
- Training rows are never rejected against a compiler interval because it is not a fitting domain.

Planning adapters structurally marginalize through the existing TPM primitive before calling the
compiler. This ordering does not introduce conditional numerator/denominator embedding.

## Breakpoint derivation

The existing compiler layout policy supplies relative positions within the requested physical
interval; this feature does not prescribe an exact count. For a feature normalized by mathematical
domain $[40,160]$ and approximation interval $[60,140]$, the derived validity is
$[1/6,5/6]$. The approximation subset is not renormalized to `[0,1]`.

For every approximated feature, compiled payload v2 records:

- feature name and schema index;
- authoritative physical interval;
- derived model-coordinate interval;
- actual physical and model-coordinate breakpoint lists;
- caller source and encoding identity;
- normalization kind/parameters used; and
- compiler and payload schema versions.

## Evaluation contract

The physical-evidence path:

1. validates the physical value against recorded physical validity;
2. transforms it using persisted normalization;
3. validates the derived coordinate against recorded coordinate validity; and
4. evaluates the compiled curve.

An internal/model-coordinate path enforces recorded coordinate validity. Already-persisted legacy
compiled-v1 evaluation remains normalized-only and visibly legacy; it does not depend on whether
the source fitted artifact could qualify for a new compilation. Neither path clips nor
extrapolates. Diagnostics identify the feature and relevant physical/model-coordinate interval.

## Pyomo decision linking

For a continuous approximated decision, model assembly exposes:

- a physical decision variable bounded by recorded physical validity;
- a TPM model-coordinate variable bounded by derived validity; and
- the affine equality from persisted normalization, or identity equality when normalization is
  identity.

For a declared binary decision, the solver variable remains binary while caller ordering maps its
zero/one states back to declared physical labels. Integer-domain linking is not introduced.

The required HiGHS smoke test fixes physical decisions at lower, interior, and upper validity
points, solves a feasibility model, and verifies the linked coordinates. An outside point is
rejected or infeasible. It adds no benchmark objective, chance constraint, or solver-option bundle.
