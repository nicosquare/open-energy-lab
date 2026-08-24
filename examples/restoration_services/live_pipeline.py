"""Assemble one explicit in-memory restoration demonstration from live artifacts.

This module is an example consumer of the public Open Energy Lab contracts.  It
does not acquire credentials or perform network IO.  RTE area values are mapped
to a labelled directional simulation using caller-supplied assumptions; they
are never represented as observed asset commands.
"""

from __future__ import annotations

from dataclasses import dataclass

from open_energy_lab.control.restoration_service import (
    DIRECTIONAL_CAPACITY_SEMANTICS_VERSION,
    AFRRBaselineMode,
    DirectionalCapacitySchedule,
    MFRRBaselineMode,
    RestorationBaselineBundle,
    RestorationCapability,
    build_afrr_baseline,
    build_afrr_baseline_config,
    build_afrr_directional_capacity_schedule,
    build_mfrr_baseline,
    build_mfrr_baseline_config,
    build_mfrr_directional_capacity_schedule,
    build_restoration_capability,
)
from open_energy_lab.market.artifact import MarketDataArtifact
from open_energy_lab.market.entsoe import FRANCE_QUARTER_HOUR_DAY_AHEAD_PROFILE_ID
from open_energy_lab.market.restoration_activation import (
    AFRRActivationTrajectory,
    DerivedSimulationMapping,
    MFRRActivationKind,
    MFRRActivationSequence,
    RestorationDirection,
    RestorationProduct,
    build_afrr_trajectory_from_rte_requested_need,
    build_derived_simulation_mapping,
    build_mfrr_sequence_from_rte_sa_requested_volume,
)
from open_energy_lab.market.restoration_artifact import (
    ObservationValueState,
    RestorationMarketArtifact,
    RestorationMarketSeries,
)
from open_energy_lab.simulator.battery import build_initial_state
from open_energy_lab.simulator.restoration_service import (
    AFRRReplayResult,
    MFRRReplayResult,
    build_afrr_replay_request,
    build_mfrr_replay_request,
    build_restoration_integration_grid,
    replay_afrr,
    replay_mfrr,
)
from open_energy_lab.simulator.restoration_settlement import (
    RestorationSettlement,
    SettlementPriceState,
    build_area_price_proxy_mapping,
    build_day_ahead_energy_price,
    build_directional_activation_price,
    build_directional_capacity_price,
    build_throughput_degradation_rule,
    settle_restoration_services,
)
from open_energy_lab.simulator.scenario import BatteryComponent


LIVE_SEMANTICS_VERSION = "fr-restoration-live-demonstration-v1"
DEFAULT_TOLERANCE = 1e-6

_BATTERY = {
    "name": "live-restoration-demonstration-bess",
    "capacity_kwh": 2000.0,
    "max_charge_kw": 500.0,
    "max_discharge_kw": 500.0,
    "charge_efficiency": 0.95,
    "discharge_efficiency": 0.95,
    "initial_soc": 0.5,
    "min_soc": 0.1,
    "max_soc": 0.9,
}
_CAPABILITY = {
    "max_ramp_up_kw_per_second": 500.0,
    "max_ramp_down_kw_per_second": 500.0,
    "max_activation_delay_seconds": {"AFRR": 1.0, "MFRR": 1.0},
    "min_supported_duration_seconds": {"AFRR": 1.0, "MFRR": 1.0},
    "max_supported_duration_seconds": {"AFRR": 3600.0, "MFRR": 3600.0},
}


class LiveRestorationPipelineError(ValueError):
    """Raised when live inputs cannot support the declared demonstration."""


@dataclass(frozen=True, slots=True)
class LiveRestorationPipelineResult:
    """One source-to-settlement live demonstration result held in memory."""

    market: RestorationMarketArtifact
    product: RestorationProduct
    direction: RestorationDirection
    driver_series_id: str
    mapping: DerivedSimulationMapping
    commitments: DirectionalCapacitySchedule
    activation: AFRRActivationTrajectory | MFRRActivationSequence
    baseline: RestorationBaselineBundle
    replay: AFRRReplayResult | MFRRReplayResult
    settlement: RestorationSettlement
    day_ahead_source: str


def _series(
    artifact: RestorationMarketArtifact, series_id: str
) -> RestorationMarketSeries:
    matches = [item for item in artifact.series if item.series_id == series_id]
    if len(matches) != 1:
        raise LiveRestorationPipelineError(
            f"RTE source field {series_id} is missing or ambiguous for "
            f"[{artifact.requested_period.start_utc.isoformat()}, "
            f"{artifact.requested_period.end_utc.isoformat()})"
        )
    return matches[0]


