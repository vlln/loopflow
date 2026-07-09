"""Terminal graph renderer — PhaseGraph → Rich renderable.

Renders three layout modes:
- Linear: straight line with arrows
- Back-edge: curved/loopback with iteration labels
- Branch: tree fork with ┌ └ characters
"""

from __future__ import annotations

from rich.text import Text

from loopflow.graph import PhaseGraph


class TerminalGraphRenderer:
    """Renders a PhaseGraph to Rich renderables for terminal display."""

    def __init__(self, graph: PhaseGraph) -> None:
        self._graph = graph

    def render(self) -> Text:
        """Render the full graph as a Rich Text object."""
        nodes = self._graph.nodes()
        edges = self._graph.edges()
        current = self._graph.current_phase()

        if not nodes:
            return Text("")

        if self._graph.has_cycle():
            return self._render_cycle(nodes, edges, current)
        else:
            return self._render_linear(nodes, edges, current)

    def _render_linear(self, nodes: list[str], edges: list[Edge],
                       current: str | None) -> Text:
        """Linear path: ● A ──→ ● B ──→ ● C ✓"""
        result = Text()
        for i, node in enumerate(nodes):
            style = "bold" if node == current else ""
            done = " ✓" if node != current else ""
            result.append(f"● {node}{done}", style=style)
            if i < len(nodes) - 1:
                result.append(" ──→ ")
        return result

    def _render_cycle(self, nodes: list[str], edges: list[Edge],
                      current: str | None) -> Text:
        """Cycle path with back-edge markers and iteration labels."""
        result = Text()
        cycle_nodes = self._graph.cycle_nodes()
        back_edges = [e for e in edges if e.is_backedge]

        # Build linear chain with back-edge annotations
        for i, node in enumerate(nodes):
            style = "bold" if node == current else ""
            done = " ✓" if node != current and node not in cycle_nodes else ""
            result.append(f"● {node}{done}", style=style)
            if i < len(nodes) - 1:
                result.append(" ──→ ")

        # Append back-edge info
        for be in back_edges:
            label = f"第{be.count}轮" if be.count > 0 else ""
            result.append(f"\n  ↑ {be.from_phase} ←── {be.to_phase}  {label}")

        return result

    def render_inline(self) -> Text:
        """Single-line compact render for status display."""
        nodes = self._graph.nodes()
        if not nodes:
            return Text("(no phases)")
        return Text(" → ".join(f"● {n}" for n in nodes))