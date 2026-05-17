# Simulator Fixtures

Fixtures in this directory support deterministic simulator validation for the
battery arbitrage MVP.

The first committed fixture is expected to be
`tests/fixtures/simulator/battery_arbitrage_case.json`, a small synthetic case
used by unit and integration tests for scenario assembly, battery trace
evaluation, and discounted export settlement.

Each committed simulator fixture must include:

- origin and author/source note
- legacy reference paths used as evidence
- generation command or manual construction note
- any seed used
- expected invariants or outputs
- numeric tolerance
- refresh policy
