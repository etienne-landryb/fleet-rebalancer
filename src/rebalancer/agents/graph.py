from langgraph.graph import END, StateGraph

from rebalancer.agents.edges import after_approval, check_plan, should_act
from rebalancer.agents.nodes import (
    assess_imbalance,
    dispatch,
    evaluate_plan,
    explain,
    forecast,
    human_approval,
    ingest,
    plan,
    relax_constraints,
)
from rebalancer.agents.state import RebalanceState


def build_graph() -> StateGraph:
    g = StateGraph(RebalanceState)

    g.add_node("do_ingest", ingest)
    g.add_node("do_forecast", forecast)
    g.add_node("do_assess", assess_imbalance)
    g.add_node("do_plan", plan)
    g.add_node("do_evaluate", evaluate_plan)
    g.add_node("do_relax", relax_constraints)
    g.add_node("do_explain", explain)
    g.add_node("do_approval", human_approval)
    g.add_node("do_dispatch", dispatch)

    g.set_entry_point("do_ingest")
    g.add_edge("do_ingest", "do_forecast")
    g.add_edge("do_forecast", "do_assess")

    g.add_conditional_edges(
        "do_assess", should_act, {"plan": "do_plan", "__end__": END}
    )
    g.add_edge("do_plan", "do_evaluate")

    g.add_conditional_edges(
        "do_evaluate",
        check_plan,
        {
            "explain": "do_explain",
            "relax_constraints": "do_relax",
            "explain_best_effort": "do_explain",
        },
    )
    g.add_edge("do_relax", "do_plan")

    g.add_edge("do_explain", "do_approval")
    g.add_conditional_edges(
        "do_approval",
        after_approval,
        {"dispatch": "do_dispatch", "__end__": END},
    )
    g.add_edge("do_dispatch", END)

    return g
