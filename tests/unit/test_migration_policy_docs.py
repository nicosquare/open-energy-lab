"""Documentation contract tests for migration governance policy."""

from __future__ import annotations

from pathlib import Path
import re
import tomllib


MIGRATION_POLICY_DOCS = (
    Path("docs/migration/parity-validation.md"),
    Path("docs/migration/migration-spec-template.md"),
    Path("docs/migration/simulator-preparation.md"),
)

REQUIRED_TERMS = (
    "target module path",
    "validation/test path",
    "legacy paths",
    "behavior to preserve",
    "behavior to improve",
    "behavior to reject",
    "validation evidence",
    "tolerances",
    "out-of-scope algorithm migration",
)

FEATURE_010_POLICY_DOCS = (
    Path("docs/migration/api-maturity.md"),
    Path("docs/migration/fixture-provenance.md"),
)
FEATURE_010_OWNERS = {
    "OEL-F010-OWNER-RETRIEVAL": "open_energy_lab.market.entsoe",
    "OEL-F010-OWNER-MARKET-ARTIFACT": "open_energy_lab.market.artifact",
    "OEL-F010-OWNER-ACTIVATION": "open_energy_lab.market.activation",
    "OEL-F010-OWNER-SCHEDULES": "open_energy_lab.control.stacked_service",
    "OEL-F010-OWNER-PHYSICAL": "open_energy_lab.simulator.stacked_service",
    "OEL-F010-OWNER-SETTLEMENT": "open_energy_lab.simulator.fcr_settlement",
    "OEL-F010-OWNER-ROBUST": "later robust-bidding feature",
}


def _read_text(path: Path) -> str:
    assert path.is_file(), f"{path} must exist"
    return path.read_text(encoding="utf-8").lower()


def test_migration_policy_docs_cover_required_gov_contract_terms() -> None:
    for path in MIGRATION_POLICY_DOCS:
        content = _read_text(path)
        missing_terms = [term for term in REQUIRED_TERMS if term not in content]
        assert missing_terms == [], f"{path} is missing: {missing_terms}"


def test_feature_010_docs_define_each_single_owner_exactly_once() -> None:
    row_pattern = re.compile(
        r"^\| `(?P<responsibility>OEL-F010-OWNER-[A-Z-]+)` "
        r"\| [^|]+ \| `?(?P<owner>[^|`]+)`? \|$",
        flags=re.MULTILINE,
    )
    for path in FEATURE_010_POLICY_DOCS:
        content = path.read_text(encoding="utf-8")
        rows = row_pattern.findall(content)
        responsibilities = [responsibility for responsibility, _ in rows]
        assert len(responsibilities) == len(set(responsibilities)), (
            f"{path} assigns a Feature 010 responsibility more than once"
        )
        actual = {
            responsibility: owner.strip()
            for responsibility, owner in rows
        }
        assert actual == FEATURE_010_OWNERS


def test_feature_010_docs_record_maturity_locations_and_offline_default() -> None:
    required = (
        "experimental-v1",
        "open_energy_lab.market.entsoe",
        "open_energy_lab.market.artifact",
        "open_energy_lab.market.activation",
        "open_energy_lab.control.stacked_service",
        "open_energy_lab.simulator.stacked_service",
        "open_energy_lab.simulator.fcr_settlement",
        "offline",
    )
    for path in FEATURE_010_POLICY_DOCS:
        content = _read_text(path)
        missing = [term for term in required if term.lower() not in content]
        assert missing == [], f"{path} is missing: {missing}"


def test_entsoe_architecture_guide_records_the_exact_r3_api_contract() -> None:
    path = Path("docs/architecture/entsoe-transparency-platform.md")
    content = _read_text(path)
    required = (
        "transparency platform **r3**",
        "https://web-api.tp.entsoe.eu/api",
        "documenttype` | `a44",
        "documenttype` | `a81",
        "businesstype` | `b95",
        "processtype` | `a52",
        "type_marketagreement.type` | `a01",
        "controlarea_domain` | `10yfr-rte------c",
        "eur/mw/h = source_value / isp_duration_hours",
        "securitytoken",
        "entsoe_api_token",
        "application/zip",
        "cc by 4.0",
        "epex spot",
        "prior consent",
        "private repository",
        "repository_publication=prohibited",
        "package",
        "removed before repository visibility",
        "official entso-e postman collection",
        "list of data available for free reuse",
    )
    missing = [term for term in required if term not in content]
    assert missing == [], f"{path} is missing: {missing}"


