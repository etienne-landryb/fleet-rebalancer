"""Shared graph manager for the fleet rebalancer API."""

import json
import logging
import os
import re
import sys
import tempfile
from contextlib import ExitStack

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

# On Vercel, GCP credentials are stored as a JSON string in an env var
# rather than a file path. Write to a temp file so the SDK can find it.
_gac_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if _gac_json and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
    try:
        _cred = json.loads(_gac_json)
        _tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump(_cred, _tmp)
        _tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _tmp.name
    except (json.JSONDecodeError, OSError):
        pass

from langgraph.checkpoint.memory import MemorySaver  # noqa: E402

from rebalancer.agents.graph import build_graph  # noqa: E402
from rebalancer.config import get_settings  # noqa: E402

logger = logging.getLogger(__name__)

_settings = get_settings()
_checkpointer_stack = ExitStack()
if _settings.supabase_db_url:
    from langgraph.checkpoint.postgres import PostgresSaver

    _checkpointer = _checkpointer_stack.enter_context(
        PostgresSaver.from_conn_string(_settings.supabase_db_url)
    )
    _checkpointer.setup()
else:
    _checkpointer = MemorySaver()

_compiled = build_graph().compile(checkpointer=_checkpointer)


def get_config(thread_id: str = "operator-1"):
    safe_thread_id = (
        thread_id
        if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", thread_id)
        else "operator-1"
    )
    return {"configurable": {"thread_id": safe_thread_id}}


def get_compiled_graph():
    return _compiled


def error_response(error: str) -> dict:
    return {
        "phase": "error",
        "error": error,
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
        "forecast_method": "persistence_baseline",
    }


def build_response(state: dict, phase: str) -> dict:
    """Build a JSON-serializable response from graph state."""
    stations = state.get("stations", {})
    imbalance = state.get("imbalance", {})
    impact = state.get("projected_impact", {})
    plan_routes = state.get("plan", [])
    trace = state.get("decision_trace", [])

    node_details: dict[str, str] = {}
    for node in trace:
        if node == "ingest":
            node_details["ingest"] = f"{len(stations):,} stations"
        elif node == "forecast":
            fm = state.get("forecast_method", "persistence_baseline")
            if fm == "xgboost":
                node_details["forecast"] = "XGBoost · 45 min horizon"
            else:
                node_details["forecast"] = (
                    "Persistence baseline (no model for this system)"
                )
        elif node == "assess_imbalance":
            warning = imbalance.get("warning")
            if warning:
                node_details["assess_imbalance"] = warning
            else:
                agg = imbalance.get("aggregate", 0)
                trigger = state.get("trigger", False)
                node_details["assess_imbalance"] = (
                    f"{agg * 100:.1f}% — trigger={'true' if trigger else 'false'}"
                )
        elif node == "plan":
            bikes = sum(r.get("total_pickups", 0) for r in plan_routes)
            node_details["plan"] = f"{len(plan_routes)} routes · {bikes} bikes"
        elif node == "evaluate_plan":
            feasible = state.get("plan_feasible", False)
            imp = impact.get("health_improvement", 0)
            sign = "+" if imp >= 0 else ""
            node_details["evaluate_plan"] = (
                f"{'feasible' if feasible else 'infeasible'} · "
                f"{sign}{imp * 100:.1f}% health"
            )
        elif node == "explain":
            llm = state.get("llm_calls", 0)
            node_details["explain"] = (
                f"{llm} LLM call{'s' if llm != 1 else ''}"
                if llm > 0
                else "deterministic fallback"
            )
        elif node.startswith("human_approval"):
            node_details["human_approval"] = state.get("approval", "pending")
        elif node == "dispatch":
            node_details["dispatch"] = "plan persisted"
        elif node.startswith("relax_constraints"):
            node_details[node] = (
                f"attempt {state.get('replan_count', 0)}"
            )

    enriched_routes = []
    for route in plan_routes:
        enriched_stops = []
        for stop in route.get("stops", []):
            sid = stop["station_id"]
            station = stations.get(sid, {})
            enriched_stops.append(
                {
                    **stop,
                    "lat": station.get("lat", 0),
                    "lon": station.get("lon", 0),
                }
            )
        enriched_routes.append({**route, "stops": enriched_stops})

    imb_stations = imbalance.get("stations", {})
    starving = sum(
        1 for v in imb_stations.values() if v.get("risk") == "starving"
    )
    saturated = sum(
        1 for v in imb_stations.values() if v.get("risk") == "saturated"
    )
    total = len(stations) or 1
    health = (total - starving - saturated) / total

    clean_trace = []
    for node in trace:
        if node.startswith("human_approval"):
            clean_trace.append("human_approval")
        elif node.startswith("relax_constraints"):
            clean_trace.append("relax_constraints")
        else:
            clean_trace.append(node)

    idle_reason = None
    if phase == "idle" and "assess_imbalance" in trace:
        warning = imbalance.get("warning")
        agg = imbalance.get("aggregate", 0)
        if warning:
            idle_reason = warning
        elif starving == 0 and saturated == 0:
            idle_reason = (
                f"Network is healthy — no rebalancing needed "
                f"(imbalance {agg * 100:.1f}% < threshold 30%)"
            )
        elif starving > 0 and saturated == 0:
            idle_reason = (
                "System-wide shortage — every station is low with no surplus "
                "to redistribute from. This requires external restocking, "
                "not rebalancing."
            )
        elif saturated > 0 and starving == 0:
            idle_reason = (
                "System-wide surplus — every station is full with no deficit "
                "to move bikes to. External removal required."
            )
        else:
            idle_reason = (
                f"Network within acceptable balance (imbalance {agg * 100:.1f}% "
                f"below 30% threshold) — no intervention needed."
            )

    return {
        "phase": phase,
        "trigger": state.get("trigger", False),
        "stations_count": len(stations),
        "decision_trace": clean_trace,
        "node_details": node_details,
        "plan": enriched_routes,
        "projected_impact": impact or None,
        "work_orders": state.get("work_orders", ""),
        "llm_calls": state.get("llm_calls", 0),
        "replan_count": state.get("replan_count", 0),
        "kpi": {
            "health": round(health, 4),
            "starving": starving,
            "saturated": saturated,
        },
        "forecast_method": state.get("forecast_method", "persistence_baseline"),
        "error": None,
        "idle_reason": idle_reason,
    }
