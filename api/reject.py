"""Reject the pending plan. POST /api/reject"""

import logging

from langgraph.types import Command

from ._shared import (
    build_response,
    call_with_reconnect,
    error_response,
    get_compiled_graph,
    get_config,
)

logger = logging.getLogger(__name__)


async def handle_reject(thread_id: str = "operator-1") -> dict:
    """Resume the graph with 'rejected', then stream to completion."""
    graph = get_compiled_graph()
    config = get_config(thread_id)

    def _run() -> dict:
        for chunk in graph.stream(
            Command(resume="rejected"), config, stream_mode="updates"
        ):
            for node_name in chunk:
                logger.info("Node completed: %s", node_name)

        return graph.get_state(config).values

    try:
        state = call_with_reconnect(_run)
        return build_response(state, "rejected")

    except Exception as exc:
        logger.exception("Reject failed")
        return error_response(str(exc))
