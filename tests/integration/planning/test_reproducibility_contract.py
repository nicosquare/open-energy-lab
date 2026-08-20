"""Reproducibility-contract checks for TPM-planning fixtures and docs."""

from __future__ import annotations

from pathlib import Path

from tests.integration.planning.fixture_utils import (
    PLANNING_DATASET_EXPORT_FIXTURE_PATH,
    PLANNING_PROBLEM_FIXTURE_PATH,
    TPM_QUERY_FIXTURE_PATH,
    load_planning_fixture,
)


VALIDATION_CONTRACT_PATH = Path("specs/009-tpm-planning/contracts/validation-contract.md")
QUICKSTART_PATH = Path("specs/009-tpm-planning/quickstart.md")


def test_validation_contract_documents_offline_review_boundary() -> None:
    contract_text = VALIDATION_CONTRACT_PATH.read_text(encoding="utf-8").lower()

    assert "offline" in contract_text
    assert "fixture-backed" in contract_text
    assert "import-boundary" in contract_text
    assert "optional" in contract_text
    assert "spflow" in contract_text
    assert "solver" in contract_text


def test_quickstart_lists_reproducibility_review_commands() -> None:
    quickstart_text = QUICKSTART_PATH.read_text(encoding="utf-8")

    assert "uv run pytest tests/unit/planning tests/unit/tpm tests/integration/planning" in (
        quickstart_text
    )
    assert (
        'uv run python -c "import open_energy_lab; import open_energy_lab.simulator; '
        'import open_energy_lab.tpm; import open_energy_lab.planning"'
        in quickstart_text
    )
    assert 'rg "from legacy|import legacy"' in quickstart_text


def test_export_query_and_planning_fixtures_share_reproducibility_provenance_contract() -> None:
    export_fixture = load_planning_fixture(PLANNING_DATASET_EXPORT_FIXTURE_PATH)
    query_fixture = load_planning_fixture(TPM_QUERY_FIXTURE_PATH)
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)

    for fixture in (export_fixture, query_fixture, planning_fixture):
        assert fixture["spec_feature"] == "009-tpm-planning"
        assert "specs/009-tpm-planning/contracts/validation-contract.md" in fixture[
            "planned_contracts"
        ]

        provenance = fixture["provenance"]
        assert set(("author", "origin", "legacy_evidence_paths")).issubset(provenance)
        assert "generation_command" in provenance
        assert "random_seed" in provenance
        assert "refresh_policy" in provenance


def test_export_query_and_planning_fixtures_reference_workflow_specific_contracts() -> None:
    export_fixture = load_planning_fixture(PLANNING_DATASET_EXPORT_FIXTURE_PATH)
    query_fixture = load_planning_fixture(TPM_QUERY_FIXTURE_PATH)
    planning_fixture = load_planning_fixture(PLANNING_PROBLEM_FIXTURE_PATH)

    assert "specs/009-tpm-planning/contracts/simulator-export-contract.md" in export_fixture[
        "planned_contracts"
    ]
    assert "specs/009-tpm-planning/contracts/planning-dataset-contract.md" in export_fixture[
        "planned_contracts"
    ]
    assert "specs/009-tpm-planning/contracts/tpm-artifact-contract.md" in query_fixture[
        "planned_contracts"
    ]
    assert "specs/009-tpm-planning/contracts/planning-solve-contract.md" in planning_fixture[
        "planned_contracts"
    ]
