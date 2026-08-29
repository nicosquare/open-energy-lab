# Contract: Embedding Parity and Compiler Fidelity Evidence

## Separation rule

Validation produces two separate immutable record kinds:

1. **embedding/solver parity** compares direct and Pyomo evaluation of the identical compiled pair;
2. **native/compiler fidelity** compares direct compiled evaluation with the original current-SPFlow
   model.

They shall not share a pass criterion, be averaged into one error, or be labelled interchangeably.

## Embedding/solver parity

For each representative fixed assignment $x$, the parity workflow shall:

1. directly evaluate the published pair and retain
   $(z_{\mathrm{num}}^C,z_{\mathrm{den}}^C,r^C,\exp(r^C))$;
2. create a caller-owned Pyomo model and primary decisions, attach the unchanged pair, and fix those
   decisions to the same declared values;
3. solve the objective-free diagnostic model with open CPU Pyomo/HiGHS;
4. inspect the attachment and retain
   $(z_{\mathrm{num}}^P,z_{\mathrm{den}}^P,r^P,\exp(r^P))$, solver status, and attachment-local
   residuals;
5. calculate signed and absolute deltas for both roots and the conditional difference.

Acceptance requires a successful/optimal diagnostic termination appropriate to the objective-free
model and:

$$
|z_{\mathrm{num}}^P-z_{\mathrm{num}}^C|\leq10^{-6},
$$

$$
|z_{\mathrm{den}}^P-z_{\mathrm{den}}^C|\leq10^{-6},
$$

$$
|r^P-r^C|\leq10^{-6},
$$

with every reported attachment constraint violation at most $10^{-6}$. Nonfinite values or a
materially positive compiled/Pyomo log-risk are operational failures under the numerical contract.

The direct evaluator must use the pair's selected max/PWL semantics. Exact mathematical
log-sum-exp is not an eligible parity reference for either approximate encoding.

## Native/compiler fidelity

For the same assignment, the fidelity workflow queries the exact pair source artifact for raw
current-SPFlow logs
$(\ell_{\mathrm{num}}^N,\ell_{\mathrm{den}}^N)$ and reuses the pair's direct compiled logs
$(\ell_{\mathrm{num}}^C,\ell_{\mathrm{den}}^C)$. It preserves:

$$
\Delta_{\mathrm{num}}=\ell_{\mathrm{num}}^C-\ell_{\mathrm{num}}^N,
$$

$$
\Delta_{\mathrm{den}}=\ell_{\mathrm{den}}^C-\ell_{\mathrm{den}}^N,
$$

$$
\Delta_{\mathrm{risk}}=
(\ell_{\mathrm{num}}^C-\ell_{\mathrm{den}}^C)
-(\ell_{\mathrm{num}}^N-\ell_{\mathrm{den}}^N),
$$

and

$$
\Delta_p=
\exp(\ell_{\mathrm{num}}^C-\ell_{\mathrm{den}}^C)
-\exp(\ell_{\mathrm{num}}^N-\ell_{\mathrm{den}}^N).
$$

All raw values and signed differences remain visible. This record has no numerical adequacy gate.
Large or unfavorable discrepancies are complete scientific evidence, not a reason to change pair
semantics or mark solver parity failed.

## Record content and identity

Each evidence record contains:

- record kind and schema/evaluator versions;
- deterministic evidence ID;
- pair ID and source artifact/model identity where applicable;
- encoding and all purpose-labelled tolerances;
- ordered assignment cases and assignment mode;
- all raw inputs, derived metrics, and classifications;
- solver name/version/status for parity only;
- attachment namespace and residual definitions for parity only;
- backend identity for native fidelity;
- creation provenance that does not replace semantic identity.

The evidence ID is a canonical SHA-256 digest of record kind, pair/source identities, ordered cases,
metric definitions, evaluator/solver semantic versions, and numerical policy. Publication uses the
same create-only or verify-identical rule as conditional pairs. Changed defining input creates a new
ID and never overwrites earlier evidence.

## Failure behavior

Parity publication fails on solver failure, direct/Pyomo disagreement beyond tolerance, excessive
residual, namespace/mapping error, nonfinite values, or pair mutation/mismatch. The record may
preserve a completed failed diagnostic when its fields are finite and auditable, but it cannot be
labelled accepted.

Fidelity publication fails operationally only when the source/pair provenance is inconsistent, the
current backend cannot execute, a query is invalid/nonfinite, or the record cannot be published.
Numerical disagreement itself is retained normally.

Generating either record shall not modify pair bytes, source artifacts, sidecars, caller decisions,
or a previously published record.
