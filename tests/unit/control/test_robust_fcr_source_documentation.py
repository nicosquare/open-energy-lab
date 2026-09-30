"""Source-provenance contracts for the migrated robust FCR equations."""

from __future__ import annotations

from pathlib import Path

from open_energy_lab.control.robust_fcr_bidding import RobustFCRFormulationProfile
from open_energy_lab.control._robust_fcr_formulation import (
    SOURCE_EQUATION_REFERENCES,
    SOURCE_EQUATION_VERSION,
)


ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "docs/migration/reference-robust-fcr-bidding.md"


def test_private_equation_inventory_pins_every_preserved_line_range() -> None:
    assert SOURCE_EQUATION_VERSION == "robust-storage-bidding-non-intraday-milp-v1"
    assert dict(SOURCE_EQUATION_REFERENCES) == {
        "variables": "baselines/robust_storage_bidding/code/02_model.jl:86-135",
        "power_headroom": "baselines/robust_storage_bidding/code/02_model.jl:170-174",
        "robust_stored_energy": "baselines/robust_storage_bidding/code/02_model.jl:183-188",
        "efficiency_epigraphs": "baselines/robust_storage_bidding/code/02_model.jl:191-197",
        "upper_counterpart": "baselines/robust_storage_bidding/code/02_model.jl:199-219",
        "exact_bilinear": "baselines/robust_storage_bidding/code/02_model.jl:220-224",
        "restriction_tightening": "baselines/robust_storage_bidding/code/02_model.jl:225-230",
        "objective_terminal": "baselines/robust_storage_bidding/code/02_model.jl:252-263",
        "horizon_budget": "baselines/robust_storage_bidding/code/02_model.jl:293-305",
    }
    for kind in ("restriction", "relaxation", "exact"):
        profile = RobustFCRFormulationProfile.for_kind(kind)
        assert profile.equation_version == SOURCE_EQUATION_VERSION
        assert all(reference.startswith("baselines/") for reference in profile.source_refs)


def test_migration_guide_documents_units_signs_and_reference_quirks() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    required_fragments = (
        "`baselines/robust_storage_bidding/code/01_datastruct.jl:3-49`",
        "`baselines/robust_storage_bidding/code/02_model.jl:86-135`",
        "`baselines/robust_storage_bidding/code/02_model.jl:170-174`",
        "`baselines/robust_storage_bidding/code/02_model.jl:183-188`",
        "`baselines/robust_storage_bidding/code/02_model.jl:191-197`",
        "`baselines/robust_storage_bidding/code/02_model.jl:199-219`",
        "`baselines/robust_storage_bidding/code/02_model.jl:220-224`",
        "`baselines/robust_storage_bidding/code/02_model.jl:225-230`",
        "`baselines/robust_storage_bidding/code/02_model.jl:252-263`",
        "`baselines/robust_storage_bidding/code/02_model.jl:293-305`",
        "`baselines/robust_storage_bidding/code/12.jl:27-95`",
        "positive-discharge",
        "charge-positive",
        "EUR/kW/4h-block",
        "`lambdaHigh[l]`",
        "`lambdaHigh[k]`",
        "source comment says `EUR/kWh`",
        "inert",
        "`lp_relax`",
        "`lp_restrict`",
        "intraday",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    assert missing == []


def test_documented_sign_adapter_is_an_explicit_equation() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "public_charge_positive_kw = -source_positive_discharge_kw" in text
    assert "public_fcr_capacity_kw = source_xr_kw" in text