def _product(artifact: RestorationMarketArtifact) -> RestorationProduct:
    if artifact.resource == "standard_afrr_data":
        return RestorationProduct.AFRR
    if artifact.resource == "standard_mfrr_data":
        return RestorationProduct.MFRR
    raise LiveRestorationPipelineError(
        f"unsupported RTE restoration resource {artifact.resource!r}"
    )


def _commitments(
    *,
    product: RestorationProduct,
    artifact: RestorationMarketArtifact,
    committed_capacity_kw: float,
) -> DirectionalCapacitySchedule:
    intervals = [
        {
            "interval": artifact.covered_period,
            "product": product.value,
            "direction": direction.value,
            "committed_capacity_kw": committed_capacity_kw,
            "eligibility": True,
            "source_or_assumption_ref": (
                "notebook-assumption:fixed-bidirectional-live-capacity-v1"
            ),
        }
        for direction in RestorationDirection
    ]
    builder = (
        build_afrr_directional_capacity_schedule
        if product is RestorationProduct.AFRR
        else build_mfrr_directional_capacity_schedule
    )
    return builder(
        schedule_id=f"live-{product.value.lower()}-capacity-v1",
        semantics_version=DIRECTIONAL_CAPACITY_SEMANTICS_VERSION,
        period=artifact.covered_period,
        intervals=intervals,
    )


def _lineage(series: RestorationMarketSeries) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            f"{series.series_id}:{series.series_fingerprint}:"
            f"source-row-{observation.source_row}",
        )
        for observation in series.observations
    )


def _driver_values(
    series: RestorationMarketSeries, *, allow_null: bool
) -> tuple[float | None, ...]:
    values: list[float | None] = []
    for observation in series.observations:
        if observation.value_state is ObservationValueState.VALUE:
            assert observation.value is not None
            values.append(observation.value)
        elif allow_null:
            values.append(None)
        else:
            raise LiveRestorationPipelineError(
                f"RTE source field {series.source_field} is "
                f"{observation.value_state.value} over "
                f"[{observation.interval.start_utc.isoformat()}, "
                f"{observation.interval.end_utc.isoformat()})"
            )
    return tuple(values)


def _mapping(
    *,
    artifact: RestorationMarketArtifact,
    product: RestorationProduct,
    direction: RestorationDirection,
    driver: RestorationMarketSeries,
    values: tuple[float | None, ...],
    commitments: DirectionalCapacitySchedule,
    asset_allocation_fraction: float,
    committed_capacity_kw: float,
) -> DerivedSimulationMapping:
    driver_semantics = (
        "afrr_requested_need"
        if product is RestorationProduct.AFRR
        else "mfrr_sa_requested_volume"
    )
    return build_derived_simulation_mapping(
        {
            "mapping_id": f"live-{product.value.lower()}-{direction.value.lower()}-v1",
            "source_artifact_fingerprint": artifact.artifact_fingerprint,
            "source_series_fingerprints": [driver.series_fingerprint],
            "product": product.value,
            "direction": direction.value,
            "asset_allocation_fraction": asset_allocation_fraction,
            "unit_scale_kw_per_mw": 1000.0,
            "capacity_commitment_ref": commitments.schedule_fingerprint,
            "driver_semantics": driver_semantics,
            "comparison_series": [
                item.series_fingerprint
                for item in sorted(artifact.series, key=lambda item: item.series_id)
                if item.series_id != driver.series_id
            ],
            "assumptions": [
                "RTE values are French control-area aggregates, not asset commands",
                f"only the selected {direction.value} driver series is mapped",
                "the caller-selected allocation is fixed and no request is clipped",
                "the output is a derived simulation scenario",
            ],
            "created_at_utc": artifact.retrieved_at_utc,
            "source_kind": "DERIVED_SIMULATION",
            "output_label": "derived_simulation",
        },
        driver_values_mw=tuple(0.0 if value is None else value for value in values),
        committed_capacity_kw=committed_capacity_kw,
    )


