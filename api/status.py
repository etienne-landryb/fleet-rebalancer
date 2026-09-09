"""Get current graph status. GET /api/status"""

import logging

from ._shared import (
    build_response,
    call_with_reconnect,
    error_response,
    get_compiled_graph,
    get_config,
)

logger = logging.getLogger(__name__)


async def handle_status(thread_id: str = "operator-1") -> dict:
    """Return the current state from the checkpointer."""
    graph = get_compiled_graph()
    config = get_config(thread_id)

    try:
        snapshot = call_with_reconnect(lambda: graph.get_state(config))
        state = snapshot.values

        if not state:
            return {
                "phase": "idle",
                "error": None,
                "trigger": False,
                "stations_count": 0,
                "decision_trace": [],
                "node_details": {},
                "plan": [],
                "projected_impact": None,
                "work_orders": "",
                "llm_calls": 0,
                "replan_count": 0,
                "kpi": {"health": 0, "starving": 0, "saturated": 0},
            }

        if snapshot.next:
            return build_response(state, "approval")

        approval = state.get("approval", "")
        if approval == "approved":
            return build_response(state, "dispatched")
        elif approval == "rejected":
            return build_response(state, "rejected")
        elif state.get("trigger", False):
            return build_response(state, "approval")
        else:
            return build_response(state, "idle")

    except Exception as exc:
        logger.exception("Status check failed")
        return error_response(str(exc))
