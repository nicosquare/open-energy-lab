"""Run the gated French stacked-services demonstration entirely offline."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

from open_energy_lab.market import (
    load_market_data_artifact,
    load_regulation_activation_trace,
)
from open_energy_lab.simulator import (
    BatteryComponent,
    MultiRateTimeContract,
    StackedServiceReplayRequest,
    StackedServiceReplayResult,
    TerminalSOCTarget,
    build_energy_baseline_schedule,
    build_fcr_capacity_schedule,
    replay_stacked_services,
)


DEFAULT_FIXTURE_DIR = Path("tests/fixtures/market")
MARKET_FILENAME = "france_2022-08-19_market_v1.json"
ACTIVATION_FILENAME = "france_2022-08-19_activation_v1.json"
EXPECTED_FILENAME = "france_2022-08-19_expected_replay_v1.json"


class OfflineReplayError(ValueError):
    """Raised when gated inputs are absent, incompatible, or do not reproduce."""


def _instant(value: object, *, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise OfflineReplayError(f"{field_name} must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OfflineReplayError(f"{field_name} is not a valid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OfflineReplayError(f"{field_name} must be timezone-aware")
    return parsed.astimezone(UTC)


def _mapping(value: object, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OfflineReplayError(f"{field_name} must be an object")
    return value


def _required_paths(fixture_dir: Path) -> tuple[Path, Path, Path]:
    paths = tuple(
        fixture_dir / name
        for name in (MARKET_FILENAME, ACTIVATION_FILENAME, EXPECTED_FILENAME)
    )
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise OfflineReplayError(
            "credentialed ENTSO-E fixture gate is incomplete; missing "
            + ", ".join(missing)
            + "; see tests/fixtures/market/README.md and do not substitute data"
        )
    return paths


def _schedule_intervals(payload: object, *, field_name: str) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        raise OfflineReplayError(f"{field_name} must be an array")
    intervals: list[dict[str, object]] = []
    for index, value in enumerate(payload):
        item = _mapping(value, field_name=f"{field_name}[{index}]")
        intervals.append(
            {
                **item,
                "start_utc": _instant(
                    item.get("start_utc"),
                    field_name=f"{field_name}[{index}].start_utc",
                ),
                "end_utc": _instant(
                    item.get("end_utc"),
                    field_name=f"{field_name}[{index}].end_utc",
                ),
            }
        )
    return intervals


def run_offline_replay(
    fixture_dir: str | Path = DEFAULT_FIXTURE_DIR,
) -> tuple[StackedServiceReplayResult, dict[str, Any]]:
    """Load, verify, replay, settle, and compare the recorded demonstration."""

    directory = Path(fixture_dir)
    market_path, activation_path, expected_path = _required_paths(directory)
    try:
        expected_raw = json.loads(expected_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OfflineReplayError("expected replay fixture is not valid UTF-8 JSON") from exc
    expected = _mapping(expected_raw, field_name="expected replay fixture")
    if expected.get("schema_version") != "oel.stacked-service-reference.v1":
        raise OfflineReplayError("unsupported expected replay fixture schema")
    period = _mapping(expected.get("period"), field_name="period")
    start = _instant(period.get("start_utc"), field_name="period.start_utc")
    end = _instant(period.get("end_utc"), field_name="period.end_utc")

    market = load_market_data_artifact(market_path)
    activation = load_regulation_activation_trace(activation_path)
    battery_payload = _mapping(expected.get("battery"), field_name="battery")
    battery = BatteryComponent(**battery_payload)
    energy_payload = _mapping(expected.get("energy_schedule"), field_name="energy_schedule")
    energy_schedule = build_energy_baseline_schedule(
        schedule_id=energy_payload["schedule_id"],
        semantics_version=energy_payload["semantics_version"],
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=_schedule_intervals(
            energy_payload.get("intervals"),
            field_name="energy_schedule.intervals",
        ),
    )
    fcr_payload = _mapping(expected.get("fcr_schedule"), field_name="fcr_schedule")
    fcr_schedule = build_fcr_capacity_schedule(
        schedule_id=fcr_payload["schedule_id"],
        semantics_version=fcr_payload["semantics_version"],
        product_identity=fcr_payload["product_identity"],
        covered_start_utc=start,
        covered_end_utc=end,
        intervals=_schedule_intervals(
            fcr_payload.get("intervals"),
            field_name="fcr_schedule.intervals",
        ),
    )
    terminal_payload = _mapping(
        expected.get("terminal_soc_target"),
        field_name="terminal_soc_target",
    )
    request = StackedServiceReplayRequest(
        market_artifact=market,
        activation_trace=activation,
        battery=battery,
        energy_schedule=energy_schedule,
        fcr_schedule=fcr_schedule,
        time_contract=MultiRateTimeContract(
            start_utc=start,
            end_utc=end,
            activation_resolution="PT10S",
            state_checkpoint_resolution="PT15M",
            energy_resolution="PT1H",
            fcr_resolution="PT4H",
            market_timezone="Europe/Paris",
            interval_convention="start-inclusive/end-exclusive",
        ),
        penalty_rule=None,
        terminal_soc_target=TerminalSOCTarget(**terminal_payload),
        numeric_tolerance=1e-6,
        simulation_semantics_version="stacked-service-replay-v1",
    )
    result = replay_stacked_services(request)
    recorded = _mapping(expected.get("expected"), field_name="expected")
    totals = _mapping(recorded.get("totals"), field_name="expected.totals")
    fingerprints = _mapping(
        recorded.get("fingerprints"),
        field_name="expected.fingerprints",
    )
    actual_values = {
        "throughput_kwh": result.throughput_kwh,
        "day_ahead_energy_revenue_eur": result.settlement.day_ahead_energy_revenue_eur,
        "fcr_capacity_revenue_eur": result.settlement.fcr_capacity_revenue_eur,
        "penalty_eur": result.settlement.penalty_eur,
        "total_profit_eur": result.settlement.total_profit_eur,
    }
    for name, actual in actual_values.items():
        recorded_value = totals.get(name)
        if not isinstance(recorded_value, (int, float)) or abs(actual - recorded_value) > 1e-6:
            raise OfflineReplayError(
                f"recorded {name} does not reproduce: expected {recorded_value}, got {actual}"
            )
    actual_fingerprints = {
        "market_artifact": market.artifact_fingerprint,
        "activation_artifact": activation.artifact_fingerprint,
        "energy_schedule": energy_schedule.schedule_fingerprint,
        "fcr_schedule": fcr_schedule.schedule_fingerprint,
        "trace": result.trace_fingerprint,
        "result": result.result_fingerprint,
    }
    for name, actual in actual_fingerprints.items():
        if fingerprints.get(name) != actual:
            raise OfflineReplayError(f"recorded {name} fingerprint does not reproduce")
    return result, expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    args = parser.parse_args(argv)
    try:
        result, _ = run_offline_replay(args.fixture_dir)
    except (OSError, TypeError, ValueError) as exc:
        print(f"offline replay failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.settlement.to_dict(), indent=2, sort_keys=True))
    print(f"trace_fingerprint={result.trace_fingerprint}")
    print(f"result_fingerprint={result.result_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
