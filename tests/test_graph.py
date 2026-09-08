from datetime import datetime, timezone
from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from rebalancer.agents.graph import build_graph


def _mock_stations_balanced():
    return {
        "1": {
            "station_id": "1",
            "name": "Station A",
            "lat": 40.75,
            "lon": -73.99,
            "capacity": 20,
            "num_bikes_available": 10,
            "num_docks_available": 10,
            "is_renting": True,
            "is_returning": True,
        },
        "2": {
            "station_id": "2",
            "name": "Station B",
            "lat": 40.76,
            "lon": -73.98,
            "capacity": 20,
            "num_bikes_available": 10,
            "num_docks_available": 10,
            "is_renting": True,
            "is_returning": True,
        },
    }


def _mock_stations_imbalanced():
    return {
        "1": {
            "station_id": "1",
            "name": "Penn Station",
            "lat": 40.750,
            "lon": -73.992,
            "capacity": 40,
            "num_bikes_available": 38,
            "num_docks_available": 2,
            "is_renting": True,
            "is_returning": True,
        },
        "2": {
            "station_id": "2",
            "name": "Times Square",
            "lat": 40.758,
            "lon": -73.985,
            "capacity": 30,
            "num_bikes_available": 28,
            "num_docks_available": 2,
            "is_renting": True,
            "is_returning": True,
        },
        "3": {
            "station_id": "3",
            "name": "Central Park",
            "lat": 40.768,
            "lon": -73.970,
            "capacity": 50,
            "num_bikes_available": 4,
            "num_docks_available": 46,
            "is_renting": True,
            "is_returning": True,
        },
        "4": {
            "station_id": "4",
            "name": "Grand Central",
            "lat": 40.753,
            "lon": -73.977,
            "capacity": 30,
            "num_bikes_available": 3,
            "num_docks_available": 27,
            "is_renting": True,
            "is_returning": True,
        },
    }


def _mock_ingest_balanced(state):
    return {
        "stations": _mock_stations_balanced(),
        "tick_time": datetime.now(timezone.utc),
        "system_id": "test",
        "decision_trace": ["ingest"],
        "llm_calls": 0,
    }


def _mock_ingest_imbalanced(state):
    return {
        "stations": _mock_stations_imbalanced(),
        "tick_time": datetime.now(timezone.utc),
        "system_id": "test",
        "decision_trace": ["ingest"],
        "llm_calls": 0,
    }


_INITIAL_INPUT = {"decision_trace": [], "llm_calls": 0}


def _run_to_pause(app, config):
    visited = []
    for event in app.stream(_INITIAL_INPUT, config=config):
        for node_name in event:
            visited.append(node_name)
    return visited


def _resume(app, config, decision):
    visited = []
    for event in app.stream(Command(resume=decision), config=config):
        for node_name in event:
            visited.append(node_name)
    return visited


class TestIdleTick:
    @patch("rebalancer.agents.graph.ingest", _mock_ingest_balanced)
    def test_idle_tick_zero_llm_calls(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "idle-1"}}

        _run_to_pause(app, config)

        state = app.get_state(config)
        assert state.values.get("llm_calls", 0) == 0
        assert state.values.get("trigger") is False

    @patch("rebalancer.agents.graph.ingest", _mock_ingest_balanced)
    def test_idle_tick_ends_at_assess(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "idle-2"}}

        _run_to_pause(app, config)

        state = app.get_state(config)
        trace = state.values.get("decision_trace", [])
        assert "ingest" in trace
        assert "forecast" in trace
        assert "assess_imbalance" in trace
        assert "plan" not in trace


class TestTriggeredTick:
    @patch("rebalancer.agents.graph.ingest", _mock_ingest_imbalanced)
    def test_pauses_at_approval(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "trig-1"}}

        _run_to_pause(app, config)

        state = app.get_state(config)
        assert state.next
        assert "do_approval" in state.next

    @patch("rebalancer.agents.graph.ingest", _mock_ingest_imbalanced)
    def test_has_explain_in_trace(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "trig-2"}}

        _run_to_pause(app, config)

        state = app.get_state(config)
        trace = state.values.get("decision_trace", [])
        assert "explain" in trace
        assert "plan" in trace

    @patch("rebalancer.agents.graph.ingest", _mock_ingest_imbalanced)
    def test_approve_dispatches(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "trig-3"}}

        _run_to_pause(app, config)
        visited = _resume(app, config, "approved")

        assert "do_dispatch" in visited
        state = app.get_state(config)
        assert state.values.get("approval") == "approved"
        assert "dispatch" in state.values.get("decision_trace", [])

    @patch("rebalancer.agents.graph.ingest", _mock_ingest_imbalanced)
    def test_reject_does_not_dispatch(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "trig-4"}}

        _run_to_pause(app, config)
        _resume(app, config, "rejected")

        state = app.get_state(config)
        assert state.values.get("approval") == "rejected"
        assert "dispatch" not in state.values.get("decision_trace", [])


class TestReplanLoop:
    def test_replan_terminates_at_max(self):
        def force_infeasible(state):
            trace = list(state.get("decision_trace", []))
            trace.append("evaluate_plan")
            return {"plan_feasible": False, "decision_trace": trace}

        with (
            patch("rebalancer.agents.graph.ingest", _mock_ingest_imbalanced),
            patch("rebalancer.agents.graph.evaluate_plan", force_infeasible),
        ):
            graph = build_graph()
            app = graph.compile(checkpointer=MemorySaver())
            config = {"configurable": {"thread_id": "replan-1"}}

            _run_to_pause(app, config)

            state = app.get_state(config)
            replan_count = state.values.get("replan_count", 0)
            trace = state.values.get("decision_trace", [])
            assert replan_count >= 3
            assert "explain" in trace


class TestLLMFallback:
    @patch("rebalancer.agents.graph.ingest", _mock_ingest_imbalanced)
    def test_no_groq_key_uses_fallback(self):
        graph = build_graph()
        app = graph.compile(checkpointer=MemorySaver())
        config = {"configurable": {"thread_id": "fallback-1"}}

        _run_to_pause(app, config)

        state = app.get_state(config)
        work_orders = state.values.get("work_orders", "")
        assert "DRIVER WORK ORDER" in work_orders or len(work_orders) > 0
