"""Paths of the TPM artifact fixtures shared by tpm and planning tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TPM_FIXTURE_DIR = Path("tests/fixtures/tpm")
TPM_ARTIFACT_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_artifact_v2.json"
TPM_PRODUCTION_ARTIFACT_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_artifact_spflow_v1.json"
TPM_ARTIFACT_V1_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_artifact_v1.json"
UNSUPPORTED_TPM_ARTIFACT_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_artifact_unsupported_version.json"
TPM_QUERY_FIXTURE_PATH = TPM_FIXTURE_DIR / "tpm_query_case.json"


def load_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
