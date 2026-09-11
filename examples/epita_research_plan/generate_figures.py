"""Generate publication-safe OEL evidence for the EPITA research plan.

The figure combines deterministic, offline evidence from two implemented OEL
workflows: reviewed TPM conditional-risk evidence and the authored robust-FCR
walkthrough problem. It never reads the restricted BESS or French
restoration-service fixtures.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from examples.robust_fcr_bidding.run_small_case import build_walkthrough_problem
from open_energy_lab.control import solve_robust_fcr_bid


DEFAULT_OUTPUT_DIRECTORY = Path("tmp/epita-research-plan/figures")
OUTPUT_FILENAME = "oel-research-backbone.pdf"
DEMONSTRATION_MAP_FILENAME = "oel-current-demonstrations.pdf"
TPM_EVIDENCE_PATH = Path("tests/fixtures/tpm/conditional_mio_evidence_v1.json")


@dataclass(frozen=True)
class ResearchBackboneData:
    """Plot-ready values and provenance for the proposal figure."""

    case_names: tuple[str, ...]
    native_probabilities: tuple[float, ...]
    compiled_probabilities_by_encoding: tuple[tuple[str, tuple[float, ...]], ...]
    energy_baseline_kw: tuple[float, ...]
    reserve_by_hour_kw: tuple[float, ...]
    maximum_charge_power_kw: float
    maximum_discharge_power_kw: float
    tpm_evidence_ids: tuple[str, ...]
    robust_result_fingerprint: str


def find_repository_root(start: Path | None = None) -> Path:
    """Resolve the OEL checkout without assuming the caller's working directory."""

    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src/open_energy_lab"
        ).is_dir():
            return candidate
    raise RuntimeError("run the figure generator from inside the OEL checkout")


def _load_tpm_evidence(repository_root: Path) -> tuple[
    tuple[str, ...],
    tuple[float, ...],
    tuple[tuple[str, tuple[float, ...]], ...],
    tuple[str, ...],
]:
    payload: dict[str, Any] = json.loads(
        (repository_root / TPM_EVIDENCE_PATH).read_text(encoding="utf-8")
    )
    records = payload["compiler_fidelity_records"]
    if not records:
        raise ValueError("conditional MIO evidence contains no fidelity records")

    first_cases = records[0]["cases"]
    case_names = tuple(case["case_name"] for case in first_cases)
    native_probabilities = tuple(
        float(case["native"]["conditional_probability"]) for case in first_cases
    )
    compiled_by_encoding: list[tuple[str, tuple[float, ...]]] = []
    evidence_ids: list[str] = []
    for record in records:
        record_case_names = tuple(case["case_name"] for case in record["cases"])
        if record_case_names != case_names:
            raise ValueError("conditional MIO fidelity records use different cases")
        raw_encoding = str(record["encoding"]["mode"])
        encoding = "PWL" if raw_encoding == "piecewise" else raw_encoding.upper()
        compiled_by_encoding.append(
            (
                encoding,
                tuple(
                    float(case["compiled"]["conditional_probability"])
                    for case in record["cases"]
                ),
            )
        )
        evidence_ids.append(str(record["evidence_id"]))

    return (
        case_names,
        native_probabilities,
        tuple(compiled_by_encoding),
        tuple(evidence_ids),
    )


