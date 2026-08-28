# Data Model: Declared TPM Feature Domains

## Overview

The resolved feature description is an envelope over four independent meanings. These records are
small, immutable, JSON-compatible, and importable without SPFlow, Pyomo, or HiGHS.

```text
Resolved TPM feature
├── mathematical domain       caller claim, or explicit unknown/omitted state
├── training support          observation summary derived only from physical rows
├── normalization meaning     physical ↔ model-coordinate transform and provenance
└── compatibility views       old bounds/order fields derived from the records above

Compilation request/result
└── approximation validity    finite physical interval for one selected encoding
    └── derived coordinates   result of applying persisted normalization
```

Approximation validity is never an intrinsic field of the fitted feature. It is joined to a feature
only in a particular compiled result.

## Entity 1: Mathematical Feature Domain

**Purpose**: One of `decision-domain` or `distribution-support`.

**Feature kind**: Continuous, binary, or categorical. This kind is authoritative when declared and
therefore does not depend on which values appeared in training.

**Continuous shape**:

| Shape | Stored finite data | Meaning |
|---|---|---|
| finite | lower and upper | closed interval $[l,u]$; equality is a valid fixed domain |
| lower-bounded | lower | $[l,\infty)$; infinity is semantic, not numeric data |
| upper-bounded | upper | $(-\infty,u]$ |
| unbounded | none | $(-\infty,\infty)$ is explicitly asserted |
| unknown | none | mathematical extent is not known or asserted |

**Discrete form**:

- Binary stores exactly two distinct finite/serializable values in caller order.
- Categorical stores a non-empty complete set and caller order without duplicates.
- Observed discrete values are not stored here unless they are independently declared as complete.

**Origin**:

- caller-declared;
- explicitly unknown by caller;
- omitted by caller; or
- internal exact target where existing OEL behavior creates one.

**Invariants**:

- One feature cannot carry both decision-domain and distribution-support purposes.
- One declaration describes exactly one feature and contains no multi-feature references or
  constraint expressions.
- Numeric endpoints are finite and are never encoded with `NaN` or infinity.
- A finite lower endpoint does not exceed its upper endpoint.
- A declared purpose is compatible with the feature role.
- Coupled capacity, budget, storage, or knapsack constraints are not feature domains.
- Finite and one-sided membership comparisons are exact and closed; other workflow tolerances do
  not alter membership.

## Entity 2: Training Support

**Purpose**: Record physical coverage actually present in the supplied training rows.

**Continuous form**: Observed minimum and maximum plus observation provenance. Both are finite.

**Discrete form**: The distinct observed subset in stable existing order, independent of the
complete declared domain.

**Invariants**:

- Derived before normalization and only from caller-supplied physical rows.
- Never widened by declarations, compiler requests, backend smoothing, or queries.
- A declared discrete value may be absent.
- An empty training input remains invalid under existing fit requirements.

## Entity 3: Normalization Meaning

**Purpose**: Specify the auditable physical-to-model-coordinate transform used by fitting, native
queries, persistence, and compilation.

| Source state | Continuous transform | Query admissibility source |
|---|---|---|
| finite declared mathematical domain $[l,u]$, $l<u$ | $(x-l)/(u-l)$ | declared closed domain |
| fixed declared mathematical domain $[l,l]$ | sole value maps to $0$ | declared singleton |
| one-sided declared domain | identity | declared finite endpoint |
| explicitly unbounded support | identity | every finite value |
| explicitly unknown | identity | every finite value |
| declaration omitted | observed-extrema min-max, including existing fixed behavior | visibly legacy-inferred observed limit |
| declared binary/category | caller-order index | complete declared value set |
| undeclared discrete | existing inferred index | visibly legacy-inferred observed set |

**Stored properties**: Transform kind, origin, finite parameters if any, and enough information for
forward and inverse transformation. An approximation interval never changes these properties.

## Entity 4: Resolved TPM Feature

**Purpose**: Stable feature envelope consumed by fit, native query, artifact, and compiler code.

**Properties**:

- Existing identity: name, type, role, modifiability, monotonicity, and legacy reference.
- One mathematical-domain record.
- One training-support record for fitted artifacts.
- One normalization record.
- Compatibility projections for existing bounds, discrete values, ordering, and normalization
  labels.

**Invariants**:

- The three semantic records agree on feature kind but do not overwrite one another.
- A compatibility projection is derived, never independently authoritative.
- Serialization is schema-aware: a resolved v3 feature is not silently serialized as v2.

