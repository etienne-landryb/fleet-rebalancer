"""Approve the pending plan. POST /api/approve"""

import logging

from langgraph.types import Command

from ._shared import build_response, error_response, get_compiled_graph, get_config

logger = logging.getLogger(__name__)


async def handle_approve(thread_id: str = "operator-1") -> dict:
    """Resume the graph with 'approved', then stream to completion."""
    graph = get_compiled_graph()
    config = get_config(thread_id)

    try:
        for chunk in graph.stream(
            Command(resume="approved"), config, stream_mode="updates"
        ):
            for node_name in chunk:
                logger.info("Node completed: %s", node_name)

        state = graph.get_state(config).values
        return build_response(state, "dispatched")

    except Exception as exc:
        logger.exception("Approve failed")
        return error_response(str(exc))
