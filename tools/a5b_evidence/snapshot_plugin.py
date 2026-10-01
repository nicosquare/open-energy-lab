"""Temporary A5b evidence: record every to_dict() output of FCR dataclasses per test."""
from __future__ import annotations

import dataclasses, enum, importlib, json, os, pkgutil
from datetime import date, datetime
from pathlib import Path

MODULES = [
    "open_energy_lab.control.fcr_rolling_backtest",
    "open_energy_lab.control._fcr_rolling_orchestrator",
    "open_energy_lab.control.robust_fcr_bidding",
    "open_energy_lab.control.robust_fcr_rolling",
    "open_energy_lab.control._robust_fcr_formulation",
    "open_energy_lab.control._robust_fcr_solver",
    "open_energy_lab.control.stacked_service",
    "open_energy_lab.simulator.fcr_bid_evaluation",
    "open_energy_lab.simulator.fcr_rolling_evaluation",
    "open_energy_lab.simulator.fcr_bid_plan",
    "open_energy_lab.simulator.stacked_service",
    "open_energy_lab.simulator.fcr_settlement",
]
OUT = Path(os.environ["A5B_SNAPSHOT"])
_current = {"node": "<collect>", "seq": 0}
_records: list[str] = []


def _default(value):
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(map(str, value))
    if dataclasses.is_dataclass(value):
        return repr(value)
    return repr(value)


def _wrap(cls):
    original = cls.__dict__["to_dict"]

    def to_dict(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            text = json.dumps(result, sort_keys=True, default=_default)
        except Exception as exc:  # noqa: BLE001
            text = json.dumps({"<unserializable>": repr(exc)})
        _current["seq"] += 1
        _records.append(json.dumps([_current["node"], cls.__qualname__, _current["seq"], text]))
        return result

    cls.to_dict = to_dict


def pytest_configure(config):
    for name in MODULES:
        module = importlib.import_module(name)
        for obj in list(vars(module).values()):
            if isinstance(obj, type) and obj.__module__ == name and "to_dict" in obj.__dict__:
                _wrap(obj)


def pytest_runtest_setup(item):
    _current["node"] = item.nodeid
    _current["seq"] = 0


def pytest_sessionfinish(session, exitstatus):
    OUT.write_text("\n".join(_records) + "\n")
