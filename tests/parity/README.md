# Parity Tests

Parity tests compare migrated library behavior with legacy references,
documented equations, fixtures, snapshots, or deterministic smoke checks.

## Future Parity Strategy

Future migration specs should add parity cases here only after naming the
target module path, validation path, legacy reference paths, fixtures, and the
relevant parity evidence for the migrated behavior.

Acceptable parity evidence includes fixture-based checks, deterministic seeds
or configs, documented equations or invariants, legacy command output,
snapshots, focused smoke runs, or an explicit note explaining why full parity
cannot run locally.

## Legacy Reference Policy

Parity cases must cite exact files, directories, configs, notebooks, or scripts
under `legacy/*`. Legacy code remains reference material and must not become
the target architecture for new reusable library code.

When a migration spec uses legacy behavior as evidence, it should record what
is being preserved, improved, or rejected and keep any environment assumptions,
tolerances, and provenance visible to reviewers.

## Current State

No migrated parity cases exist in this foundation feature. This directory is a
placeholder for future migration specs rather than a home for algorithm
migration in the current scope.
