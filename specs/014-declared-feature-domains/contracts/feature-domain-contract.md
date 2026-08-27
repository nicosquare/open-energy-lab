# Contract: Feature-Domain Declaration

## Consumer promise

A fitting caller may optionally provide one mathematical declaration per feature. The declaration
is interpreted in physical units and is independent of the finite values observed in training.
Omission remains supported but is visibly classified as compatibility behavior.

The public carrier is named `feature_domains`. Generic-row fitting stores it on
`TPMArtifactBuildRequest`; planning-dataset and study-manifest fitting accept it as an optional
keyword mapping. Every path uses the same declaration value type and resolver. A key outside the
fitted/selected columns is rejected, while an omitted key enters compatibility behavior.

## Accepted declarations

### Continuous

A continuous declaration states exactly one purpose—decision domain or distribution support—and
exactly one shape:

- finite closed interval $[l,u]$, including a fixed $[l,l]$;
- lower-bounded $[l,\infty)$;
- upper-bounded $(-\infty,u]$;
- fully unbounded $(-\infty,\infty)$; or
- explicitly unknown.

All supplied numeric endpoints must be finite. Missing endpoints carry the one-sided or unbounded
meaning; numeric infinity is neither accepted nor serialized.

### Binary

A binary declaration provides exactly two distinct values as an ordered pair. The first maps to
model coordinate $0$ and the second to $1$. The complete pair is preserved even if training
contains only one member.

### Categorical

A categorical declaration provides a complete non-empty set and an authoritative order without
duplicates. The complete declaration is preserved separately from the observed subset.

## Role compatibility

- Decision features may declare decision domains.
- Uncertainty/evidence features may declare distribution support.
- One feature may not carry both purposes.
- A finite decision-sampling policy is not distribution support.
- Coupled constraints such as capacity, budget, shared storage, and knapsack capacity remain
  caller-owned model constraints, not coordinate domains.
- Each mapping entry describes exactly its named feature. Domain values cannot contain expressions
  or references to another feature.
- No integer feature type or integer decision linking is added by this contract.

## Omission and explicit states

| Caller input | Mathematical meaning | Transformation policy |
|---|---|---|
| no declaration | unknown, origin omitted | existing inferred behavior, labelled legacy-inferred |
| explicit unknown | unknown, origin caller | identity for continuous values |
| explicit unbounded support | unbounded distribution support | identity for continuous values |

These rows are observably different after persistence and reload.

## Validation failures

Resolution fails before backend fitting when a declaration:

- contains a non-numeric or non-finite numeric endpoint;
- reverses finite endpoints;
- mixes unknown/unbounded markers with finite endpoints;
- supplies the wrong number of binary values;
- repeats a binary or categorical value;
- provides an empty category set;
- conflicts with the resolved feature kind or role; or
- attempts to declare both domain purposes;
- names an unknown or unselected fit column; or
- contains a multi-feature reference, budget/capacity expression, or other coupled constraint.

Diagnostics identify the feature, rejected declaration component, and semantic requirement. They do
not silently sort, clamp, widen, truncate, or reinterpret the input.

## Persistence promise

For new v3 artifacts, purpose, shape, finite endpoints or discrete order, origin, training support,
and normalization meaning survive serialization independently. Unknown never reloads as unbounded,
and a sampled extremum never reloads as a mathematical endpoint.
