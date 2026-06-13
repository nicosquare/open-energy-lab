# Contract: Fitted Weather Artifact

This contract defines the persisted model artifact that the feature writes and
loads later for offline sampling.

## Purpose

The artifact is the durable handoff between the network-backed fit workflow and
offline stochastic sampling. It must be inspectable, versioned, and
deterministic to validate with committed fixtures.

## Stable Artifact Contents

The first-release artifact must contain:

- explicit schema version
- artifact identifier
- feature identifier
- geolocation and source provenance
- timezone and local-civil-time basis metadata
- canonical weather field order
- fixed timestep resolution
- base joint weather model parameters
- cloud-event model parameters
- any documented clipping or physical-bounds policy needed for sampling

## Versioning Rules

- loading must accept only explicitly supported schema versions
- unsupported versions fail fast with explicit errors
- the first release does not promise auto-migration of older artifacts
- artifacts are not partial: the canonical field set is complete or the
  artifact does not exist

## Timestep Rules

- each artifact is bound to one timestep resolution
- offline sampling must use that same timestep
- requests implying a different timestep fail fast rather than silently
  aggregating or interpolating

## Serialization Rules

- the artifact format is JSON and must remain human-inspectable enough for
  deterministic fixture review
- schema fields required for loading must be explicit, not inferred from file
  name or environment
- artifact contents must be sufficient for offline sampling without contacting
  the original TMY source

## Guarantees

The first-release artifact guarantees:

- deterministic reload behavior
- stable provenance capture
- explicit schema compatibility behavior
- fixed-timestep sampling semantics
- no hidden dependency on network connectivity after persistence
