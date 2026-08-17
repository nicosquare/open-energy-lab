# Contract: Fitted Demand Artifact

This contract defines the persisted model artifact that the feature writes and
loads later for offline weather-conditioned demand sampling.

## Purpose

The artifact is the durable handoff between aligned-history fitting and
offline paired-family sampling. It must be inspectable, versioned, and
deterministic to validate with committed fixtures.

## Stable Artifact Contents

The first-release artifact must contain:

- explicit schema version
- artifact identifier
- feature identifier
- timezone and local-civil-time basis metadata
- required weather field order for conditioning
- fixed timestep resolution
- separate non-thermal electric and cooling-demand model parameters
- shared residual or cross-output variability parameters
- explicit double-counting policy metadata
- provenance needed to trust the training record and fit

## Versioning Rules

- loading must accept only explicitly supported schema versions
- unsupported versions fail fast with explicit errors
- the first release does not promise auto-migration of older artifacts
- artifacts are not partial: both first-release demand outputs are present or
  the artifact does not exist

## Timestep Rules

- each artifact is bound to one timestep resolution
- offline sampling must use that same timestep
- requests implying a different timestep fail fast rather than silently
  resampling or interpolating

## Weather-Conditioning Rules

- the artifact must state which canonical weather fields are required for
  sampling
- sampling against a weather trace that does not satisfy that contract fails
  fast
- weather and demand remain separate artifacts even when sampled together

## Serialization Rules

- the artifact format is JSON and must remain human-inspectable enough for
  deterministic fixture review
- schema fields required for loading must be explicit, not inferred from file
  name or environment
- artifact contents must be sufficient for offline sampling without refitting
  or live-service access

## Guarantees

The first-release artifact guarantees:

- deterministic reload behavior
- stable provenance capture
- explicit schema compatibility behavior
- fixed-timestep sampling semantics
- explicit separation of non-thermal electric and cooling demand outputs