def _activation(
    *,
    artifact: RestorationMarketArtifact,
    product: RestorationProduct,
    direction: RestorationDirection,
    driver: RestorationMarketSeries,
    values: tuple[float | None, ...],
    mapping: DerivedSimulationMapping,
    committed_capacity_kw: float,
) -> AFRRActivationTrajectory | MFRRActivationSequence:
    intervals = tuple(item.interval for item in driver.observations)
    capacities = (committed_capacity_kw,) * len(intervals)
    lineage = _lineage(driver)
    upward = values if direction is RestorationDirection.UPWARD else (None,) * len(values)
    downward = values if direction is RestorationDirection.DOWNWARD else (None,) * len(values)
    if product is RestorationProduct.AFRR:
        return build_afrr_trajectory_from_rte_requested_need(
            trajectory_id=f"live-afrr-{direction.value.lower()}-v1",
            semantics_version=LIVE_SEMANTICS_VERSION,
            period=artifact.covered_period,
            resolution=driver.canonical_resolution,
            created_or_retrieved_at_utc=artifact.retrieved_at_utc,
            mapping=mapping,
            intervals=intervals,
            upward_requested_need_mw=tuple(0.0 if item is None else item for item in upward),
            downward_requested_need_mw=tuple(0.0 if item is None else item for item in downward),
            committed_capacity_kw=capacities,
            source_observation_refs=lineage,
        )
    return build_mfrr_sequence_from_rte_sa_requested_volume(
        sequence_id=f"live-mfrr-{direction.value.lower()}-v1",
        semantics_version=LIVE_SEMANTICS_VERSION,
        period=artifact.covered_period,
        created_or_retrieved_at_utc=artifact.retrieved_at_utc,
        mapping=mapping,
        intervals=intervals,
        upward_requested_volume_mw=upward,
        downward_requested_volume_mw=downward,
        committed_capacity_kw=capacities,
        source_observation_refs=lineage,
    )


def _replay(
    *,
    artifact: RestorationMarketArtifact,
    product: RestorationProduct,
    commitments: DirectionalCapacitySchedule,
    activation: AFRRActivationTrajectory | MFRRActivationSequence,
    driver: RestorationMarketSeries,
    battery: BatteryComponent,
    capability: RestorationCapability,
) -> tuple[RestorationBaselineBundle, AFRRReplayResult | MFRRReplayResult]:
    period = artifact.covered_period
    intervals = tuple(item.interval for item in driver.observations)
    if product is RestorationProduct.AFRR:
        config = build_afrr_baseline_config(
            config_id="live-afrr-zero-baseline-v1",
            semantics_version=LIVE_SEMANTICS_VERSION,
            period=period,
            resolution=driver.canonical_resolution,
            commitments=commitments,
            battery=battery,
            capability=capability,
            mode=AFRRBaselineMode.ZERO,
            fixed_power_kw=None,
        )
        baseline = build_afrr_baseline(config)
    else:
        duration_seconds = (
            intervals[0].end_utc - intervals[0].start_utc
        ).total_seconds()
        config = build_mfrr_baseline_config(
            config_id="live-mfrr-zero-baseline-v1",
            semantics_version=LIVE_SEMANTICS_VERSION,
            period=period,
            resolution=driver.canonical_resolution,
            commitments=commitments,
            battery=battery,
            capability=capability,
            mode=MFRRBaselineMode.ZERO,
            fixed_power_kw=None,
            declared_service_duration_seconds=duration_seconds,
        )
        baseline = build_mfrr_baseline(config)
    grid = build_restoration_integration_grid(
        period=period,
        resolution=driver.canonical_resolution,
        intervals=intervals,
    )
    common = {
        "semantics_version": LIVE_SEMANTICS_VERSION,
        "battery": battery,
        "initial_state": build_initial_state(battery),
        "capability": capability,
        "commitments": commitments,
        "baseline": baseline.baseline,
        "integration_grid": grid,
        "tolerance": DEFAULT_TOLERANCE,
    }
    if product is RestorationProduct.AFRR:
        assert isinstance(activation, AFRRActivationTrajectory)
        request = build_afrr_replay_request(
            request_id="live-afrr-replay-v1",
            activation_trajectory=activation,
            **common,
        )
        return baseline, replay_afrr(request)
    assert isinstance(activation, MFRRActivationSequence)
    request = build_mfrr_replay_request(
        request_id="live-mfrr-replay-v1",
        activation_sequence=activation,
        **common,
    )
    return baseline, replay_mfrr(request)


