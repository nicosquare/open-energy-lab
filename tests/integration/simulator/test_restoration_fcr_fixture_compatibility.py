"""Byte and fingerprint locks for the restricted Feature 010 FCR evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
import socket

import pytest

from tests.integration.simulator import test_stacked_service_real_replay as fcr_replay


FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "market"
FIXTURE_SHA256 = {
    "france_2022-08-19_market_v1.json": (
        "7558ffd7b07470d77d50b4c5baf20eb196808324e99b0ee575060f42a83b1c8d"
    ),
    "france_2022-08-19_activation_v1.json": (
        "859f9bfb40e94d756f1e45eaa6c9ca6dd0e31ef943fc065659a62b343a616779"
    ),
    "france_2022-08-19_expected_replay_v1.json": (
        "13df60b98ca511bf6f71252ab669eb828f00ba04363fec7064043e730118208f"
    ),
}
EXPECTED_FINGERPRINTS = {
    "market_content": (
        "64494e7ba5c00bdcdcbd3e3f09eed4a162d46ef971a13b86e72f4ce1989159c5"
    ),
    "market_artifact": (
        "8e591eb1e2f8aa65bace94d482bcc08acccc9c43061df7fede92397d064de025"
    ),
    "activation_content": (
        "9f80abf7e5913b05a281f6e8c1129b7ad7c6dcab69419e6872383f3a199d26f2"
    ),
    "activation_artifact": (
        "a3463ee73afc7149f1a75d1fa19866ddb53997fac1e054feed96203d0943df18"
    ),
    "energy_schedule": (
        "98c4b3c6519ed1c77f29a461f8000a6ef621a7562295ac2a5f394d56ffbc6fcc"
    ),
    "fcr_schedule": (
        "c2572ec40009fc23d62e9e2ac43682ccb4e01bd0bf6bf7e0fd01d6e8ed610704"
    ),
    "trace": "706666d280dd08d04a58c5d8a001115c489fc16c46b79e4658a889e1946541a9",
    "result": "39599ea6b04d2369e327cf4627c324cc817856c0990f02deac16a6519fbbfc67",
}


def _fixture_bytes() -> dict[str, bytes]:
    return {
        filename: (FIXTURE_DIR / filename).read_bytes()
        for filename in FIXTURE_SHA256
    }


def test_feature_010_restricted_fixture_bytes_and_recorded_fingerprints_are_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _fixture_bytes()
    for filename, expected_sha256 in FIXTURE_SHA256.items():
        assert hashlib.sha256(before[filename]).hexdigest() == expected_sha256

    monkeypatch.setattr(
        fcr_replay,
        "MARKET_PATH",
        FIXTURE_DIR / "france_2022-08-19_market_v1.json",
    )
    monkeypatch.setattr(
        fcr_replay,
        "ACTIVATION_PATH",
        FIXTURE_DIR / "france_2022-08-19_activation_v1.json",
    )
    monkeypatch.setattr(
        fcr_replay,
        "EXPECTED_PATH",
        FIXTURE_DIR / "france_2022-08-19_expected_replay_v1.json",
    )

    def network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Feature 010 compatibility replay attempted networking")

    monkeypatch.setattr(socket, "socket", network_forbidden)
    run = fcr_replay._load_and_replay()
    fcr_replay._assert_reference_result(run)
    expected, market, activation, energy, fcr, result = run

    assert market.content_fingerprint == EXPECTED_FINGERPRINTS["market_content"]
    assert market.artifact_fingerprint == EXPECTED_FINGERPRINTS["market_artifact"]
    assert activation.content_fingerprint == EXPECTED_FINGERPRINTS[
        "activation_content"
    ]
    assert activation.artifact_fingerprint == EXPECTED_FINGERPRINTS[
        "activation_artifact"
    ]
    assert energy.schedule_fingerprint == EXPECTED_FINGERPRINTS["energy_schedule"]
    assert fcr.schedule_fingerprint == EXPECTED_FINGERPRINTS["fcr_schedule"]
    assert result.trace_fingerprint == EXPECTED_FINGERPRINTS["trace"]
    assert result.result_fingerprint == EXPECTED_FINGERPRINTS["result"]
    assert expected["expected"]["fingerprints"] == {
        "activation_artifact": EXPECTED_FINGERPRINTS["activation_artifact"],
        "baseline_configuration": (
            "435acac8cebc5beba250542b1c7a9d4e2b737ca433aa5ef919f362703a931524"
        ),
        "energy_schedule": EXPECTED_FINGERPRINTS["energy_schedule"],
        "fcr_schedule": EXPECTED_FINGERPRINTS["fcr_schedule"],
        "market_artifact": EXPECTED_FINGERPRINTS["market_artifact"],
        "result": EXPECTED_FINGERPRINTS["result"],
        "trace": EXPECTED_FINGERPRINTS["trace"],
    }

    assert _fixture_bytes() == before
