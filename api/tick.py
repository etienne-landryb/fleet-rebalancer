"""Run one graph tick. POST /api/tick"""

import logging
import os

from ._shared import (
    build_response,
    call_with_reconnect,
    error_response,
    get_compiled_graph,
    get_config,
)

logger = logging.getLogger(__name__)


async def handle_tick(
    params: dict | None = None, thread_id: str = "operator-1"
) -> dict:
    """Execute a full graph tick. Blocks until the graph hits an interrupt or END."""
    params = params or {}

    discovery_url = params.get("discovery_url")
    system_id = params.get("system_id")

    if discovery_url:
        os.environ["GBFS_PRIMARY_DISCOVERY_URL"] = discovery_url
    if system_id:
        os.environ["GBFS_PRIMARY_SYSTEM_ID"] = system_id

    constraints = {}
    for key in ("van_count", "van_capacity", "shift_budget_min"):
        if params.get(key) is not None:
            constraints[key] = params[key]

    graph = get_compiled_graph()
    config = get_config(thread_id)

    initial_state: dict = {"decision_trace": [], "llm_calls": 0}
    if constraints:
        initial_state["constraints"] = constraints

    def _run() -> tuple:
        for chunk in graph.stream(
            initial_state,
            config,
            stream_mode="updates",
        ):
            for node_name in chunk:
                logger.info("Node completed: %s", node_name)

        snapshot = graph.get_state(config)
        return snapshot, snapshot.values

    try:
        snapshot, state = call_with_reconnect(_run)

        if snapshot.next:
            return build_response(state, "approval")
        elif state.get("trigger", False):
            return build_response(state, "dispatched")
        else:
            return build_response(state, "idle")

    except Exception as exc:
        logger.exception("Tick failed")
        return error_response(str(exc))