def _day_ahead_prices(
    *,
    product: RestorationProduct,
    replay: AFRRReplayResult | MFRRReplayResult,
    entsoe_artifact: MarketDataArtifact | RestorationMarketArtifact | None,
) -> tuple[tuple[object, ...], str]:
    if entsoe_artifact is None:
        return (
            tuple(
                build_day_ahead_energy_price(
                    price_id=f"live-zero-day-ahead-{index:04d}",
                    product=product,
                    interval=item.interval,
                    value_state=SettlementPriceState.VALUE,
                    price=0.0,
                    unit="EUR/MWh",
                    currency="EUR",
                    source_or_assumption_ref="notebook-assumption:zero-day-ahead-v1",
                    source_field="declared_zero_day_ahead_price",
                )
                for index, item in enumerate(replay.request.baseline.intervals)
            ),
            "study assumption: zero day-ahead price (no ENTSO-E artifact supplied)",
        )
    supported_profiles = {
        "fr-day-ahead-symmetric-fcr-v1",
        FRANCE_QUARTER_HOUR_DAY_AHEAD_PROFILE_ID,
    }
    if entsoe_artifact.profile_id not in supported_profiles:
        raise LiveRestorationPipelineError(
            "ENTSO-E artifact profile must be the Feature 010 hourly profile "
            "or fr-day-ahead-quarter-hour-v2"
        )
    period = replay.request.integration_grid.period
    if isinstance(entsoe_artifact, MarketDataArtifact):
        covered_period = entsoe_artifact.actual_covered_period
        series = entsoe_artifact.series.get("day_ahead_price")
    else:
        covered_period = entsoe_artifact.covered_period
        matches = [
            item for item in entsoe_artifact.series if item.series_id == "day_ahead_price"
        ]
        series = matches[0] if len(matches) == 1 else None
    if not (
        covered_period.start_utc <= period.start_utc
        and covered_period.end_utc >= period.end_utc
        and series is not None
    ):
        raise LiveRestorationPipelineError(
            "ENTSO-E A44 day_ahead_price does not cover the selected RTE period "
            f"[{period.start_utc.isoformat()}, {period.end_utc.isoformat()})"
        )
    source_field = (
        series.source_value_field
        if isinstance(entsoe_artifact, MarketDataArtifact)
        else series.source_field
    )
    prices = tuple(
        build_day_ahead_energy_price(
            price_id=f"live-entsoe-a44-{index:04d}",
            product=product,
            interval=observation.interval,
            value_state=SettlementPriceState.VALUE,
            price=observation.value,
            unit=series.canonical_unit,
            currency=series.currency or "EUR",
            source_or_assumption_ref=entsoe_artifact.artifact_fingerprint,
            source_field=source_field,
        )
        for index, observation in enumerate(series.observations)
        if observation.interval.end_utc > period.start_utc
        and observation.interval.start_utc < period.end_utc
    )
    return prices, (
        f"ENTSO-E A44 {series.canonical_resolution} day_ahead_price from artifact "
        f"{entsoe_artifact.artifact_fingerprint}; native intervals preserved"
    )


def _capacity_prices(
    *,
    product: RestorationProduct,
    commitments: DirectionalCapacitySchedule,
) -> tuple[object, ...]:
    return tuple(
        build_directional_capacity_price(
            price_id=f"live-zero-capacity-{index:04d}",
            product=product,
            direction=item.direction,
            interval=item.interval,
            value_state=SettlementPriceState.VALUE,
            price=0.0,
            unit="EUR/MW/h",
            currency="EUR",
            eligibility=item.eligibility,
            source_or_assumption_ref="notebook-assumption:zero-capacity-price-v1",
            source_field="declared_zero_capacity_price",
        )
        for index, item in enumerate(commitments.intervals)
    )


def _activation_prices(
    *,
    artifact: RestorationMarketArtifact,
    product: RestorationProduct,
    direction: RestorationDirection,
    mapping: DerivedSimulationMapping,
) -> tuple[object, ...]:
    suffix = direction.value.lower()
    series_id = (
        f"afrr_weighted_average_price_{suffix}"
        if product is RestorationProduct.AFRR
        else f"mfrr_clearing_price_{suffix}"
    )
    series = _series(artifact, series_id)
    proxy = build_area_price_proxy_mapping(
        mapping_id=f"live-{product.value.lower()}-{suffix}-area-price-v1",
        source_artifact_fingerprint=artifact.artifact_fingerprint,
        source_series_fingerprint=series.series_fingerprint,
        derived_activation_mapping_fingerprint=mapping.mapping_fingerprint,
        product=product,
        direction=direction,
        price_field=series.source_field,
        coverage=series.covered_period,
        source_unit=series.source_unit,
        canonical_unit=series.canonical_unit,
        transformation="identity_EUR_per_MWh",
        assumptions=(
            "RTE area price is a scenario proxy, not an asset invoice",
        ),
        output_label="scenario_proxy",
    )
    return tuple(
        build_directional_activation_price(
            price_id=f"live-{product.value.lower()}-{suffix}-{index:04d}",
            product=product,
            direction=direction,
            mfrr_kind=(
                None
                if product is RestorationProduct.AFRR
                else MFRRActivationKind.SCHEDULED
            ),
            interval=observation.interval,
            value_state=SettlementPriceState(observation.value_state.value),
            price=observation.value,
            unit=series.canonical_unit,
            currency=series.currency or "EUR",
            pricing_basis="RTE_AREA_PRICE_PROXY",
            source_or_assumption_ref=artifact.artifact_fingerprint,
            source_field=series.source_field,
            area_price_proxy_mapping=proxy,
        )
        for index, observation in enumerate(series.observations)
    )


