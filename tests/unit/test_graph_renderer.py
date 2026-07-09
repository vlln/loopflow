"""Unit tests for TerminalGraphRenderer — AC-009-U-4, AC-009-U-5."""

from loopflow.graph import PhaseGraph
from loopflow.display.graph_renderer import TerminalGraphRenderer


class TestRenderLinear:
    """AC-009-U-4: linear path rendering."""

    def test_linear_four_nodes(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")
        g.record("C", "D")

        renderer = TerminalGraphRenderer(g)
        result = renderer.render()

        text = result.plain
        assert "A" in text
        assert "B" in text
        assert "C" in text
        assert "D" in text
        assert "──" in text  # connection chars

    def test_linear_single_node(self):
        g = PhaseGraph()
        g.record(None, "A")

        renderer = TerminalGraphRenderer(g)
        result = renderer.render()

        text = result.plain
        assert "A" in text
        assert "──" not in text  # no edges

    def test_linear_empty(self):
        g = PhaseGraph()
        renderer = TerminalGraphRenderer(g)
        result = renderer.render()

        assert result.plain == ""

    def test_current_highlighted(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")

        renderer = TerminalGraphRenderer(g)
        result = renderer.render()

        # Current node should be bold
        spans = result.spans
        assert any(s.style and s.style.bold for s in spans)


class TestRenderCycle:
    """AC-009-U-5: cycle/back-edge rendering."""

    def test_cycle_shows_backedge(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")
        g.record("C", "A")  # back-edge

        renderer = TerminalGraphRenderer(g)
        result = renderer.render()

        text = result.plain
        assert "└──" in text  # branch marker for back-edge
        assert "回边" in text  # back-edge label

    def test_cycle_nodes_marked(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "A")

        renderer = TerminalGraphRenderer(g)
        result = renderer.render()

        text = result.plain
        assert "A" in text
        assert "B" in text
        assert "回边" in text


class TestRenderInline:
    """Compact inline render."""

    def test_inline(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")

        renderer = TerminalGraphRenderer(g)
        result = renderer.render_inline()

        assert "A" in result.plain
        assert "B" in result.plain
        assert "C" in result.plain
        assert "→" in result.plain

    def test_inline_empty(self):
        g = PhaseGraph()
        renderer = TerminalGraphRenderer(g)
        result = renderer.render_inline()

        assert "(no phases)" in result.plain