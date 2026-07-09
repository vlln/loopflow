"""Phase graph data structure — adjacency list, edge counting, cycle detection.

Pure data — no rendering dependencies. Used by runtime to record phase
transitions, and by display renderers to visualize execution flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Edge:
    from_phase: str
    to_phase: str
    count: int = 1
    is_backedge: bool = False


@dataclass
class PhaseGraph:
    """Tracks phase transitions during workflow execution.

    Detects back-edges (cycles) by checking if the target phase already
    appears in the current path from root.
    """

    _nodes: list[str] = field(default_factory=list)
    _edges: list[Edge] = field(default_factory=list)
    _current: str | None = None

    def record(self, from_phase: str | None, to_phase: str) -> None:
        """Record a phase transition. Detects back-edges automatically."""
        if to_phase not in self._nodes:
            self._nodes.append(to_phase)

        # Detect back-edge: to_phase already in path from root, or self-loop
        is_back = (
            from_phase is not None
            and (from_phase == to_phase or to_phase in self._ancestors(from_phase))
        )

        if from_phase is not None:
            existing = self._find_edge(from_phase, to_phase)
            if existing:
                existing.count += 1
            else:
                self._edges.append(Edge(
                    from_phase=from_phase,
                    to_phase=to_phase,
                    count=1,
                    is_backedge=is_back,
                ))

        self._current = to_phase

    def _ancestors(self, node: str, visited: set[str] | None = None) -> set[str]:
        """Collect all ancestors of a node by walking edges backward."""
        if visited is None:
            visited = set()
        if node in visited:
            return set()
        visited.add(node)
        ancestors: set[str] = set()
        for edge in self._edges:
            if edge.to_phase == node:
                ancestors.add(edge.from_phase)
                ancestors.update(self._ancestors(edge.from_phase, visited))
        return ancestors

    def _find_edge(self, from_phase: str, to_phase: str) -> Edge | None:
        for edge in self._edges:
            if edge.from_phase == from_phase and edge.to_phase == to_phase:
                return edge
        return None

    def nodes(self) -> list[str]:
        return list(self._nodes)

    def edges(self) -> list[Edge]:
        return list(self._edges)

    def current_phase(self) -> str | None:
        return self._current

    def has_cycle(self) -> bool:
        return any(e.is_backedge for e in self._edges)

    def cycle_nodes(self) -> list[str]:
        """Return nodes involved in cycles (back-edges), in order."""
        result: list[str] = []
        seen: set[str] = set()
        for edge in self._edges:
            if edge.is_backedge:
                # Find the forward path from to_phase to from_phase
                path = self._find_path(edge.to_phase, edge.from_phase)
                for node in path:
                    if node not in seen:
                        result.append(node)
                        seen.add(node)
        return result

    def _find_path(self, from_node: str, to_node: str,
                   visited: set[str] | None = None) -> list[str]:
        """Find a forward path from from_node to to_node."""
        if visited is None:
            visited = set()
        if from_node == to_node:
            return [to_node]
        if from_node in visited:
            return []
        visited.add(from_node)
        for edge in self._edges:
            if edge.from_phase == from_node and not edge.is_backedge:
                path = self._find_path(edge.to_phase, to_node, visited)
                if path:
                    return [from_node] + path
        return []

    def iteration_count(self) -> int:
        """Estimate iteration count from max edge count on back-edges."""
        return max((e.count for e in self._edges if e.is_backedge), default=0)

    def to_dict(self) -> dict:
        return {
            "nodes": self._nodes,
            "edges": [
                {
                    "from": e.from_phase,
                    "to": e.to_phase,
                    "count": e.count,
                    "is_backedge": e.is_backedge,
                }
                for e in self._edges
            ],
            "current": self._current,
        }

    @classmethod
    def from_events(cls, events: list[dict]) -> "PhaseGraph":
        """Build graph from phase events list."""
        graph = cls()
        prev: str | None = None
        for evt in events:
            if evt.get("type") == "phase":
                title = evt.get("title", "")
                if title:
                    graph.record(prev, title)
                    prev = title
        return graph