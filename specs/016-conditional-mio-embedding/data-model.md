# Data Model: Composable Conditional MIO Embedding

## Design principles

- A fitted TPM artifact, a compiled conditional pair, and validation evidence are separate records
  with separate identities and lifecycles.
- Persisted records are finite, canonical JSON values. Runtime Pyomo and SPFlow objects never enter
  the serialized pair.
- Records are recursively immutable after construction. Publication is create-only or
  verify-identical; no workflow silently rewrites scientific evidence.
- Every ordered collection whose ordering changes meaning remains ordered in both memory and JSON.
- Optional dependencies are required only by compilation, native evaluation, or Pyomo attachment;
  record construction, validation, identity, and loading stay import-light.

## 1. Conditional compilation request

`TPMConditionalCompilationRequest` captures every caller choice that can change a pair.

| Field | Meaning and validation |
|---|---|
| Source artifact | Path or already-loaded persisted schema-v3 TPM artifact. It must identify a verified current-SPFlow sidecar. |
| Event target | Exactly one declared binary feature. |
| Event value | Exactly one of the event feature's two declared values; its model-coordinate index is resolved and retained. |
| Retained decisions | Nonempty ordered tuple of unique feature names. The event cannot also be retained. |
| Approximation domains | One explicit finite closed interval for every retained continuous feature. Each interval lies within that feature's declared finite decision domain. No interval is invented for a discrete feature. |
| Leaf configuration | Fully resolved existing continuous-leaf approximation inputs, including breakpoints and numerical settings. |
| Sum encoding | Exactly one explicit encoding policy: max or PWL. PWL includes all resolved exponential and logarithm curves; max includes all resolved constants needed by the existing encoding. |
| Numerical policy | Finite, positive purpose-labelled tolerances, including the fixed $10^{-6}$ parity/residual and conditional-log-risk rules. |

Validation is complete before SPFlow compilation begins. Unknown feature names, duplicate retained
features, an invalid event value, a retained event target, missing continuous intervals, unrecorded
encoding defaults, or ineligible domains reject the request.

## 2. Conditional pair

`TPMConditionalPair` is the immutable, solver-neutral result of compilation.

### Identity and source

| Field | Meaning |
|---|---|
| Record kind | `conditional-pair-v1`. |
| Pair schema/compiler version | Versions for record parsing and conditioned-circuit semantics. |
| Pair ID | SHA-256 of the canonical identity payload. It excludes storage path, publication timestamp, and the ID field itself. |
| Source artifact reference | Artifact identity, schema version, persisted manifest reference, verified sidecar digest, current-SPFlow backend generation, and public API generation. |
| Source model digest | Digest of the canonical retained compiled graph plus its resolved compiler inputs. It distinguishes model semantics from unrelated manifest bytes. |

### Mathematical meaning

| Field | Meaning |
|---|---|
| Feature schema | Complete ordered persisted schema needed to interpret domains, normalization, binary ordering, and categorical ordering. |
| Event declaration | Event feature name, declared event value, and resolved model-coordinate index. |
| Retained decisions | Ordered decision feature identities and model-coordinate meanings. |
| Marginalized features | Ordered identities of every nondecision, nonevent feature marginalized in both circuits. The event is marked fixed in the numerator and marginalized in the denominator. |
| Validity | Closed approximation intervals for retained continuous decisions and exact ordered domains for retained discrete decisions. |
| Encoding | One fully resolved max or PWL policy shared by both circuits, including leaf and Sum settings and compiler constants. |
| Numerical policy | Tolerances identified by purpose rather than one ambiguous global epsilon. |

### Circuits

The pair contains two immutable directed acyclic circuits:

- numerator root: approximate $\log p_{X,Y}(x,y)$;
- denominator root: approximate $\log p_X(x)$.

Supported node kinds are:

