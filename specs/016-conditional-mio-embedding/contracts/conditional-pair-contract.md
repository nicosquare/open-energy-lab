# Contract: Conditional Pair Compilation and Persistence

## Purpose

This contract defines the additive OEL capability that compiles one eligible persisted TPM artifact
into one reusable numerator/denominator pair. It does not define fitting, caller optimization, or
solver execution.

## Public capability

The public TPM surface shall provide import-light request and pair records plus lazy workflow
operations equivalent to:

1. compile a request into an in-memory immutable pair;
2. publish a pair to a caller-selected path using create-only or verify-identical semantics;
3. load and validate a published pair without importing SPFlow, Pyomo, or HiGHS.

Final public symbol names are an implementation choice. Existing whole-model compilation and
planning entry points remain available and behaviorally compatible.

## Preconditions and eligibility

Compilation shall reject before producing a pair unless all conditions hold:

- the input is a persisted production schema-v3 TPM artifact;
- its referenced current-SPFlow payload exists and passes the artifact's integrity checks;
- its backend/API generation is supported by the current production path;
- every feature has explicit U-Bounds semantics sufficient for its role;
- no retained decision or event feature relies on omitted or legacy-inferred normalization/domain
  meaning;
- the event target is binary, has exactly two declared ordered values, and the requested value is in
  that domain;
- retained decisions are nonempty, unique, known, and exclude the event target;
- every retained continuous decision has a finite declared decision domain and an explicit finite
  closed approximation interval contained within it;
- every retained binary or categorical decision has a complete declared ordered domain;
- one max or PWL policy and every required leaf/Sum parameter are explicit and finite.

Explicitly caller-declared unknown or unbounded support is permitted for a marginalized uncertainty
feature when no finite interval is required to compile it. Legacy inference is never promoted to a
declaration.

An ineligible artifact is neither migrated nor rewritten. A failed request leaves the source
artifact and sidecar byte-for-byte unchanged.

## Compilation behavior

The compiler shall:

1. verify and load the source model once;
2. retain the event target and ordered decision features while structurally marginalizing all other
   features;
3. compile this retained graph once with the resolved leaf configuration;
4. derive a numerator circuit by fixing the event to the resolved declared-value index;
5. derive a denominator circuit by marginalizing the event;
6. exactly simplify normalized, fully marginalized subtrees to log-one before applying a max or PWL
   Sum approximation;
7. apply one and only one resolved Sum policy to both circuits;
8. validate both circuits and construct the pair identity.

The numerator represents the selected compiled semantics for
$z_{\mathrm{num}}(x)\approx\log p_{X,Y}(x,y)$. The denominator represents
$z_{\mathrm{den}}(x)\approx\log p_X(x)$. For continuous decisions these are log densities. The
pair does not replace the learned denominator with a uniform constant, caller constant, or sampled
training range.

The denominator's event marginalization must be exact with respect to normalization. In particular,
a marginalized normalized Sum subtree becomes log-one rather than an approximate maximum over its
weighted children.

## Encoding policy

- `max` and configured `PWL` are the only supported Sum policies in this feature.
- The compiler shall never silently fall back from one to the other.
- Max remains visibly approximate and uncertified unless the existing compiler already supplies
  valid case-specific certification; this feature adds no certification method.
- PWL persists the exact exponential and logarithm curves and domain/bound information needed to
  reproduce its weighted log-sum-exp approximation.
- The pair persists all resolved leaf curves, breakpoints, maximum-term constants, big-M values,
  epsilon values, valid intervals, and compiler/backend versions used by either circuit.
- An unrecorded default that affects numerical semantics is prohibited.

## Pair invariants

A valid pair shall prove on load that:

- record kind and schema/compiler versions are supported;
- pair ID matches its canonical identity payload;
- source artifact/model digests are present and well formed;
- numerator and denominator share the source, event, decisions, validity, feature ordering,
  normalization, encoding, and numerical policy;
- both circuits are finite acyclic graphs with unique node IDs and valid roots/references;
- only retained decision leaves remain unresolved;
- event treatment and all marginalization declarations match circuit metadata;
- all persisted intervals, curves, constants, and tolerances are finite and valid;
- no serialized floating-point infinity, NaN, runtime backend object, or absolute output path is
  required to interpret the record.

Corrupt, incomplete, unsupported, or semantically mismatched pair content is rejected before use.

## Identity and persistence

Pair ID is the SHA-256 digest of a canonical JSON identity payload that includes every defining
semantic input and excludes the ID field, publication timestamp, and destination path. Changing the
source model, event/value, retained decision order, marginalization, validity interval, leaf policy,
Sum policy, compiler version, or resolved tolerance shall change the identity.

Publication shall:

- encode canonical finite JSON;
- flush and fsync a same-directory temporary file, then publish it with an atomic no-replace
  primitive; final `os.replace`-style overwriting is prohibited;
- return verified reuse when an existing target has identical canonical bytes/content and ID;
- validate an identical target that appears in a concurrent publication race;
- fail when an existing or concurrently created target differs, without overwriting it;
- leave no incomplete target on serialization or filesystem failure.

Loading shall not rewrite, strengthen, or migrate the record.

## Errors

User-visible failures shall distinguish at least:

- ineligible or legacy-inferred source semantics;
- sidecar integrity/backend failure;
- invalid event or retained-feature declaration;
- absent or invalid approximation domain;
- unresolved or unsupported encoding configuration;
- circuit invariant or nonfinite-data failure;
- pair identity/schema/corruption failure; and
- publication conflict or unwritable destination.

Messages identify the affected feature, interval, record, or path without relying on a backend
traceback as the explanation.

## Compatibility

- Existing fitted-artifact v2/v3 loading remains unchanged.
- Existing compiled-v1/v2 and whole-model planning APIs remain loadable and callable.
- Existing planning graph conditioning may delegate to a new shared primitive only when its
  externally observed payload and semantics remain covered by regression tests.
- The new pair is not a TPM artifact v4, a compiled-v3 migration, or a generalized artifact store.
- Root-level TPM imports remain usable without eagerly importing SPFlow, Torch, Pyomo, or HiGHS.
