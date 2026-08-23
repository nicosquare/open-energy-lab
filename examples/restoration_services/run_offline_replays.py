"""Reproduce the restricted aFRR/mFRR references with no source access."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
import json
from pathlib import Path
import sys

if __package__:
    from .generate_reference_results import (
        AFRR_SCENARIO_FILENAME,
        EXPECTED_RESULTS_FILENAME,
        MFRR_SCENARIO_FILENAME,
        ReferenceResultGenerationError,
        build_reference_case,
        build_reference_results_payload,
        load_reference_scenario,
    )
else:
    from generate_reference_results import (
        AFRR_SCENARIO_FILENAME,
        EXPECTED_RESULTS_FILENAME,
        MFRR_SCENARIO_FILENAME,
        ReferenceResultGenerationError,
        build_reference_case,
        build_reference_results_payload,
        load_reference_scenario,
    )
from open_energy_lab.market.restoration_activation import (
    AFRRActivationTrajectory,
    MFRRActivationKind,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_FIXTURE_DIRECTORY = _REPOSITORY_ROOT / "tests/fixtures/restoration"


def _load_recorded(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceResultGenerationError(
            f"recorded expected result cannot be loaded: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReferenceResultGenerationError(
            "recorded expected result must contain one object"
        )
    return payload


def build_offline_audit(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> dict[str, object]:
    """Rebuild both cases and return concise human-facing audit rows."""

    afrr = load_reference_scenario(
        fixture_directory / AFRR_SCENARIO_FILENAME,
        fixture_directory=fixture_directory,
    )
    mfrr = load_reference_scenario(
        fixture_directory / MFRR_SCENARIO_FILENAME,
        fixture_directory=fixture_directory,
    )
    cases = (build_reference_case(afrr), build_reference_case(mfrr))
    rebuilt = build_reference_results_payload(fixture_directory)
    recorded = _load_recorded(fixture_directory / EXPECTED_RESULTS_FILENAME)
    if rebuilt != recorded:
        raise ReferenceResultGenerationError(
            "offline replay differs from the committed expected-result fixture"
        )
    rows = []
    for case in cases:
        activation = case.scenario.activation
        if isinstance(activation, AFRRActivationTrajectory):
            activation_count = len(activation.samples)
            direct_status = "not applicable to aFRR"
        else:
            activation_count = len(activation.events)
            direct_status = str(case.scenario.payload["direct_activation_status"])
        rows.append(
            {
                "product": case.scenario.commitments.product.value,
                "source_profile": case.scenario.market.profile_id,
                "market_fingerprint": case.scenario.market.artifact_fingerprint,
                "scenario_fingerprint": case.scenario.scenario_fingerprint,
                "mapping_fingerprint": case.scenario.mapping.mapping_fingerprint,
                "allocation_fraction": (
                    case.scenario.mapping.asset_allocation_fraction
                ),
                "scenario_label": str(case.scenario.payload["output_label"]),
                "activation_count": activation_count,
                "direct_status": direct_status,
                "requested_energy_kwh": (
                    case.replay.totals.requested_activation_energy_kwh
                ),
                "delivered_energy_kwh": (
                    case.replay.totals.delivered_activation_energy_kwh
                ),
                "undelivered_energy_kwh": (
                    case.replay.totals.undelivered_activation_energy_kwh
                ),
                "terminal_soc": case.replay.samples[-1].state.soc,
                "throughput_kwh": case.replay.totals.throughput_kwh,
                "replay_fingerprint": case.replay.result_fingerprint,
                "settlement_availability": case.settlement.availability.value,
                "gross_revenue_eur": case.settlement.gross_revenue_eur,
                "degradation_cost_eur": case.settlement.degradation_cost_eur,
                "net_result_eur": case.settlement.net_result_eur,
                "price_label": case.settlement.price_mapping_labels[0],
                "settlement_fingerprint": case.settlement.settlement_fingerprint,
                "scheduled_revenue_eur": (
                    None
                    if not hasattr(
                        case.settlement,
                        "activation_revenue_by_mfrr_kind_eur",
                    )
                    else case.settlement.activation_revenue_by_mfrr_kind_eur[
                        MFRRActivationKind.SCHEDULED.value
                    ]
                ),
            }
        )
    return {
        "result_set_fingerprint": rebuilt["result_set_fingerprint"],
        "cases": rows,
    }


def _render_table(
    title: str,
    rows: Sequence[Mapping[str, object]],
    columns: Sequence[tuple[str, str]],
) -> None:
    def render(value: object) -> str:
        if isinstance(value, float):
            return f"{value:.6f}".rstrip("0").rstrip(".")
        return str(value)

    print(title)
    headers = [header for _field, header in columns]
    rendered = [
        [render(row[field]) for field, _header in columns]
        for row in rows
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rendered))
        for index in range(len(headers))
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rendered:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    print()


def run_offline_replays(
    fixture_directory: Path = _FIXTURE_DIRECTORY,
) -> int:
    audit = build_offline_audit(fixture_directory)
    rows = audit["cases"]
    assert isinstance(rows, list)
    _render_table(
        "SOURCE AND MAPPING AUDIT",
        rows,
        (
            ("product", "product"),
            ("source_profile", "source profile"),
            ("allocation_fraction", "fraction"),
            ("scenario_label", "scenario label"),
            ("activation_count", "inputs"),
        ),
    )
    _render_table(
        "PHYSICAL REPLAY AUDIT",
        rows,
        (
            ("product", "product"),
            ("requested_energy_kwh", "requested kWh"),
            ("delivered_energy_kwh", "delivered kWh"),
            ("undelivered_energy_kwh", "undelivered kWh"),
            ("terminal_soc", "terminal SOC"),
            ("throughput_kwh", "throughput kWh"),
        ),
    )
    _render_table(
        "SETTLEMENT AUDIT",
        rows,
        (
            ("product", "product"),
            ("settlement_availability", "availability"),
            ("gross_revenue_eur", "gross EUR"),
            ("degradation_cost_eur", "degradation EUR"),
            ("net_result_eur", "net EUR"),
            ("price_label", "price label"),
        ),
    )
    mfrr_row = next(row for row in rows if row["product"] == "MFRR")
    direct_status = str(mfrr_row["direct_status"])
    if direct_status.startswith("source-null"):
        print("DIRECT source status: source-null; no event fabricated")
    else:
        print(f"DIRECT source status: {direct_status}")
    print(f"result_set_fingerprint={audit['result_set_fingerprint']}")
    print("Interpretation: area-derived simulation, not observed battery dispatch.")
    print("Settlement prices: scenario proxies, not an asset invoice.")
    return 0


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(description=__doc__)


def main(argv: Sequence[str] | None = None) -> int:
    _parser().parse_args(argv)
    try:
        return run_offline_replays()
    except (OSError, ReferenceResultGenerationError, ValueError) as exc:
        print(f"offline replay failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
