"""Unit tests for PhaseGraph data structure — AC-009-U-1 through AC-009-U-3, AC-009-U-6."""

import sys

from loopflow.graph import Edge, PhaseGraph


class TestPhaseGraphRecord:
    """AC-009-U-1: record() creates edges correctly."""

    def test_single_transition(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")

        assert g.nodes() == ["A", "B"]
        assert len(g.edges()) == 1
        edge = g.edges()[0]
        assert edge.from_phase == "A"
        assert edge.to_phase == "B"
        assert edge.count == 1
        assert edge.is_backedge is False

    def test_linear_chain(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")
        g.record("C", "D")

        assert g.nodes() == ["A", "B", "C", "D"]
        assert len(g.edges()) == 3
        assert g.current_phase() == "D"
        assert g.has_cycle() is False

    def test_duplicate_edge_increments_count(self):
        """AC-009-U-3: same edge twice increments count."""
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "A")  # back-edge
        g.record("A", "B")  # second time

        ab_edges = [e for e in g.edges() if e.from_phase == "A" and e.to_phase == "B"]
        assert len(ab_edges) == 1
        assert ab_edges[0].count == 2

    def test_first_node_no_from(self):
        g = PhaseGraph()
        g.record(None, "A")

        assert g.nodes() == ["A"]
        assert len(g.edges()) == 0
        assert g.current_phase() == "A"


class TestPhaseGraphCycleDetection:
    """AC-009-U-2: back-edge detection with 3-node cycle."""

    def test_three_node_cycle(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")
        g.record("C", "A")  # back to A

        assert g.has_cycle() is True
        assert set(g.cycle_nodes()) == {"A", "B", "C"}

        # C→A should be marked as back-edge
        ca_edge = g._find_edge("C", "A")
        assert ca_edge is not None
        assert ca_edge.is_backedge is True

    def test_no_cycle_linear(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "C")

        assert g.has_cycle() is False
        assert g.cycle_nodes() == []

    def test_self_loop(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "A")  # self-loop

        assert g.has_cycle() is True
        assert "A" in g.cycle_nodes()

    def test_iteration_count(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")
        g.record("B", "A")  # round 1 back
        g.record("A", "B")  # round 2 forward
        g.record("B", "A")  # round 2 back

        # The B→A edge should have count=2
        assert g.iteration_count() == 2


class TestPhaseGraphSerialization:
    """to_dict and from_events."""

    def test_to_dict(self):
        g = PhaseGraph()
        g.record(None, "A")
        g.record("A", "B")

        d = g.to_dict()
        assert d["nodes"] == ["A", "B"]
        assert len(d["edges"]) == 1
        assert d["edges"][0]["from"] == "A"
        assert d["edges"][0]["to"] == "B"
        assert d["current"] == "B"

    def test_from_events(self):
        events = [
            {"type": "phase", "title": "A", "ts": 1.0},
            {"type": "phase", "title": "B", "ts": 2.0},
            {"type": "phase", "title": "C", "ts": 3.0},
        ]
        g = PhaseGraph.from_events(events)
        assert g.nodes() == ["A", "B", "C"]
        assert len(g.edges()) == 2

    def test_from_events_skips_non_phase(self):
        events = [
            {"type": "agent_start", "session": "x"},
            {"type": "phase", "title": "A", "ts": 1.0},
            {"type": "agent_message_chunk", "content": "ok"},
            {"type": "phase", "title": "B", "ts": 2.0},
        ]
        g = PhaseGraph.from_events(events)
        assert g.nodes() == ["A", "B"]

    def test_from_events_skips_empty_title(self):
        events = [
            {"type": "phase", "title": "", "ts": 1.0},
            {"type": "phase", "title": "A", "ts": 2.0},
        ]
        g = PhaseGraph.from_events(events)
        assert g.nodes() == ["A"]
        assert len(g.edges()) == 0


class TestPhaseGraphNoRich:
    """AC-009-U-6: PhaseGraph does not import rich."""

    def test_no_rich_import(self):
        # Reload graph module to check imports
        if "loopflow.graph" in sys.modules:
            del sys.modules["loopflow.graph"]
        # rich should not be in the module's imports
        import loopflow.graph as gmod
        assert "rich" not in dir(gmod)
        assert "rich" not in sys.modules.get("loopflow.graph", object()).__dict__