| Node kind | Persisted content | Evaluation |
|---|---|---|
| Log-one constant | Exact finite value zero | Returns $0$ |
| Continuous leaf | Feature, physical/model-coordinate mapping, resolved leaf curve | Evaluates the persisted curve at the assigned coordinate |
| Binary leaf | Feature ordering and compiled state terms | Selects by the declared value/index |
| Categorical leaf | Complete ordered categories and compiled state terms | Selects by declared category/index |
| Product | Ordered child IDs | Sum of child log values |
| Max Sum | Ordered weighted child terms and resolved encoding constants | Maximum of the same weighted log terms used in Pyomo |
| PWL Sum | Ordered weighted child terms, shift construction, persisted exponential curve, total bounds, and persisted logarithm curve | Executes the same shift, interpolation, accumulation, and logarithm sequence used in Pyomo |

Circuit invariants:

- node IDs are unique and every child reference resolves;
- each circuit has exactly one declared root and contains no cycle;
- only retained decision leaves remain unresolved;
- the numerator fixes exactly the declared event value;
- the denominator marginalizes the event;
- every other nondecision feature is exactly marginalized in both circuits;
- a normalized fully marginalized subtree is simplified to the log-one constant before max/PWL
  approximation, so approximation cannot turn probability one into a weighted branch maximum;
- numerator and denominator share one source model, feature ordering, encoding, validity, and
  numerical policy.

## 3. Direct evaluation

`TPMConditionalEvaluation` is a value record produced without Pyomo.

| Field | Meaning |
|---|---|
| Pair ID | Exact pair evaluated. |
| Assignment mode | `declared-domain` or `model-coordinate`. |
| Assignments | Complete named assignment for all retained decisions, stored in declared order. |
| Numerator log | Raw finite evaluated numerator root. |
| Denominator log | Raw finite evaluated denominator root. |
| Conditional log-risk | Raw numerator minus denominator. |
| Conditional probability | Raw $\exp(z_{\mathrm{num}}-z_{\mathrm{den}})$; never clamped. |
| Classification | `valid`, `positive-numerical-noise`, or operational failure. |

The declared-domain mode accepts physical continuous values and declared discrete values. The
model-coordinate mode accepts already-normalized continuous coordinates and discrete indices.
Modes cannot be mixed. Inputs are finite, complete, contain no unknown feature, and satisfy the
pair's closed validity and exact-domain rules.

## 4. Caller-owned mapping records

Attachment accepts an ordered sequence so duplicate feature names remain detectable.

### Continuous mapping

- retained continuous feature identity;
- caller-owned Pyomo scalar variable or affine expression in physical units;
- expression references at least one variable owned by the target model;
- every referenced variable is continuous, including when fixed;
- fixed parameters and affine constants are allowed;
- general integers, binaries, nonlinear structure, external-model variables, and constant-only
  expressions are rejected.

### Binary mapping

- retained binary feature identity;
- exactly one caller-owned Pyomo binary variable;
- value interpretation comes from the pair's persisted two-value ordering.

### Categorical mapping

- retained categorical feature identity;
- ordered tuple of `(declared category, caller-owned binary indicator)` entries;
- every declared category appears exactly once in persisted category order;
- no unknown or duplicate category appears;
- the attachment adds one exactly-one constraint over the supplied indicators.

Across all mapping records, every retained decision appears exactly once and no extra feature is
accepted.

## 5. Runtime attachment

`TPMConditionalAttachment` is a runtime-only result; it is not serialized as part of the pair.

| Field | Meaning |
|---|---|
| Pair metadata | Pair ID plus event, decision, validity, encoding, and tolerance summaries. |
| Namespace | Unique caller-supplied Pyomo component name. |
| Block | The one new namespaced block owned by OEL. |
| Numerator root | Pyomo root variable/expression for the numerator circuit. |
| Denominator root | Pyomo root variable/expression for the denominator circuit. |
| Conditional log-risk | Pyomo expression `numerator_root - denominator_root`. |
| Decision links | Read-only mapping from retained feature to created normalization/link components or caller-owned discrete variables. |
| Diagnostics metadata | Attachment-local component identities and resolved policies required for inspection. |

The block owns numerator and denominator circuit subblocks, auxiliary encoding components,
physical-to-model-coordinate links, closed validity constraints, and categorical exactly-one
constraints. It references but never recreates caller primary decisions. It contains no objective,
chance threshold, chance constraint, solver invocation, or exponential probability expression.

