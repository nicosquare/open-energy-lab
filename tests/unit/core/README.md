# Core Unit Tests

Unit tests in this directory cover the stable controller-facing boundary in
`open_energy_lab.core`, including typed contract validation, public exports,
and import-light behavior.

These tests must stay independent of simulator internals and must not require
TorchRL, PyTorch, CityLearn, solver licenses, W&B access, GPU/SLURM tooling,
notebook execution, external data APIs, or runtime imports from `legacy/*`.
