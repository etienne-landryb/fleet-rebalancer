from typing import Literal

from rebalancer.agents.state import RebalanceState
from rebalancer.config import get_settings


def should_act(state: RebalanceState) -> Literal["plan", "__end__"]:
    if state.get("trigger", False):
        return "plan"
    return "__end__"


def check_plan(
    state: RebalanceState,
) -> Literal["explain", "relax_constraints", "explain_best_effort"]:
    settings = get_settings()
    feasible = state.get("plan_feasible", False)
    replan_count = state.get("replan_count", 0)

    if feasible:
        return "explain"
    if replan_count < settings.max_replan:
        return "relax_constraints"
    return "explain_best_effort"


def after_approval(
    state: RebalanceState,
) -> Literal["dispatch", "__end__"]:
    if state.get("approval") == "approved":
        return "dispatch"
    return "__end__"
