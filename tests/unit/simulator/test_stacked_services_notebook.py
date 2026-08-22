"""Structural contract for the source-only Feature 010 walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/bess_stacked_services/stacked_services_walkthrough.ipynb"
)


def _notebook() -> dict[str, object]:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source(*, cell_type: str | None = None) -> str:
    cells = _notebook()["cells"]
    assert isinstance(cells, list)
    return "\n".join(
        "".join(cell.get("source", ()))
        for cell in cells
        if cell_type is None or cell.get("cell_type") == cell_type
    )


def _cell_source(cell_id: str) -> str:
    cells = _notebook()["cells"]
    assert isinstance(cells, list)
    matches = [cell for cell in cells if cell.get("id") == cell_id]
    assert len(matches) == 1
    return "".join(matches[0].get("source", ()))


def test_notebook_is_valid_source_only_python() -> None:
    notebook = _notebook()
    assert notebook["nbformat"] == 4
    cells = notebook["cells"]
    assert isinstance(cells, list)
    assert len(cells) >= 20

    ids: set[str] = set()
    for cell in cells:
        cell_id = cell["id"]
        assert isinstance(cell_id, str)
        assert cell_id not in ids
        ids.add(cell_id)
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs", []) == []
            ast.parse("".join(cell["source"]))


def test_notebook_documents_and_plots_the_full_stacked_service_surface() -> None:
    source = _source().lower()
    required = (
        "canonical market inputs",
        "separate activation input",
        "deterministic control",
        "multi-rate physical replay",
        "settlement and audit",
        "day-ahead energy price and controller thresholds",
        "symmetric fcr capacity remuneration",
        "total symmetric fcr contracted volume",
        "energy controller and reserved symmetric power headroom",
        "fcr activation and available committed capacity",
        "requested and delivered response attributable to fcr",
        "stored battery energy and operating bounds",
        "post-step state of charge",
        "charge, discharge, and net terminal energy",
        "cumulative terminal-side charge plus discharge energy",
        "power-delivery error audit",
        "cumulative response non-delivery",
        "hourly day-ahead schedule revenue",
        "four-hour fcr capacity revenue",
        "terminal target and reproducibility audit",
    )
    missing = [term for term in required if term not in source]
    assert missing == []

    for variable in (
        "price_eur_per_mwh",
        "contracted_volume_mw",
        "capacity_price_eur_per_mw_h",
        "unmodified_threshold_request_kw",
        "headroom_lower_kw / headroom_upper_kw",
        "fixed_baseline_power_kw",
        "fcr_capacity_kw",
        "activation",
        "requested_fcr_power_kw / delivered_fcr_power_kw",
        "requested_combined_power_kw / delivered_combined_power_kw",
        "charge_energy_kwh / discharge_energy_kwh",
        "stored_energy_before_kwh / stored_energy_after_kwh",
        "soc_before / soc_after",
        "baseline_delivery_error_kw",
        "signed_tracking_error_kw / absolute_tracking_error_kw",
        "non_delivery_energy_kwh / saturation_causes",
        "throughput / terminal target / fingerprints",
    ):
        assert variable in source

    assert source.count("plt.subplots(") >= 6
    assert "import matplotlib.pyplot as plt" in source
    assert "import seaborn as sns" in source
    assert "import pandas as pd" in source


def test_notebook_reuses_offline_consumers_and_guards_live_acquisition() -> None:
    code = _source(cell_type="code")
    assert "run_offline_replay(fixture_dir)" in code.lower()
    assert "load_market_data_artifact" in code
    assert "load_regulation_activation_trace" in code
    assert "france_2022-08-19_market_v1.json" in code
    assert "france_2022-08-19_activation_v1.json" in code
    assert "EXPORT_FIGURES = False" in code
    assert '"tmp/bess-stacked-services-notebook/figures"' in code

    live_code = _cell_source("live-entsoe-query")
    live_tree = ast.parse(live_code)
    assert "RUN_LIVE_QUERY = False" in live_code
    assert "LIVE_QUERY_PARAMETERS" in live_code
    assert "LIVE_ENV_FILE = REPO_ROOT / \".env\"" in live_code
    assert "LIVE_DESTINATION = REPO_ROOT / \"artifacts/market/notebook-live-query\"" in live_code
    assert "raw_retention_policy=\"digest_only\"" in live_code

    guarded_blocks = [
        node
        for node in live_tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "RUN_LIVE_QUERY"
    ]
    assert len(guarded_blocks) == 1
    guarded = guarded_blocks[0]
    guarded_imports = {
        node.module
        for node in ast.walk(guarded)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    guarded_calls = {
        node.func.id
        for node in ast.walk(guarded)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "examples.bess_stacked_services.fetch_french_period" in guarded_imports
    assert "open_energy_lab.market.entsoe" in guarded_imports
    assert {
        "_api_token",
        "build_entsoe_query_windows",
        "fetch_entsoe_market_data",
    } <= guarded_calls
    assert "request_parameters" in live_code

    other_code = "\n".join(
        "".join(cell.get("source", ()))
        for cell in _notebook()["cells"]
        if cell.get("cell_type") == "code" and cell.get("id") != "live-entsoe-query"
    )
    assert "fetch_entsoe_market_data" not in other_code
    assert "_api_token" not in other_code
    assert "api_token = \"\"" in live_code

    forbidden_imports = {
        "http",
        "requests",
        "socket",
        "urllib",
    }
    for cell in _notebook()["cells"]:
        if cell["cell_type"] != "code":
            continue
        tree = ast.parse("".join(cell["source"]))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {item.name for item in node.names}
                assert imported.isdisjoint(forbidden_imports)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module not in forbidden_imports

    assert "ENTSOE_API_TOKEN" not in code
    assert "refresh_entsoe_market_data" not in code


def test_notebook_documents_live_query_parameters_and_r3_outputs() -> None:
    source = _source().lower()
    required = (
        "optional live entso-e r3 query",
        "disabled by default",
        "caller-selected utc half-open period",
        "a44",
        "combined a81",
        "b95/a52/a01",
        "three canonical series from two source responses",
        "day_ahead_price",
        "fcr_contracted_volume",
        "fcr_capacity_price",
        "digest-only",
        "ignored artifacts/market/notebook-live-query",
        "does not replace the reviewed replay fixtures",
    )
    missing = [term for term in required if term not in source]
    assert missing == []

    assert _cell_source("plot-live-market-variables").count("plt.subplots(") == 1


def test_notebook_warns_that_outputs_and_figures_remain_restricted() -> None:
    markdown = _source(cell_type="markdown").lower()
    required = (
        "private-repository data",
        "authorized collaborators",
        "do not publish the executed notebook",
        "screenshots",
        "html exports",
        "public ci artifacts",
        "remove the restricted fixtures before making the repository public",
        "source notebook is committed with empty outputs",
        "one historical french day",
        "not a forecast or profitability guarantee",
        "fixed or deterministic heuristics, not optimized bids",
        "activation-energy, imbalance, degradation",
    )
    missing = [term for term in required if term not in markdown]
    assert missing == []


def test_notebook_setup_and_private_output_boundary_are_documented() -> None:
    for path in (
        Path("examples/bess_stacked_services/README.md"),
        Path("specs/010-bess-stacked-services/quickstart.md"),
    ):
        content = path.read_text(encoding="utf-8").lower()
        required = (
            "stacked_services_walkthrough.ipynb",
            "uv sync --group notebook",
            ".venv/bin/python",
            "offline",
            "cleared outputs" if path.name == "quickstart.md" else "no execution state",
            "screenshots",
            "html exports",
            "restricted real values",
            "tmp/bess-stacked-services-notebook/figures",
        )
        missing = [term for term in required if term not in content]
        assert missing == [], f"{path} is missing: {missing}"
