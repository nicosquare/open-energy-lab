"""Source-only contract for the Feature 011 restoration walkthrough."""

from __future__ import annotations

import ast
import json
from pathlib import Path


NOTEBOOK_PATH = Path(
    "examples/restoration_services/restoration_services_walkthrough.ipynb"
)
EXPECTED_CELL_IDS = (
    "title-and-safety",
    "plain-language-products",
    "source-and-evidence-boundary",
    "offline-setup",
    "load-offline-cases",
    "provenance-table",
    "market-tables",
    "plot-afrr-market",
    "plot-mfrr-market",
    "mapping-and-commitments",
    "activation-tables",
    "plot-requested-delivered-power",
    "physical-performance-tables",
    "plot-soc-headroom",
    "plot-tracking-performance",
    "energy-throughput-table",
    "plot-energy-throughput",
    "settlement-table",
    "plot-settlement",
    "reproducibility-audit",
    "optional-export",
    "live-query-explanation",
    "live-rte-and-entsoe-query",
    "conclusions-and-limits",
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


def test_notebook_has_stable_ids_and_empty_saved_execution_state() -> None:
    notebook = _notebook()
    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] >= 5
    cells = notebook["cells"]
    assert isinstance(cells, list)
    assert tuple(cell["id"] for cell in cells) == EXPECTED_CELL_IDS
    assert len(set(EXPECTED_CELL_IDS)) == len(EXPECTED_CELL_IDS)

    for cell in cells:
        assert set(cell) >= {"cell_type", "id", "metadata", "source"}
        if cell["cell_type"] == "code":
            assert cell.get("execution_count") is None
            assert cell.get("outputs", []) == []
            ast.parse("".join(cell["source"]))


def test_notebook_explains_products_evidence_and_conclusion_limits() -> None:
    markdown = _source(cell_type="markdown").lower()
    required = (
        "automatic frequency restoration reserve",
        "manual frequency restoration reserve",
        "scheduled activation (sa)",
        "direct activation (da)",
        "french control-area aggregates",
        "not commands sent to an individual battery",
        "derived_simulation",
        "fixed 0.001 allocation",
        "15-minute interval averages",
        "no interpolation or upsampling",
        "source-null da",
        "no direct event is fabricated",
        "scenario_proxy",
        "not an asset invoice",
        "throughput comparison proxy",
        "not an electrochemical aging model",
        "not observed battery dispatch",
        "not a forecast, bid, optimization, or profitability guarantee",
    )
    missing = [term for term in required if term not in markdown]
    assert missing == []


def test_notebook_reuses_offline_cases_and_displays_the_full_audit_surface() -> None:
    code = _source(cell_type="code")
    required_code = (
        "load_reference_scenario",
        "build_reference_case",
        "build_reference_results_payload",
        "build_reference_display_payload",
        "france_2026-08-20_afrr_scenario_v1.json",
        "france_2026-08-15_mfrr_scenario_v1.json",
        "france_restoration_expected_results_v1.json",
        "provenance_table",
        "afrr_market_table",
        "mfrr_market_table",
        "commitment_table",
        "activation_table",
        "physical_table",
        "performance_table",
        "energy_table",
        "settlement_table",
        "reproducibility_table",
        "notebook_display_fingerprint",
        "result_set_fingerprint",
        "generated_figures",
    )
    missing = [term for term in required_code if term not in code]
    assert missing == []

    source = _source().lower()
    required_variables = (
        "source field / series fingerprint / unit / resolution",
        "requested need / activated for france / activated in france / weighted-average price",
        "sa requested / sa satisfied / sa activated / da status / clearing price",
        "upward commitment / downward commitment / accepted baseline / reserved headroom",
        "requested balancing power / delivered balancing power / combined power",
        "soc / upward power headroom / downward power headroom / energy headroom",
        "tracking error / response delay / achieved ramp / non-performance / causes",
        "charge / discharge / net terminal energy / throughput",
        "day-ahead / capacity / activated energy / penalty / degradation / gross / net",
        "artifact / mapping / commitment / activation / replay / settlement / display fingerprints",
    )
    missing_variables = [term for term in required_variables if term not in source]
    assert missing_variables == []

    assert source.count("plt.subplots(") >= 7
    assert "import pandas as pd" in code
    assert "import matplotlib.pyplot as plt" in code
    assert "import seaborn as sns" in code


def test_notebook_export_is_explicit_disabled_and_restricted() -> None:
    export_code = _cell_source("optional-export")
    assert "EXPORT_FIGURES = False" in export_code
    assert '"tmp/restoration-services-notebook/figures"' in export_code
    assert "if EXPORT_FIGURES:" in export_code

    markdown = _source(cell_type="markdown").lower()
    required = (
        "private-repository data",
        "authorized collaborators",
        "do not publish the executed notebook",
        "screenshots",
        "html exports",
        "public ci artifacts",
        "source notebook is committed with empty outputs",
        "remove or reassess the restricted fixtures before a visibility change",
    )
    missing = [term for term in required if term not in markdown]
    assert missing == []


def test_live_rte_and_existing_profile_entsoe_branch_are_guarded() -> None:
    live_code = _cell_source("live-rte-and-entsoe-query")
    tree = ast.parse(live_code)
    required = (
        "RUN_LIVE_QUERY = False",
        "RUN_LIVE_ENTSOE_QUERY = False",
        "LIVE_QUERY_PARAMETERS",
        "LIVE_ENTSOE_ARTIFACT_PATH = None",
        "LIVE_PERSIST_NORMALIZED_ARTIFACT = False",
        'LIVE_ENV_FILE = REPO_ROOT / ".env"',
        "raw_responses = ()",
        'raw_retention_policy="DIGEST_ONLY"',
        "day_ahead_price",
        "series_fingerprint",
        "no compatible profile was selected",
    )
    missing = [term for term in required if term not in live_code]
    assert missing == []

    guarded = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "RUN_LIVE_QUERY"
    ]
    assert len(guarded) == 1
    guarded_imports = {
        node.module
        for node in ast.walk(guarded[0])
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert {
        "examples.restoration_services.fetch_rte_period",
        "open_energy_lab.market.rte",
        "open_energy_lab.market.artifact",
    } <= guarded_imports

    guarded_calls = {
        node.func.id
        for node in ast.walk(guarded[0])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert {
        "_rte_credentials",
        "build_rte_restoration_request",
        "execute_rte_request",
        "parse_rte_restoration_responses",
        "load_market_data_artifact",
    } <= guarded_calls

    other_code = "\n".join(
        "".join(cell.get("source", ()))
        for cell in _notebook()["cells"]
        if cell.get("cell_type") == "code"
        and cell.get("id") != "live-rte-and-entsoe-query"
    )
    assert "open_energy_lab.market.rte" not in other_code
    assert "fetch_rte_period" not in other_code
    assert "load_market_data_artifact" not in other_code

    unguarded_imports = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert unguarded_imports == set()


def test_live_section_documents_parameters_lifecycle_and_no_persistence() -> None:
    source = _source().lower()
    required = (
        "caller-selected utc half-open period",
        "disabled by default",
        "rte balancing energy 5.2",
        "standard_afrr_data",
        "standard_mfrr_data",
        "short-lived oauth",
        "raw responses remain in memory only",
        "no raw response is written",
        "existing feature 010 `fr-day-ahead-symmetric-fcr-v1` lifecycle",
        "time-compatible a44 `day_ahead_price`",
        "selected by series fingerprint",
        "not an automatic fallback",
        "no compatible profile was selected",
        "live availability is not required for offline results",
    )
    missing = [term for term in required if term not in source]
    assert missing == []