## 6. Post-solve attachment diagnostics

`TPMConditionalAttachmentDiagnostics` records values from an attachment after the caller has fixed
or optimized its model and invoked a solver.

| Field | Meaning |
|---|---|
| Pair/namespace | Exact attached pair and block. |
| Solver status | Caller-supplied or result-derived termination/status summary. |
| Roots and risk | Raw numerator root, denominator root, difference, and Python-computed exponential. |
| Residual summary | Maximum and per-constraint violation magnitudes for active constraints inside the attachment only. |
| Numerical classification | Same raw conditional-log-risk classification used by direct evaluation. |

For equality constraints, violation is the absolute distance from the bound. For inequalities,
violation is only the amount outside a finite lower or upper bound; feasible slack is not a
residual. Nonfinite or unevaluable values are failures.

## 7. Evidence records

### Embedding/solver parity evidence

This acceptance record compares direct and Pyomo evaluation of the same pair at one or more fixed
assignments. It contains:

- evidence schema/version and deterministic evidence ID;
- pair ID, encoding, assignment cases, solver identity/status, and tolerance policy;
- direct and Pyomo roots, conditional differences, derived probabilities, and their signed/absolute
  deltas;
- attachment-local residuals;
- pass/fail status using the absolute $10^{-6}$ gate;
- provenance and evaluator versions.

### Native/compiler fidelity evidence

This scientific record compares the pair's direct evaluation with raw current-SPFlow queries from
the exact source artifact. It contains:

- evidence schema/version and deterministic evidence ID;
- pair/source identity and assignment cases;
- native and compiled numerator/denominator logs;
- $\ell_{\mathrm{num}}^C-\ell_{\mathrm{num}}^N$ and
  $\ell_{\mathrm{den}}^C-\ell_{\mathrm{den}}^N$;
- compiled-versus-native conditional-log-risk error and conditional-probability difference;
- provenance and evaluator versions;
- no adequacy verdict or threshold.

The records cannot be merged because parity disagreement is operational failure while fidelity
disagreement is retained approximation evidence.

## Relationships

```text
persisted current TPM artifact
  └── verified current-SPFlow sidecar
        └── conditional compilation request
              └── immutable conditional pair
                    ├── direct evaluations
                    ├── caller-model attachments ──> post-solve diagnostics
                    ├── embedding/solver parity evidence
                    └── native/compiler fidelity evidence
```

One source artifact may produce many pairs when a defining input changes. One pair may be attached
many times under distinct namespaces and to distinct caller models. Evidence always references a
published pair and never modifies it.

## Lifecycle and state transitions

1. **Requested**: Parse the full compilation request and source reference.
2. **Validated**: Verify artifact eligibility, sidecar integrity, declared domains, event, retained
   decisions, validity intervals, and resolved compiler policy.
3. **Compiled in memory**: Load the current model, compile the retained graph once, derive and
   simplify numerator and denominator circuits, validate invariants, and calculate identity.
4. **Published**: Atomically create the canonical JSON pair, or verify that an existing file has
   identical canonical content. A conflicting path is an error.
5. **Evaluated or attached**: Reuse the unchanged pair. Attachment first completes all preflight,
   builds a detached block, then performs one namespace mutation.
6. **Evidenced**: Create separate immutable parity and fidelity records from unchanged pair/source
   identities.

A failure before pair publication leaves no file. A failed attachment leaves the caller model
unchanged. A failed evidence write leaves prior pair and evidence records untouched.

## Identity rules

- Canonical identity payloads use sorted JSON object keys, stable ordered arrays, UTF-8, finite
  JSON numbers, and no environment-dependent absolute output path.
- Pair identity includes every semantic compilation input, source-model identity, event meaning,
  feature ordering, validity interval, resolved leaf/Sum policy, compiler version, and numerical
  tolerance.
- Evidence identity additionally includes pair ID, assignment cases, evaluator/solver identity,
  metric definition, and the record kind. Parity and fidelity can never collide.
- Publication timestamps and local paths are provenance but not identity unless they change source
  semantics.
- A changed defining input produces a different ID and cannot overwrite an earlier record.
