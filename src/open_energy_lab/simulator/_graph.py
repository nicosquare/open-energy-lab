"""Internal component-graph primitives for simulator scenario assembly.

The battery arbitrage MVP needs explicit components and explicit links between
them, but it does not need a general-purpose graph engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ComponentRef:
    """Reference to a typed simulator component."""

    name: str
    kind: str


@dataclass(frozen=True, slots=True)
class Connection:
    """Directed relationship between two component refs."""

    source: str
    target: str
    relation: str


@dataclass(slots=True)
class ComponentGraph:
    """Minimal graph container for scenario validation."""

    components: dict[str, ComponentRef] = field(default_factory=dict)
    connections: list[Connection] = field(default_factory=list)

    def add_component(self, component: ComponentRef) -> None:
        if component.name in self.components:
            raise ValueError(f"duplicate component: {component.name}")
        self.components[component.name] = component

    def add_connection(self, connection: Connection) -> None:
        if connection.source not in self.components:
            raise ValueError(f"unknown source component: {connection.source}")
        if connection.target not in self.components:
            raise ValueError(f"unknown target component: {connection.target}")
        self.connections.append(connection)

    def has_connection(self, source: str, target: str, relation: str) -> bool:
        return any(
            item.source == source and item.target == target and item.relation == relation
            for item in self.connections
        )

    def require_connections(self, required: list[Connection]) -> None:
        missing = [
            item
            for item in required
            if not self.has_connection(item.source, item.target, item.relation)
        ]
        if missing:
            formatted = ", ".join(
                f"{item.source}->{item.target} ({item.relation})" for item in missing
            )
            raise ValueError(f"missing required connections: {formatted}")


__all__ = ["ComponentGraph", "ComponentRef", "Connection"]
