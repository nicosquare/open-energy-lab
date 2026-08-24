"""Build and verify the restricted deterministic restoration references.

The command is offline-only.  It reads the two fixed normalized RTE artifacts,
constructs explicitly labelled fixed-fraction scenarios, replays the reference
battery, applies declared study-price proxies, and writes immutable scenario and
expected-result fixtures.  It never imports a live source adapter or reads a
credential.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from open_energy_lab.control.restoration_service import (
    DIRECTIONAL_CAPACITY_SEMANTICS_VERSION,
    AFRRBaselineMode,
    DirectionalCapacitySchedule,
    MFRRBaselineMode,
    RestorationCapability,
    build_afrr_baseline,
    build_afrr_baseline_config,
    build_afrr_directional_capacity_schedule,
    build_mfrr_baseline,
    build_mfrr_baseline_config,
    build_mfrr_directional_capacity_schedule,
    build_restoration_capability,
)
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
    canonical_restoration_json_bytes,
    load_restoration_market_artifact,
)
from open_energy_lab.market.time import CanonicalInterval
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
    AFRRRestorationSettlement,
    MFRRRestorationSettlement,
    SettlementPriceState,
    build_area_price_proxy_mapping,
    build_day_ahead_energy_price,
    build_directional_activation_price,
    build_directional_capacity_price,
    build_throughput_degradation_rule,
    settle_restoration_services,
)
from open_energy_lab.simulator.scenario import BatteryComponent


REFERENCE_SCENARIO_SCHEMA_VERSION = "oel.restoration.reference-scenario.v1"
REFERENCE_RESULTS_SCHEMA_VERSION = "oel.restoration.reference-results.v1"
REFERENCE_DISPLAY_SCHEMA_VERSION = "oel.restoration.notebook-display.v1"
REFERENCE_SEMANTICS_VERSION = "fr-restoration-reference-v1"
ASSET_ALLOCATION_FRACTION = 0.001
ABSOLUTE_TOLERANCE = 1e-6
DEGRADATION_PROXY_EUR_PER_KWH = 0.02
AFRR_MARKET_FILENAME = "france_2026-08-20_afrr_market_v1.json"
MFRR_MARKET_FILENAME = "france_2026-08-15_mfrr_market_v1.json"
AFRR_SCENARIO_FILENAME = "france_2026-08-20_afrr_scenario_v1.json"
MFRR_SCENARIO_FILENAME = "france_2026-08-15_mfrr_scenario_v1.json"
EXPECTED_RESULTS_FILENAME = "france_restoration_expected_results_v1.json"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIRECTORY = _REPOSITORY_ROOT / "tests/fixtures/restoration"
_BATTERY_PAYLOAD = {
    "name": "reference-restoration-bess",
    "capacity_kwh": 2000.0,
    "max_charge_kw": 500.0,
    "max_discharge_kw": 500.0,
    "charge_efficiency": 0.95,
    "discharge_efficiency": 0.95,
    "initial_soc": 0.5,
    "min_soc": 0.1,
    "max_soc": 0.9,
}
_CAPABILITY_PAYLOAD = {
    "max_ramp_up_kw_per_second": 500.0,
    "max_ramp_down_kw_per_second": 500.0,
    "max_activation_delay_seconds": {"AFRR": 1.0, "MFRR": 1.0},
    "min_supported_duration_seconds": {"AFRR": 1.0, "MFRR": 1.0},
    "max_supported_duration_seconds": {"AFRR": 3600.0, "MFRR": 3600.0},
}
_RESTRICTED_POLICY_FIELDS = (
    "repository_storage",
    "repository_publication",
    "package_distribution",
    "release_distribution",
    "public_ci_artifact",
    "public_mirror_or_fork",
    "external_artifact_store",
    "visibility_change_action",
)


class ReferenceResultGenerationError(ValueError):
    """Raised when a restricted scenario or expected result is inconsistent."""


@dataclass(frozen=True, slots=True)
class ReferenceScenario:
    path: Path
    market: RestorationMarketArtifact
    battery: BatteryComponent
    capability: RestorationCapability
    commitments: DirectionalCapacitySchedule
    mapping: DerivedSimulationMapping
    activation: AFRRActivationTrajectory | MFRRActivationSequence
    payload: Mapping[str, object]
    scenario_fingerprint: str


@dataclass(frozen=True, slots=True)
class ReferenceCase:
    scenario: ReferenceScenario
    replay: AFRRReplayResult | MFRRReplayResult
    settlement: AFRRRestorationSettlement | MFRRRestorationSettlement
    payload: Mapping[str, object]


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(canonical_restoration_json_bytes(payload)).hexdigest()


def _finite_json_bytes(payload: Mapping[str, object]) -> bytes:
    try:
        return (
            json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ReferenceResultGenerationError(
            "reference payload is not finite JSON"
        ) from exc


def _read_json(path: Path) -> dict[str, Any]:
    def reject(value: str) -> object:
        raise ReferenceResultGenerationError(
            f"reference fixture contains non-finite value {value}"
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)
    except ReferenceResultGenerationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceResultGenerationError(
            f"reference fixture cannot be loaded: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReferenceResultGenerationError(
            f"reference fixture must contain an object: {path}"
        )
    return payload


def _battery() -> BatteryComponent:
    return BatteryComponent(**_BATTERY_PAYLOAD)


def _capability() -> RestorationCapability:
    return build_restoration_capability(_CAPABILITY_PAYLOAD)


def _series(market: RestorationMarketArtifact, series_id: str) -> RestorationMarketSeries:
    matches = [item for item in market.series if item.series_id == series_id]
    if len(matches) != 1:
        raise ReferenceResultGenerationError(
            f"market artifact must contain exactly one {series_id} series"
        )
    return matches[0]


def _values(series: RestorationMarketSeries) -> tuple[float | None, ...]:
    return tuple(item.value for item in series.observations)


def _lineage(series: RestorationMarketSeries) -> tuple[tuple[str, ...], ...]:
    return tuple(
        (
            f"{series.series_id}:{series.series_fingerprint}:"
            f"source-row-{item.source_row}",
        )
        for item in series.observations
    )


def _combined_lineage(
    *series_values: RestorationMarketSeries,
) -> tuple[tuple[str, ...], ...]:
    lineages = tuple(_lineage(series) for series in series_values)
    if not lineages or len({len(items) for items in lineages}) != 1:
        raise ReferenceResultGenerationError(
            "source lineage series must align one-to-one by interval"
        )
    return tuple(
        tuple(ref for lineage in lineages for ref in lineage[index])
        for index in range(len(lineages[0]))
    )


def _commitments(
    *, product: RestorationProduct, period: CanonicalInterval
) -> DirectionalCapacitySchedule:
    capacity = 450.0 if product is RestorationProduct.AFRR else 400.0
    intervals = [
        {
            "interval": period,
            "product": product.value,
            "direction": direction.value,
            "committed_capacity_kw": capacity,
            "eligibility": True,
            "source_or_assumption_ref": (
                "study-assumption:fixed-bidirectional-capacity-v1"
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
        schedule_id=f"fr-reference-{product.value.lower()}-capacity-v1",
        semantics_version=DIRECTIONAL_CAPACITY_SEMANTICS_VERSION,
        period=period,
        intervals=intervals,
    )


def _mapping(
    *,
    market: RestorationMarketArtifact,
    commitments: DirectionalCapacitySchedule,
    driver: RestorationMarketSeries,
    comparison: Sequence[RestorationMarketSeries],
    direction: RestorationDirection,
    driver_semantics: str,
    driver_values: Sequence[float],
) -> DerivedSimulationMapping:
    product = commitments.product
    return build_derived_simulation_mapping(
        {
            "mapping_id": f"fr-reference-{product.value.lower()}-fraction-v1",
            "source_artifact_fingerprint": market.artifact_fingerprint,
            "source_series_fingerprints": [driver.series_fingerprint],
            "product": product.value,
            "direction": direction.value,
            "asset_allocation_fraction": ASSET_ALLOCATION_FRACTION,
            "unit_scale_kw_per_mw": 1000.0,
            "capacity_commitment_ref": commitments.schedule_fingerprint,
            "driver_semantics": driver_semantics,
            "comparison_series": [
                item.series_fingerprint
                for item in sorted(comparison, key=lambda item: item.series_id)
            ],
            "assumptions": [
                "RTE values are French control-area aggregates, not asset commands",
                "one fixed 0.001 allocation fraction is applied without clipping",
                "the output is a derived simulation scenario",
            ],
            "created_at_utc": market.retrieved_at_utc,
            "source_kind": "DERIVED_SIMULATION",
            "output_label": "derived_simulation",
        },
        driver_values_mw=driver_values,
        committed_capacity_kw=max(
            item.committed_capacity_kw
            for item in commitments.intervals_for(direction)
        ),
    )


def _market_reference(
    market: RestorationMarketArtifact,
    *,
    fixture_name: str,
    driver: RestorationMarketSeries,
    comparison: Sequence[RestorationMarketSeries],
) -> dict[str, object]:
    return {
        "fixture_name": fixture_name,
        "artifact_id": market.artifact_id,
        "artifact_fingerprint": market.artifact_fingerprint,
        "content_fingerprint": market.content_fingerprint,
        "profile_id": market.profile_id,
        "resource": market.resource,
        "requested_period": market.requested_period.to_dict(),
        "retrieved_at_utc": market.retrieved_at_utc,
        "driver_series_id": driver.series_id,
        "driver_series_fingerprint": driver.series_fingerprint,
        "comparison_series_fingerprints": {
            item.series_id: item.series_fingerprint
            for item in sorted(comparison, key=lambda item: item.series_id)
        },
    }


def _scenario_payload(
    *,
    market: RestorationMarketArtifact,
    fixture_name: str,
    commitments: DirectionalCapacitySchedule,
    mapping: DerivedSimulationMapping,
    driver: RestorationMarketSeries,
    comparison: Sequence[RestorationMarketSeries],
    activation: AFRRActivationTrajectory | MFRRActivationSequence,
) -> dict[str, object]:
    product = commitments.product
    payload: dict[str, object] = {
        "schema_version": REFERENCE_SCENARIO_SCHEMA_VERSION,
        "scenario_id": f"fr-2026-reference-{product.value.lower()}-v1",
        "semantics_version": REFERENCE_SEMANTICS_VERSION,
        "product": product.value,
        "source_kind": "DERIVED_SIMULATION",
        "output_label": "derived_simulation",
        "source_market_artifact": _market_reference(
            market,
            fixture_name=fixture_name,
            driver=driver,
            comparison=comparison,
        ),
        "battery": dict(_BATTERY_PAYLOAD),
        "capability": _capability().to_dict(),
        "commitments": commitments.to_dict(),
        "baseline_assumption": {
            "mode": "ZERO",
            "resolution": "PT15M",
            "no_activation_lookahead": True,
        },
        "mapping": mapping.to_dict(),
        "settlement_assumptions": {
            "day_ahead_price_eur_per_mwh": 0.0,
            "capacity_price_eur_per_mw_per_hour": 0.0,
            "activation_price_basis": "RTE_AREA_PRICE_PROXY",
            "non_performance_penalty": "UNCONFIGURED",
            "degradation_proxy_eur_per_kwh": DEGRADATION_PROXY_EUR_PER_KWH,
            "invoice_claim": False,
        },
        "restricted_data_policy": {
            key: market.redistribution_policy[key]
            for key in _RESTRICTED_POLICY_FIELDS
        },
    }
    if product is RestorationProduct.AFRR:
        assert isinstance(activation, AFRRActivationTrajectory)
        payload["activation_trajectory"] = activation.to_dict()
        payload["activation_interpretation"] = (
            "PT15M interval-average simulated power; no interpolation or AGC claim"
        )
    else:
        assert isinstance(activation, MFRRActivationSequence)
        payload["activation_sequence"] = activation.to_dict()
        payload["activation_interpretation"] = (
            "rectangular 15-minute scheduled event assumption; no asset-order claim"
        )
        payload["direct_activation_status"] = (
            "source-null; no direct activation event fabricated"
        )
    payload["scenario_fingerprint"] = _fingerprint(payload)
    return payload


def build_reference_scenario_payloads(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build both fixed-fraction scenario manifests from normalized artifacts."""

    afrr_market = load_restoration_market_artifact(
        fixture_directory / AFRR_MARKET_FILENAME
    )
    mfrr_market = load_restoration_market_artifact(
        fixture_directory / MFRR_MARKET_FILENAME
    )

    afrr_driver = _series(afrr_market, "afrr_requested_need_upward")
    afrr_opposing = _series(afrr_market, "afrr_requested_need_downward")
    afrr_comparison = tuple(
        item for item in afrr_market.series if item is not afrr_driver
    )
    afrr_values = _values(afrr_driver)
    afrr_opposing_values = _values(afrr_opposing)
    if any(value is None for value in (*afrr_values, *afrr_opposing_values)):
        raise ReferenceResultGenerationError(
            "aFRR requested-need values must be present in both directions"
        )
    afrr_commitments = _commitments(
        product=RestorationProduct.AFRR,
        period=afrr_market.requested_period,
    )
    afrr_mapping = _mapping(
        market=afrr_market,
        commitments=afrr_commitments,
        driver=afrr_driver,
        comparison=afrr_comparison,
        direction=RestorationDirection.UPWARD,
        driver_semantics="afrr_requested_need",
        driver_values=tuple(float(value) for value in afrr_values),
    )
    afrr_trajectory = build_afrr_trajectory_from_rte_requested_need(
        trajectory_id="fr-2026-08-20-afrr-derived-v1",
        semantics_version=REFERENCE_SEMANTICS_VERSION,
        period=afrr_market.requested_period,
        resolution="PT15M",
        created_or_retrieved_at_utc=afrr_market.retrieved_at_utc,
        mapping=afrr_mapping,
        intervals=tuple(item.interval for item in afrr_driver.observations),
        upward_requested_need_mw=tuple(float(value) for value in afrr_values),
        downward_requested_need_mw=tuple(
            float(value) for value in afrr_opposing_values
        ),
        committed_capacity_kw=(450.0,) * len(afrr_driver.observations),
        source_observation_refs=_combined_lineage(afrr_driver, afrr_opposing),
    )

    mfrr_driver = _series(mfrr_market, "mfrr_sa_requested_volume_downward")
    mfrr_opposing = _series(mfrr_market, "mfrr_sa_requested_volume_upward")
    mfrr_comparison = tuple(
        item for item in mfrr_market.series if item is not mfrr_driver
    )
    mfrr_values = _values(mfrr_driver)
    if mfrr_values != (357.0,):
        raise ReferenceResultGenerationError(
            "mFRR downward SA driver must equal the verified 357 MW value"
        )
    mfrr_commitments = _commitments(
        product=RestorationProduct.MFRR,
        period=mfrr_market.requested_period,
    )
    mfrr_mapping = _mapping(
        market=mfrr_market,
        commitments=mfrr_commitments,
        driver=mfrr_driver,
        comparison=mfrr_comparison,
        direction=RestorationDirection.DOWNWARD,
        driver_semantics="mfrr_sa_requested_volume",
        driver_values=(357.0,),
    )
    mfrr_sequence = build_mfrr_sequence_from_rte_sa_requested_volume(
        sequence_id="fr-2026-08-15-mfrr-derived-v1",
        semantics_version=REFERENCE_SEMANTICS_VERSION,
        period=mfrr_market.requested_period,
        created_or_retrieved_at_utc=mfrr_market.retrieved_at_utc,
        mapping=mfrr_mapping,
        intervals=tuple(item.interval for item in mfrr_driver.observations),
        upward_requested_volume_mw=_values(mfrr_opposing),
        downward_requested_volume_mw=mfrr_values,
        committed_capacity_kw=(400.0,),
        source_observation_refs=_combined_lineage(mfrr_driver, mfrr_opposing),
    )
    return (
        _scenario_payload(
            market=afrr_market,
            fixture_name=AFRR_MARKET_FILENAME,
            commitments=afrr_commitments,
            mapping=afrr_mapping,
            driver=afrr_driver,
            comparison=afrr_comparison,
            activation=afrr_trajectory,
        ),
        _scenario_payload(
            market=mfrr_market,
            fixture_name=MFRR_MARKET_FILENAME,
            commitments=mfrr_commitments,
            mapping=mfrr_mapping,
            driver=mfrr_driver,
            comparison=mfrr_comparison,
            activation=mfrr_sequence,
        ),
    )


