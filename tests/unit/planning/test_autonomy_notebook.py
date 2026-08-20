from __future__ import annotations

import ast
import json
from pathlib import Path

from open_energy_lab.simulator import PriceSignal, TimeGrid


NOTEBOOK_PATH = Path("examples/tpm_planning/discrete_study_walkthrough.ipynb")


def _notebook():
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source() -> str:
    return "\n".join("".join(cell.get("source", ())) for cell in _notebook()["cells"])


def test_notebook_has_configurable_abu_dhabi_defaults_and_no_fixture_fallback() -> None:
    source = _source()

    for required in (
        '"latitude": 24.4539',
        '"longitude": 54.3773',
        '"timezone": "Asia/Dubai"',
        "api/v5_3/",
        "HORIZON_STEPS = 24",
        "LOCAL_START_STEP = 0",
        "INITIAL_SOC = 1.0",
        'DEMAND_MODE = "synthetic"',
        "SOLAR_CAPACITIES_KW = (80.0, 120.0, 160.0)",
        "BATTERY_CAPACITIES_KWH = (100.0, 200.0, 300.0)",
        'EVENT_KIND = "unmet_energy_kwh"',
        "EVENT_THRESHOLD = 0.1",
        "CHANCE_LIMIT = 0.05",
    ):
        assert required in source
    assert "tests/fixtures" not in source
    assert "load_or_fetch_tmy_dataset" in source
    assert "fit_weather_dataset" in source


def test_notebook_separates_splits_selects_candidates_and_gates_recommendation() -> None:
    source = _source()

    for required in (
        'SAMPLE_COUNTS = {"train": 1_000, "validation": 250, "test": 250}',
        'SPLIT_SEEDS = {"train": 13, "validation": 37, "test": 101}',
        "SPN_CANDIDATES",
        "brier_score_by_configuration",
        "select_spn_candidate",
        "compile_planning_study_tpm",
        "solve_planning_study",
        "assess_calibration",
        "assess_recommendation",
        "one-sided held-out 95% risk bound",
        "EXPLORATORY ONLY",
    ):
        assert required in source
    assert source.count("generate_planning_study_dataset") >= 2
    assert "manifest.semantic_sha256" in source
    assert "solution.solve_summary.solver_metadata" in source


def test_notebook_includes_all_dynamic_visualization_topics_and_compiles() -> None:
    source = _source().lower()
    for topic in (
        "representative abu dhabi tmy days",
        "hourly tmy ghi distribution",
        "fitted versus generated/measured site demand",
        "sampled autonomy episode",
        "controller request and realized battery action",
        "post-step battery state of charge",
        "risk-heatmap",
        "spn probability versus held-out empirical probability",
        "cost-risk frontier",
        "final recommendation status",
    ):
        assert topic in source

    for cell in _notebook()["cells"]:
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]))


def test_notebook_uses_standard_plotting_libraries_and_explains_organization() -> None:
    notebook = _notebook()
    source = _source()
    markdown_ids = {
        cell["id"] for cell in notebook["cells"] if cell["cell_type"] == "markdown"
    }

    assert "import matplotlib.pyplot as plt" in source
    assert "import seaborn as sns" in source
    assert "sns.heatmap(" in source
    assert "sns.scatterplot(" in source
    assert "plt.subplots(" in source
    assert "class InlineSVG" not in source
    assert "def line_chart(" not in source
    assert "def heatmap_chart(" not in source

    for required_id in (
        "notebook-map",
        "data-config-heading",
        "physical-config-heading",
        "evidence-config-heading",
        "weather-visuals-heading",
        "demand-visual-heading",
        "split-heatmaps-heading",
        "calibration-visuals-heading",
        "frontier-heading",
    ):
        assert required_id in markdown_ids


def test_notebook_placeholder_tariff_satisfies_simulator_contract() -> None:
    notebook = _notebook()
    price_signal_calls: list[ast.Call] = []

    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        tree = ast.parse("".join(cell["source"]))
        price_signal_calls.extend(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "PriceSignal"
        )
        assert not any(output.get("output_type") == "error" for output in cell["outputs"])

    assert len(price_signal_calls) == 1
    keywords = {keyword.arg: keyword.value for keyword in price_signal_calls[0].keywords}
    export_ratio = ast.literal_eval(keywords["export_price_ratio"])
    interpretation = ast.literal_eval(keywords["interpretation"])
    assert 0.0 < export_ratio < 1.0
    assert "discount" in interpretation.lower()
    PriceSignal(
        currency="AED",
        unit_rate_name="planning-placeholder",
        import_prices=[0.0],
        export_price_ratio=export_ratio,
        interpretation=interpretation,
        time_alignment="step-start",
        time_grid=TimeGrid(num_steps=1, time_step_hours=1.0),
    )


def test_notebook_states_conditional_scope_and_tmy_demand_limitations() -> None:
    source = _source().lower()

    for required in (
        "not an absolute blackout guarantee",
        "location, horizon, local start hour",
        "explicitly reset initial soc",
        "tmy does not represent interannual extremes",
        "synthetic demand is not site-calibrated",
        "no controller or state-of-charge burn-in",
    ):
        assert required in source
