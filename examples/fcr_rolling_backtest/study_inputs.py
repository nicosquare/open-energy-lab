"""Example-owned deterministic builders for Feature 015 research commands."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
import hashlib
import json
from zoneinfo import ZoneInfo

from open_energy_lab.control import (
    RecoveryWindowActivationBudget,
    RobustFCRBatteryParameters,
    RobustFCRPriceInputs,
    RobustFCRSolvePolicy,
    RobustFCRUncertaintyProfile,
    RollingFCRDayInput,
    TerminalStoredEnergyRule,
    build_rolling_fcr_experiment_profile,
    build_rolling_fcr_study_manifest,
    build_robust_fcr_time_contract,
    derive_non_intraday_horizon_budget,
)
from open_energy_lab.control.fcr_rolling_backtest import (
    AGGREGATION_POLICY,
    FAILURE_POLICY_COUPLED,
    FAILURE_POLICY_INDEPENDENT,
    RESUME_POLICY,
    AcceptedBidPolicy,
    DeliveryDateClassification,
    RollingFCRBatteryBinding,
    RollingFCRDataDescriptor,
    RollingFCRNumericPolicy,
)
from open_energy_lab.market import (
    ActivationImportRequest,
    import_regulation_activation_trace,
)


REFERENCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
BOUNDED_DATES = tuple(date(2023, 6, day) for day in range(17, 21))
PROFILE_IDS = (
    "script-11-relaxation-reset-midnight-v1",
    "script-12-restriction-reset-midnight-v1",
    "script-13-arbitrage-only-midnight-v1",
    "script-14-restriction-rolling-0800-v1",
    "script-15-restriction-rolling-midnight-v1",
)
MARKET_TIMEZONE = "Europe/Paris"
ACTIVATION_CREATED_AT_UTC = datetime(2026, 8, 28, 12, tzinfo=UTC)


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def build_solve_policy(
    *,
    solver_name: str = "highs",
    time_limit_seconds: float = 30.0,
    allow_feasible_incumbent_plan: bool = False,
) -> RobustFCRSolvePolicy:
    return RobustFCRSolvePolicy(
        solver_name=solver_name,
        time_limit_seconds=time_limit_seconds,
        threads=1,
        random_seed=15,
        primal_feasibility_tolerance=1e-7,
        dual_feasibility_tolerance=1e-7,
        mip_feasibility_tolerance=1e-6,
        relative_mip_gap=1e-6,
        objective_comparison_absolute_tolerance_eur=1e-6,
        objective_comparison_relative_tolerance=1e-9,
        allow_feasible_incumbent_plan=allow_feasible_incumbent_plan,
        decision_canonicalization_id="solver-output-kw-1e-9-half-even-v1",
    )


def build_uncertainty() -> RobustFCRUncertaintyProfile:
    recovery = RecoveryWindowActivationBudget(
        recovery_activation_budget_hours=0.25,
        recovery_window_hours=2.25,
        pointwise_activation_lower=-1.0,
        pointwise_activation_upper=1.0,
    )
    return RobustFCRUncertaintyProfile(
        recovery_window=recovery,
        horizon_wide=derive_non_intraday_horizon_budget(
            recovery,
            horizon_hours=24.0,
        ),
    )


def _battery_from_mapping(values: Mapping[str, object]) -> RobustFCRBatteryParameters:
    return RobustFCRBatteryParameters(
        maximum_charge_power_kw=float(values["maximum_charge_power_kw"]),
        maximum_discharge_power_kw=float(values["maximum_discharge_power_kw"]),
        minimum_stored_energy_kwh=float(values["minimum_stored_energy_kwh"]),
        maximum_stored_energy_kwh=float(values["maximum_stored_energy_kwh"]),
        initial_stored_energy_kwh=float(values["initial_stored_energy_kwh"]),
        charge_efficiency=float(values["charge_efficiency"]),
        discharge_efficiency=float(values["discharge_efficiency"]),
    )


def _terminal_from_mapping(values: Mapping[str, object]) -> TerminalStoredEnergyRule:
    return TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=float(
            values["minimum_terminal_stored_energy_kwh"]
        ),
        allow_penalized_shortfall=bool(values["allow_penalized_shortfall"]),
        shortfall_penalty_eur_per_kwh=float(
            values["shortfall_penalty_eur_per_kwh"]
        ),
        rule_id="feature-015-reference-terminal-rule-v1",
    )


def _reference_problem_input(
    reference_fixture: object,
    profile_id: str,
    delivery_date: date,
) -> object:
    try:
        return next(
            item
            for item in reference_fixture.problem_inputs
            if item.profile_id == profile_id
            and item.delivery_date == delivery_date
        )
    except StopIteration as exc:
        raise ValueError(
            "normalized reference fixture does not contain the requested "
            f"profile/date pair: {profile_id} {delivery_date}"
        ) from exc


def _authored_battery() -> RobustFCRBatteryParameters:
    return RobustFCRBatteryParameters(
        maximum_charge_power_kw=10.0,
        maximum_discharge_power_kw=10.0,
        minimum_stored_energy_kwh=0.0,
        maximum_stored_energy_kwh=20.0,
        initial_stored_energy_kwh=10.0,
        charge_efficiency=0.92,
        discharge_efficiency=0.92,
    )


def _authored_terminal() -> TerminalStoredEnergyRule:
    return TerminalStoredEnergyRule(
        minimum_terminal_stored_energy_kwh=10.0,
        allow_penalized_shortfall=True,
        shortfall_penalty_eur_per_kwh=100.0,
        rule_id="feature-015-authored-terminal-v1",
    )


def _data_descriptor(
    kind: str,
    *,
    coverage_dates: tuple[date, ...],
    content_fingerprint: str,
    source_kind: str,
) -> RollingFCRDataDescriptor:
    definitions = {
        "day_ahead_price": (
            "EUR/kWh",
            "positive is a payment for source-positive discharge",
            "PT1H",
            "hourly-delivery-interval-v1",
        ),
        "fcr_capacity_price": (
            "EUR/kW/4h-block",
            "non-negative symmetric capacity payment",
            "PT4H",
            "six-four-hour-delivery-blocks-v1",
        ),
        "regulation_activation": (
            "dimensionless",
            "positive requests upward discharge",
            "PT10S",
            "ten-second-half-open-activation-v1",
        ),
    }
    unit, sign, resolution, mapping = definitions[kind]
    first = min(coverage_dates) - timedelta(days=1)
    last = max(coverage_dates) + timedelta(days=2)
    return RollingFCRDataDescriptor(
        descriptor_id=f"feature-015-{source_kind}-{kind}-v1",
        kind=kind,
        schema_version=f"{source_kind}-descriptor-v1",
        unit=unit,
        sign_convention=sign,
        timezone=MARKET_TIMEZONE,
        temporal_resolution=resolution,
        mapping_rule_id=mapping,
        coverage_start_utc=datetime.combine(first, time(), tzinfo=UTC),
        coverage_end_utc=datetime.combine(last, time(), tzinfo=UTC),
        source_organization="Open Energy Lab",
        source_document_id=f"{source_kind}-{kind}",
        acquisition_cutoff_utc=(
            datetime.combine(first, time(), tzinfo=UTC) - timedelta(days=1)
        ),
        content_sha256=content_fingerprint,
        normalized_data_fingerprint=fingerprint(
            {"content": content_fingerprint, "mapping": mapping}
        ),
        provenance={
            "kind": source_kind,
            "retention": "fingerprint_and_normalized_values_only",
        },
    )


def _date_classifications(
    profile_id: str,
    dates: tuple[date, ...],
) -> tuple[DeliveryDateClassification, ...]:
    values = []
    for index, delivery_date in enumerate(dates):
        if profile_id == PROFILE_IDS[3]:
            if index == 0:
                role, eligible, reasons = (
                    "warm-up",
                    False,
                    ("initialization_only",),
                )
            elif index == len(dates) - 1:
                role, eligible, reasons = (
                    "close-out",
                    False,
                    ("closes_predecessor",),
                )
            else:
                role, eligible, reasons = "included", True, ()
        else:
            role, eligible, reasons = "included", True, ()
        values.append(
            DeliveryDateClassification(
                delivery_date=delivery_date,
                execution_role=role,
                comparison_eligible=eligible,
                reason_codes=reasons,
            )
        )
    return tuple(values)


def build_manifest(
    profile_id: str,
    *,
    dates: Sequence[date] = BOUNDED_DATES,
    state_carry_policy: str = "source_three_decimal",
    solve_policy: RobustFCRSolvePolicy | None = None,
    reference_fixture: object | None = None,
) -> object:
    ordered_dates = tuple(dates)
    if not ordered_dates or tuple(sorted(ordered_dates)) != ordered_dates:
        raise ValueError("dates must be a nonempty immutable ascending sequence")
    profile = build_rolling_fcr_experiment_profile(profile_id)
    policy = solve_policy or build_solve_policy()
    if reference_fixture is None:
        battery = _authored_battery()
        terminal = _authored_terminal()
        capacity = 20.0
        source_kind = "project_authored"
        lineage = {
            "reference_revision": REFERENCE_REVISION,
            "fixture_status": "not_required_for_authored_case",
        }
        content = fingerprint(
            {
                "profile_id": profile_id,
                "dates": [item.isoformat() for item in ordered_dates],
            }
        )
    else:
        first_input = _reference_problem_input(
            reference_fixture,
            profile_id,
            ordered_dates[0],
        )
        battery = _battery_from_mapping(first_input.battery)
        terminal = _terminal_from_mapping(first_input.terminal_rule)
        capacity = 100.0
        source_kind = "normalized_reference"
        lineage = {
            "reference_revision": (
                reference_fixture.reference_provenance.reference_revision
            ),
            "fixture_fingerprint": reference_fixture.fixture_fingerprint,
        }
        content = reference_fixture.fixture_fingerprint
    binding = RollingFCRBatteryBinding(
        optimization_battery=battery,
        capacity_kwh=capacity,
        component_name=f"feature-015-{source_kind}-battery",
        replay_timestep_seconds=900,
    )
    return build_rolling_fcr_study_manifest(
        study_id=f"feature-015-{source_kind}-{profile_id}",
        profile=profile,
        dates=_date_classifications(profile_id, ordered_dates),
        day_ahead_descriptor=_data_descriptor(
            "day_ahead_price",
            coverage_dates=ordered_dates,
            content_fingerprint=content,
            source_kind=source_kind,
        ),
        fcr_capacity_descriptor=_data_descriptor(
            "fcr_capacity_price",
            coverage_dates=ordered_dates,
            content_fingerprint=content,
            source_kind=source_kind,
        ),
        activation_descriptor=_data_descriptor(
            "regulation_activation",
            coverage_dates=ordered_dates,
            content_fingerprint=content,
            source_kind=source_kind,
        ),
        battery_binding=binding,
        uncertainty_profile=build_uncertainty(),
        terminal_rule=terminal,
        solve_policy=policy,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        acceptance_policy=AcceptedBidPolicy(
            policy_id=f"feature-015-{source_kind}-accepted-bid-v1",
            kind="assumed_accepted",
            assumption_statement=(
                "optimizer-selected schedules are assumed accepted for this "
                "offline research profile"
            ),
        ),
        numeric_policy=RollingFCRNumericPolicy(
            state_carry_policy=state_carry_policy,
            decimal_places=(
                3 if state_carry_policy == "source_three_decimal" else 0
            ),
        ),
        failure_policy=(
            FAILURE_POLICY_INDEPENDENT
            if profile.is_independent
            else FAILURE_POLICY_COUPLED
        ),
        aggregation_policy=AGGREGATION_POLICY,
        resume_policy=RESUME_POLICY,
        reference_lineage=lineage,
    )


def build_explicit_manifest(
    profile_id: str,
    *,
    study_id: str,
    dates: Sequence[date],
    state_carry_policy: str,
    solve_policy: RobustFCRSolvePolicy,
    battery_values: Mapping[str, object],
    capacity_kwh: float,
    terminal_values: Mapping[str, object],
    data_fingerprints: Mapping[str, str],
    acceptance_policy: Mapping[str, object],
    bundle_fingerprint: str,
) -> object:
    """Build one caller-supplied research manifest without path discovery."""

    ordered_dates = tuple(dates)
    required_fingerprints = {
        "day_ahead_price",
        "fcr_capacity_price",
        "regulation_activation",
    }
    if set(data_fingerprints) != required_fingerprints:
        raise ValueError(
            "explicit data fingerprints must identify price, FCR, and activation"
        )
    battery = _battery_from_mapping(battery_values)
    terminal = _terminal_from_mapping(terminal_values)
    profile = build_rolling_fcr_experiment_profile(profile_id)
    kind = acceptance_policy.get("kind")
    if kind == "assumed_accepted":
        accepted = AcceptedBidPolicy(
            policy_id=f"{study_id}-accepted-bid-v1",
            kind=kind,
            assumption_statement=str(acceptance_policy.get("statement", "")),
        )
    elif kind == "evidence_backed_accepted":
        descriptor = acceptance_policy.get("evidence_descriptor")
        if not isinstance(descriptor, Mapping):
            raise ValueError(
                "evidence-backed acceptance requires an evidence_descriptor"
            )
        accepted = AcceptedBidPolicy(
            policy_id=f"{study_id}-accepted-bid-v1",
            kind=kind,
            evidence_descriptor=descriptor,
        )
    else:
        raise ValueError("explicit manifest requires an accepted-bid policy")
    binding = RollingFCRBatteryBinding(
        optimization_battery=battery,
        capacity_kwh=capacity_kwh,
        component_name=f"{study_id}-battery",
        replay_timestep_seconds=10,
    )
    return build_rolling_fcr_study_manifest(
        study_id=study_id,
        profile=profile,
        dates=_date_classifications(profile_id, ordered_dates),
        day_ahead_descriptor=_data_descriptor(
            "day_ahead_price",
            coverage_dates=ordered_dates,
            content_fingerprint=data_fingerprints["day_ahead_price"],
            source_kind="explicit_full_history",
        ),
        fcr_capacity_descriptor=_data_descriptor(
            "fcr_capacity_price",
            coverage_dates=ordered_dates,
            content_fingerprint=data_fingerprints["fcr_capacity_price"],
            source_kind="explicit_full_history",
        ),
        activation_descriptor=_data_descriptor(
            "regulation_activation",
            coverage_dates=ordered_dates,
            content_fingerprint=data_fingerprints["regulation_activation"],
            source_kind="explicit_full_history",
        ),
        battery_binding=binding,
        uncertainty_profile=build_uncertainty(),
        terminal_rule=terminal,
        solve_policy=solve_policy,
        settlement_profile="robust-storage-bidding-reference-settlement-v1",
        acceptance_policy=accepted,
        numeric_policy=RollingFCRNumericPolicy(
            state_carry_policy=state_carry_policy,
            decimal_places=(
                3 if state_carry_policy == "source_three_decimal" else 0
            ),
        ),
        failure_policy=(
            FAILURE_POLICY_INDEPENDENT
            if profile.is_independent
            else FAILURE_POLICY_COUPLED
        ),
        aggregation_policy=AGGREGATION_POLICY,
        resume_policy=RESUME_POLICY,
        reference_lineage={
            "reference_revision": REFERENCE_REVISION,
            "explicit_data_bundle_fingerprint": bundle_fingerprint,
            "research_scope": "optional_full_history_non_release_gate",
        },
    )


def _authored_prices(delivery_date: date) -> RobustFCRPriceInputs:
    offset = float((delivery_date - BOUNDED_DATES[0]).days)
    energy = tuple(
        value + 0.001 * offset
        for value in (
            0.050, 0.045, 0.040, 0.035, 0.030, 0.025,
            0.040, 0.055, 0.070, 0.085, 0.100, 0.090,
            0.075, 0.060, 0.050, 0.045, 0.055, 0.070,
            0.095, 0.120, 0.110, 0.090, 0.070, 0.055,
        )
    )
    fcr = tuple(
        value + 0.002 * offset
        for value in (0.060, 0.055, 0.050, 0.052, 0.058, 0.065)
    )
    return _prices(delivery_date, energy=energy, fcr=fcr, source="authored")


def _prices(
    delivery_date: date,
    *,
    energy: Sequence[float],
    fcr: Sequence[float],
    source: str,
) -> RobustFCRPriceInputs:
    return RobustFCRPriceInputs(
        day_ahead_energy_prices_eur_per_kwh=tuple(energy),
        fcr_capacity_prices_eur_per_kw_block=tuple(fcr),
        energy_interval_refs=tuple(
            f"{source}:{delivery_date}:day_ahead:{index}" for index in range(24)
        ),
        fcr_interval_refs=tuple(
            f"{source}:{delivery_date}:fcr:{index}" for index in range(6)
        ),
    )


def build_day_inputs(
    manifest: object,
    *,
    reference_fixture: object | None = None,
) -> tuple[RollingFCRDayInput, ...]:
    values = []
    for classification in manifest.dates:
        delivery_date = classification.delivery_date
        time_contract = build_robust_fcr_time_contract(
            delivery_date=delivery_date,
            market_timezone=MARKET_TIMEZONE,
        )
        if reference_fixture is None:
            prices = _authored_prices(delivery_date)
            battery = manifest.battery_binding.optimization_battery
            source_fingerprint = fingerprint(
                {"kind": "authored", "date": delivery_date.isoformat()}
            )
        else:
            source = _reference_problem_input(
                reference_fixture,
                manifest.profile.profile_id,
                delivery_date,
            )
            prices = _prices(
                delivery_date,
                energy=source.day_ahead_prices_eur_per_kwh,
                fcr=source.fcr_prices_eur_per_kw_block,
                source="normalized_reference",
            )
            battery = _battery_from_mapping(source.battery)
            source_fingerprint = source.input_fingerprint
        if manifest.profile.state_mode == "rolling_0800":
            cutoff = datetime.combine(
                delivery_date - timedelta(days=1),
                time(8),
                tzinfo=ZoneInfo(MARKET_TIMEZONE),
            ).astimezone(UTC)
        else:
            cutoff = time_contract.delivery_period.start_utc - timedelta(hours=12)
        values.append(
            RollingFCRDayInput(
                date_classification=classification,
                time_contract=time_contract,
                battery=battery,
                prices=prices,
                decision_cutoff_utc=cutoff,
                information_cutoff_utc=cutoff,
                producer_input_fingerprints={
                    "market_prices": fingerprint(prices.to_dict()),
                    "battery_binding": manifest.battery_binding.binding_fingerprint,
                    "uncertainty_profile": (
                        fingerprint(manifest.uncertainty_profile.to_dict())
                    ),
                    "numeric_policy": (
                        manifest.numeric_policy.numeric_policy_fingerprint
                    ),
                    "source_problem": source_fingerprint,
                },
                provenance={
                    "source_kind": (
                        "project_authored"
                        if reference_fixture is None
                        else "normalized_reference"
                    ),
                    "information_boundary": "pre_delivery_only",
                },
            )
        )
    return tuple(values)


def build_explicit_day_inputs(
    manifest: object,
    rows: Sequence[Mapping[str, object]],
) -> tuple[RollingFCRDayInput, ...]:
    """Build canonical bidder-visible inputs from an explicit ordered bundle."""

    ordered_rows = tuple(rows)
    expected_dates = tuple(item.delivery_date for item in manifest.dates)
    if len(ordered_rows) != len(expected_dates):
        raise ValueError("explicit day inputs must cover every manifest date")
    values = []
    for expected_date, row in zip(expected_dates, ordered_rows, strict=True):
        required = {
            "delivery_date",
            "day_ahead_prices_eur_per_kwh",
            "fcr_capacity_prices_eur_per_kw_block",
        }
        if set(row) != required:
            raise ValueError("explicit day input keys differ from the v1 bundle")
        delivery_date = date.fromisoformat(str(row["delivery_date"]))
        if delivery_date != expected_date:
            raise ValueError("explicit day inputs differ from manifest date order")
        energy = row["day_ahead_prices_eur_per_kwh"]
        fcr = row["fcr_capacity_prices_eur_per_kw_block"]
        if (
            not isinstance(energy, Sequence)
            or isinstance(energy, (str, bytes))
            or not isinstance(fcr, Sequence)
            or isinstance(fcr, (str, bytes))
        ):
            raise ValueError("explicit price inputs must be sequences")
        prices = _prices(
            delivery_date,
            energy=energy,
            fcr=fcr,
            source="explicit_full_history",
        )
        contract = build_robust_fcr_time_contract(
            delivery_date=delivery_date,
            market_timezone=MARKET_TIMEZONE,
        )
        cutoff = (
            datetime.combine(
                delivery_date - timedelta(days=1),
                time(8),
                tzinfo=ZoneInfo(MARKET_TIMEZONE),
            ).astimezone(UTC)
            if manifest.profile.state_mode == "rolling_0800"
            else contract.delivery_period.start_utc - timedelta(hours=12)
        )
        row_fingerprint = fingerprint(
            {
                "delivery_date": delivery_date.isoformat(),
                "day_ahead_prices_eur_per_kwh": list(energy),
                "fcr_capacity_prices_eur_per_kw_block": list(fcr),
            }
        )
        values.append(
            RollingFCRDayInput(
                date_classification=manifest.dates[len(values)],
                time_contract=contract,
                battery=manifest.battery_binding.optimization_battery,
                prices=prices,
                decision_cutoff_utc=cutoff,
                information_cutoff_utc=cutoff,
                producer_input_fingerprints={
                    "market_prices": fingerprint(prices.to_dict()),
                    "battery_binding": manifest.battery_binding.binding_fingerprint,
                    "uncertainty_profile": (
                        fingerprint(manifest.uncertainty_profile.to_dict())
                    ),
                    "numeric_policy": (
                        manifest.numeric_policy.numeric_policy_fingerprint
                    ),
                    "explicit_day_row": row_fingerprint,
                },
                provenance={
                    "source_kind": "explicit_full_history_data_bundle",
                    "information_boundary": "pre_delivery_only",
                },
            )
        )
    return tuple(values)


def build_explicit_activation_traces(
    manifest: object,
    rows: Sequence[Mapping[str, object]],
) -> dict[date, object]:
    """Import explicitly embedded ten-second samples without searching for data."""

    traces = {}
    manifest_dates = {item.delivery_date for item in manifest.dates}
    for row in rows:
        if set(row) != {"delivery_date", "source_revision", "values"}:
            raise ValueError("explicit activation keys differ from the v1 bundle")
        delivery_date = date.fromisoformat(str(row["delivery_date"]))
        if delivery_date not in manifest_dates or delivery_date in traces:
            raise ValueError("explicit activation date is duplicated or undeclared")
        raw_values = row["values"]
        if not isinstance(raw_values, Sequence) or isinstance(
            raw_values, (str, bytes)
        ):
            raise ValueError("explicit activation values must be a sequence")
        values = tuple(float(item) for item in raw_values)
        if len(values) != 8_640:
            raise ValueError(
                "ordinary full-history activation requires exactly 8,640 samples"
            )
        contract = build_robust_fcr_time_contract(
            delivery_date=delivery_date,
            market_timezone=MARKET_TIMEZONE,
        )
        request = ActivationImportRequest(
            source_name="Feature 015 explicit full-history activation",
            source_locator="explicit-full-history-data-bundle",
            source_revision=str(row["source_revision"]),
            source_timezone=MARKET_TIMEZONE,
            requested_start_utc=contract.delivery_period.start_utc,
            requested_end_utc=contract.delivery_period.end_utc,
            source_resolution="PT10S",
            source_value_kind="interval_average",
            source_sign_meaning="positive requests upward/discharge",
            normalization_rule={
                "conversion": "identity",
                "formula": "activation = explicit_value",
                "point_to_interval": "already_interval_average",
                "clip_min": -1.0,
                "clip_max": 1.0,
                "target_sign": "positive is upward/discharge",
            },
            redistribution_basis={
                "source": "caller-supplied fingerprinted research bundle",
                "terms": "caller-governed",
            },
        )
        timestep = timedelta(seconds=10)
        traces[delivery_date] = import_regulation_activation_trace(
            request,
            tuple(
                {
                    "start_utc": contract.delivery_period.start_utc
                    + index * timestep,
                    "end_utc": contract.delivery_period.start_utc
                    + (index + 1) * timestep,
                    "value": value,
                    "source_value": value,
                    "source_unit": "dimensionless",
                }
                for index, value in enumerate(values)
            ),
            trace_id=f"feature-015-explicit-{delivery_date}-activation-v1",
            created_at_utc=ACTIVATION_CREATED_AT_UTC,
        )
    return traces


def build_authored_activation_traces(
    dates: Sequence[date],
) -> dict[date, object]:
    traces = {}
    pattern = (0.0, 0.25, 0.5, 0.25, 0.0, -0.25, -0.5, -0.25)
    for delivery_date in dates:
        contract = build_robust_fcr_time_contract(
            delivery_date=delivery_date,
            market_timezone=MARKET_TIMEZONE,
        )
        intervals = contract.planning_intervals
        phase = (delivery_date - min(dates)).days
        activation = tuple(
            pattern[(index + phase) % len(pattern)]
            for index in range(len(intervals))
        )
        request = ActivationImportRequest(
            source_name="Feature 015 authored activation",
            source_locator="examples/fcr_rolling_backtest/study_inputs.py",
            source_revision=fingerprint(list(activation)),
            source_timezone=MARKET_TIMEZONE,
            requested_start_utc=contract.delivery_period.start_utc,
            requested_end_utc=contract.delivery_period.end_utc,
            source_resolution="PT15M",
            source_value_kind="interval_average",
            source_sign_meaning="positive requests upward/discharge",
            normalization_rule={
                "conversion": "identity",
                "formula": "activation = authored_value",
                "point_to_interval": "already_interval_average",
                "clip_min": -1.0,
                "clip_max": 1.0,
                "target_sign": "positive is upward/discharge",
            },
            redistribution_basis={
                "source": "project-authored deterministic input",
                "terms": "Apache-2.0",
            },
        )
        traces[delivery_date] = import_regulation_activation_trace(
            request,
            tuple(
                {
                    "start_utc": interval.start_utc,
                    "end_utc": interval.end_utc,
                    "value": value,
                    "source_value": value,
                    "source_unit": "dimensionless",
                }
                for interval, value in zip(intervals, activation, strict=True)
            ),
            trace_id=f"feature-015-authored-{delivery_date}-activation-v1",
            created_at_utc=ACTIVATION_CREATED_AT_UTC,
        )
    return traces


def truncate_manifest(manifest: object, stop_after: int | None) -> object:
    if stop_after is None:
        return manifest
    if stop_after <= 0 or stop_after > len(manifest.dates):
        raise ValueError("stop_after must select at least one declared date")
    selected = list(manifest.dates[:stop_after])
    if manifest.profile.state_mode == "rolling_0800" and len(selected) > 1:
        selected[-1] = replace(
            selected[-1],
            execution_role="close-out",
            comparison_eligible=False,
            reason_codes=("closes_predecessor",),
        )
    return replace(manifest, dates=tuple(selected))


__all__ = [
    "BOUNDED_DATES",
    "PROFILE_IDS",
    "REFERENCE_REVISION",
    "build_authored_activation_traces",
    "build_day_inputs",
    "build_explicit_activation_traces",
    "build_explicit_day_inputs",
    "build_explicit_manifest",
    "build_manifest",
    "build_solve_policy",
    "fingerprint",
    "truncate_manifest",
]