def _write_immutable(path: Path, payload: Mapping[str, object]) -> Path:
    desired = _finite_json_bytes(payload)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != desired:
                raise ReferenceResultGenerationError(
                    f"existing immutable restricted fixture differs: {path.name}"
                )
            return path
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(desired)
                handle.flush()
                os.fsync(handle.fileno())
            if path.exists():
                raise ReferenceResultGenerationError(
                    f"restricted fixture appeared during generation: {path.name}"
                )
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    except ReferenceResultGenerationError:
        raise
    except OSError as exc:
        raise ReferenceResultGenerationError(
            f"restricted fixture could not be written atomically: {path.name}"
        ) from exc
    return path


def write_reference_scenario_fixtures(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> tuple[Path, Path]:
    afrr_payload, mfrr_payload = build_reference_scenario_payloads(fixture_directory)
    return (
        _write_immutable(fixture_directory / AFRR_SCENARIO_FILENAME, afrr_payload),
        _write_immutable(fixture_directory / MFRR_SCENARIO_FILENAME, mfrr_payload),
    )


def _restore_commitments(payload: Mapping[str, Any]) -> DirectionalCapacitySchedule:
    product = RestorationProduct(payload["product"])
    period = CanonicalInterval.from_dict(payload["period"])
    intervals = [
        {
            **item,
            "interval": CanonicalInterval.from_dict(item["interval"]),
        }
        for item in payload["intervals"]
    ]
    builder = (
        build_afrr_directional_capacity_schedule
        if product is RestorationProduct.AFRR
        else build_mfrr_directional_capacity_schedule
    )
    restored = builder(
        schedule_id=payload["schedule_id"],
        semantics_version=payload["semantics_version"],
        period=period,
        intervals=intervals,
    )
    if restored.schedule_fingerprint != payload["schedule_fingerprint"]:
        raise ReferenceResultGenerationError("commitment schedule fingerprint mismatch")
    return restored


def load_reference_scenario(
    scenario_path: Path,
    *,
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> ReferenceScenario:
    """Load and cross-verify a scenario against its exact source artifact."""

    payload = _read_json(scenario_path)
    if payload.get("schema_version") != REFERENCE_SCENARIO_SCHEMA_VERSION:
        raise ReferenceResultGenerationError("unsupported reference scenario schema")
    recorded = payload.get("scenario_fingerprint")
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("scenario_fingerprint", None)
    if not isinstance(recorded, str) or _fingerprint(fingerprint_payload) != recorded:
        raise ReferenceResultGenerationError("scenario_fingerprint mismatch")
    source = payload.get("source_market_artifact")
    if not isinstance(source, Mapping):
        raise ReferenceResultGenerationError("scenario source reference is missing")
    fixture_name = source.get("fixture_name")
    if fixture_name not in {AFRR_MARKET_FILENAME, MFRR_MARKET_FILENAME}:
        raise ReferenceResultGenerationError("scenario source fixture is not fixed")
    market = load_restoration_market_artifact(fixture_directory / str(fixture_name))
    if (
        source.get("artifact_fingerprint") != market.artifact_fingerprint
        or source.get("content_fingerprint") != market.content_fingerprint
        or source.get("profile_id") != market.profile_id
        or source.get("resource") != market.resource
    ):
        raise ReferenceResultGenerationError("scenario source artifact mismatch")

    battery_payload = payload.get("battery")
    capability_payload = payload.get("capability")
    commitment_payload = payload.get("commitments")
    mapping_payload = payload.get("mapping")
    if not all(
        isinstance(item, Mapping)
        for item in (
            battery_payload,
            capability_payload,
            commitment_payload,
            mapping_payload,
        )
    ):
        raise ReferenceResultGenerationError("scenario typed inputs are incomplete")
    battery = BatteryComponent(**dict(battery_payload))
    capability = build_restoration_capability(dict(capability_payload))
    if capability.capability_fingerprint != capability_payload.get(
        "capability_fingerprint"
    ):
        raise ReferenceResultGenerationError("capability fingerprint mismatch")
    commitments = _restore_commitments(commitment_payload)
    mapping = DerivedSimulationMapping.from_dict(mapping_payload)
    if mapping.capacity_commitment_ref != commitments.schedule_fingerprint:
        raise ReferenceResultGenerationError("mapping commitment reference mismatch")
    driver = _series(market, str(source.get("driver_series_id")))
    if (
        mapping.source_artifact_fingerprint != market.artifact_fingerprint
        or mapping.source_series_fingerprints != (driver.series_fingerprint,)
    ):
        raise ReferenceResultGenerationError("mapping source lineage mismatch")

    product = RestorationProduct(payload["product"])
    if product is RestorationProduct.AFRR:
        activation_payload = payload.get("activation_trajectory")
        if not isinstance(activation_payload, Mapping):
            raise ReferenceResultGenerationError("aFRR trajectory is missing")
        activation: AFRRActivationTrajectory | MFRRActivationSequence = (
            AFRRActivationTrajectory.from_dict(activation_payload)
        )
        if activation.mapping_fingerprint != mapping.mapping_fingerprint:
            raise ReferenceResultGenerationError("aFRR mapping fingerprint mismatch")
    else:
        activation_payload = payload.get("activation_sequence")
        if not isinstance(activation_payload, Mapping):
            raise ReferenceResultGenerationError("mFRR sequence is missing")
        activation = MFRRActivationSequence.from_dict(activation_payload)
        if any(
            event.mapping_fingerprint != mapping.mapping_fingerprint
            for event in activation.events
        ):
            raise ReferenceResultGenerationError("mFRR mapping fingerprint mismatch")
    return ReferenceScenario(
        path=scenario_path,
        market=market,
        battery=battery,
        capability=capability,
        commitments=commitments,
        mapping=mapping,
        activation=activation,
        payload=payload,
        scenario_fingerprint=recorded,
    )


def _baseline_and_grid(scenario: ReferenceScenario):
    period = scenario.commitments.period
    if isinstance(scenario.activation, AFRRActivationTrajectory):
        config = build_afrr_baseline_config(
            config_id="fr-reference-afrr-zero-baseline-v1",
            semantics_version=REFERENCE_SEMANTICS_VERSION,
            period=period,
            resolution="PT15M",
            commitments=scenario.commitments,
            battery=scenario.battery,
            capability=scenario.capability,
            mode=AFRRBaselineMode.ZERO,
            fixed_power_kw=None,
        )
        baseline = build_afrr_baseline(config)
        intervals = tuple(item.interval for item in scenario.activation.samples)
    else:
        config = build_mfrr_baseline_config(
            config_id="fr-reference-mfrr-zero-baseline-v1",
            semantics_version=REFERENCE_SEMANTICS_VERSION,
            period=period,
            resolution="PT15M",
            commitments=scenario.commitments,
            battery=scenario.battery,
            capability=scenario.capability,
            mode=MFRRBaselineMode.ZERO,
            fixed_power_kw=None,
            declared_service_duration_seconds=900.0,
        )
        baseline = build_mfrr_baseline(config)
        intervals = (period,)
    grid = build_restoration_integration_grid(
        period=period,
        resolution="PT15M",
        intervals=intervals,
    )
    return baseline, grid


def _replay(scenario: ReferenceScenario):
    baseline, grid = _baseline_and_grid(scenario)
    common = {
        "semantics_version": REFERENCE_SEMANTICS_VERSION,
        "battery": scenario.battery,
        "initial_state": build_initial_state(scenario.battery),
        "capability": scenario.capability,
        "commitments": scenario.commitments,
        "baseline": baseline.baseline,
        "integration_grid": grid,
        "tolerance": ABSOLUTE_TOLERANCE,
    }
    if isinstance(scenario.activation, AFRRActivationTrajectory):
        request = build_afrr_replay_request(
            request_id="fr-reference-afrr-replay-v1",
            activation_trajectory=scenario.activation,
            **common,
        )
        return baseline, replay_afrr(request)
    request = build_mfrr_replay_request(
        request_id="fr-reference-mfrr-replay-v1",
        activation_sequence=scenario.activation,
        **common,
    )
    return baseline, replay_mfrr(request)


def _settle(
    scenario: ReferenceScenario,
    replay: AFRRReplayResult | MFRRReplayResult,
):
    product = scenario.commitments.product
    baseline_intervals = replay.request.baseline.intervals
    day_ahead_prices = [
        build_day_ahead_energy_price(
            price_id=f"{product.value.lower()}-zero-day-ahead-{index:04d}",
            product=product,
            interval=item.interval,
            value_state=SettlementPriceState.VALUE,
            price=0.0,
            unit="EUR/MWh",
            currency="EUR",
            source_or_assumption_ref="study-assumption:zero-day-ahead-v1",
            source_field="declared_zero_day_ahead_price",
        )
        for index, item in enumerate(baseline_intervals)
    ]
    capacity_prices = [
        build_directional_capacity_price(
            price_id=(
                f"{product.value.lower()}-zero-capacity-"
                f"{item.direction.value.lower()}-{index:04d}"
            ),
            product=product,
            direction=item.direction,
            interval=item.interval,
            value_state=SettlementPriceState.VALUE,
            price=0.0,
            unit="EUR/MW/h",
            currency="EUR",
            eligibility=True,
            source_or_assumption_ref="study-assumption:zero-capacity-price-v1",
            source_field="declared_zero_capacity_price",
        )
        for index, item in enumerate(scenario.commitments.intervals)
    ]
    activation_prices = []
    if isinstance(scenario.activation, AFRRActivationTrajectory):
        price_series = _series(
            scenario.market, "afrr_weighted_average_price_upward"
        )
        proxy = build_area_price_proxy_mapping(
            mapping_id="fr-reference-afrr-upward-area-price-v1",
            source_artifact_fingerprint=scenario.market.artifact_fingerprint,
            source_series_fingerprint=price_series.series_fingerprint,
            derived_activation_mapping_fingerprint=(
                scenario.mapping.mapping_fingerprint
            ),
            product=RestorationProduct.AFRR,
            direction=RestorationDirection.UPWARD,
            price_field=price_series.source_field,
            coverage=price_series.covered_period,
            source_unit=price_series.source_unit,
            canonical_unit=price_series.canonical_unit,
            transformation="identity_EUR_per_MWh",
            assumptions=(
                "RTE area weighted-average price is a scenario proxy, not an asset invoice",
            ),
            output_label="scenario_proxy",
        )
        for index, observation in enumerate(price_series.observations):
            if (
                observation.value_state is not ObservationValueState.VALUE
                or observation.value is None
            ):
                raise ReferenceResultGenerationError(
                    "aFRR upward price proxy must be present"
                )
            activation_prices.append(
                build_directional_activation_price(
                    price_id=f"afrr-upward-area-proxy-{index:04d}",
                    product=RestorationProduct.AFRR,
                    direction=RestorationDirection.UPWARD,
                    mfrr_kind=None,
                    interval=observation.interval,
                    value_state=SettlementPriceState.VALUE,
                    price=observation.value,
                    unit="EUR/MWh",
                    currency="EUR",
                    pricing_basis="RTE_AREA_PRICE_PROXY",
                    source_or_assumption_ref=scenario.market.artifact_fingerprint,
                    source_field=price_series.source_field,
                    area_price_proxy_mapping=proxy,
                )
            )
    else:
        price_series = _series(scenario.market, "mfrr_clearing_price_downward")
        observation = price_series.observations[0]
        if (
            observation.value_state is not ObservationValueState.VALUE
            or observation.value is None
        ):
            raise ReferenceResultGenerationError(
                "mFRR downward clearing-price proxy must be present"
            )
        proxy = build_area_price_proxy_mapping(
            mapping_id="fr-reference-mfrr-downward-sa-area-price-v1",
            source_artifact_fingerprint=scenario.market.artifact_fingerprint,
            source_series_fingerprint=price_series.series_fingerprint,
            derived_activation_mapping_fingerprint=(
                scenario.mapping.mapping_fingerprint
            ),
            product=RestorationProduct.MFRR,
            direction=RestorationDirection.DOWNWARD,
            price_field=price_series.source_field,
            coverage=price_series.covered_period,
            source_unit=price_series.source_unit,
            canonical_unit=price_series.canonical_unit,
            transformation="identity_EUR_per_MWh",
            assumptions=(
                "RTE area clearing price is a scheduled-event scenario proxy, not an asset invoice",
            ),
            output_label="scenario_proxy",
        )
        activation_prices.append(
            build_directional_activation_price(
                price_id="mfrr-downward-sa-area-proxy-0000",
                product=RestorationProduct.MFRR,
                direction=RestorationDirection.DOWNWARD,
                mfrr_kind=MFRRActivationKind.SCHEDULED,
                interval=observation.interval,
                value_state=SettlementPriceState.VALUE,
                price=observation.value,
                unit="EUR/MWh",
                currency="EUR",
                pricing_basis="RTE_AREA_PRICE_PROXY",
                source_or_assumption_ref=scenario.market.artifact_fingerprint,
                source_field=price_series.source_field,
                area_price_proxy_mapping=proxy,
            )
        )
    degradation = build_throughput_degradation_rule(
        rule_id=f"{product.value.lower()}-throughput-comparison-proxy-v1",
        cost_per_kwh=DEGRADATION_PROXY_EUR_PER_KWH,
        unit="EUR/kWh",
        description=(
            "First-order throughput comparison proxy; not an electrochemical aging model"
        ),
    )
    return settle_restoration_services(
        settlement_id=f"fr-reference-{product.value.lower()}-settlement-v1",
        semantics_version=REFERENCE_SEMANTICS_VERSION,
        replay_result=replay,
        day_ahead_prices=day_ahead_prices,
        capacity_prices=capacity_prices,
        activation_prices=activation_prices,
        penalty_rule=None,
        degradation_rule=degradation,
        require_day_ahead_prices=True,
        require_capacity_prices=True,
        require_activation_prices=True,
        tolerance=ABSOLUTE_TOLERANCE,
    )


def build_reference_case(scenario: ReferenceScenario) -> ReferenceCase:
    baseline, replay = _replay(scenario)
    settlement = _settle(scenario, replay)
    product = scenario.commitments.product
    payload = {
        "product": product.value,
        "source_market_artifact_fingerprint": (
            scenario.market.artifact_fingerprint
        ),
        "source_market_content_fingerprint": scenario.market.content_fingerprint,
        "scenario_fingerprint": scenario.scenario_fingerprint,
        "mapping_fingerprint": scenario.mapping.mapping_fingerprint,
        "commitments_fingerprint": scenario.commitments.schedule_fingerprint,
        "capability_fingerprint": scenario.capability.capability_fingerprint,
        "baseline_bundle_fingerprint": baseline.bundle_fingerprint,
        "baseline_fingerprint": baseline.baseline.schedule_fingerprint,
        "activation_fingerprint": (
            scenario.activation.trajectory_fingerprint
            if isinstance(scenario.activation, AFRRActivationTrajectory)
            else scenario.activation.sequence_fingerprint
        ),
        "replay_request_fingerprint": replay.request_fingerprint,
        "replay_result": replay.to_dict(),
        "settlement": settlement.to_dict(),
        "audit_labels": {
            "scenario": "derived_simulation",
            "activation_price": "scenario_proxy",
            "invoice_claim": False,
            "non_performance_penalty": "UNCONFIGURED",
            "degradation": "comparison_proxy_not_aging_model",
        },
        "absolute_tolerance": ABSOLUTE_TOLERANCE,
    }
    payload["case_fingerprint"] = _fingerprint(payload)
    return ReferenceCase(
        scenario=scenario,
        replay=replay,
        settlement=settlement,
        payload=payload,
    )


def _reference_display_payload(
    cases: Sequence[ReferenceCase],
) -> dict[str, object]:
    """Build the exact source-only notebook table/plot contract."""

    by_product = {
        case.scenario.commitments.product.value: case for case in cases
    }
    if set(by_product) != {"AFRR", "MFRR"}:
        raise ReferenceResultGenerationError(
            "notebook display requires exactly one aFRR and one mFRR case"
        )

    provenance_rows: list[dict[str, object]] = []
    market_rows: dict[str, list[dict[str, object]]] = {
        "AFRR": [],
        "MFRR": [],
    }
    commitment_rows: list[dict[str, object]] = []
    activation_rows: list[dict[str, object]] = []
    physical_rows: list[dict[str, object]] = []
    performance_rows: list[dict[str, object]] = []
    energy_rows: list[dict[str, object]] = []
    settlement_rows: list[dict[str, object]] = []

    for product in ("AFRR", "MFRR"):
        case = by_product[product]
        scenario = case.scenario
        market = scenario.market
        replay_payload = case.replay.to_dict()
        settlement_payload = case.settlement.to_dict()
        provenance_rows.append(
            {
                "product": product,
                "source": market.source.value,
                "source_version": market.source_version,
                "profile_id": market.profile_id,
                "resource": market.resource,
                "requested_start_utc": (
                    market.requested_period.start_utc.isoformat().replace(
                        "+00:00", "Z"
                    )
                ),
                "requested_end_utc": (
                    market.requested_period.end_utc.isoformat().replace(
                        "+00:00", "Z"
                    )
                ),
                "market_timezone": market.requested_period.market_timezone,
                "artifact_fingerprint": market.artifact_fingerprint,
                "content_fingerprint": market.content_fingerprint,
                "mapping_fingerprint": scenario.mapping.mapping_fingerprint,
                "scenario_fingerprint": scenario.scenario_fingerprint,
                "output_label": "derived_simulation",
                "redistribution": market.redistribution_policy[
                    "repository_publication"
                ],
            }
        )
        for series in sorted(market.series, key=lambda item: item.series_id):
            for observation in series.observations:
                market_rows[product].append(
                    {
                        "product": product,
                        "source": series.source.value,
                        "source_version": series.source_version,
                        "profile_id": market.profile_id,
                        "resource": series.resource,
                        "series_id": series.series_id,
                        "source_field": series.source_field,
                        "process": series.process,
                        "direction": series.direction,
                        "unit": series.canonical_unit,
                        "resolution": series.canonical_resolution,
                        "start_utc": observation.interval.start_utc.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "end_utc": observation.interval.end_utc.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "value_state": observation.value_state.value,
                        "value": observation.value,
                        "series_fingerprint": series.series_fingerprint,
                        "artifact_fingerprint": market.artifact_fingerprint,
                        "transformation": ";".join(series.transformations),
                        "identity": "observed_area_aggregate",
                        "redistribution": market.redistribution_policy[
                            "repository_publication"
                        ],
                    }
                )

        commitments_payload = scenario.payload["commitments"]
        if not isinstance(commitments_payload, Mapping):
            raise ReferenceResultGenerationError(
                "reference commitments display payload is invalid"
            )
        intervals = commitments_payload.get("intervals")
        if isinstance(intervals, (str, bytes)) or not isinstance(intervals, Sequence):
            raise ReferenceResultGenerationError(
                "reference commitment intervals display payload is invalid"
            )
        for interval in intervals:
            if not isinstance(interval, Mapping):
                raise ReferenceResultGenerationError(
                    "reference commitment display row is invalid"
                )
            commitment_rows.append(
                {
                    "product": product,
                    "direction": interval["direction"],
                    "committed_capacity_kw": interval["committed_capacity_kw"],
                    "eligible": interval["eligibility"],
                    "accepted_baseline_power_kw": 0.0,
                    "source_or_assumption_ref": interval[
                        "source_or_assumption_ref"
                    ],
                    "commitment_fingerprint": (
                        scenario.commitments.schedule_fingerprint
                    ),
                }
            )

        activation_payload = scenario.payload[
            "activation_trajectory" if product == "AFRR" else "activation_sequence"
        ]
        if not isinstance(activation_payload, Mapping):
            raise ReferenceResultGenerationError(
                "reference activation display payload is invalid"
            )
        if product == "AFRR":
            samples = activation_payload.get("samples")
            if isinstance(samples, (str, bytes)) or not isinstance(samples, Sequence):
                raise ReferenceResultGenerationError(
                    "aFRR display samples are invalid"
                )
            for sample in samples:
                if not isinstance(sample, Mapping):
                    raise ReferenceResultGenerationError(
                        "aFRR display sample is invalid"
                    )
                interval = sample["interval"]
                assert isinstance(interval, Mapping)
                requested_power = float(sample["requested_balancing_power_kw"])
                activation_rows.append(
                    {
                        "product": product,
                        "kind": "AUTOMATIC",
                        "direction": (
                            "UPWARD"
                            if requested_power < 0
                            else "DOWNWARD" if requested_power > 0 else "ZERO"
                        ),
                        "start_utc": interval["start_utc"],
                        "end_utc": interval["end_utc"],
                        "duration_seconds": 900.0,
                        "requested_balancing_power_kw": requested_power,
                        "source_kind": activation_payload["source_kind"],
                        "output_label": "derived_simulation",
                        "activation_fingerprint": (
                            scenario.activation.trajectory_fingerprint
                        ),
                    }
                )
        else:
            events = activation_payload.get("events")
            if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
                raise ReferenceResultGenerationError(
                    "mFRR display events are invalid"
                )
            for event in events:
                if not isinstance(event, Mapping):
                    raise ReferenceResultGenerationError(
                        "mFRR display event is invalid"
                    )
                requested_start = datetime.fromisoformat(
                    str(event["requested_start_utc"]).replace("Z", "+00:00")
                ).astimezone(UTC)
                requested_duration = sum(
                    float(event[field])
                    for field in (
                        "activation_delay_seconds",
                        "ramp_up_seconds",
                        "hold_seconds",
                        "ramp_down_seconds",
                    )
                )
                requested_end = requested_start + timedelta(
                    seconds=requested_duration
                )
                activation_rows.append(
                    {
                        "product": product,
                        "kind": event["kind"],
                        "direction": event["direction"],
                        "start_utc": event["requested_start_utc"],
                        "end_utc": requested_end.isoformat().replace(
                            "+00:00", "Z"
                        ),
                        "duration_seconds": requested_duration,
                        "requested_balancing_power_kw": event[
                            "requested_power_kw"
                        ],
                        "source_kind": event["source_kind"],
                        "output_label": "derived_simulation",
                        "activation_fingerprint": (
                            scenario.activation.sequence_fingerprint
                        ),
                    }
                )

        samples_payload = replay_payload["samples"]
        assert isinstance(samples_payload, list)
        for sample in samples_payload:
            assert isinstance(sample, Mapping)
            state = sample["state"]
            interval = sample["interval"]
            assert isinstance(state, Mapping)
            assert isinstance(interval, Mapping)
            physical_rows.append(
                {
                    "product": product,
                    "start_utc": interval["start_utc"],
                    "end_utc": interval["end_utc"],
                    "accepted_baseline_power_kw": sample[
                        "accepted_baseline_power_kw"
                    ],
                    "requested_balancing_power_kw": sample[
                        "requested_balancing_power_kw"
                    ],
                    "delivered_balancing_power_kw": sample[
                        "delivered_balancing_power_kw"
                    ],
                    "requested_combined_power_kw": sample[
                        "requested_combined_power_kw"
                    ],
                    "delivered_combined_power_kw": sample[
                        "delivered_combined_power_kw"
                    ],
                    "soc": state["soc"],
                    "upward_power_headroom_kw": sample[
                        "upward_power_headroom_kw"
                    ],
                    "downward_power_headroom_kw": sample[
                        "downward_power_headroom_kw"
                    ],
                    "upward_energy_headroom_kwh": sample[
                        "upward_energy_headroom_kwh"
                    ],
                    "downward_energy_headroom_kwh": sample[
                        "downward_energy_headroom_kwh"
                    ],
                    "tracking_error_kw": sample["tracking_error_kw"],
                    "absolute_tracking_error_kw": sample[
                        "absolute_tracking_error_kw"
                    ],
                    "response_delay_seconds": sample["response_delay_seconds"],
                    "achieved_ramp_kw_per_second": sample[
                        "achieved_ramp_kw_per_second"
                    ],
                    "non_performance_duration_seconds": sample[
                        "non_performance_duration_seconds"
                    ],
                    "causes": list(sample["causes"]),
                    "charge_energy_kwh": sample["charge_energy_kwh"],
                    "discharge_energy_kwh": sample["discharge_energy_kwh"],
                    "net_terminal_energy_kwh": sample[
                        "net_terminal_energy_kwh"
                    ],
                    "requested_activation_energy_kwh": sample[
                        "requested_activation_energy_kwh"
                    ],
                    "delivered_activation_energy_kwh": sample[
                        "delivered_activation_energy_kwh"
                    ],
                    "undelivered_activation_energy_kwh": sample[
                        "undelivered_activation_energy_kwh"
                    ],
                }
            )

        directional = replay_payload["directional_performance"]
        assert isinstance(directional, Mapping)
        for direction, values in directional.items():
            assert isinstance(values, Mapping)
            performance_rows.append(
                {
                    "product": product,
                    "dimension": "direction",
                    "value": direction,
                    "requested_energy_kwh": values["requested_energy_kwh"],
                    "delivered_energy_kwh": values["delivered_energy_kwh"],
                    "undelivered_energy_kwh": values["undelivered_energy_kwh"],
                    "non_performance_duration_seconds": values[
                        "non_performance_duration_seconds"
                    ],
                    "causes": list(values["causes"]),
                }
            )
        if product == "MFRR":
            kind_performance = replay_payload["kind_performance"]
            assert isinstance(kind_performance, Mapping)
            for kind, values in kind_performance.items():
                assert isinstance(values, Mapping)
                performance_rows.append(
                    {
                        "product": product,
                        "dimension": "kind",
                        "value": kind,
                        "requested_energy_kwh": values[
                            "requested_energy_kwh"
                        ],
                        "delivered_energy_kwh": values[
                            "delivered_energy_kwh"
                        ],
                        "undelivered_energy_kwh": values[
                            "undelivered_energy_kwh"
                        ],
                        "non_performance_duration_seconds": values[
                            "non_performance_duration_seconds"
                        ],
                        "causes": list(values["causes"]),
                    }
                )

        totals = replay_payload["totals"]
        assert isinstance(totals, Mapping)
        energy_rows.append(
            {
                "product": product,
                "charge_energy_kwh": totals["charge_energy_kwh"],
                "discharge_energy_kwh": totals["discharge_energy_kwh"],
                "net_terminal_energy_kwh": totals["net_terminal_energy_kwh"],
                "requested_activation_energy_kwh": totals[
                    "requested_activation_energy_kwh"
                ],
                "delivered_activation_energy_kwh": totals[
                    "delivered_activation_energy_kwh"
                ],
                "undelivered_activation_energy_kwh": totals[
                    "undelivered_activation_energy_kwh"
                ],
                "throughput_kwh": totals["throughput_kwh"],
                "terminal_soc": samples_payload[-1]["state"]["soc"],
            }
        )
        settlement_rows.append(
            {
                "product": product,
                "availability": settlement_payload["availability"],
                "day_ahead_energy_revenue_eur": settlement_payload[
                    "day_ahead_energy_revenue_eur"
                ],
                "upward_capacity_revenue_eur": settlement_payload[
                    "upward_capacity_revenue_eur"
                ],
                "downward_capacity_revenue_eur": settlement_payload[
                    "downward_capacity_revenue_eur"
                ],
                "upward_activation_revenue_eur": settlement_payload[
                    "upward_activation_revenue_eur"
                ],
                "downward_activation_revenue_eur": settlement_payload[
                    "downward_activation_revenue_eur"
                ],
                "non_performance_penalty_eur": settlement_payload[
                    "non_performance_penalty_eur"
                ],
                "degradation_cost_eur": settlement_payload[
                    "degradation_cost_eur"
                ],
                "gross_revenue_eur": settlement_payload["gross_revenue_eur"],
                "net_result_eur": settlement_payload["net_result_eur"],
                "price_label": settlement_payload["price_mapping_labels"][0],
                "settlement_fingerprint": settlement_payload[
                    "settlement_fingerprint"
                ],
            }
        )

    afrr_case = by_product["AFRR"]
    mfrr_case = by_product["MFRR"]
    reproducibility_rows = [
        {"input": "semantics_version", "fingerprint_or_value": REFERENCE_SEMANTICS_VERSION},
        {"input": "absolute_tolerance", "fingerprint_or_value": ABSOLUTE_TOLERANCE},
        {"input": "allocation_fraction", "fingerprint_or_value": ASSET_ALLOCATION_FRACTION},
        {"input": "afrr_market", "fingerprint_or_value": afrr_case.scenario.market.artifact_fingerprint},
        {"input": "mfrr_market", "fingerprint_or_value": mfrr_case.scenario.market.artifact_fingerprint},
        {"input": "afrr_mapping", "fingerprint_or_value": afrr_case.scenario.mapping.mapping_fingerprint},
        {"input": "mfrr_mapping", "fingerprint_or_value": mfrr_case.scenario.mapping.mapping_fingerprint},
        {"input": "afrr_commitment", "fingerprint_or_value": afrr_case.scenario.commitments.schedule_fingerprint},
        {"input": "mfrr_commitment", "fingerprint_or_value": mfrr_case.scenario.commitments.schedule_fingerprint},
        {"input": "capability", "fingerprint_or_value": afrr_case.scenario.capability.capability_fingerprint},
        {"input": "afrr_activation", "fingerprint_or_value": afrr_case.payload["activation_fingerprint"]},
        {"input": "mfrr_activation", "fingerprint_or_value": mfrr_case.payload["activation_fingerprint"]},
        {"input": "afrr_replay", "fingerprint_or_value": afrr_case.replay.result_fingerprint},
        {"input": "mfrr_replay", "fingerprint_or_value": mfrr_case.replay.result_fingerprint},
        {"input": "afrr_settlement", "fingerprint_or_value": afrr_case.settlement.settlement_fingerprint},
        {"input": "mfrr_settlement", "fingerprint_or_value": mfrr_case.settlement.settlement_fingerprint},
    ]
    payload: dict[str, object] = {
        "schema_version": REFERENCE_DISPLAY_SCHEMA_VERSION,
        "provenance_rows": provenance_rows,
        "afrr_market_rows": market_rows["AFRR"],
        "mfrr_market_rows": market_rows["MFRR"],
        "commitment_rows": commitment_rows,
        "activation_rows": activation_rows,
        "physical_rows": physical_rows,
        "performance_rows": performance_rows,
        "energy_rows": energy_rows,
        "settlement_rows": settlement_rows,
        "reproducibility_rows": reproducibility_rows,
    }
    payload["notebook_display_fingerprint"] = _fingerprint(payload)
    return payload


def build_reference_display_payload(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> dict[str, object]:
    """Load, replay, and return the exact deterministic notebook display data."""

    scenarios = (
        load_reference_scenario(
            fixture_directory / AFRR_SCENARIO_FILENAME,
            fixture_directory=fixture_directory,
        ),
        load_reference_scenario(
            fixture_directory / MFRR_SCENARIO_FILENAME,
            fixture_directory=fixture_directory,
        ),
    )
    return _reference_display_payload(
        tuple(build_reference_case(scenario) for scenario in scenarios)
    )


def build_reference_results_payload(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> dict[str, object]:
    afrr = load_reference_scenario(
        fixture_directory / AFRR_SCENARIO_FILENAME,
        fixture_directory=fixture_directory,
    )
    mfrr = load_reference_scenario(
        fixture_directory / MFRR_SCENARIO_FILENAME,
        fixture_directory=fixture_directory,
    )
    afrr_case = build_reference_case(afrr)
    mfrr_case = build_reference_case(mfrr)
    display_payload = _reference_display_payload((afrr_case, mfrr_case))
    payload: dict[str, object] = {
        "schema_version": REFERENCE_RESULTS_SCHEMA_VERSION,
        "semantics_version": REFERENCE_SEMANTICS_VERSION,
        "notebook_display_schema_version": REFERENCE_DISPLAY_SCHEMA_VERSION,
        "notebook_display_fingerprint": display_payload[
            "notebook_display_fingerprint"
        ],
        "cases": {
            "AFRR": dict(afrr_case.payload),
            "MFRR": dict(mfrr_case.payload),
        },
        "restricted_data_policy": {
            key: afrr.market.redistribution_policy[key]
            for key in _RESTRICTED_POLICY_FIELDS
        },
        "reproducibility": {
            "network_required": False,
            "credentials_required": False,
            "raw_responses_persisted": False,
            "deterministic_finite_json": True,
        },
    }
    payload["result_set_fingerprint"] = _fingerprint(payload)
    return payload


def write_reference_results_fixture(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> Path:
    return _write_immutable(
        fixture_directory / EXPECTED_RESULTS_FILENAME,
        build_reference_results_payload(fixture_directory),
    )


def generate_all_reference_fixtures(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> tuple[Path, Path, Path]:
    """Write/reuse scenario manifests, then replay and write expected results."""

    afrr, mfrr = write_reference_scenario_fixtures(fixture_directory)
    expected = write_reference_results_fixture(fixture_directory)
    return afrr, mfrr, expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--acknowledge-private-restricted-repository",
        action="store_true",
        help="confirm that all derived fixtures remain private and restricted",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.acknowledge_private_restricted_repository:
        print(
            "reference generation failed: private restricted repository storage "
            "must be explicitly acknowledged",
            file=sys.stderr,
        )
        return 2
    try:
        afrr, mfrr, expected = generate_all_reference_fixtures()
        result = _read_json(expected)
    except (OSError, ReferenceResultGenerationError, ValueError) as exc:
        print(f"reference generation failed: {exc}", file=sys.stderr)
        return 2
    print(f"afrr_scenario={afrr}")
    print(f"mfrr_scenario={mfrr}")
    print(f"expected_results={expected}")
    print(f"result_set_fingerprint={result['result_set_fingerprint']}")
    print(
        "notebook_display_fingerprint="
        f"{result['notebook_display_fingerprint']}"
    )
    print("output_label=derived_simulation")
    print("activation_price_label=scenario_proxy")
    print("repository_publication=prohibited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
