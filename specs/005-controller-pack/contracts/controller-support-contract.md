# Contract: Shipped Controller Support Matrix

This contract defines the behavior and scenario support guarantees for the
first native controller pack.

## Shipped Controllers

The initial controller pack must include:

- `PriceThresholdController`
- `SocGuardrailController`
- `PVSelfConsumptionController`

## Support Matrix

- `PriceThresholdController` supports `ArbitrageScenario`
- `SocGuardrailController` supports `ArbitrageScenario` and
  `BatteryLoadPVScenario`
- `PVSelfConsumptionController` supports `BatteryLoadPVScenario`

No shipped controller may claim support beyond this matrix unless the spec,
tests, and migration docs are updated together.

## Behavior Guarantees

Across all shipped controllers:

- one dispatch proposal is produced per controller call
- positive requested power means charge
- the same context and same configuration produce the same request
- the controller never assumes ownership of physical feasibility or settlement

### Price Threshold Controller

The price-threshold controller must:

- compare the current import price against configured charge and discharge
  thresholds
- request charging below the charge threshold
- request discharging above the discharge threshold
- idle inside the neutral band and at exact threshold equality

### SOC Guardrail Controller

The SOC guardrail controller must:

- request charging when current SOC is below the configured minimum band
- request discharging when current SOC is above the configured maximum band
- idle when current SOC is already inside the configured band
- treat exact satisfied boundary equality as idle

### PV Self-Consumption Controller

The PV self-consumption controller must:

- compare current-step `pv_generation_kw` and `load_kw`
- request charging when PV exceeds load and SOC is below the configured
  reserve ceiling
- request discharging when load exceeds PV and SOC is above the configured
  reserve floor
- idle when load equals PV or the battery is already at the relevant reserve
  boundary

## Unsupported Scenario Behavior

If a shipped controller is used with an unsupported scenario family, the
failure must be:

- immediate
- deterministic
- attributable to unsupported scenario usage rather than simulator physics

The failure must not depend on optional research stacks, legacy wrappers, or
partial compatibility shims.

## Rejected Directions

This controller pack does not include:

- CityLearn compatibility adapters
- RL training loops
- replay buffers
- policy networks
- stochastic exploration logic
- solver-backed planning or MPC
- multi-agent control
- federated control
- notebook-first controller workflows
