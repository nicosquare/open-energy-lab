"""TMY fetch adapter placeholders for the stochastic-weather feature."""

from __future__ import annotations


def fetch_tmy_dataset(*args: object, **kwargs: object) -> object:
    """Reserve the planned geolocation-to-TMY fetch entry point."""

    raise NotImplementedError(
        "TMY fetch is planned but not implemented in the foundational weather scaffolding."
    )


__all__ = ["fetch_tmy_dataset"]
