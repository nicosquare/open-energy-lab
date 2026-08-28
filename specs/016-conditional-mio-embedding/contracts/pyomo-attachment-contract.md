# Contract: Caller-Owned Pyomo Attachment

## Purpose and ownership boundary

OEL attaches an already-compiled conditional pair to an existing caller-owned Pyomo model. OEL owns
only one new namespaced block and its auxiliary encoding components. The caller continues to own all
primary decisions, deterministic constraints, objective, chance threshold, chance constraint, solve
call, and solver options.

Attachment shall not compile or modify the pair, refit a TPM, recreate caller primary decisions,
add an objective, add an operational risk constraint, or invoke a solver.

## Inputs

The attachment operation consumes:

- one validated immutable conditional pair;
- one existing caller-owned Pyomo model;
- one unique caller-supplied namespace valid as a Pyomo component name; and
- one ordered sequence of typed mappings whose feature coverage is exactly the pair's retained
  decision set.

Pyomo is imported lazily only when this operation is called.

## Mapping contracts

### Continuous

A continuous feature maps to one caller-owned scalar Pyomo variable or affine expression in physical
units. The expression:

- references at least one variable owned by the target model;
- may use fixed or unfixed continuous variables, fixed parameters, coefficients, and a constant;
- may not reference a binary, general integer, semicontinuous/discrete, or foreign-model variable;
- may not be nonlinear, even if fixing a participating variable would make its current numerical
  value constant.

Validation is structural. Implementations shall not rely only on `polynomial_degree()` or a standard
representation that folds fixed variables. A sound implementation may traverse/clone the expression
with fixed variables treated as unfixed symbolic placeholders, but it shall not mutate the caller's
variables to validate it.

The attachment adds physical-to-model-coordinate equality links according to the pair's persisted
U-Bounds normalization and closed inclusive approximation-validity constraints on the physical
expression. It never clamps the expression.

### Binary

A binary feature maps to exactly one caller-owned scalar Pyomo binary variable. Its zero/one model
state is interpreted through the pair's persisted two-value ordering. A Boolean, integer bounded to
$[0,1]$, continuous bounded to $[0,1]$, parameter, expression, or variable from another model is not
silently accepted as a binary variable.

### Categorical

A categorical feature maps to an ordered sequence containing one
`(declared category, caller-owned binary indicator)` for every persisted category. Labels, count,
ordering, uniqueness, variable domains, and model ownership are validated. The attachment adds one
exactly-one constraint inside its block. It does not enumerate category combinations.

### Complete coverage

Because mappings arrive as a sequence, the operation can reject duplicate feature entries. Every
retained decision appears exactly once. Missing, duplicate, or unknown extra features fail before
model mutation.

## Preflight and atomicity

Before adding any Pyomo component, OEL shall validate:

- pair schema, identity, circuit invariants, and numerical/encoding policy;
- namespace syntax and absence on the target model;
- exact mapping coverage;
- mapping type versus persisted feature type;
- continuous structural affinity and variable types;
- binary and categorical domains/orderings;
- ownership of every referenced variable by the target model;
- approximation intervals and normalization/link definitions; and
- absence of unresolved circuit inputs.

After preflight, OEL builds a detached concrete block that may reference caller variables. Only when
the complete block has been built and locally validated does it call the model's component-addition
operation once for the namespace. If that final operation fails after partial registration, OEL
removes exactly that newly introduced component and re-raises. It never deletes or alters a
pre-existing caller component.

Any attachment failure leaves no partial OEL variables, blocks, expressions, objectives, or
constraints on the caller model.

## Attached block

The single outer block contains:

- numerator circuit subblock;
- denominator circuit subblock;
- compiler-created auxiliaries and selected max/PWL constraints;
- continuous physical/model-coordinate links and closed validity constraints;
- categorical exactly-one constraints; and
- one conditional log-risk expression equal to numerator root minus denominator root.

Numerator and denominator reference the same model-coordinate links. The block may reference
caller-owned variables but does not transfer their ownership. It does not expose or add an
exponential probability component, because the log-risk expression is the optimization-facing
quantity.

The returned structured attachment gives the caller access to the outer block, both roots, log-risk
expression, decision links, pair metadata, and diagnostic component identities without requiring
knowledge of compiler internals.

## Namespace behavior

- Multiple pairs, or the same pair multiple times, may attach to one model under distinct names.
- A duplicate or conflicting namespace fails before mutation.
- OEL does not search for or delete prior attachments automatically.
- The attachment result retains the exact caller namespace and pair ID.

## Post-solve inspection

A separate read-only inspector consumes an attachment after a caller-managed solve. It does not call
a solver. It reports raw numerator/denominator roots, their difference, Python-computed exponential,
solver status supplied by the caller/result, and residuals for active constraints owned by the
attachment block.

Residuals mean violation magnitude:

- equality: absolute distance from the finite bound;
- lower inequality: $\max(l-b,0)$;
- upper inequality: $\max(b-u,0)$;
- ranged inequality: the maximum lower/upper violation.

Feasible slack is not reported as residual. Unrelated caller constraints are not scanned. A
nonfinite root/residual or unevaluable required component fails clearly. The same $10^{-6}$
positive-log-risk and residual classifications used by validation are retained without clamping.

## Consumer composition

After successful attachment, a caller can independently add, for example:

$$
z_{\mathrm{num}}-z_{\mathrm{den}}\leq\log\alpha,
$$

an unrelated objective, and arbitrary caller-owned deterministic constraints. The caller can also
fix its decisions and solve an objective-free model for diagnostic parity. Neither usage requires
access to OEL's internal node representation.
