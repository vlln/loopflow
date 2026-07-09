"""Terminal graph renderer — PhaseGraph → Rich renderable.

Renders three layout modes:
- Linear: single-line straight path with arrows
- Cycle: back-edge loopback annotations
- Branch: multi-line tree fork with └ ┌ characters
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from loopflow.graph import Edge, PhaseGraph

BOLD = Style(bold=True)
DIM = Style(dim=True)


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

        forward = self._graph.forward_edges()
        back = self._graph.back_edges()

        if not forward and not back:
            return Text(f"● {nodes[0]} ✓" if nodes else "", style=BOLD)

        # Build children map (forward only)
        children: dict[str, list[str]] = {}
        for e in forward:
            children.setdefault(e.from_phase, []).append(e.to_phase)

        # Build back-edge map: {from_node: [Edge, ...]}
        back_map: dict[str, list[Edge]] = {}
        for e in back:
            back_map.setdefault(e.from_phase, []).append(e)

        # Find root (node with no incoming forward edges)
        all_to = {e.to_phase for e in forward}
        root = nodes[0]
        for n in nodes:
            if n not in all_to:
                root = n
                break

        # Find main path (longest from root)
        main_path = self._longest_path(root, children, set())

        # Render
        lines: list[Text] = []
        self._render_trunk(lines, main_path, children, back_map, current)
        self._render_branches(lines, main_path, children, back_map)

        return Text("\n").join(lines) if len(lines) > 1 else lines[0]

    # ── path helpers ────────────────────────────────────────────────────

    def _longest_path(self, node: str, children: dict[str, list[str]],
                      visited: set[str]) -> list[str]:
        """Find the longest simple forward path from node."""
        if node in visited:
            return [node]
        visited.add(node)
        kids = children.get(node, [])
        if not kids:
            return [node]
        best: list[str] = []
        for k in kids:
            if k not in visited:
                sub = self._longest_path(k, children, visited.copy())
                if len(sub) > len(best):
                    best = sub
        return [node] + best

    def _pos_in_path(self, path: list[str], node: str) -> int:
        """Return the index of node in path, or -1."""
        try:
            return path.index(node)
        except ValueError:
            return -1

    # ── trunk rendering ──────────────────────────────────────────────────

    def _render_trunk(self, lines: list[Text], main_path: list[str],
                      children: dict[str, list[str]],
                      back_map: dict[str, list[Edge]],
                      current: str | None) -> None:
        """Render the main path as the first line."""
        trunk = Text()
        for i, node in enumerate(main_path):
            is_current = node == current
            is_last = i == len(main_path) - 1
            style = BOLD if is_current else None
            done = " ✓" if not is_current else ""
            trunk.append(f"● {node}{done}", style=style)
            if not is_last:
                trunk.append(" ──→ ")
        lines.append(trunk)

    def _render_branches(self, lines: list[Text], main_path: list[str],
                         children: dict[str, list[str]],
                         back_map: dict[str, list[Edge]]) -> None:
        """Render branches and back-edges below the trunk."""

        for i, node in enumerate(main_path):
            next_in_main = main_path[i + 1] if i + 1 < len(main_path) else None
            kids = children.get(node, [])
            branch_kids = [k for k in kids if k != next_in_main]

            # Calculate indent: position of this node in the trunk
            prefix = self._trunk_prefix(main_path, i)

            # Render forward branches
            for bk in branch_kids:
                branch_path = self._longest_path(bk, children, set())
                merge = self._find_merge(branch_path[-1], children, main_path[i + 1:])

                line = Text(prefix)
                line.append("└─→ ", style=DIM)
                for j, bn in enumerate(branch_path):
                    done = " ✓" if j == len(branch_path) - 1 and not merge else ""
                    line.append(f"● {bn}{done}")
                    if j < len(branch_path) - 1:
                        line.append(" ──→ ")
                if merge:
                    line.append(f" ─┘", style=DIM)
                lines.append(line)

                # Render back-edges from branch nodes
                for bj, bn in enumerate(branch_path):
                    for be in back_map.get(bn, []):
                        blabel = f"第{be.count}轮" if be.count > 0 else ""
                        # Indent: trunk prefix + branch path so far
                        br_indent = prefix + "└─→ "
                        for k in range(bj):
                            br_indent += f"● {branch_path[k]} ──→ "
                        bprefix = " " * len(br_indent)
                        bline = Text(bprefix)
                        bline.append("└── ", style=DIM)
                        bline.append(f"{be.to_phase} ({blabel}, 回边)", style=DIM)
                        lines.append(bline)

            # Render back-edges from this node
            for be in back_map.get(node, []):
                label = f"第{be.count}轮" if be.count > 0 else ""
                line = Text(prefix)
                line.append("└── ", style=DIM)
                line.append(f"{be.to_phase} ({label}, 回边)", style=DIM)
                lines.append(line)

    def _trunk_prefix(self, main_path: list[str], up_to: int) -> str:
        """Calculate the indent for a branch at position up_to in trunk."""
        # Build the trunk up to this node and measure its width
        trunk = Text()
        for i, node in enumerate(main_path[:up_to + 1]):
            trunk.append(f"● {node}")
            if i < up_to:
                trunk.append(" ──→ ")
        return " " * trunk.cell_len

    def _find_merge(self, leaf: str, children: dict[str, list[str]],
                    remaining: list[str]) -> str | None:
        """Check if leaf's children merge back into remaining trunk."""
        for kid in children.get(leaf, []):
            if kid in remaining:
                return kid
        return None

    # ── inline ───────────────────────────────────────────────────────────

    def render_inline(self) -> Text:
        """Single-line compact render for status display."""
        nodes = self._graph.nodes()
        if not nodes:
            return Text("(no phases)")
        return Text(" → ".join(f"● {n}" for n in nodes))