def build_research_backbone_data(
    repository_root: Path | None = None,
) -> ResearchBackboneData:
    """Build deterministic proposal data through reviewed evidence and OEL APIs."""

    root = repository_root or find_repository_root()
    (
        case_names,
        native_probabilities,
        compiled_by_encoding,
        evidence_ids,
    ) = _load_tpm_evidence(root)

    problem = build_walkthrough_problem()
    restriction = solve_robust_fcr_bid(problem, formulation="restriction")
    if restriction.deployable_plan is None or restriction.decisions is None:
        raise RuntimeError(
            "the authored robust-FCR restriction did not produce an eligible plan: "
            f"{restriction.deployability_status}"
        )

    baseline = tuple(
        float(value)
        for value in restriction.decisions.energy_baseline_charge_positive_kw
    )
    block_reserve = tuple(
        float(value) for value in restriction.decisions.fcr_capacity_kw
    )
    reserve_by_hour = tuple(block_reserve[hour // 4] for hour in range(24))

    return ResearchBackboneData(
        case_names=case_names,
        native_probabilities=native_probabilities,
        compiled_probabilities_by_encoding=compiled_by_encoding,
        energy_baseline_kw=baseline,
        reserve_by_hour_kw=reserve_by_hour,
        maximum_charge_power_kw=float(problem.battery.maximum_charge_power_kw),
        maximum_discharge_power_kw=float(
            problem.battery.maximum_discharge_power_kw
        ),
        tpm_evidence_ids=evidence_ids,
        robust_result_fingerprint=restriction.semantic_result_fingerprint,
    )


def render_research_backbone_figure(
    data: ResearchBackboneData,
    destination: Path,
) -> Path:
    """Render the two-panel, proposal-specific evidence figure."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(11.8, 4.25),
        gridspec_kw={"width_ratios": [0.9, 1.45]},
        constrained_layout=True,
    )

    positions = list(range(len(data.case_names)))
    axes[0].plot(
        positions,
        data.native_probabilities,
        marker="o",
        linewidth=2.2,
        color="black",
        label="native TPM",
    )
    styles = (("tab:blue", "--", "s"), ("tab:green", ":", "^"))
    for (encoding, probabilities), (color, linestyle, marker) in zip(
        data.compiled_probabilities_by_encoding,
        styles,
        strict=False,
    ):
        axes[0].plot(
            positions,
            probabilities,
            marker=marker,
            linewidth=2,
            linestyle=linestyle,
            color=color,
            label=f"compiled {encoding}",
        )
    axes[0].set(
        title="A. Probabilistic decision evidence",
        xlabel="Reviewed conditional case",
        ylabel="Conditional event probability",
        xticks=positions,
        xticklabels=[name.replace("-", "\n") for name in data.case_names],
        ylim=(0.3, 0.75),
    )
    axes[0].legend(frameon=False, fontsize=8)

    hours = list(range(25))
    baseline = [*data.energy_baseline_kw, data.energy_baseline_kw[-1]]
    reserve = [*data.reserve_by_hour_kw, data.reserve_by_hour_kw[-1]]
    lower = [power - margin for power, margin in zip(baseline, reserve, strict=True)]
    upper = [power + margin for power, margin in zip(baseline, reserve, strict=True)]
    axes[1].fill_between(
        hours,
        lower,
        upper,
        step="post",
        alpha=0.28,
        color="tab:orange",
        label="symmetric FCR commitment $p \\pm r$",
    )
    axes[1].step(
        hours,
        baseline,
        where="post",
        linewidth=2.2,
        color="tab:blue",
        label="day-ahead baseline $p$",
    )
    axes[1].axhline(
        data.maximum_charge_power_kw,
        color="black",
        linestyle="--",
        linewidth=1,
        label="battery power limits",
    )
    axes[1].axhline(
        -data.maximum_discharge_power_kw,
        color="black",
        linestyle="--",
        linewidth=1,
    )
    axes[1].axhline(0.0, color="black", linewidth=0.6)
    axes[1].set(
        title="B. Market commitment constrained by physics",
        xlabel="Delivery hour",
        ylabel="Battery power (kW, charge-positive)",
        xlim=(0, 24),
        ylim=(-11.5, 11.5),
    )
    axes[1].legend(frameon=False, fontsize=8, loc="lower right")

    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        destination,
        bbox_inches="tight",
        metadata={
            "Title": "Open Energy Lab research backbone",
            "Author": "Nicolas Cuadrado",
            "Creator": "Open Energy Lab",
            "CreationDate": datetime(2026, 9, 3, tzinfo=UTC),
            "ModDate": datetime(2026, 9, 3, tzinfo=UTC),
        },
    )
    plt.close(figure)
    return destination


def render_demonstration_map_figure(destination: Path) -> Path:
    """Render an explanatory map of implemented, research-facing workflows."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    plt.style.use("seaborn-v0_8-whitegrid")
    figure, axis = plt.subplots(figsize=(12.2, 5.1), constrained_layout=True)
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")

    lanes = (
        (
            "1. Probabilistic investment planning",
            "What is the least-cost solar and battery design that satisfies a reliability limit?",
            (
                "Weather + demand\nartifacts",
                "Simulate each\ndesign under\nuncertainty",
                "Fit and validate\na TPM of\nshortfall risk",
                "Embed risk in a\nPyomo/HiGHS\nplanning model",
                "Verify on held-out\nsimulations; release or\nlabel exploratory",
            ),
            "#DCEAF7",
        ),
        (
            "2. Robust FCR commitment and evaluation",
            "How much energy and symmetric reserve can a battery commit before activation is known?",
            (
                "Energy + FCR\nprices and battery",
                "Optimize baseline\nand reserve bids",
                "Audit converter,\nenergy, and terminal\nconstraints",
                "Replay realized\nactivation with the\naccepted plan fixed",
                "Settle delivery and\ncompare ex-ante with\nrealized economics",
            ),
            "#FCE5C8",
        ),
        (
            "3. French market and restoration-service evidence",
            "Can public market observations feed reproducible aFRR/mFRR and stacked-service studies?",
            (
                "Explicit ENTSO-E /\nRTE acquisition",
                "Validate and publish\nimmutable canonical\nartifacts",
                "Declare scenario or\ncommitment mapping",
                "Replay BESS\nresponse and physical\nlimitations",
                "Report delivery,\ndegradation proxy,\nsettlement, provenance",
            ),
            "#E1F1E4",
        ),
    )
    lane_y = (0.73, 0.405, 0.08)
    box_width = 0.158
    box_height = 0.12
    box_x = (0.02, 0.223, 0.426, 0.629, 0.832)

    for (title, question, steps, color), y in zip(lanes, lane_y, strict=True):
        axis.text(
            0.02,
            y + 0.205,
            title,
            fontsize=11,
            fontweight="bold",
            color="#245B8A",
            va="top",
        )
        axis.text(0.02, y + 0.155, question, fontsize=8.7, va="top")
        for index, (x, step) in enumerate(zip(box_x, steps, strict=True)):
            box = FancyBboxPatch(
                (x, y),
                box_width,
                box_height,
                boxstyle="round,pad=0.009,rounding_size=0.012",
                facecolor=color,
                edgecolor="#245B8A",
                linewidth=0.9,
            )
            axis.add_patch(box)
            axis.text(
                x + box_width / 2,
                y + box_height / 2,
                step,
                ha="center",
                va="center",
                fontsize=7.5,
            )
            if index < len(steps) - 1:
                axis.annotate(
                    "",
                    xy=(box_x[index + 1] - 0.008, y + box_height / 2),
                    xytext=(x + box_width + 0.008, y + box_height / 2),
                    arrowprops={"arrowstyle": "->", "color": "#555555", "lw": 1.0},
                )

    destination.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        destination,
        bbox_inches="tight",
        metadata={
            "Title": "Current Open Energy Lab demonstration workflows",
            "Author": "Nicolas Cuadrado",
            "Creator": "Open Energy Lab",
            "CreationDate": datetime(2026, 9, 4, tzinfo=UTC),
            "ModDate": datetime(2026, 9, 4, tzinfo=UTC),
        },
    )
    plt.close(figure)
    return destination


def generate_figure(output_directory: Path) -> tuple[Path, ResearchBackboneData]:
    """Build the governed data and write the proposal figure."""

    data = build_research_backbone_data()
    destination = render_research_backbone_figure(
        data,
        output_directory / OUTPUT_FILENAME,
    )
    return destination, data


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=(
            "figure destination (default: "
            f"{DEFAULT_OUTPUT_DIRECTORY.as_posix()})"
        ),
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    destination, data = generate_figure(arguments.output_dir)
    print(f"wrote {destination}")
    print("TPM evidence IDs:", ", ".join(data.tpm_evidence_ids))
    print("robust-FCR result fingerprint:", data.robust_result_fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
