"""Explicit four-day source/native replay using caller-installed activation."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
import hashlib
import math
from pathlib import Path

import pytest

from open_energy_lab.control import (
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRUncertaintyProfile,
    TerminalStoredEnergyRule,
    build_robust_fcr_bidding_problem,
    build_robust_fcr_time_contract,
    derive_non_intraday_horizon_budget,
    solve_robust_fcr_bid,
)
from open_energy_lab.simulator.fcr_bid_plan import (
    BidPlanProducer,
    OptimizationMetric,
    build_fixed_fcr_bid_plan,
)
from oel_validation.fcr_rolling_reference import (
    load_rolling_fcr_reference_fixture,
)
from open_energy_lab.market import (
    ActivationImportRequest,
    build_local_delivery_day,
    import_regulation_activation_trace,
)
from oel_validation.reference_fcr import (
    load_golden_reference_fixture,
)
from open_energy_lab.simulator import evaluate_fixed_fcr_bid
from tests.fcr_rolling_case_utils import build_authored_fixed_plan
from tests.integration.simulator.robust_fcr_replay_utils import (
    build_post_acceptance_battery,
    build_post_acceptance_request,
)


pytestmark = pytest.mark.external_reference_data

ROLLING_FIXTURE_PATH = Path(
    "tests/fixtures/fcr_rolling_backtest/"
    "robust_storage_bidding_experiments_01_05_2023-06-17_20_v1.json"
)
FEATURE_012_FIXTURE_PATH = Path(
    "tests/fixtures/fcr_bid_evaluation/"
    "robust_storage_bidding_2023-06-18_aggregate_v1.json"
)
ACTIVATION_PATH = Path(
    "artifacts/reference/robust_storage_bidding/regulation_signal.csv"
)
PROFILE_ID = "script-12-restriction-reset-midnight-v1"
EXPECTED_DATES = (
    datetime(2023, 6, 17).date(),
    datetime(2023, 6, 18).date(),
    datetime(2023, 6, 19).date(),
    datetime(2023, 6, 20).date(),
)
EXPECTED_ACTIVATION_SHA256 = (
    "0c2bf5203410f193c555460ec5593b546af42556f29afac821584e403c407d13"
)
EXPECTED_ACTIVATION_BYTES = 528_805_941
EXPECTED_HEADER = ("DateTime", "Frequency (Hz)", "xi", "xi_EU")
EXPECTED_SAMPLES_PER_DAY = 8_640
NATIVE_TIME_LIMIT_SECONDS = 60.0


def _external_activation_path_or_skip() -> Path:
    if not ACTIVATION_PATH.is_file():
        pytest.skip(
            "external Feature 015 activation CSV is absent; install the governed "
            f"file explicitly at {ACTIVATION_PATH} and rerun this selected test"
        )
    if ACTIVATION_PATH.is_symlink():
        pytest.fail(f"external activation path must not be a symlink: {ACTIVATION_PATH}")
    return ACTIVATION_PATH


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _build_activation_traces(path: Path, descriptor) -> dict[object, object]:
    """Verify the selected file once, scan once, then delegate importing."""

    assert path.stat().st_size == EXPECTED_ACTIVATION_BYTES
    assert descriptor.byte_count == EXPECTED_ACTIVATION_BYTES
    assert descriptor.sha256 == EXPECTED_ACTIVATION_SHA256
    assert descriptor.header == EXPECTED_HEADER
    assert _file_sha256(path) == EXPECTED_ACTIVATION_SHA256

    rows_by_date: dict[object, list[tuple[datetime, float]]] = {
        item: [] for item in EXPECTED_DATES
    }
    prefixes = {item.isoformat(): item for item in EXPECTED_DATES}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == EXPECTED_HEADER
        for row_number, row in enumerate(reader, start=2):
            timestamp_text = row.get("DateTime")
            if not isinstance(timestamp_text, str):
                continue
            selected_date = prefixes.get(timestamp_text[:10])
            if selected_date is None:
                continue
            try:
                timestamp = datetime.strptime(
                    timestamp_text, "%Y-%m-%d %H:%M:%S"
                )
                value = float(row[descriptor.selected_column])
            except (KeyError, TypeError, ValueError) as exc:
                pytest.fail(
                    f"invalid selected activation row {row_number}: {exc}"
                )
            assert math.isfinite(value)
            assert -1.0 <= value <= 1.0
            rows_by_date[selected_date].append((timestamp, value))

    traces = {}
    for delivery_date in EXPECTED_DATES:
        intervals = build_local_delivery_day(
            delivery_date,
            resolution=descriptor.selected_resolution,
            market_timezone="Europe/Paris",
        )
        selected_rows = rows_by_date[delivery_date]
        assert len(intervals) == len(selected_rows) == EXPECTED_SAMPLES_PER_DAY
        samples = []
        for index, ((timestamp, value), interval) in enumerate(
            zip(selected_rows, intervals, strict=True)
        ):
            assert timestamp == interval.local_start.replace(tzinfo=None), (
                f"activation timestamp mismatch at {delivery_date} row {index}"
            )
            samples.append(
                {
                    "start_utc": interval.start_utc,
                    "end_utc": interval.end_utc,
                    "value": value,
                    "source_value": value,
                    "source_unit": "dimensionless",
                }
            )
        request = ActivationImportRequest(
            source_name="robust-storage-bidding regulation signal",
            source_locator=ACTIVATION_PATH.as_posix(),
            source_revision=EXPECTED_ACTIVATION_SHA256,
            source_timezone="Europe/Paris",
            requested_start_utc=intervals[0].start_utc,
            requested_end_utc=intervals[-1].end_utc,
            source_resolution=descriptor.selected_resolution,
            source_value_kind="interval_average",
            source_sign_meaning=(
                "positive xi_EU means upward/discharge activation"
            ),
            normalization_rule={
                "conversion": "identity",
                "formula": "activation = xi_EU",
                "point_to_interval": "already_interval_average",
                "clip_min": -1.0,
                "clip_max": 1.0,
                "target_sign": "positive is upward/discharge",
            },
            redistribution_basis={
                "retention_status": descriptor.retention_status,
                "redistribution_policy": dict(descriptor.redistribution_policy),
            },
            source_sha256=EXPECTED_ACTIVATION_SHA256,
            source_document_type="reference-regulation-csv",
        )
        traces[delivery_date] = import_regulation_activation_trace(
            request,
            samples,
            trace_id=f"{descriptor.input_id}-{delivery_date.isoformat()}",
            created_at_utc=datetime(2026, 8, 28, 12, tzinfo=UTC),
        )
    return traces


def _source_plan(fixture, problem_input, solve_record):
    template = build_authored_fixed_plan(
        problem_input.delivery_date,
        energy_charge_positive_kw=tuple(
            -value
            for value in solve_record.hourly_energy_source_positive_discharge_kw
        ),
        fcr_capacity_kw=solve_record.fcr_capacity_kw,
    )
    return build_fixed_fcr_bid_plan(
        plan_id=(
            f"{fixture.fixture_id}-{PROFILE_ID}-"
            f"{problem_input.delivery_date}-source-plan-v1"
        ),
        producer=BidPlanProducer(
            producer_id="pinned-julia-gurobi-source-incumbent",
            producer_kind="robust",
            producer_version=fixture.reference_provenance.reference_revision,
            configuration_fingerprint=problem_input.input_fingerprint,
            configuration_unavailable_reason=None,
        ),
        information_cutoff_utc=(
            template.energy_schedule.covered_period.start_utc
            - timedelta(hours=12)
        ),
        energy_schedule=template.energy_schedule,
        fcr_schedule=template.fcr_schedule,
        producer_input_fingerprints={
            "normalized_fixture": fixture.fixture_fingerprint,
            "source_problem": problem_input.input_fingerprint,
            "source_solve": solve_record.record_fingerprint,
        },
        solve_status=(
            "optimal"
            if solve_record.solver_evidence.is_optimal
            else "feasible"
        ),
        objective=OptimizationMetric(
            availability="available",
            value=solve_record.objective_eur,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_objective",
        ),
        objective_bound=OptimizationMetric(
            availability="available",
            value=solve_record.best_upper_bound_eur,
            unit="EUR",
            unavailable_reason=None,
            meaning="optimization_bound",
        ),
        diagnostics=(),
    )


def _native_problem(fixture, problem_input):
    battery_values = dict(problem_input.battery)
    battery_values.pop("source_power_sign")
    battery = RobustFCRBatteryParameters(**battery_values)
    time_contract = build_robust_fcr_time_contract(
        delivery_date=problem_input.delivery_date,
        market_timezone="Europe/Paris",
    )
    prices = RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=(
            problem_input.day_ahead_prices_eur_per_kwh
        ),
        fcr_capacity_prices_eur_per_kw_block=(
            problem_input.fcr_prices_eur_per_kw_block
        ),
        energy_interval_refs=tuple(
            f"normalized-reference-day-ahead:{index}" for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"normalized-reference-fcr:{index}" for index in range(6)
        ),
    )
    uncertainty_values = problem_input.uncertainty
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=float(
            uncertainty_values["recovery_activation_budget_hours"]
        ),
        recovery_window_hours=float(
            uncertainty_values["recovery_window_hours"]
        ),
        pointwise_activation_lower=float(
            uncertainty_values["pointwise_activation_bounds"][0]
        ),
        pointwise_activation_upper=float(
            uncertainty_values["pointwise_activation_bounds"][1]
        ),
    )
    horizon = derive_non_intraday_horizon_budget(
        recovery,
        horizon_hours=24.0,
    )
    assert horizon.horizon_activation_budget_hours == pytest.approx(
        uncertainty_values["horizon_activation_budget_hours"]
    )
    terminal_values = problem_input.terminal_rule
    terminal = TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=float(
            terminal_values["minimum_terminal_stored_energy_kwh"]
        ),
        allow_penalized_shortfall=bool(
            terminal_values["allow_penalized_shortfall"]
        ),
        shortfall_penalty_eur_per_kwh=float(
            terminal_values["shortfall_penalty_eur_per_kwh"]
        ),
        rule_id="pinned-reference-terminal-rule-v1",
    )
    policy = RobustFCRSolvePolicy(
        solver_name="highs",
        time_limit_seconds=NATIVE_TIME_LIMIT_SECONDS,
        threads=1,
        random_seed=13,
        primal_feasibility_tolerance=1e-7,
        dual_feasibility_tolerance=1e-7,
        mip_feasibility_tolerance=1e-6,
        relative_mip_gap=1e-6,
        objective_comparison_absolute_tolerance_eur=1e-6,
        objective_comparison_relative_tolerance=1e-9,
        allow_feasible_incumbent_plan=True,
        decision_canonicalization_id="solver-output-kw-1e-9-half-even-v1",
    )
    return build_robust_fcr_bidding_problem(
        problem_id=(
            f"feature-015-external-{problem_input.delivery_date}-restriction-v1"
        ),
        battery=battery,
        time_contract=time_contract,
        prices=prices,
        uncertainty=RobustFCRUncertaintyProfile(
            recovery_window=recovery,
            horizon_wide=horizon,
        ),
        terminal_rule=terminal,
        solve_policy=policy,
        information_cutoff_utc=(
            time_contract.delivery_period.start_utc - timedelta(hours=12)
        ),
        producer_input_fingerprints={
            "normalized_fixture": fixture.fixture_fingerprint,
            "source_problem": problem_input.input_fingerprint,
        },
        provenance={
            "source": "normalized_feature_015_fixture",
            "profile_id": PROFILE_ID,
            "reference_revision": (
                fixture.reference_provenance.reference_revision
            ),
        },
    )


def _replay_request(plan, problem_input, activation_trace):
    battery = problem_input.battery
    return build_post_acceptance_request(
        plan,
        battery=build_post_acceptance_battery(
            capacity_kwh=100.0,
            maximum_charge_power_kw=float(battery["maximum_charge_power_kw"]),
            maximum_discharge_power_kw=float(
                battery["maximum_discharge_power_kw"]
            ),
            minimum_stored_energy_kwh=float(
                battery["minimum_stored_energy_kwh"]
            ),
            maximum_stored_energy_kwh=float(
                battery["maximum_stored_energy_kwh"]
            ),
            initial_stored_energy_kwh=float(
                battery["initial_stored_energy_kwh"]
            ),
            charge_efficiency=float(battery["charge_efficiency"]),
            discharge_efficiency=float(battery["discharge_efficiency"]),
        ),
        activation_trace=activation_trace,
        activation_resolution="PT10S",
        day_ahead_prices_eur_per_mwh=tuple(
            value * 1000.0
            for value in problem_input.day_ahead_prices_eur_per_kwh
        ),
        fcr_capacity_prices_eur_per_kw_block=(
            problem_input.fcr_prices_eur_per_kw_block
        ),
    )


def test_four_day_source_and_native_plans_share_feature_012_external_replay() -> None:
    fixture = load_rolling_fcr_reference_fixture(ROLLING_FIXTURE_PATH)
    feature_012_fixture = load_golden_reference_fixture(
        FEATURE_012_FIXTURE_PATH
    )
    problem_inputs = tuple(
        item for item in fixture.problem_inputs if item.profile_id == PROFILE_ID
    )
    solve_records = tuple(
        item for item in fixture.solve_records if item.profile_id == PROFILE_ID
    )
    assert tuple(item.delivery_date for item in problem_inputs) == EXPECTED_DATES
    assert tuple(item.delivery_date for item in solve_records) == EXPECTED_DATES

    # Build every bidding input before selecting any evaluation-only CSV bytes.
    source_plans = tuple(
        _source_plan(fixture, problem_input, solve_record)
        for problem_input, solve_record in zip(
            problem_inputs, solve_records, strict=True
        )
    )
    native_problems = tuple(
        _native_problem(fixture, problem_input)
        for problem_input in problem_inputs
    )
    assert all(
        "activation" not in key.casefold()
        for problem in native_problems
        for key in problem.producer_input_fingerprints
    )
    activation_path = _external_activation_path_or_skip()

    native_results = tuple(
        solve_robust_fcr_bid(problem, formulation="restriction")
        for problem in native_problems
    )
    native_plans = tuple(item.deployable_plan for item in native_results)
    unavailable = [
        {
            "date": problem_inputs[index].delivery_date.isoformat(),
            "solve_status": result.solver.solve_status,
            "termination_status": result.solver.termination_status,
            "deployability_status": result.deployability_status,
        }
        for index, (plan, result) in enumerate(
            zip(native_plans, native_results, strict=True)
        )
        if plan is None
    ]
    assert not unavailable, f"native accepted plans unavailable: {unavailable}"

    traces = _build_activation_traces(
        activation_path,
        feature_012_fixture.external_activation,
    )
    assert tuple(traces) == EXPECTED_DATES
    assert all(
        len(trace.samples) == EXPECTED_SAMPLES_PER_DAY
        and trace.resolution == "PT10S"
        for trace in traces.values()
    )

    source_reports = []
    native_reports = []
    for problem_input, source_plan, native_plan in zip(
        problem_inputs, source_plans, native_plans, strict=True
    ):
        assert native_plan is not None
        trace = traces[problem_input.delivery_date]
        source_report = evaluate_fixed_fcr_bid(
            _replay_request(source_plan, problem_input, trace)
        )
        native_report = evaluate_fixed_fcr_bid(
            _replay_request(native_plan, problem_input, trace)
        )
        for report in (source_report, native_report):
            assert report.status == "settled"
            assert report.physical_metrics["interval_counts"] == {
                "activation": EXPECTED_SAMPLES_PER_DAY,
                "checkpoint": 96,
                "energy": 24,
                "fcr": 6,
            }
            assert report.trace_fingerprint is not None
            assert report.settlement_fingerprint is not None
            assert report.result_fingerprint is not None
        source_reports.append(source_report)
        native_reports.append(native_report)

    assert len(source_reports) == len(native_reports) == len(EXPECTED_DATES)
    assert all(report.total_profit_eur is not None for report in source_reports)
    assert all(report.total_profit_eur is not None for report in native_reports)
