# Simulator Unit Tests

Unit tests in this directory cover small deterministic simulator behavior for
the battery arbitrage MVP, including scenario assembly, pricing rules, battery
state transitions, settlement accounting, and import-boundary checks.

These tests must run in the minimal foundation environment and must not require
solver licenses, W&B access, GPU/SLURM tooling, notebook execution, external
data APIs, Rust builds, or heavyweight optional research dependencies.
