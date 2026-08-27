# Contract: Training, Normalization, and Native Query

## Fit preparation order

Every public TPM fit entry point that accepts rows supports the same optional feature declarations
and follows this order:

1. Canonicalize physical rows and resolve the feature order.
2. Derive observed training support from those rows only.
3. Resolve declared feature kind/domain or the omission compatibility state.
4. Validate every physical observation.
5. Derive the persisted normalization meaning.
6. Normalize and invoke SPFlow.
7. Publish the v3 artifact only after successful fit and persistence validation.

Invalid observations fail before SPFlow is invoked. Compiler approximation intervals are not
consulted anywhere in this pipeline.

## Continuous normalization

| Mathematical state | Physical-to-model transform | Accepted physical values |
|---|---|---|
| finite $[l,u]$, $l<u$ | $(x-l)/(u-l)$ | finite $x$ with $l\leq x\leq u$ |
| fixed $[l,l]$ | $l\mapsto0$ | only $l$ |
| lower-bounded $[l,\infty)$ | identity | finite $x\geq l$ |
| upper-bounded $(-\infty,u]$ | identity | finite $x\leq u$ |
| unbounded support | identity | every finite $x$ |
| explicit unknown | identity | every finite $x$ |
| declaration omitted | existing observed-extrema transform | existing observed-range restriction, labelled legacy-inferred |

Closed-bound comparisons are exact. Existing fit, query, compiler, or assertion tolerances retain
their current purpose and provenance and are not applied to mathematical-domain membership. Values
exactly on an endpoint are accepted; values outside it, including the adjacent representable value,
are rejected without clamping.

## Discrete normalization

- Declared binary: first caller value maps to $0$, second to $1$.
- Declared categorical: caller order maps to stable consecutive indices.
- Undeclared discrete: retain current inferred values, order, encoding, and validation, labelled
  legacy-inferred.
- Training support records only observed values, even if the declared domain is larger.

Backend-specific preparation may stabilize numerical fitting but may not add values to persisted
training support or present a synthetic value as observed evidence.

## Native-query validation

- Every numeric assignment must be finite.
- A query inside a declared mathematical domain is valid even outside training support.
- A query outside a bounded mathematical domain fails.
- An explicit unknown or unbounded continuous domain accepts every finite query value.
- A declared binary/category accepts any declared value, including one absent in training; the
  fitted backend owns the resulting probability.
- Undeclared legacy-inferred features preserve their operational observed-range/value restriction,
  reported explicitly as compatibility behavior rather than a mathematical-domain violation.
- Query validation never mutates domain, support, normalization, or artifact bytes.

## Required diagnostics

Failures distinguish at least:

- non-finite physical value;
- declared decision-domain violation;
- declared distribution-support violation;
- undeclared legacy-inferred operational restriction;
- declared discrete membership violation; and
- missing mathematical meaning for an operation that requires it.

No path clamps, truncates, widens, extrapolates, or silently substitutes training support.

## Stability evidence

Given two physical datasets with different observed extrema and the same finite declaration, the
same physical probe produces the same model coordinate. Each artifact still records its own
different training support. A real scalar SPFlow fit keeps finite decision $x$ on declared
coordinates while explicitly unbounded normal demand remains in physical units.
