# Migration Spec Template

Use this template when moving selected behavior from `legacy/*` into
`src/open_energy_lab`.

## Required Sections

```text
Migration name:
Target module path:
Validation/test path:
Target API maturity:
Legacy source paths:
Behavior to preserve:
Behavior to improve:
Behavior to reject:
Dependencies and classifications:
Fixtures and provenance:
Parity or validation cases:
Known environment assumptions:
Documentation updates:
Out-of-scope work:
```

## Writing Rules

- Name the `target module path` and `validation/test path` explicitly.
- List exact `legacy source paths` and cite them as reference material only.
- Use the phrase `legacy paths` when summarizing where the behavior came from.
- State `behavior to preserve`, `behavior to improve`, and `behavior to reject`
  separately.
- Classify dependencies before implementation so optional, external-service-
  backed, hardware-bound, and legacy-only dependencies stay out of core
  imports.
- Include `fixtures and provenance` for any committed generated data or
  snapshots.
- Record `parity or validation cases` with the evidence used to support them.
- Include `validation evidence` in a form reviewers can run or inspect.
- State `tolerances` when exact equality is not expected.
- Document `known environment assumptions` and `documentation updates` so
  reviewers can see the full migration boundary.
- Call out `out-of-scope work` so simulator, TPM, RL, optimization, weather,
  planning, and control migrations remain separate.
- Make `out-of-scope algorithm migration` explicit when behavior is deferred to
  another spec.

## Acceptance Guidance

A migration spec is not ready for implementation until reviewers can identify
where new code belongs, where tests belong, which legacy behavior is being
reviewed, which validations apply, and which assumptions or limitations keep
the change reproducible.