def test_restricted_fixture_policy_is_exact_and_fail_closed() -> None:
    path = Path("docs/migration/restricted-reference-fixtures.md")
    content = _read_text(path)
    required = (
        "authorized repository collaborators",
        "permitted_private_restricted",
        "repository_publication` as `prohibited",
        "public repository, fork, or mirror",
        "source or wheel package",
        "release attachment",
        "remove all three fixtures",
        "not offered under the repository's apache-2.0 license",
        "stage_private_reference_market.py",
        "--acknowledge-private-restricted-repository",
        "france_2022-08-19_market_v1.json",
        "france_2022-08-19_activation_v1.json",
        "france_2022-08-19_expected_replay_v1.json",
        "does not claim public redistribution rights",
    )
    missing = [term for term in required if term not in content]
    assert missing == [], f"{path} is missing: {missing}"

    assert not Path(
        "examples/bess_stacked_services/authorize_reference_market.py"
    ).exists()
    assert not Path(
        "examples/bess_stacked_services/epex_publication_permission.example.json"
    ).exists()
    assert not Path(
        "docs/migration/epex-spot-publication-permission.md"
    ).exists()


def test_restricted_real_fixtures_are_excluded_from_distributions() -> None:
    configuration = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))
    sdist_exclusions = set(
        configuration["tool"]["hatch"]["build"]["targets"]["sdist"][
            "exclude"
        ]
    )
    wheel_exclusions = set(
        configuration["tool"]["hatch"]["build"]["targets"]["wheel"][
            "exclude"
        ]
    )
    feature_010 = {
        "/tests/fixtures/market/france_2022-08-19_market_v1.json",
        "/tests/fixtures/market/france_2022-08-19_activation_v1.json",
        "/tests/fixtures/market/france_2022-08-19_expected_replay_v1.json",
    }
    feature_011 = {
        "/tests/fixtures/restoration/france_2026-08-20_afrr_market_v1.json",
        "/tests/fixtures/restoration/france_2026-08-20_afrr_scenario_v1.json",
        "/tests/fixtures/restoration/france_2026-08-15_mfrr_market_v1.json",
        "/tests/fixtures/restoration/france_2026-08-15_mfrr_scenario_v1.json",
        "/tests/fixtures/restoration/france_restoration_expected_results_v1.json",
    }
    assert feature_010 | feature_011 <= sdist_exclusions
    assert feature_011 <= wheel_exclusions


def test_feature_011_restricted_paths_are_absent_from_upload_manifests() -> None:
    fixture_names = {
        "france_2026-08-20_afrr_market_v1.json",
        "france_2026-08-20_afrr_scenario_v1.json",
        "france_2026-08-15_mfrr_market_v1.json",
        "france_2026-08-15_mfrr_scenario_v1.json",
        "france_restoration_expected_results_v1.json",
    }
    manifest_roots = (
        Path(".github/workflows"),
        Path(".github/actions"),
        Path("release"),
        Path("releases"),
        Path("mirrors"),
        Path("external-artifacts"),
    )
    checked: list[Path] = []
    for root in manifest_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeError:
                continue
            checked.append(path)
            matches = sorted(name for name in fixture_names if name in content)
            assert matches == [], (
                f"restricted Feature 011 paths appear in upload/release manifest "
                f"{path}: {matches}"
            )

    assert Path(".github/workflows/ci.yml") in checked
    policy = _read_text(Path("tests/fixtures/restoration/RESTRICTED_DATA.md"))
    for required in (
        "package_distribution: prohibited",
        "release_distribution: prohibited",
        "public_ci_artifact: prohibited",
        "public_mirror_or_fork: prohibited",
        "external_artifact_store: prohibited",
    ):
        assert required in policy


