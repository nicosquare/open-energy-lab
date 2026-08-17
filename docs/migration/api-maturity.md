# API Maturity Policy

This policy defines how `open_energy_lab` import paths become stable, remain
experimental, or stay private while the project migrates selected behavior from
legacy references.

## Stable Public API

An import path is stable public API when all conditions hold:

- It is documented as an `open_energy_lab.*` import outside
  `open_energy_lab.experimental`.
- It has focused tests under `tests/unit`, `tests/integration`, or
  `tests/parity`.
- Its dependencies are classified and do not unexpectedly import optional
  research stacks.
- Its expected behavior and compatibility expectations are documented.
- A migration or capability spec explicitly reviews the promotion.

Stable public APIs should preserve import paths and documented behavior across
future migrations unless a deprecation decision is recorded.

### Weather-Conditioned Demand And Cooling-Aware Simulator Evaluation

The `008-weather-demand-modeling` feature now promotes the first shipped demand
workflow and simulator-side demand-family evaluation surface to stable public
API.

Stable demand package-root imports:

```python
from open_energy_lab.demand import (
    DemandSamplingRequest,
    fit_demand_model,
    load_demand_artifact,
    sample_demand_family,
)
```

Stable simulator package-root imports:

```python
from open_energy_lab.simulator import (
    DEMAND_SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    DemandFamilyEvaluationRequest,
    DemandFamilyEvaluationResult,
    DemandScenarioEvaluationResult,
    evaluate_demand_family,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for aligned-history validation,
  artifact schema and reload behavior, offline paired-family sampling,
  cooling-service configuration, paired-family alignment, and preserved
  deterministic `BatteryLoadPVScenario` behavior
- deterministic committed fixtures for aligned training history, supported and
  unsupported artifacts, offline sampled demand families, and local-electric
  versus district-cooling simulator-family baselines
- import-boundary, import-contract, and no-legacy-import coverage that names
  both `open_energy_lab.demand` and the demand-family simulator exports
  explicitly
- migration documentation that records the producer-versus-simulator
  ownership split, explicit non-thermal-versus-cooling separation, paired-seed
  replay contract, and simulator-side cooling settlement semantics
- documented dependency isolation proving package-root demand imports,
  offline artifact loading, offline demand sampling, and simulator-family
  evaluation remain import-light and clear of live-service assumptions

Focused imports remain intentionally narrower in maturity:

```python
from open_energy_lab.simulator.demand import (
    CoolingServiceConfiguration,
    DistrictCoolingTariff,
    LocalElectricCoolingConfiguration,
)
```

These cooling-service configuration types are part of the shipped workflow,
but they remain focused module imports instead of package-root simulator
exports so the stable root surface stays small.

Implementation-facing modules such as `open_energy_lab.demand._aligned_history`,
`open_energy_lab.demand._weather_response`,
`open_energy_lab.demand.fit`, `open_energy_lab.demand.artifact`,
`open_energy_lab.demand.sampling`, and
`open_energy_lab.simulator.stochastic_demand` remain the hosts for the
shipped logic. Callers may use those focused imports when needed, but the
stable user-facing contract for ordinary use is the package-root surface shown
above.

### Controller Boundary MVP

The `004-controller-boundary` feature promotes the following imports to stable
public API for the MVP:

```python
from open_energy_lab.core import (
    ControllerContext,
    ControllerEvaluationResult,
    ControllerInterface,
    DispatchProposal,
)

