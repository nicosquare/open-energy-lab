# Contract: Direct and Native Conditional Evaluation

## Purpose

This contract makes a compiled pair independently evaluable and provides a separate raw
current-SPFlow comparison. Direct evaluation is the authoritative numerical reference for the
attached Pyomo circuit; native evaluation is compiler-fidelity evidence, not solver parity.

## Compiled direct evaluation

The public TPM surface shall accept one validated conditional pair and exactly one complete
assignment mode:

- **declared-domain**: physical continuous values and declared binary/category values; or
- **model-coordinate**: compiled continuous coordinates and declared discrete indices.

The call shall reject:

- a missing, duplicate, or unknown retained feature;
- a mixed physical/model-coordinate assignment;
- nonfinite numeric input;
- a continuous value outside its closed approximation interval or corresponding compiled interval;
- a binary/category value or index outside the persisted exact ordered domain; or
- a corrupt/incompatible pair.

Boundary values are accepted. Evaluation never clips, widens, extrapolates, or reinterprets an
assignment. Declared-domain normalization follows persisted U-Bounds semantics; training extrema
do not participate.

## Exact selected semantics

The evaluator shall walk the persisted conditioned circuit, not the source SPFlow graph, and execute
the same selected mathematics used by Pyomo:

- log-one constant: return zero;
- continuous/discrete leaf: use its persisted compiled function/state term;
- product: sum child log values;
- max Sum: take the maximum of the persisted weighted child log terms;
- PWL Sum: apply the persisted shift, exponential interpolation, weighted accumulation, and
  logarithm interpolation sequence in the same operation order and domains as the encoded model.

Using exact mathematical log-sum-exp as the direct reference for an approximate max or PWL pair is
prohibited. Existing interpolation helpers may be reused only if their out-of-range clipping is
disabled or preceded by strict validation.

The numerator and denominator are evaluated from the same pair and assignment. The result contains
raw finite $z_{\mathrm{num}}$, $z_{\mathrm{den}}$,
$r=z_{\mathrm{num}}-z_{\mathrm{den}}$, and $\exp(r)$ plus the pair ID, assignments, mode, and
classification. No value is clamped into $[0,1]$.

## Numerical validity

- If any root, difference, exponential, or required intermediate is nonfinite, evaluation fails.
- If $r>10^{-6}$, evaluation fails as an invalid compiled conditional result while retaining the raw
  diagnostic values in the raised/result context.
- If $0<r\leq10^{-6}$, the result is returned and visibly classified as positive numerical noise.
- Otherwise the result is classified valid.
- This rule is distinct from exact domain membership and from compiled-versus-native fidelity.

## Native raw-log evaluation

A separate lazy current-SPFlow operation shall accept a published pair, its exact persisted source
artifact, and one complete declared-domain assignment. It shall:

1. verify artifact identity, sidecar digest, backend generation, feature schema, event declaration,
   and pair source-model provenance before querying;
2. assign every retained decision in the persisted model coordinate convention;
3. fix the explicit event target to the pair's resolved declared value for the numerator;
4. marginalize every nondecision, nonevent feature in both queries;
5. marginalize the event in the denominator;
6. return raw native numerator and denominator logs, their difference, and unclamped exponential.

The operation supports either declared binary event value, not only the last/positive ordering
entry. It shall not silently use empirical replay, metadata, a compiled evaluator, or a clamped
probability query as a substitute for current-SPFlow.

Native query failure, source mismatch, nonfinite roots, or unavailable required current backend is
an operational failure. Native/compiled numerical disagreement is returned as data and receives no
adequacy threshold in this feature.

## Determinism and side effects

For an unchanged pair and assignment, direct evaluation is deterministic and has no filesystem,
model, random-state, or backend side effect. Native evaluation is read-only with respect to the
artifact and pair. Neither operation writes evidence automatically.