## Entity 5: Approximation-Domain Request

**Purpose**: Select the finite physical interval over which one compiler encoding is constructed.

**Properties**:

- Feature identity.
- Closed finite physical lower and upper endpoints with positive width.
- Caller-declared source.
- Encoding identity qualified by the interval.
- Existing breakpoint-layout policy, interpreted relative to this interval.

**Invariants**:

- Required only for a retained continuous treatment that actually approximates a feature.
- Never inferred from a mathematical domain, training support, legacy bounds, or normalized defaults.
- For a decision feature, the interval is contained in its declared decision domain.
- Unknown, unused, discrete, exact, or marginalized request entries are rejected rather than ignored.
- Approximation metadata does not affect fitting or native-query normalization.

## Entity 6: Compiled Validity Record

**Purpose**: Persist what a compiled curve may legitimately evaluate.

**Properties**:

- Feature name and resolved schema index.
- Authoritative physical interval.
- Derived model-coordinate interval.
- Physical and model-coordinate breakpoints.
- Declaration source and encoding identity.
- Normalization kind and parameters used for derivation.
- Compiler and payload schema versions.

**Invariants**:

- Physical points transformed through the fitted feature normalization equal stored model points.
- Both physical and model-coordinate evaluation paths enforce their recorded interval.
- Evaluation does not clip or extrapolate.
- A legacy compiled v1 payload has only normalized legacy validity and is not promoted to this
  record.

## Entity 7: TPM Artifact v3

**Purpose**: Persist the fitted TPM with complete semantic and provenance information.

**Properties**:

- Existing model identity, feature order, fit/query metadata, and sidecar digest.
- V3 resolved features and schema-level provenance.
- Physical training-support evidence.
- Fit seed/config and backend/version identity.

**Compatibility states**:

| Input | New reader behavior | Write behavior |
|---|---|---|
| v3 | validate and preserve all semantic records | v3 only |
| v2 | adapt bare ranges/values to visible legacy-inferred behavior; domain remains unknown | write the schema-aware v2 representation only; refit to obtain v3 |
| v1 | reject with existing refit guidance | none |
| unknown future version | reject | none |

The embedded sidecar feature schema must be checked in the same artifact-version context so it
cannot disagree silently with the manifest.

## Public Declaration Carriers

- Generic rows: `TPMArtifactBuildRequest.feature_domains`.
- Planning dataset: optional keyword-only `feature_domains` on `fit_tpm_artifact`.
- Study manifest: optional keyword-only `feature_domains` on
  `fit_tpm_artifact_from_study_manifest`.

Every carrier uses the same mapping value type and internal resolver. Keys must be present in the
fitted/selected column set. Omitted keys enter the legacy-inferred compatibility path; existing
planning or study metadata never becomes a declaration automatically.

## State Transitions

### New fit

```text
physical rows
  → canonical rows + observed training support
  → resolve caller declaration or omission compatibility state
  → validate finite values and declared membership
  → derive normalization meaning
  → normalize an unchanged semantic dataset
  → invoke SPFlow
  → persist v3 manifest + integrity-checked sidecar
```

Failure before SPFlow publishes no complete artifact. Backend-only stabilization must not alter the
training-support record.

### Load legacy artifact

```text
v2 bytes
  → validate v2 schema and sidecar integrity
  → construct in-memory legacy-inferred semantic view
  → preserve old normalization/query restriction
  → do not rewrite bytes or assert a mathematical domain
```

### Compile

```text
v3 fitted artifact with finite declared retained decision domains
  → select/structurally marginalize graph using existing capability
  → identify retained approximate continuous treatments
  → validate one explicit physical interval for each
  → derive model coordinates through persisted normalization
  → compile curves and physical/model links
  → persist compiled v2 validity records
```

A loaded v2 fitted artifact, or a v3 artifact with only unknown/legacy-inferred meaning for a
retained continuous decision, fails new compiled-v2 compilation. Refitting original evidence with
declarations is the migration path. This does not affect evaluation of already-persisted compiled-v1
payloads through their normalized-only compatibility path.

### Evaluate compiled result

```text
physical evidence
  → validate against recorded physical interval
  → transform through recorded normalization
  → validate against recorded model-coordinate interval
  → evaluate without clipping or extrapolation
```

Normalized-only evaluation remains available solely for legacy compiled v1 compatibility and
internal checked use.