from open_energy_lab.simulator import evaluate_with_controller
```

These imports are stable because they now have:

- focused unit and integration coverage
- deterministic committed fixtures for both supported scenario families
- import-boundary checks proving they stay clear of optional research stacks
- no-legacy-import checks for the stable core package
- documented controller-boundary behavior, validation commands, and migration
  evidence

Supporting controller-boundary types that remain in
`open_energy_lab.core.controller` are intentionally narrower in maturity for
now. They may be used by package-internal code and focused validation, but
they are not yet promoted as root-level stable imports until a later spec
explicitly broadens the public surface.

### Native Controller Pack

The `005-controller-pack` feature promotes the following imports to stable
public API for the first shipped native controller surface:

```python
from open_energy_lab.control import (
    PVSelfConsumptionConfig,
    PVSelfConsumptionController,
    PriceThresholdConfig,
    PriceThresholdController,
    SocGuardrailConfig,
    SocGuardrailController,
)
```

These imports are stable because they now have:

- package-root export coverage tied to the documented support matrix
- typed configuration validation and `ControllerInterface` conformance tests
- deterministic controller-pack fixtures plus repeated-run runner checks
- import-boundary, import-contract, and no-legacy-import coverage that names
  `open_energy_lab.control` explicitly
- preserved-path regression evidence proving the controller pack does not
  replace explicit-dispatch or built-in simulator rule flows
- migration documentation that records behavior, dependency boundaries, and
  selective parity expectations

Supporting controller modules such as `open_energy_lab.control._config`,
`open_energy_lab.control.price_threshold`,
`open_energy_lab.control.soc_guardrail`, and
`open_energy_lab.control.pv_self_consumption` remain implementation-facing
modules. They are intentionally imported lazily through the package root so
ordinary `open_energy_lab.control` imports stay import-light while the stable
package-root surface remains fixed.

### Visualization Trace Inspection MVP

The `006-visualization-traces` feature now promotes the stable visualization
inspection/reporting root surface and keeps plotting explicitly experimental.

The package root now ships these stable public imports:

```python
from open_energy_lab.visualization import (
    build_inspection_view,
    load_persisted_run_output,
    summarize_inspection_view,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for supported arbitrage and
  battery-load-PV inspection flows
- persisted-output validation and reuse checks that avoid re-simulation
- package-root import-boundary, import-contract, and no-legacy-import
  coverage naming `open_energy_lab.visualization` explicitly
- direct smoke coverage proving experimental plotting stays outside the stable
  root import path
- migration documentation that records stable inspection/reporting behavior,
  same-family comparison scope, and the experimental plotting split

Same-family comparison is also shipped user-facing behavior, but it remains a
focused module import rather than a package-root export:

```python
from open_energy_lab.visualization.comparison import compare_inspection_views
```

This comparison helper is intentionally not promoted into the package root
because the stable root contract for this MVP is inspection/reporting only,
while comparison remains discoverable through its dedicated module.

Experimental plotting remains outside the stable root contract:

```python
from open_energy_lab.visualization.plotting import plot_inspection_view
```

This plotting helper remains experimental because rendered output shape,
backend conventions, and future comparison-plot scope are still expected to
evolve. The package root now rejects root-level plotting access explicitly so
ordinary imports remain import-light and callers must opt in through the
focused plotting module.

### Stochastic Weather And Simulator Family Evaluation

The `007-stochastic-weather` feature now promotes the first shipped weather
workflow and simulator-side stochastic family evaluation to stable public API.

Stable weather package-root imports:

```python
from open_energy_lab.weather import (
    WeatherSamplingRequest,
    fit_weather_model,
    load_weather_artifact,
    sample_weather_family,
)
```

Stable simulator package-root imports:

```python
from open_energy_lab.simulator import (
    SUPPORTED_SUMMARY_OUTPUT_FIELDS,
    WeatherFamilyEvaluationRequest,
    WeatherFamilyEvaluationResult,
    WeatherScenarioEvaluationResult,
    evaluate_weather_family,
)
```

These imports are stable because they now have:

- focused unit and integration coverage for canonical normalization, artifact
  schema and reload behavior, offline family sampling, simulator family
  evaluation, blackout semantics, and preserved deterministic
  `BatteryLoadPVScenario` debugging
- deterministic committed fixtures for recorded fetch responses, fitted
  artifacts, sampled weather families, and simulator family baselines
- import-boundary, import-contract, and no-legacy-import coverage that names
  both `open_energy_lab.weather` and stochastic simulator exports explicitly
- migration documentation that records the stable fit/load/sample workflow,
  blackout semantics, summary-field limits, and the explicit boundary between
  artifact-preserved fields and simulator-consumed fields
- documented dependency isolation proving offline artifact loading, sampling,
  and simulator-family imports remain usable without live weather-service
  dependencies

Focused module imports remain intentionally narrower in maturity:

```python
from open_energy_lab.weather.fit import WeatherFitConfig
```

`WeatherFitConfig` is part of the shipped fit workflow, but it remains a
focused module import instead of a package-root export so the stable root
surface stays small.

Implementation-facing modules such as `open_energy_lab.weather._canonical`,
`.tmy`, `.fit`, `.artifact`, `.sampling`, `.events`, and
`open_energy_lab.simulator.stochastic_weather` remain the hosts for the shipped
logic. Callers may use those focused imports when needed, but the stable
user-facing contract for ordinary use is the package-root surface shown above.

## Experimental API

`open_energy_lab.experimental.*` is for immature migrations and incubating APIs.
Experimental APIs may change or move while behavior is being migrated,
validated, and reviewed.

Experimental placement does not remove quality requirements. Experimental code
still needs appropriate tests or smoke checks, dependency classification, and
clear documentation before users rely on it.

## Private API

Private modules and objects use a leading underscore or are undocumented
implementation details. They are not user-facing contracts and may change
without deprecation.

Examples:

```text
open_energy_lab.simulator._internal
open_energy_lab.core._legacy_adapter
```

## Promotion Rules

Promotion from private or experimental to stable requires:

- Target import path and user-facing purpose.
- Validation evidence, including parity cases when migrated from `legacy/*`.
- Dependency classification.
- Documentation update.
- Explicit review in the migration or capability spec.

Promotion must not make solver licenses, W&B accounts, GPU/SLURM tooling,
notebooks, Rust builds, or external data APIs required for ordinary package
imports unless a later spec explicitly accepts that tradeoff.

## Deprecation Rules

Deprecating stable public API requires:

- A recorded reason in the relevant spec, changelog, or migration note.
- A replacement path or explicit statement that no replacement exists.
- A compatibility expectation for how long the old path remains available.
- Tests or documentation updates that make the transition visible.

Experimental and private APIs may change faster, but changes should still be
documented when users or future migration specs are expected to notice them.
