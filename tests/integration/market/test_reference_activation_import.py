"""Offline provenance checks for the selected RTE activation fixture."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import socket

from open_energy_lab.market import load_regulation_activation_trace


FIXTURE_PATH = (
    Path(__file__).parents[2]
    / "fixtures"
    / "market"
    / "france_2022-08-19_activation_v1.json"
)
PERIOD_START = datetime(2022, 8, 18, 22, tzinfo=UTC)
PERIOD_END = datetime(2022, 8, 19, 22, tzinfo=UTC)
SOURCE_REVISION = "7e44738bb30e5c8204efe40103b9be4c2203685c"
SOURCE_SHA256 = "314a84556383161e9a9628b31eaa885e471f04db213a971c4f25efaef1053a8a"
CONTENT_FINGERPRINT = "9f80abf7e5913b05a281f6e8c1129b7ad7c6dcab69419e6872383f3a199d26f2"
ARTIFACT_FINGERPRINT = "a3463ee73afc7149f1a75d1fa19866ddb53997fac1e054feed96203d0943df18"


def test_reference_activation_fixture_is_complete_provenanced_and_offline(
    monkeypatch,
) -> None:
    original_path_open = Path.open

    def _guarded_path_open(path: Path, *args: object, **kwargs: object):
        if path.name == "RTE_Frequence_2022_08.txt":
            raise AssertionError("routine validation opened the external raw RTE file")
        return original_path_open(path, *args, **kwargs)

    def _network_forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("reference activation validation attempted network access")

    monkeypatch.setattr(Path, "open", _guarded_path_open)
    monkeypatch.setattr(socket, "socket", _network_forbidden)

    trace = load_regulation_activation_trace(FIXTURE_PATH)

    assert trace.resolution == "PT10S"
    assert trace.covered_period.start_utc == PERIOD_START
    assert trace.covered_period.end_utc == PERIOD_END
    assert len(trace.samples) == 8_640
    assert trace.source["revision"] == SOURCE_REVISION
    assert trace.source["sha256"] == SOURCE_SHA256
    assert trace.source["timezone"] == "Europe/Paris"
    assert trace.source["locator"] == (
        "lauinger/robust-storage-bidding@"
        f"{SOURCE_REVISION}:data_processing/freq_data/RTE_Frequence_2022_08.txt"
    )
    assert trace.normalization["point_to_interval"] == "instantaneous_left_hold"
    assert trace.normalization["formula"] == (
        "clip((50.0 - frequency_hz) / 0.2, -1, 1)"
    )
    assert trace.sign_semantics == "positive is upward/discharge"
    assert trace.content_fingerprint == CONTENT_FINGERPRINT
    assert trace.artifact_fingerprint == ARTIFACT_FINGERPRINT

    assert trace.samples[0].interval.local_start.isoformat() == (
        "2022-08-19T00:00:00+02:00"
    )
    assert trace.samples[-1].interval.local_start.isoformat() == (
        "2022-08-19T23:59:50+02:00"
    )
    assert min(sample.source_value for sample in trace.samples) == 49.9234
    assert max(sample.source_value for sample in trace.samples) == 50.0547
    for index, sample in enumerate(trace.samples):
        assert sample.interval.start_utc == PERIOD_START + timedelta(seconds=10 * index)
        assert sample.interval.end_utc == PERIOD_START + timedelta(seconds=10 * (index + 1))
        assert sample.source_unit == "Hz"
        assert sample.conversion_ref == "frequency-droop-left-hold-v1"
        expected = max(-1.0, min(1.0, (50.0 - sample.source_value) / 0.2))
        assert sample.activation == expected