def test_feature_012_external_csv_is_ignored_and_excluded_from_distributions() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    configuration = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))
    wheel = set(
        configuration["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"]
    )
    sdist = set(
        configuration["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]
    )

    assert "artifacts/" in gitignore
    assert {"/artifacts/**", "/baselines/**"} <= wheel
    assert {"/artifacts/**", "/baselines/**"} <= sdist
    assert not Path(
        "artifacts/reference/robust_storage_bidding/regulation_signal.csv"
    ).exists()
    assert not Path("src/open_energy_lab/regulation_signal.csv").exists()


def test_feature_012_migration_docs_define_common_environment_and_limits() -> None:
    paths = (
        Path("docs/migration/fcr-bid-evaluation-parity.md"),
        Path("docs/migration/parity-validation.md"),
        Path("docs/migration/environment-assumptions.md"),
    )
    required = (
        "reference implementation",
        "common environment",
        "source_precision_compatible",
        "external_reference_data",
        "no julia",
        "no gurobi",
        "complete ten-second",
        "bid generation",
    )
    for path in paths:
        content = _read_text(path)
        missing = [term for term in required if term not in content]
        assert missing == [], f"{path} is missing Feature 012 policy: {missing}"
        assert "status = paper-compatible" not in content
        assert "is paper-compatible" not in content


def test_feature_012_docs_use_exact_reference_terms_and_source_paths() -> None:
    migration_path = Path("docs/migration/fcr-bid-evaluation-parity.md")
    migration = _read_text(migration_path)
    required_terms = (
        "reference implementation",
        "reference-result parity",
        "energy baseline schedule",
        "golden reference fixture",
        "source_precision_compatible",
    )
    required_sources = (
        "baselines/robust_storage_bidding/code/01_datastruct.jl",
        "baselines/robust_storage_bidding/code/02_model.jl",
        "baselines/robust_storage_bidding/code/03_backtest_save.jl",
        "baselines/robust_storage_bidding/code/04_parse_results.jl",
        "baselines/robust_storage_bidding/results/02/2023-06-18.json",
        "baselines/robust_storage_bidding/results/result_overview.xlsx",
    )
    missing = [
        term for term in required_terms + required_sources if term not in migration
    ]
    assert missing == [], f"{migration_path} is missing exact Feature 012 terms: {missing}"


def test_feature_012_docs_bound_supported_and_unavailable_claims() -> None:
    fixture_policy = _read_text(
        Path("tests/fixtures/fcr_bid_evaluation/README.md")
    )
    parity_policy = _read_text(Path("docs/migration/parity-validation.md"))
    for path, content in (
        (Path("tests/fixtures/fcr_bid_evaluation/README.md"), fixture_policy),
        (Path("docs/migration/parity-validation.md"), parity_policy),
    ):
        required = (
            "aggregate",
            "source_precision_compatible",
            "unavailable",
            "complete ten-second",
            "directional fcr energy",
            "throughput",
        )
        missing = [term for term in required if term not in content]
        assert missing == [], f"{path} overstates or omits the parity boundary: {missing}"

    claim_paths = (
        Path("README.md"),
        Path("docs/architecture/README.md"),
        Path("docs/migration/fcr-bid-evaluation-parity.md"),
        Path("docs/migration/parity-validation.md"),
        Path("examples/fcr_bid_evaluation/README.md"),
        Path("specs/012-fcr-bid-evaluation-parity/quickstart.md"),
        Path("tests/fixtures/fcr_bid_evaluation/README.md"),
    )
    forbidden_claims = (
        "status = paper-compatible",
        "status: paper-compatible",
        "is paper-compatible",
        "are paper-compatible",
        "must be paper-compatible",
        "paper-compatible parity",
    )
    for path in claim_paths:
        content = _read_text(path)
        found = [claim for claim in forbidden_claims if claim in content]
        assert found == [], f"{path} contains vague acceptance claims: {found}"