def run_live_restoration_pipeline(
    artifact: RestorationMarketArtifact,
    *,
    direction: RestorationDirection | str,
    asset_allocation_fraction: float,
    committed_capacity_kw: float,
    entsoe_day_ahead_artifact: MarketDataArtifact | RestorationMarketArtifact | None = None,
    degradation_proxy_eur_per_kwh: float = 0.02,
) -> LiveRestorationPipelineResult:
    """Map, replay, validate, and settle one selected live directional slice."""

    if not isinstance(artifact, RestorationMarketArtifact):
        raise LiveRestorationPipelineError(
            "artifact must be a validated RestorationMarketArtifact"
        )
    try:
        normalized_direction = RestorationDirection(direction)
    except (TypeError, ValueError) as exc:
        raise LiveRestorationPipelineError(
            "direction must be UPWARD or DOWNWARD"
        ) from exc
    product = _product(artifact)
    suffix = normalized_direction.value.lower()
    driver_id = (
        f"afrr_requested_need_{suffix}"
        if product is RestorationProduct.AFRR
        else f"mfrr_sa_requested_volume_{suffix}"
    )
    driver = _series(artifact, driver_id)
    values = _driver_values(driver, allow_null=False)
    commitments = _commitments(
        product=product,
        artifact=artifact,
        committed_capacity_kw=committed_capacity_kw,
    )
    mapping = _mapping(
        artifact=artifact,
        product=product,
        direction=normalized_direction,
        driver=driver,
        values=values,
        commitments=commitments,
        asset_allocation_fraction=asset_allocation_fraction,
        committed_capacity_kw=committed_capacity_kw,
    )
    activation = _activation(
        artifact=artifact,
        product=product,
        direction=normalized_direction,
        driver=driver,
        values=values,
        mapping=mapping,
        committed_capacity_kw=committed_capacity_kw,
    )
    battery = BatteryComponent(**_BATTERY)
    capability = build_restoration_capability(_CAPABILITY)
    baseline, replay = _replay(
        artifact=artifact,
        product=product,
        commitments=commitments,
        activation=activation,
        driver=driver,
        battery=battery,
        capability=capability,
    )
    day_ahead, day_ahead_source = _day_ahead_prices(
        product=product,
        replay=replay,
        entsoe_artifact=entsoe_day_ahead_artifact,
    )
    settlement = settle_restoration_services(
        settlement_id=f"live-{product.value.lower()}-settlement-v1",
        semantics_version=LIVE_SEMANTICS_VERSION,
        replay_result=replay,
        day_ahead_prices=day_ahead,
        capacity_prices=_capacity_prices(
            product=product, commitments=commitments
        ),
        activation_prices=_activation_prices(
            artifact=artifact,
            product=product,
            direction=normalized_direction,
            mapping=mapping,
        ),
        penalty_rule=None,
        degradation_rule=build_throughput_degradation_rule(
            rule_id="live-throughput-comparison-proxy-v1",
            cost_per_kwh=degradation_proxy_eur_per_kwh,
            unit="EUR/kWh",
            description=(
                "First-order throughput comparison proxy; not an "
                "electrochemical aging model"
            ),
        ),
        require_day_ahead_prices=True,
        require_capacity_prices=True,
        require_activation_prices=True,
        tolerance=DEFAULT_TOLERANCE,
    )
    return LiveRestorationPipelineResult(
        market=artifact,
        product=product,
        direction=normalized_direction,
        driver_series_id=driver_id,
        mapping=mapping,
        commitments=commitments,
        activation=activation,
        baseline=baseline,
        replay=replay,
        settlement=settlement,
        day_ahead_source=day_ahead_source,
    )


__all__ = [
    "LIVE_SEMANTICS_VERSION",
    "LiveRestorationPipelineError",
    "LiveRestorationPipelineResult",
    "run_live_restoration_pipeline",
]
