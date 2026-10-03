"""Memoized depth-first traversal of acyclic node graphs."""

from __future__ import annotations

from collections.abc import Callable, Container, MutableMapping
from typing import TypeVar

_Value = TypeVar("_Value")


def memoized_acyclic(
    compute: Callable[[int], _Value],
    *,
    cycle_message: str,
    nodes: Container[int] | None = None,
    missing_message: str = "",
    cache: MutableMapping[int, _Value] | None = None,
) -> Callable[[int], _Value]:
    """Return ``visit(node_id)``, which runs ``compute`` once per node.

    ``compute`` recurses by calling ``visit`` on children, so shared sub-graphs
    are computed once and a node reached again while still being computed
    raises ``ValueError(cycle_message)``. With ``nodes``, an unknown id raises
    ``ValueError(missing_message.format(node_id=node_id))``. Pass ``cache`` to
    read the computed values afterwards.
    """

    values: MutableMapping[int, _Value] = {} if cache is None else cache
    active: set[int] = set()

    def visit(node_id: int) -> _Value:
        if node_id in values:
            return values[node_id]
        if node_id in active:
            raise ValueError(cycle_message)
        if nodes is not None and node_id not in nodes:
            raise ValueError(missing_message.format(node_id=node_id))
        active.add(node_id)
        value = compute(node_id)
        active.remove(node_id)
        values[node_id] = value
        return value

    return visit
