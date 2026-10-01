"""Import-light boundary for source-independent restoration artifacts."""

from __future__ import annotations

import subprocess
import sys
import textwrap


def test_restoration_artifact_import_is_transport_and_credential_free() -> None:
    source = textwrap.dedent(
        """
        import importlib
        import os
        import sys

        credential_keys = {"RTE_CLIENT_ID", "RTE_CLIENT_SECRET", "ENTSOE_API_TOKEN"}
        forbidden_roots = {
            "requests", "socket", "ssl", "httpx", "aiohttp",
            "IPython", "jupyter", "nbformat", "notebook", "pyomo", "torch",
            "wandb", "legacy",
        }

        class GuardedEnvironment(dict):
            def __getitem__(self, key):
                if key in credential_keys:
                    raise AssertionError(f"credential read during import: {key}")
                return super().__getitem__(key)
            def get(self, key, default=None):
                if key in credential_keys:
                    raise AssertionError(f"credential read during import: {key}")
                return super().get(key, default)
            def __contains__(self, key):
                if key in credential_keys:
                    raise AssertionError(f"credential inspected during import: {key}")
                return super().__contains__(key)

        os.environ = GuardedEnvironment(os.environ)
        loaded_before = set(sys.modules)
        module = importlib.import_module("open_energy_lab.market.restoration_artifact")
        newly_loaded = set(sys.modules) - loaded_before
        loaded_roots = {name.split(".", 1)[0] for name in newly_loaded}
        assert not (forbidden_roots & loaded_roots)
        # urllib.parse (pure string parsing) is allowed; pathlib imports it on Python <= 3.12.
        assert not ({"urllib.request", "urllib.response"} & newly_loaded)
        assert "open_energy_lab.market.rte" not in sys.modules
        assert "open_energy_lab.market.entsoe" not in sys.modules
        assert module.RestorationMarketArtifact.__module__ == module.__name__
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
