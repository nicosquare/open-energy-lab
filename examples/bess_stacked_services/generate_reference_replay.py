"""Generate the French reference replay under its restricted-data boundary.

The default workflow writes only beneath the Git-ignored ``artifacts/`` tree.
Writing elsewhere requires market metadata produced by the explicit private-
repository staging workflow. That metadata permits restricted repository
storage but prohibits public publication and package or release distribution.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import UTC, datetime
import json
import math
import os
from pathlib import Path
import tempfile

from open_energy_lab.control import (
    PriceThresholdConfig,
    StackedHeuristicConfig,
    build_stacked_heuristic_baseline,
)
from open_energy_lab.market import (
    MarketDataArtifact,
    load_market_data_artifact,
    load_regulation_activation_trace,
)
from open_energy_lab.simulator import (
    BatteryComponent,
    MultiRateTimeContract,
    StackedServiceReplayRequest,
    TerminalSOCTarget,
    build_fcr_capacity_schedule,
    replay_stacked_services,
)


REFERENCE_START = datetime(2022, 8, 18, 22, tzinfo=UTC)
REFERENCE_END = datetime(2022, 8, 19, 22, tzinfo=UTC)
DEFAULT_ACTIVATION_PATH = Path(
    "tests/fixtures/market/france_2022-08-19_activation_v1.json"
)
DEFAULT_DESTINATION = Path("artifacts/market/reference-gate")
EXPECTED_FILENAME = "france_2022-08-19_expected_replay_v1.json"


class ReferenceReplayGenerationError(ValueError):
    """Raised when the selected artifacts cannot produce the reference replay."""


def _z(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _thaw(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [_thaw(inner) for inner in value]
    return value


def _battery_payload(battery: BatteryComponent) -> dict[str, object]:
    return {
        "name": battery.name,
        "capacity_kwh": battery.capacity_kwh,
        "max_charge_kw": battery.max_charge_kw,
        "max_discharge_kw": battery.max_discharge_kw,
        "charge_efficiency": battery.charge_efficiency,
        "discharge_efficiency": battery.discharge_efficiency,
        "initial_soc": battery.initial_soc,
        "min_soc": battery.min_soc,
        "max_soc": battery.max_soc,
    }


def _private_repository_storage_allowed(market: MarketDataArtifact) -> bool:
    retention = market.retention_and_license
    policy = retention.get("restricted_repository_policy")
    if not isinstance(policy, Mapping):
        return False
    return (
        retention.get("repository_storage")
        == "permitted_private_restricted"
        and retention.get("repository_publication") == "prohibited"
        and policy.get("repository_visibility") == "private"
        and policy.get("authorized_audience") == "repository collaborators"
        and policy.get("repository_storage") == "permitted"
        and policy.get("public_distribution") == "prohibited"
        and policy.get("public_forks_and_mirrors") == "prohibited"
        and policy.get("package_distribution") == "prohibited"
        and policy.get("release_attachment") == "prohibited"
        and policy.get("external_artifact_upload") == "prohibited"
    )


def _restricted_data_policy_payload(
    market: MarketDataArtifact,
) -> dict[str, object]:
    retention = market.retention_and_license
    if _private_repository_storage_allowed(market):
        policy = retention["restricted_repository_policy"]
        assert isinstance(policy, Mapping)
        return {
            "policy_version": policy.get("policy_version"),
            "repository_storage": retention["repository_storage"],
            "repository_publication": retention["repository_publication"],
            "authorized_audience": policy["authorized_audience"],
            "public_distribution": policy["public_distribution"],
            "public_forks_and_mirrors": policy["public_forks_and_mirrors"],
            "package_distribution": policy["package_distribution"],
            "release_attachment": policy["release_attachment"],
            "external_artifact_upload": policy["external_artifact_upload"],
            "source_market_artifact": market.artifact_fingerprint,
        }
    return {
        "policy_version": "oel.local-artifact-only.v1",
        "repository_storage": "prohibited_until_private_staging",
        "repository_publication": "prohibited",
        "authorized_audience": "local operator only",
        "public_distribution": "prohibited",
        "public_forks_and_mirrors": "prohibited",
        "package_distribution": "prohibited",
        "release_attachment": "prohibited",
        "external_artifact_upload": "prohibited",
        "source_market_artifact": market.artifact_fingerprint,
    }


def _is_beneath(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _require_safe_destination(
    market: MarketDataArtifact,
    destination_dir: Path,
) -> None:
    if _private_repository_storage_allowed(market):
        return
    if not _is_beneath(destination_dir, Path("artifacts")):
        raise ReferenceReplayGenerationError(
            "unstaged A44 market data must remain beneath ignored artifacts/; "
            "repository fixture output requires the explicit restricted private-"
            "repository staging policy"
        )


def _reference_battery() -> BatteryComponent:
    return BatteryComponent(
        name="france-reference-bess",
        capacity_kwh=100.0,
        max_charge_kw=50.0,
        max_discharge_kw=50.0,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
        initial_soc=0.5,
        min_soc=0.1,
        max_soc=0.9,
    )


def _build_fcr_schedule(market: MarketDataArtifact):
    volumes = market.series["fcr_contracted_volume"].observations
    prices = market.series["fcr_capacity_price"].observations
    if len(volumes) != 6 or len(prices) != 6:
        raise ReferenceReplayGenerationError(
            "reference market artifact must contain six aligned FCR blocks"
        )
    return build_fcr_capacity_schedule(
        schedule_id="france-2022-08-19-fcr-v1",
        semantics_version="symmetric-fcr-fixed-v1",
        product_identity={
            "product": "symmetric-fcr",
            "tender": "daily",
            "block_duration": "PT4H",
        },
        covered_start_utc=REFERENCE_START,
        covered_end_utc=REFERENCE_END,
        intervals=[
            {
                "start_utc": volume.interval.start_utc,
                "end_utc": volume.interval.end_utc,
                "capacity_kw": 5.0,
                "volume_observation_ref": f"fcr_contracted_volume:{index}",
                "price_observation_ref": f"fcr_capacity_price:{index}",
            }
            for index, (volume, price) in enumerate(
                zip(volumes, prices, strict=True)
            )
            if volume.interval.start_utc == price.interval.start_utc
            and volume.interval.end_utc == price.interval.end_utc
        ],
    )


def _threshold_request(price: float) -> float:
    if price < 475.0:
        return 5.0
    if price > 540.0:
        return -5.0
    return 0.0


def _baseline_derivation(
    market: MarketDataArtifact,
    *,
    battery: BatteryComponent,
    fcr_schedule: object,
    baseline: object,
) -> dict[str, object]:
    observations = market.series["day_ahead_price"].observations
    energy_intervals = baseline.energy_schedule.intervals
    records: list[dict[str, object]] = []
    for index, (observation, interval) in enumerate(
        zip(observations, energy_intervals, strict=True)
    ):
        commitments = [
            item
            for item in fcr_schedule.intervals
            if item.interval.start_utc <= observation.interval.start_utc
            and observation.interval.end_utc <= item.interval.end_utc
        ]
        if len(commitments) != 1:
            raise ReferenceReplayGenerationError(
                f"energy interval {index} does not map to one FCR commitment"
            )
        reserve_kw = commitments[0].capacity_kw
        lower_kw = -battery.max_discharge_kw + reserve_kw
        upper_kw = battery.max_charge_kw - reserve_kw
        unmodified_kw = _threshold_request(observation.value)
        clipped_kw = max(lower_kw, min(upper_kw, unmodified_kw))
        if not math.isclose(
            interval.power_kw,
            clipped_kw,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ReferenceReplayGenerationError(
                f"energy interval {index} differs from the independent "
                "threshold/headroom derivation"
            )
        records.append(
            {
                "start_utc": _z(observation.interval.start_utc),
                "end_utc": _z(observation.interval.end_utc),
                "price_observation_ref": f"day_ahead_price:{index}",
                "unmodified_threshold_request_kw": unmodified_kw,
                "admissible_power_interval_kw": [lower_kw, upper_kw],
                "committed_fcr_capacity_kw": reserve_kw,
                "fixed_baseline_power_kw": interval.power_kw,
            }
        )
    return {
        "price_threshold": {
            "charge_below_eur_per_mwh": 475.0,
            "discharge_above_eur_per_mwh": 540.0,
            "charge_request_kw": 5.0,
            "discharge_request_kw": 5.0,
            "controller_name": "feature-010-price-threshold",
            "strict_comparisons": True,
        },
        "headroom_rule": (
            "[-max_discharge_kw + reserve_kw, max_charge_kw - reserve_kw]"
        ),
        "intervals": records,
        "configuration_fingerprint": baseline.configuration_fingerprint,
    }


def _schedule_payload(schedule: object) -> dict[str, object]:
    return {
        "schedule_id": schedule.schedule_id,
        "semantics_version": schedule.semantics_version,
        "intervals": [
            {
                "start_utc": _z(item.interval.start_utc),
                "end_utc": _z(item.interval.end_utc),
                **(
                    {
                        "power_kw": item.power_kw,
                        "schedule_source": item.schedule_source,
                    }
                    if hasattr(item, "power_kw")
                    else {
                        "capacity_kw": item.capacity_kw,
                        "volume_observation_ref": item.volume_observation_ref,
                        "price_observation_ref": item.price_observation_ref,
                    }
                ),
            }
            for item in schedule.intervals
        ],
    }


def _independent_totals(
    market: MarketDataArtifact,
    *,
    energy_schedule: object,
    fcr_schedule: object,
    result: object,
) -> dict[str, float]:
    energy_revenue = sum(
        -interval.power_kw
        / 1000.0
        * (
            (interval.interval.end_utc - interval.interval.start_utc).total_seconds()
            / 3600.0
        )
        * observation.value
        for interval, observation in zip(
            energy_schedule.intervals,
            market.series["day_ahead_price"].observations,
            strict=True,
        )
    )
    fcr_revenue = sum(
        interval.capacity_kw
        / 1000.0
        * (
            (interval.interval.end_utc - interval.interval.start_utc).total_seconds()
            / 3600.0
        )
        * market.series["fcr_capacity_price"].observations[index].value
        for index, interval in enumerate(fcr_schedule.intervals)
    )
    throughput = sum(
        abs(sample.delivered_combined_power_kw)
        * (
            (sample.interval.end_utc - sample.interval.start_utc).total_seconds()
            / 3600.0
        )
        for sample in result.samples
    )
    totals = {
        "throughput_kwh": throughput,
        "day_ahead_energy_revenue_eur": energy_revenue,
        "fcr_capacity_revenue_eur": fcr_revenue,
        "penalty_eur": 0.0,
        "total_profit_eur": energy_revenue + fcr_revenue,
    }
    actual = {
        "throughput_kwh": result.throughput_kwh,
        "day_ahead_energy_revenue_eur": (
            result.settlement.day_ahead_energy_revenue_eur
        ),
        "fcr_capacity_revenue_eur": result.settlement.fcr_capacity_revenue_eur,
        "penalty_eur": result.settlement.penalty_eur,
        "total_profit_eur": result.settlement.total_profit_eur,
    }
    for name, expected_value in totals.items():
        if not math.isclose(
            expected_value,
            actual[name],
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            raise ReferenceReplayGenerationError(
                f"independent {name} calculation does not match replay"
            )
    return totals


def build_reference_replay_payload(
    market: MarketDataArtifact,
    activation_path: str | Path = DEFAULT_ACTIVATION_PATH,
) -> dict[str, object]:
    """Build and independently reconcile the selected reference replay payload."""

    if (
        market.actual_covered_period.start_utc != REFERENCE_START
        or market.actual_covered_period.end_utc != REFERENCE_END
        or len(market.series["day_ahead_price"].observations) != 24
    ):
        raise ReferenceReplayGenerationError(
            "market artifact must be the exact 24-hour 2022-08-19 France profile"
        )
    activation = load_regulation_activation_trace(activation_path)
    if (
        activation.covered_period.start_utc != REFERENCE_START
        or activation.covered_period.end_utc != REFERENCE_END
        or len(activation.samples) != 8_640
    ):
        raise ReferenceReplayGenerationError(
            "activation artifact must be the exact 8,640-sample reference trace"
        )

    battery = _reference_battery()
    fcr_schedule = _build_fcr_schedule(market)
    threshold_config = PriceThresholdConfig(
        charge_below_import_price=475.0,
        discharge_above_import_price=540.0,
        charge_request_kw=5.0,
        discharge_request_kw=5.0,
        controller_name="feature-010-price-threshold",
    )
    baseline = build_stacked_heuristic_baseline(
        StackedHeuristicConfig(
            schedule_id="france-2022-08-19-stacked-heuristic-v1",
            semantics_version="headroom-clipped-price-threshold-v1",
            price_threshold_config=threshold_config,
            fcr_schedule=fcr_schedule,
        ),
        market_artifact=market,
        battery=battery,
    )
    terminal_target = TerminalSOCTarget(
        target_kind="stored_energy_kwh",
        target_value=50.0,
        tolerance=1e-6,
    )
    time_contract = MultiRateTimeContract(
        start_utc=REFERENCE_START,
        end_utc=REFERENCE_END,
        activation_resolution="PT10S",
        state_checkpoint_resolution="PT15M",
        energy_resolution="PT1H",
        fcr_resolution="PT4H",
        market_timezone="Europe/Paris",
        interval_convention="start-inclusive/end-exclusive",
    )
    result = replay_stacked_services(
        StackedServiceReplayRequest(
            market_artifact=market,
            activation_trace=activation,
            battery=baseline.battery,
            energy_schedule=baseline.energy_schedule,
            fcr_schedule=baseline.fcr_schedule,
            time_contract=time_contract,
            penalty_rule=None,
            terminal_soc_target=terminal_target,
            numeric_tolerance=1e-6,
            simulation_semantics_version="stacked-service-replay-v1",
        )
    )
    totals = _independent_totals(
        market,
        energy_schedule=baseline.energy_schedule,
        fcr_schedule=baseline.fcr_schedule,
        result=result,
    )
    return {
        "schema_version": "oel.stacked-service-reference.v1",
        "restricted_data_policy": _restricted_data_policy_payload(market),
        "period": {
            "start_utc": _z(REFERENCE_START),
            "end_utc": _z(REFERENCE_END),
            "market_timezone": "Europe/Paris",
            "local_delivery_day": "2022-08-19",
            "interval_convention": "start-inclusive/end-exclusive",
        },
        "battery": _battery_payload(baseline.battery),
        "baseline_derivation": _baseline_derivation(
            market,
            battery=baseline.battery,
            fcr_schedule=baseline.fcr_schedule,
            baseline=baseline,
        ),
        "energy_schedule": _schedule_payload(baseline.energy_schedule),
        "fcr_schedule": {
            **_schedule_payload(baseline.fcr_schedule),
            "product_identity": _thaw(baseline.fcr_schedule.product_identity),
        },
        "terminal_soc_target": terminal_target.to_dict(),
        "expected": {
            "counts": {
                "energy_intervals": len(baseline.energy_schedule.intervals),
                "checkpoint_intervals": len(result.checkpoint_summaries),
                "fcr_blocks": len(baseline.fcr_schedule.intervals),
                "activation_samples": len(result.samples),
                "saturation_events": len(result.saturation_events),
            },
            "totals": totals,
            "tracking_summary": _thaw(result.tracking_summary),
            "terminal_soc_report": (
                None
                if result.terminal_soc_report is None
                else result.terminal_soc_report.to_dict()
            ),
            "fingerprints": {
                "market_artifact": market.artifact_fingerprint,
                "activation_artifact": activation.artifact_fingerprint,
                "baseline_configuration": baseline.configuration_fingerprint,
                "energy_schedule": baseline.energy_schedule.schedule_fingerprint,
                "fcr_schedule": baseline.fcr_schedule.schedule_fingerprint,
                "trace": result.trace_fingerprint,
                "result": result.result_fingerprint,
            },
            "independent_checks": {
                "energy_revenue": "sum(-baseline_kw / 1000 * hours * EUR_per_MWh)",
                "fcr_revenue": "sum(capacity_kw / 1000 * hours * EUR_per_MW_h)",
                "throughput": "sum(abs(delivered_combined_kw) * interval_hours)",
                "penalty": "zero because no penalty rule is configured",
                "absolute_tolerance": 1e-6,
            },
        },
    }


def write_reference_replay_fixture(
    market_path: str | Path,
    *,
    activation_path: str | Path = DEFAULT_ACTIVATION_PATH,
    destination_dir: str | Path = DEFAULT_DESTINATION,
) -> Path:
    """Generate and atomically write the replay under its storage boundary."""

    market = load_market_data_artifact(market_path)
    destination = Path(destination_dir)
    _require_safe_destination(market, destination)
    payload = build_reference_replay_payload(market, activation_path)
    try:
        data = (
            json.dumps(
                payload,
                allow_nan=False,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
        destination.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{EXPECTED_FILENAME}.",
            suffix=".tmp",
            dir=destination,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            output = destination / EXPECTED_FILENAME
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)
    except (OSError, TypeError, ValueError) as exc:
        raise ReferenceReplayGenerationError(
            "reference replay fixture could not be written atomically"
        ) from exc
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", type=Path, required=True)
    parser.add_argument(
        "--activation",
        type=Path,
        default=DEFAULT_ACTIVATION_PATH,
    )
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
    )
    args = parser.parse_args(argv)
    try:
        output = write_reference_replay_fixture(
            args.market,
            activation_path=args.activation,
            destination_dir=args.destination,
        )
    except (OSError, TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(f"expected_replay={output}")
    market = load_market_data_artifact(args.market)
    if _private_repository_storage_allowed(market):
        print("repository_storage=permitted_private_restricted")
    else:
        print("repository_storage=ignored_artifacts_only")
    print("repository_publication=prohibited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
